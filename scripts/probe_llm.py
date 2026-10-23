"""Ask the running service to perform a real, non-news LLM compatibility probe."""

import asyncio
import json

import httpx


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api", timeout=10, headers={"X-FrontierSignal": "1"}
    ) as client:
        response = await client.post("/settings/probe")
        if response.status_code == 409:
            print(response.json()["detail"])
            raise SystemExit(2)
        response.raise_for_status()
        task_id = response.json()["id"]
        for _ in range(200):
            runs = (await client.get("/tasks")).json()
            task = next(t for t in runs if t["id"] == task_id)
            if task["status"] not in {"queued", "running"}:
                print(json.dumps(task, ensure_ascii=False))
                raise SystemExit(0 if task["status"] == "success" else 1)
            await asyncio.sleep(1)
        raise SystemExit("Probe did not finish within observation window")


if __name__ == "__main__":
    asyncio.run(main())
