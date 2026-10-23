"""Bounded live B4-B8 check against the running local API; restores collection scopes."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from verify_model_sources import analyze_sample, records, wait_run

PLAN = [
    ("B4", "hf-models", ["3d", "cad", "world_models", "robotics"], 1),
    (
        "B5",
        "github-discovery",
        ["vibe_tools", "vibe_projects", "ai_design", "creative_workflows"],
        2,
    ),
    (
        "B6",
        "github-discovery",
        ["automation", "mcp_skills", "dev_quality", "local_apps", "knowledge_tools"],
        3,
    ),
    ("B7", "hf-models", ["scientific", "math", "materials", "biology"], 1),
    ("B7", "arxiv-research", ["scientific", "math", "materials", "biology"], 2),
    ("B7", "hf-datasets", None, 1),
]


def main(analyze_one=False):
    report = {"at": datetime.now(UTC).isoformat(), "tasks": [], "checks": {}, "analysis": None}
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        headers={"X-FrontierSignal": "1"},
        timeout=30,
        trust_env=False,
    ) as client:
        response = client.get("/api/sources")
        response.raise_for_status()
        originals = {row["id"]: row for row in response.json()}
        before = records(client)
        changed = set()
        try:
            for batch, source_id, topics, rounds in PLAN:
                if not originals[source_id]["enabled"]:
                    report["tasks"].append(
                        {"batch": batch, "source_id": source_id, "status": "skipped_disabled"}
                    )
                    continue
                if topics:
                    response = client.patch(
                        f"/api/sources/{source_id}", json={"discovery_topics": topics}
                    )
                    response.raise_for_status()
                    changed.add(source_id)
                for _ in range(rounds):
                    response = client.post(f"/api/sources/{source_id}/collect")
                    response.raise_for_status()
                    run = wait_run(client, response.json()["id"])
                    report["tasks"].append({"batch": batch, **run})
                    print(
                        json.dumps(
                            {
                                "batch": batch,
                                **{
                                    key: run[key]
                                    for key in (
                                        "source_id",
                                        "status",
                                        "added",
                                        "updated",
                                        "duplicates",
                                        "failed",
                                        "error",
                                    )
                                },
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
            after = records(client)
            index = {row["id"]: row for row in after}
            report["before_count"], report["after_count"] = len(before), len(after)
            report["checks"]["existing_ids_preserved"] = all(row["id"] in index for row in before)
            report["checks"]["reading_state_preserved"] = all(
                all(index[row["id"]][key] == row[key] for key in ("is_read", "is_favorite"))
                for row in before
                if row["id"] in index
            )
            report["topic_counts"] = {
                topic: sum(topic in row["technical_topics"] for row in after)
                for _, _, topics, _ in PLAN
                for topic in topics or []
            }
            report["new_samples"] = [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "url": row["original_url"],
                    "topics": row["technical_topics"],
                    "resource_type": row["metrics"].get("resource", {}).get("type"),
                }
                for row in after
                if row["id"] not in {old["id"] for old in before}
            ][:100]
            if analyze_one:
                candidate = next(
                    (
                        row
                        for row in after
                        if row["status"] == "pending"
                        and row["technical_eligible"]
                        and set(row["technical_topics"]) & {"3d", "cad", "scientific", "biology"}
                        and len(row["body"]) > 300
                    ),
                    None,
                )
                if candidate:
                    report["analysis"] = analyze_sample(client, candidate)
                    print(
                        json.dumps({"analysis": report["analysis"]}, ensure_ascii=False), flush=True
                    )
        finally:
            report["scopes_restored"] = {}
            for source_id in sorted(changed):
                original = originals[source_id]
                restored = client.patch(
                    f"/api/sources/{source_id}",
                    json={
                        "discovery_topics": original["discovery_topics"]
                        if original.get("discovery_scope_customized")
                        else None
                    },
                )
                report["scopes_restored"][source_id] = restored.is_success
            report["coverage"] = client.get("/api/discovery/coverage").json()
            report["runtime"] = client.get("/api/discovery/runtime").json()
            path = Path(__file__).resolve().parents[1] / ".runtime" / "b4-b8-live.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Report: {path}", flush=True)
    if not all(report["checks"].values()) or not all(report["scopes_restored"].values()):
        raise SystemExit("Preservation or scope restoration check failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze-one", action="store_true")
    args = parser.parse_args()
    main(args.analyze_one)
