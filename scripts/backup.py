"""Consistent PostgreSQL backup and restore into a NEW database only."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from frontiersignal.config import PROJECT_ROOT, settings
from psycopg import sql
from sqlalchemy.engine import make_url

TABLES = [
    "sources",
    "articles",
    "raw_records",
    "task_runs",
    "analysis_attempts",
    "categories",
    "article_links",
    "article_embeddings",
    "repositories",
    "star_snapshots",
]
URL = make_url(settings.database_url.get_secret_value())


def connect(database=None, autocommit=False):
    return psycopg.connect(
        URL.set(drivername="postgresql", database=database or URL.database).render_as_string(
            hide_password=False
        ),
        autocommit=autocommit,
    )


def counts(conn, tables=None):
    return {
        name: conn.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))
        ).fetchone()[0]
        for name in (TABLES if tables is None else tables)
    }


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tool(name, arguments, *, database=None, output=None):
    env = {
        **os.environ,
        "PGHOST": URL.host or "localhost",
        "PGPORT": str(URL.port or 5432),
        "PGUSER": URL.username or "frontiersignal",
        "PGPASSWORD": URL.password or "",
        "PGDATABASE": database or URL.database,
    }
    extracted = Path.home() / ".local/share/frontiersignal-pg"
    selected = os.environ.get("FS_PG_BIN")
    if selected:
        command = [str(Path(selected) / name), *arguments]
    elif (extracted / "usr/lib/postgresql/18/bin" / name).exists():
        command = [str(extracted / "usr/lib/postgresql/18/bin" / name), *arguments]
        env["LD_LIBRARY_PATH"] = str(extracted / "usr/lib/x86_64-linux-gnu")
    elif shutil.which(name):
        command = [name, *arguments]
    else:
        # Binary backup bytes go through Python streams, not PowerShell text redirection.
        command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            name,
            "-U",
            URL.username or "frontiersignal",
            "-d",
            database or URL.database,
            *arguments,
        ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=output or subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode(errors="replace")
        if URL.password:
            message = message.replace(URL.password, "[redacted]")
        raise RuntimeError(f"{name} failed: {message[:1500]}")


def create_database(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise ValueError("New database name must use lowercase letters, digits and underscores")
    with connect("postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise ValueError("Target database already exists; refusing to overwrite it")
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def restore(path, name, on_created=None):
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if checksum(path) != metadata["sha256"]:
        raise ValueError("Backup checksum mismatch")
    create_database(name)
    if on_created:
        on_created()
    # A Docker restore uses stdin so a host filesystem path need not exist inside the container.
    extracted = Path.home() / ".local/share/frontiersignal-pg/usr/lib/postgresql/18/bin/pg_restore"
    native = bool(os.environ.get("FS_PG_BIN") or extracted.exists() or shutil.which("pg_restore"))
    if native:
        tool(
            "pg_restore",
            ["--exit-on-error", "--no-owner", "--dbname", name, str(path)],
            database=name,
        )
    else:
        with path.open("rb") as stream:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "db",
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "-U",
                    URL.username or "frontiersignal",
                    "-d",
                    name,
                ],
                stdin=stream,
                cwd=PROJECT_ROOT,
                capture_output=True,
            )
        if result.returncode:
            raise RuntimeError("Docker pg_restore failed; the new database was left for inspection")
    with connect(name) as conn:
        observed = counts(conn, metadata["counts"])
        if observed != metadata["counts"]:
            raise ValueError("Restored row counts do not match the backup snapshot")
    return observed


def backup(path):
    path.parent.mkdir(exist_ok=True, parents=True)
    if path.exists() or path.with_suffix(".json").exists():
        raise ValueError("Backup destination exists; refusing to overwrite it")
    temporary = path.with_suffix(".partial")
    if temporary.exists():
        raise ValueError("Partial backup destination already exists")
    try:
        with connect() as conn:
            conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            snapshot_counts = counts(conn)
            with temporary.open("xb") as stream:
                tool(
                    "pg_dump",
                    ["--format=custom", "--no-owner", f"--snapshot={snapshot}"],
                    output=stream,
                )
        temporary.rename(path)
        metadata = {
            "sha256": checksum(path),
            "created_at": datetime.now(UTC).isoformat(),
            "counts": snapshot_counts,
            "format": "pg_dump-custom",
        }
        path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--verify", action="store_true", help="Restore into and remove a disposable database"
    )
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--new-database")
    args = parser.parse_args()
    if args.restore:
        if not args.new_database:
            parser.error(
                "--restore requires --new-database; existing databases are never overwritten"
            )
        print(
            json.dumps(
                {
                    "restored_database": args.new_database,
                    "counts": restore(args.restore.resolve(), args.new_database),
                }
            )
        )
        return
    path = (
        args.output
        or PROJECT_ROOT / "backups" / f"frontiersignal-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.dump"
    ).resolve()
    metadata = backup(path)
    print(f"Backup: {path}")
    print(json.dumps(metadata, ensure_ascii=False))
    if args.verify:
        name = "fs_restore_test_" + uuid.uuid4().hex
        created = []
        try:
            observed = restore(path, name, on_created=lambda: created.append(name))
            print("Restore verification passed:", json.dumps(observed))
        finally:
            if created:
                with connect("postgres", autocommit=True) as conn:
                    conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
