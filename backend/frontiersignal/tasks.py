import asyncio
from contextlib import suppress
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text, update

from .analysis import AnalysisPipeline
from .collectors import COLLECTORS
from .collectors.github_discovery import GitHubDiscoveryCollector
from .collectors.huggingface import HuggingFaceCollector
from .config import Settings
from .db import Database
from .discovery_state import record_outcome
from .models import AnalysisAttempt, Article, Repository, Source, TaskRun, now
from .network import Fetcher
from .observability import record_runtime_sample
from .projects import tracking_targets
from .similarity import link_related
from .storage import ingest


class TaskManager:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings
        self.fetcher = Fetcher(settings)
        self.workers: set[asyncio.Task] = set()
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(settings.collector_concurrency)
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.owner = None
        self.owner_check_lock = asyncio.Lock()
        self.owner_error = None
        self.closing = False
        self.analysis_running = False

    async def start(self):
        if self.db.engine.dialect.name == "postgresql":
            self.owner = await self.db.engine.connect()
            owns = await self.owner.scalar(text("SELECT pg_try_advisory_lock(761849321)"))
            await self.owner.commit()
            if not owns:
                await self.owner.close()
                self.owner = None
                raise RuntimeError(
                    "Another FrontierSignal worker owns this database. Use one worker."
                )
        async with self.db.sessions() as session:
            await session.execute(
                update(Source).where(Source.kind.in_(["x", "reddit"])).values(enabled=False)
            )
            await session.execute(
                update(Source)
                .where(Source.last_status.in_(["queued", "running"]))
                .values(
                    last_status="interrupted",
                    last_error="Application stopped before collection completed",
                )
            )
            await session.execute(
                update(TaskRun)
                .where(TaskRun.status.in_(["queued", "running"]))
                .values(
                    status="interrupted",
                    finished_at=now(),
                    error="Application stopped before completion",
                )
            )
            await session.execute(
                update(Article)
                .where(Article.status == "processing")
                .values(
                    status="failed",
                    analysis_error="Application interrupted analysis",
                    retry_at=now(),
                )
            )
            await session.execute(
                update(AnalysisAttempt)
                .where(AnalysisAttempt.status == "running")
                .values(
                    status="interrupted",
                    finished_at=now(),
                    error="Application interrupted analysis",
                )
            )
            await session.commit()
        await record_runtime_sample(self.db, self.settings)
        if self.settings.scheduler_enabled:
            self.scheduler.add_job(
                self.tick,
                "interval",
                seconds=30,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
            )
            self.scheduler.start()

    async def stop(self):
        self.closing = True
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        if self.owner:
            with suppress(Exception):
                await self.owner.execute(text("SELECT pg_advisory_unlock(761849321)"))
            await self.owner.close()

    async def tick(self):
        if self.closing:
            return
        try:
            await self.ensure_owner()
        except ValueError:
            return
        await record_runtime_sample(self.db, self.settings)
        async with self.db.sessions() as session:
            sources = (await session.scalars(select(Source).where(Source.enabled.is_(True)))).all()
        for source in sources:
            if not source.automatic or source.kind not in COLLECTORS:
                continue
            if (
                not source.last_run_at
                or source.last_run_at + timedelta(minutes=source.interval_minutes) <= now()
            ):
                await self.submit(source.id)
        if self.settings.llm_configured and not self.analysis_running:
            if await AnalysisPipeline(self.db, self.settings).pending_ids():
                await self.submit_analysis()

    async def submit(self, source_id: str, publisher: str | None = None) -> TaskRun:
        async with self.lock:
            await self.ensure_owner()
            if self.closing:
                raise ValueError("Application is shutting down")
            async with self.db.sessions() as session:
                source = await session.get(Source, source_id)
                if not source:
                    raise LookupError("Source not found")
                if not source.enabled:
                    raise ValueError("Source is disabled")
                if source.kind not in COLLECTORS:
                    raise ValueError("该平台当前未接入，不创建采集任务")
                if publisher:
                    from .publishers import PUBLISHERS, publisher_authors

                    if (
                        source.kind != "hf_models"
                        or publisher not in PUBLISHERS
                        or not publisher_authors(PUBLISHERS[publisher])
                    ):
                        raise ValueError("该来源不支持所选厂商的模型采集")
                existing = await session.scalar(
                    select(TaskRun).where(
                        TaskRun.source_id == source_id,
                        TaskRun.kind == "collect",
                        TaskRun.status.in_(["queued", "running"]),
                    )
                )
                if existing:
                    if publisher:
                        raise ValueError("模型来源已有任务运行，请结束后再采集指定团队")
                    return existing
                run = TaskRun(source_id=source_id)
                session.add(run)
                await session.commit()
                worker = asyncio.create_task(self._run(run.id, source_id, publisher))
                self.workers.add(worker)
                worker.add_done_callback(self.workers.discard)
                return run

    async def _run(self, run_id: str, source_id: str, publisher: str | None = None):
        try:
            async with self.semaphore, asyncio.timeout(self.settings.task_timeout):
                async with self.db.sessions() as session:
                    run = await session.get(TaskRun, run_id)
                    source = await session.get(Source, source_id)
                    if not source.enabled:
                        raise ValueError("Source disabled before execution")
                    run.status, run.started_at = "running", now()
                    source.last_run_at, source.last_status = now(), "running"
                    await session.commit()
                    collector_type = COLLECTORS.get(source.kind)
                    if not collector_type:
                        raise ValueError(f"Unsupported collector: {source.kind}")
                    collector = collector_type(self.fetcher)
                    if isinstance(collector, HuggingFaceCollector) and source.kind == "hf_models":
                        collector.publisher_id = publisher
                        cached = (
                            await session.execute(
                                select(Article.platform_id, Article.metrics)
                                .where(Article.source_id == source.id)
                                .order_by(Article.collected_at.desc())
                                .limit(2000)
                            )
                        ).all()
                        collector.known_cards = {
                            identifier: (metrics or {}).get("model", {})
                            for identifier, metrics in cached
                        }
                    if isinstance(collector, GitHubDiscoveryCollector):
                        cached = (
                            await session.execute(
                                select(Article.title, Article.metrics)
                                .where(Article.source_id == source.id)
                                .order_by(Article.updated_at.desc())
                                .limit(2000)
                            )
                        ).all()
                        collector.known_resources = {
                            title: (metrics or {}).get("resource", {}) for title, metrics in cached
                        }
                        collector.targets = await tracking_targets(
                            session, self.settings.github_track_per_run
                        )
                        for target in collector.targets:
                            tracked = await session.get(Repository, target["id"])
                            tracked.last_tracked_at = now()
                        await session.commit()
                    collection = await collector.collect(source)
                    run.filtered = collection.filtered
                    errors = list(collection.errors)
                    for item in collection.items:
                        try:
                            async with session.begin_nested():
                                article, outcome = await ingest(session, source, item)
                                if outcome != "duplicates" or item.metrics.get("model"):
                                    await link_related(session, article)
                            setattr(run, outcome, getattr(run, outcome) + 1)
                            record_outcome(
                                collection.cursor, item.metrics.get("discovery_groups", []), outcome
                            )
                            if outcome in {"added", "updated"} and not article.technical_eligible:
                                run.filtered += 1
                        except Exception as exc:
                            run.failed += 1
                            if source.kind == "official":
                                collection.cursor.get("pages", {}).pop(item.url, None)
                            record_outcome(
                                collection.cursor,
                                item.metrics.get("discovery_groups", []),
                                "failed",
                            )
                            errors.append(f"Entry rejected ({type(exc).__name__})")
                        # Each accepted original survives later network/analysis failures.
                        await session.commit()
                    run.failed += len(collection.errors)
                    run.status = (
                        ("partial" if run.added + run.updated + run.duplicates else "failed")
                        if errors
                        else "success"
                    )
                    run.error = "; ".join(errors[:5]) or None
                    run.finished_at = now()
                    # Do not advance conditional-fetch state after partially failed ingestion.
                    if not errors or collection.advance_on_partial:
                        source.cursor = collection.cursor
                    if not errors:
                        source.last_success_at = now()
                    source.last_status, source.last_error = run.status, run.error
                    await session.commit()
        except asyncio.CancelledError:
            await self._fail(run_id, source_id, "interrupted", "Application stopped")
            raise
        except Exception as exc:
            message = (
                str(exc) if isinstance(exc, (ValueError, TimeoutError)) else type(exc).__name__
            )
            if isinstance(exc, TimeoutError):
                message = "Collection exceeded the configured task timeout"
            from .network import FetchError

            if isinstance(exc, FetchError):
                message = str(exc)
            await self._fail(run_id, source_id, "failed", message[:500])

    async def _fail(self, run_id, source_id, status, message):
        async with self.db.sessions() as session:
            run = await session.get(TaskRun, run_id)
            source = await session.get(Source, source_id)
            run.status, run.error, run.finished_at = status, message, now()
            run.failed += 1
            source.last_status, source.last_error, source.last_run_at = status, message, now()
            await session.commit()

    async def submit_analysis(self, article_id=None):
        async with self.lock:
            await self.ensure_owner()
            if not self.settings.llm_configured:
                raise ValueError("请先在本地 .env 配置 LLM Base URL、模型和 API Key")
            if self.analysis_running:
                raise ValueError("已有 AI 分析任务运行，请等待完成")
            if self.closing:
                raise ValueError("Application is shutting down")
            if (
                article_id is None
                and not await AnalysisPipeline(self.db, self.settings).pending_ids()
            ):
                raise ValueError("没有到期的待处理资讯")
            async with self.db.sessions() as session:
                if article_id:
                    article = await session.get(Article, article_id)
                    if not article:
                        raise LookupError("Article not found")
                    if article.status in {"analyzed", "filtered"}:
                        raise ValueError("该内容已完成处理，不重复调用模型")
                    article.retry_at, article.analysis_attempts = None, 0
                run = TaskRun(kind="analyze")
                session.add(run)
                await session.commit()
                self.analysis_running = True
                worker = asyncio.create_task(self._analyze(run.id, article_id))
                self.workers.add(worker)
                worker.add_done_callback(self.workers.discard)
                return run

    async def _analyze(self, run_id, article_id):
        ids = []
        try:
            pipeline = AnalysisPipeline(self.db, self.settings)
            ids = [article_id] if article_id else await pipeline.pending_ids()
            async with self.db.sessions() as session:
                run = await session.get(TaskRun, run_id)
                run.status, run.started_at = "running", now()
                await session.commit()
            for target in ids:
                outcome = await pipeline.process(target)
                async with self.db.sessions() as session:
                    run = await session.get(TaskRun, run_id)
                    field = {"analyzed": "updated", "filtered": "filtered", "failed": "failed"}.get(
                        outcome, "duplicates"
                    )
                    setattr(run, field, getattr(run, field) + 1)
                    await session.commit()
            async with self.db.sessions() as session:
                run = await session.get(TaskRun, run_id)
                run.status = (
                    ("partial" if run.updated + run.filtered else "failed")
                    if run.failed
                    else "success"
                )
                run.error = "部分内容分析失败，请查看逐条分析记录" if run.failed else None
                run.finished_at = now()
                await session.commit()
        except (Exception, asyncio.CancelledError) as exc:
            async with self.db.sessions() as session:
                run = await session.get(TaskRun, run_id)
                run.status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
                run.error, run.finished_at = f"Analysis stopped ({type(exc).__name__})", now()
                run.failed += 1
                await session.execute(
                    update(Article)
                    .where(Article.id.in_(ids), Article.status == "processing")
                    .values(
                        status="failed",
                        analysis_error=run.error,
                        retry_at=now() + timedelta(minutes=2),
                    )
                )
                await session.execute(
                    update(AnalysisAttempt)
                    .where(AnalysisAttempt.article_id.in_(ids), AnalysisAttempt.status == "running")
                    .values(status="interrupted", finished_at=now(), error=run.error)
                )
                await session.commit()
        finally:
            self.analysis_running = False

    async def submit_probe(self):
        async with self.lock:
            await self.ensure_owner()
            if self.closing:
                raise ValueError("Application is shutting down")
            if not self.settings.llm_configured:
                raise ValueError("请先在本地 .env 配置 LLM Base URL、模型和 API Key")
            if self.analysis_running:
                raise ValueError("已有模型请求任务运行")
            async with self.db.sessions() as session:
                run = TaskRun(kind="probe")
                session.add(run)
                await session.commit()
            self.analysis_running = True
            worker = asyncio.create_task(self._probe(run.id))
            self.workers.add(worker)
            worker.add_done_callback(self.workers.discard)
            return run

    async def ensure_owner(self):
        if self.owner_error:
            raise ValueError(self.owner_error)
        if self.owner is None:
            return
        async with self.owner_check_lock:
            try:
                owns = await self.owner.scalar(
                    text("""SELECT EXISTS (
                    SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()
                    AND classid=0 AND objid=761849321 AND objsubid=1 AND granted)""")
                )
                await self.owner.commit()
                if owns:
                    return
            except Exception:
                pass
            # A database restart drops session locks. Never keep scheduling after
            # losing ownership, even if pooled query connections have recovered.
            self.owner_error = "数据库调度连接已中断，请重启 FrontierSignal 后端"
            self.closing = True
            raise ValueError(self.owner_error)

    async def _probe(self, run_id):
        from .llm import LLMProvider, ProviderError

        try:
            async with self.db.sessions() as session:
                run = await session.get(TaskRun, run_id)
                run.status, run.started_at = "running", now()
                await session.commit()
            await LLMProvider(self.settings).analyze(
                "API compatibility probe",
                "这是一条模型接口格式验证消息，不是新闻。请总结为接口测试并使用 products 分类。",
                {"products": "AI 产品与应用"},
            )
            status, error = "success", None
        except (Exception, asyncio.CancelledError) as exc:
            status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
            error = (
                str(exc)
                if isinstance(exc, ProviderError)
                else f"Provider probe failed ({type(exc).__name__})"
            )
        finally:
            self.analysis_running = False
        async with self.db.sessions() as session:
            run = await session.get(TaskRun, run_id)
            run.status, run.error, run.finished_at = status, error, now()
            run.failed = 0 if status == "success" else 1
            await session.commit()
