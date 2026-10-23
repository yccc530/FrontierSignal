"""Real feed -> PostgreSQL -> API smoke. Requires the running local server."""

import asyncio
import json

import httpx


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api", timeout=10, headers={"X-FrontierSignal": "1"}
    ) as client:
        health = await client.get("/health")
        health.raise_for_status()
        assert health.json()["database"] == "postgresql"
        for iteration in range(2):
            response = await client.post("/sources/huggingface/collect")
            response.raise_for_status()
            run_id = response.json()["id"]
            for _ in range(120):
                runs = (await client.get("/tasks")).json()
                run = next(r for r in runs if r["id"] == run_id)
                if run["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(1)
            assert run["status"] == "success", run
            page = (await client.get("/articles?source=huggingface&page_size=100")).json()
            assert page["total"] > 0
            identities = {item["id"] for item in page["items"]}
            if iteration == 0:
                initial = identities
            else:
                assert initial == identities, "Repeat collection changed record identities"
            print(
                json.dumps(
                    {
                        "iteration": iteration + 1,
                        "task": run,
                        "article_count": page["total"],
                        "sample_title": page["items"][0]["title"],
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
