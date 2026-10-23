"""Collect configured sources against real services and report each outcome."""

import asyncio
import json
from pathlib import Path

import httpx


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api", timeout=10, headers={"X-FrontierSignal": "1"}
    ) as client:
        response = await client.post("/collect")
        response.raise_for_status()
        ids = {r["id"] for r in response.json()}
        for _ in range(240):
            result = await client.get("/tasks")
            result.raise_for_status()
            runs = [r for r in result.json() if r["id"] in ids]
            if len(runs) == len(ids) and all(
                r["status"] not in {"queued", "running"} for r in runs
            ):
                break
            await asyncio.sleep(1)
        payload = {
            "runs": runs,
            "total_articles": (await client.get("/articles?page_size=1")).json()["total"],
        }
        path = Path(__file__).resolve().parents[1] / ".runtime" / "source-check.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for run in runs:
            print(
                json.dumps(
                    {
                        k: run[k]
                        for k in ["source_id", "status", "added", "duplicates", "failed", "error"]
                    },
                    ensure_ascii=False,
                )
            )
        print("Total articles:", payload["total_articles"])
        if len(runs) != len(ids) or any(r["status"] != "success" for r in runs):
            raise SystemExit(
                "Some collection tasks did not succeed; see .runtime/source-check.json"
            )


if __name__ == "__main__":
    asyncio.run(main())
