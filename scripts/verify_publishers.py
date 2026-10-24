"""Collect reviewed publishers through real background tasks; never invokes paid LLMs."""

import json
import time
from pathlib import Path

import httpx
from verify_model_sources import wait_run


def main():
    targets = [
        ("hf-models", publisher)
        for publisher in (
            "kimi",
            "minimax",
            "stepfun",
            "baidu",
            "intern",
            "tencent",
            "nvidia",
            "bytedance",
            "cohere",
            "amazon",
            "xai",
        )
    ] + [
        (source, None)
        for source in (
            "anthropic-news",
            "cohere-news",
            "bytedance-news",
            "amazon-science",
        )
    ]
    results = []
    with httpx.Client(
        base_url="http://127.0.0.1:8000", headers={"X-FrontierSignal": "1"}, timeout=30
    ) as client:
        for source, publisher in targets:
            deadline = time.monotonic() + 240
            while True:
                response = client.post(
                    f"/api/sources/{source}/collect",
                    params={"publisher": publisher} if publisher else {},
                )
                if response.status_code != 409 or time.monotonic() >= deadline:
                    break
                time.sleep(2)
            response.raise_for_status()
            run = wait_run(client, response.json()["id"])
            results.append({"source": source, "publisher": publisher, "run": run})
            print(
                source,
                publisher,
                run["status"],
                {
                    key: run[key]
                    for key in ["added", "updated", "duplicates", "filtered", "failed", "error"]
                },
                flush=True,
            )
        report = {"tasks": results, "publishers": client.get("/api/publishers").json()}
        path = Path(".runtime/publishers-batch23-verification.json")
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path)
        if any(row["run"]["status"] != "success" for row in results):
            raise SystemExit(
                "Some publisher tasks failed or only partially completed; inspect the report."
            )


if __name__ == "__main__":
    main()
