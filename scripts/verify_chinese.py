"""Verify real Chinese analysis through the running API; this consumes provider quota."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx


async def verify(batches):
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api",
        timeout=10,
        headers={"X-FrontierSignal": "1"},
        trust_env=False,
    ) as client:
        response = await client.get("/articles?page_size=20")
        response.raise_for_status()
        originals = {a["id"]: (a["title"], a["body"]) for a in response.json()["items"]}
        runs = []
        for _ in range(batches):
            response = await client.post("/analyze")
            response.raise_for_status()
            task_id = response.json()["id"]
            for _ in range(1200):
                response = await client.get("/tasks")
                response.raise_for_status()
                run = next(r for r in response.json() if r["id"] == task_id)
                if run["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(1)
            runs.append(run)
            print(
                json.dumps(
                    {k: run[k] for k in ("id", "status", "updated", "filtered", "failed")},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if run["status"] != "success":
                raise SystemExit("分析未全部成功，请查看任务和逐条处理记录")
        translated = []
        for article_id, original in originals.items():
            response = await client.get(f"/articles/{article_id}")
            response.raise_for_status()
            article = response.json()
            assert (article["title"], article["body"]) == original, "原文发生变化，请重新验证"
            if article["title_zh"] and article["summary_zh"]:
                translated.append(
                    {
                        "id": article_id,
                        "title_zh": article["title_zh"],
                        "model": article["analysis_model"],
                    }
                )
        if not translated:
            raise SystemExit("首页尚无中文分析结果，不能报告验证成功")
        first = translated[0]["id"]
        before = (await client.get(f"/articles/{first}")).json()["attempts"]
        response = await client.post(f"/articles/{first}/retry")
        assert response.status_code == 409, "已成功处理的内容不应重复分析"
        after = (await client.get(f"/articles/{first}")).json()["attempts"]
        assert before == after, "重复请求不应产生新模型调用"
        report = {
            "runs": runs,
            "translated_first_page": translated,
            "originals_preserved": True,
            "duplicate_analysis_rejected": True,
        }
        path = Path(__file__).resolve().parents[1] / ".runtime/chinese-check.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"首页 {len(translated)} 条中文解读已验证，原文保持一致，重复分析请求被拒绝。",
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=1, choices=range(1, 11))
    asyncio.run(verify(parser.parse_args().batches))
