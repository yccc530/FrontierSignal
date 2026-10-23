"""Exercise migrations and pgvector in a newly-created disposable PostgreSQL DB."""

import asyncio
import os
import subprocess
import sys
import uuid

import psycopg
from frontiersignal.config import Settings, settings
from frontiersignal.db import Database
from frontiersignal.models import Article, ArticleLink, Source
from frontiersignal.normalizer import RawItem
from frontiersignal.semantic import store_and_link
from frontiersignal.storage import ingest
from frontiersignal.tasks import TaskManager
from psycopg import sql
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url


async def verify(url):
    config = Settings(database_url=url, scheduler_enabled=False, _env_file=None)
    db = Database(config)
    try:
        first, second = TaskManager(db, config), TaskManager(db, config)
        await first.start()
        try:
            await second.start()
            raise AssertionError("Second scheduler unexpectedly acquired the lock")
        except RuntimeError:
            pass
        await first.ensure_owner()
        await first.owner.execute(text("SELECT pg_advisory_unlock(761849321)"))
        await first.owner.commit()
        try:
            await first.ensure_owner()
            raise AssertionError("Lost ownership was not detected")
        except ValueError:
            assert first.closing
        await first.stop()
        await second.stop()
        async with db.sessions() as session:
            version = await session.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            for name, vector in [("first", [1.0, 0.0, 0.0]), ("second", [0.99, 0.01, 0.0])]:
                source = Source(id=name, name=name, kind="rss", url="https://example.com")
                session.add(source)
                await session.flush()
                article, _ = await ingest(
                    session,
                    source,
                    RawItem(
                        platform_id=name,
                        title=f"Fixture {name}",
                        body="Database integration fixture, not a real news item",
                    ),
                )
                await store_and_link(session, article, vector, "fixture-vector", 0.94)
            await session.commit()
            assert await session.scalar(select(func.count()).select_from(Article)) == 2
            assert await session.scalar(select(func.count()).select_from(ArticleLink)) == 1
            print(f"Fresh Alembic migrations and real pgvector {version} cosine query passed")
    finally:
        await db.engine.dispose()


def main():
    original = make_url(settings.database_url.get_secret_value())
    name = "fs_test_" + uuid.uuid4().hex
    admin = original.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    target = original.set(database=name).render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env={**os.environ, "FS_DATABASE_URL": target},
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError("Disposable database migration failed; inspect the migrations")
        asyncio.run(verify(target))
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            # Only this invocation's random database is ever dropped.
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    print("Isolated fixture database removed; application database untouched")


if __name__ == "__main__":
    main()
