"""Verify public source collection against the running API, never inserting fixtures."""

import json
import time

import httpx


def main():
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api",
        timeout=15,
        trust_env=False,
        headers={"X-FrontierSignal": "1"},
    ) as client:
        sources = client.get("/sources").json()
        assert not any(source["kind"] in {"x", "reddit"} for source in sources)
        selected = {
            "github-discovery",
            "hackernews",
            "hf-models",
            "hf-datasets",
            "arxiv-lg",
            "arxiv-cl",
            "arxiv-cv",
        }
        runs = {}
        for source in sources:
            if source["id"] in selected:
                response = client.post(f"/sources/{source['id']}/collect")
                response.raise_for_status()
                runs[response.json()["id"]] = source["id"]
        deadline = time.monotonic() + 240
        completed = {}
        while time.monotonic() < deadline:
            response = client.get("/tasks")
            response.raise_for_status()
            for run in response.json():
                if run["id"] in runs and run["status"] not in {"queued", "running"}:
                    completed[runs[run["id"]]] = {
                        key: run[key]
                        for key in [
                            "id",
                            "status",
                            "added",
                            "duplicates",
                            "filtered",
                            "failed",
                            "error",
                        ]
                    }
            if len(completed) == len(runs):
                break
            time.sleep(1)
        print(json.dumps({"sources": completed}, ensure_ascii=False, indent=2), flush=True)
        response = client.get("/recommendations")
        response.raise_for_status()
        dashboard = response.json()
        projects = client.get("/projects?pool=all&page_size=100").json()
        print(
            json.dumps(
                {
                    "recommended_projects": len(dashboard["projects"]),
                    "emerging_projects": len(dashboard["emerging_projects"]),
                    "technical_projects": projects["total"],
                    "rising_projects": projects["counts"]["rising"],
                    "sections": {
                        section["id"]: len(section["items"]) for section in dashboard["sections"]
                    },
                    "growth_unknown": sum(
                        row["growth_24h"]["value"] is None for row in projects["items"]
                    ),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        assert projects["total"] > 0, "No real technical projects collected"
        assert len(completed) == len(runs), "Collection did not finish before deadline"
        if any(run["status"] != "success" for run in completed.values()):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
