"""Exercise public model sources through the running API; never insert fixture data."""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def wait_run(client, task_id, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get("/api/tasks")
        response.raise_for_status()
        run = next((row for row in response.json() if row["id"] == task_id), None)
        if run and run["status"] not in {"queued", "running"}:
            return run
        time.sleep(1)
    raise TimeoutError(f"The task did not finish within {timeout} seconds")


def records(client, **filters):
    found = []
    page = 1
    while True:
        response = client.get("/api/articles", params={"page_size": 100, "page": page, **filters})
        response.raise_for_status()
        payload = response.json()
        found.extend(payload["items"])
        if len(found) >= payload["total"]:
            return found
        page += 1
        if page > 200:
            raise RuntimeError("Verification inventory exceeds the declared 20,000 article bound")


def analyze_sample(client, candidate):
    response = client.post(f"/api/articles/{candidate['id']}/retry")
    response.raise_for_status()
    run = wait_run(client, response.json()["id"], timeout=600)
    response = client.get(f"/api/articles/{candidate['id']}")
    response.raise_for_status()
    detail = response.json()
    checks = {
        "success": detail["status"] == "analyzed",
        "original_preserved": detail["body"] == candidate["body"],
    }
    checks["repeat_refused"] = (
        client.post(f"/api/articles/{candidate['id']}/retry").status_code == 409
        if checks["success"]
        else False
    )
    return {
        "task": run,
        "checks": checks,
        "sample": {
            key: detail[key] for key in ["id", "status", "title_zh", "summary_zh", "evidence"]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, choices=[2, 3], default=2)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--analyze-one", action="store_true")
    parser.add_argument(
        "--analyze-each", action="store_true", help="Analyze one original per B3 topic"
    )
    args = parser.parse_args()
    if not 1 <= args.rounds <= 30:
        parser.error("--rounds must be 1..30")
    if args.analyze_each and (args.batch != 3 or args.analyze_one):
        parser.error("--analyze-each requires --batch 3 and cannot combine with --analyze-one")
    expected_topics = (
        ["image", "video", "audio"]
        if args.batch == 3
        else ["llm", "coding_models", "multimodal", "ocr"]
    )
    report = {
        "at": datetime.now(UTC).isoformat(),
        "batch": args.batch,
        "tasks": [],
        "checks": {},
        "model_samples": [],
        "analysis": None,
        "analyses": [],
    }
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000",
            headers={"X-FrontierSignal": "1"},
            timeout=20,
            trust_env=False,
        ) as client:
            before = records(client)
            report["before_count"] = len(before)
            source_ids = ["hf-models"] * args.rounds
            if args.batch == 2:
                source_ids += ["google-ai", "nvidia-technical"]
            for source_id in source_ids:
                submitted = client.post(f"/api/sources/{source_id}/collect")
                submitted.raise_for_status()
                run = wait_run(client, submitted.json()["id"])
                report["tasks"].append(run)
                print(
                    json.dumps(
                        {
                            key: run[key]
                            for key in [
                                "id",
                                "source_id",
                                "status",
                                "added",
                                "updated",
                                "duplicates",
                                "failed",
                                "error",
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            after = records(client)
            models = records(client, content_type="models")
            report["after_count"], report["model_count"] = len(after), len(models)
            indexed = {item["id"]: item for item in after}
            report["checks"]["existing_ids_preserved"] = all(
                item["id"] in indexed for item in before
            )
            report["checks"]["user_states_preserved"] = all(
                item["is_read"] == indexed[item["id"]]["is_read"]
                and item["is_favorite"] == indexed[item["id"]]["is_favorite"]
                for item in before
                if item["id"] in indexed
            )
            report["checks"]["models_present"] = bool(models)
            report["checks"]["no_hub_creation_as_release"] = all(
                item["published_at"] is None
                for item in models
                if item["source"]["kind"] == "hf_models" and item["metrics"].get("model")
            )
            for topic in expected_topics:
                filtered = records(
                    client, content_type="models", topic=topic, source="hf-models", technical=True
                )
                report["checks"][f"real_{topic}_sample"] = bool(filtered)
                if filtered:
                    sample = filtered[0]
                    report["model_samples"].append(
                        {
                            "topic": topic,
                            "id": sample["id"],
                            "title": sample["title"],
                            "source": sample["source_id"],
                            "url": sample["original_url"],
                            "model": sample["metrics"]["model"],
                        }
                    )
            report["coverage"] = client.get("/api/discovery/coverage").json()
            if args.batch == 3:
                groups = next(
                    source["groups"]
                    for source in report["coverage"]["sources"]
                    if source["source_id"] == "hf-models"
                )
                targeted = [
                    group
                    for group in groups
                    if group["id"].startswith(tuple(f"topic:{topic}:" for topic in expected_topics))
                ]
                report["creative_query_groups"] = targeted
                report["checks"]["creative_query_coverage"] = bool(targeted) and all(
                    group["status"] == "success" for group in targeted
                )
            report["checks"]["observed_duplicates"] = any(
                run["source_id"] == "hf-models" and run["duplicates"] > 0 for run in report["tasks"]
            )
            if args.analyze_one or args.analyze_each:
                analysis_topics = expected_topics if args.analyze_each else [None]
                used = set()
                for topic in analysis_topics:
                    candidates = [
                        item
                        for item in models
                        if item["id"] not in used
                        and item["source"]["kind"] == "hf_models"
                        and item["status"] in {"pending", "failed", "stale"}
                        and item["technical_eligible"]
                        and (not topic or topic in item["metrics"]["model"].get("topics", []))
                        and item["metrics"]["model"].get("card_status") in {"available", "cached"}
                    ]
                    candidates.sort(
                        key=lambda item: not item["metrics"]["model"].get("publisher_verified")
                    )
                    name = f"real_{topic}_analysis" if topic else "real_model_analysis"
                    if not candidates:
                        report["checks"][name] = False
                        report["analyses"].append(
                            {
                                "topic": topic,
                                "status": "unavailable",
                                "reason": "No pending eligible model card",
                            }
                        )
                        continue
                    candidate = candidates[0]
                    used.add(candidate["id"])
                    result = analyze_sample(client, candidate)
                    report["analyses"].append({"topic": topic, **result})
                    report["checks"][name] = all(result["checks"].values())
                    print(
                        json.dumps({"topic": topic, "analysis": result}, ensure_ascii=False),
                        flush=True,
                    )
                    if args.analyze_one:
                        report["analysis"] = result["task"]
                        report["analysis_sample"] = result["sample"]
                        report["checks"]["repeat_analysis_refused"] = result["checks"][
                            "repeat_refused"
                        ]
    finally:
        target = Path(
            ".runtime/batch-3-verification.json"
            if args.batch == 3
            else ".runtime/batches-1-2-verification.json"
        )
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {target.resolve()}", flush=True)
    print(json.dumps(report["checks"], ensure_ascii=False), flush=True)
    if not all(report["checks"].values()) or any(
        run["status"] != "success" for run in report["tasks"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
