"""Persist bounded query observations separately from source-wide task status."""

from .models import now


def record_scan(scans, key, *, label, topics, count=0, error=None, partial=False):
    previous = scans.get(key, {})
    at = now().isoformat()
    scans[key] = {
        "label": label,
        "topics": topics,
        "last_scan_at": at,
        "last_success_at": previous.get("last_success_at") if error else at,
        "status": ("partial" if partial else "failed") if error else "success",
        "candidates": count,
        "error": error,
        "added": 0,
        "updated": 0,
        "duplicates": 0,
        "failed": 0,
    }


def record_outcome(cursor, groups, outcome):
    for key in groups:
        row = cursor.get("scans", {}).get(key)
        if row is not None:
            row[outcome] = (row.get(outcome) or 0) + 1


def scan_rows(source, groups):
    scans = (source.cursor or {}).get("scans", {})
    return [
        {
            "id": group["id"],
            "label": group["label"],
            "topics": group["topics"],
            "status": "pending",
            "last_scan_at": None,
            "last_success_at": None,
            "candidates": None,
            "error": None,
            **scans.get(group["id"], {}),
        }
        for group in groups
    ]
