"""Preview or execute finite backfills through the running local application."""

import argparse
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--days", type=int)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=20)
    parser.add_argument(
        "--github-date-field", choices=["created", "pushed", "both"], default="both"
    )
    parser.add_argument(
        "--topics", nargs="+", help="At most two reviewed topic IDs; omit for source defaults"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Submit real tasks; otherwise only preview"
    )
    args = parser.parse_args()
    if args.days is not None and (args.start_date or args.end_date):
        parser.error("Use --days or an explicit start/end window")
    if bool(args.start_date) != bool(args.end_date):
        parser.error("Both --start-date and --end-date are required")
    if args.days is not None and not 1 <= args.days <= 31:
        parser.error("--days must be 1..31")
    end = args.end_date or datetime.now(UTC).date() - timedelta(days=1)
    start = args.start_date or end - timedelta(days=(args.days or 5) - 1)
    request = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_pages": args.pages,
        "start_page": args.start_page,
        "per_page": args.per_page,
        "github_date_field": args.github_date_field,
    }
    if args.topics:
        request["topics"] = args.topics
    results = []
    failed = False
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api",
        timeout=15,
        trust_env=False,
        headers={"X-FrontierSignal": "1"},
    ) as client:
        for source in dict.fromkeys(args.sources):
            if (
                not source
                or len(source) > 80
                or not all(char.isalnum() or char in "-_" for char in source)
            ):
                parser.error("Source IDs may contain only letters, numbers, dash and underscore")
            try:
                response = client.post(f"/sources/{source}/backfill/preview", json=request)
                response.raise_for_status()
                plan = response.json()
                print(
                    json.dumps(
                        {
                            "source": source,
                            "mode": "apply" if args.apply else "preview",
                            "plan": plan,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if not args.apply:
                    results.append({"source": source, "plan": plan})
                    continue
                response = client.post(f"/sources/{source}/backfill", json=request)
                response.raise_for_status()
                task = response.json()
                deadline = time.monotonic() + 660
                while task["status"] in {"queued", "running"}:
                    if time.monotonic() > deadline:
                        raise TimeoutError(
                            "Task observation timed out; the task was not resubmitted"
                        )
                    time.sleep(1)
                    response = client.get("/tasks")
                    response.raise_for_status()
                    task = next(row for row in response.json() if row["id"] == task["id"])
                results.append(task)
                print(
                    json.dumps(
                        {
                            "source": source,
                            "id": task["id"],
                            "status": task["status"],
                            "added": task["added"],
                            "updated": task["updated"],
                            "duplicates": task["duplicates"],
                            "filtered": task["filtered"],
                            "failed": task["failed"],
                            "bounded": True,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                failed |= task["failed"] > 0 or task["status"] in {"failed", "interrupted"}
            except (httpx.HTTPError, TimeoutError, StopIteration) as exc:
                failed = True
                result = {"source": source, "error": type(exc).__name__, "bounded": True}
                results.append(result)
                print(json.dumps(result), flush=True)
    report = Path(".runtime") / f"backfill-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    report.parent.mkdir(exist_ok=True, mode=0o700)
    report.write_text(
        json.dumps(
            {"request": request, "applied": args.apply, "results": results},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    report.chmod(0o600)
    print(f"Report: {report}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
