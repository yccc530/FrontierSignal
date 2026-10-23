"""Start an isolated WSL PostgreSQL from extracted Ubuntu packages, without root."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
prefix = Path.home() / ".local/share/frontiersignal-pg"
bindir = prefix / "usr/lib/postgresql/18/bin"
runtime = root / ".runtime"
data = runtime / "postgres"
runtime.mkdir(mode=0o700, exist_ok=True)
env = {**os.environ, "LD_LIBRARY_PATH": str(prefix / "usr/lib/x86_64-linux-gnu")}


def run(name, *args, check=True):
    return subprocess.run([str(bindir / name), *map(str, args)], env=env, check=check)


if not bindir.exists():
    sys.exit("User PostgreSQL packages are absent; see README for Docker Desktop setup.")
if "--stop" in sys.argv:
    run("pg_ctl", "-D", data, "-m", "fast", "stop")
    sys.exit(0)
if not data.exists():
    password = dotenv_values(root / ".env").get("POSTGRES_PASSWORD")
    if not password or password == "CHANGE_ME":
        sys.exit("Run scripts/setup.py first.")
    secret = runtime / "pg-password"
    fd = os.open(secret, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as file:
            file.write(password)
        run(
            "initdb",
            "-D",
            data,
            "--username=frontiersignal",
            "--auth-local=trust",
            "--auth-host=scram-sha-256",
            "--pwfile",
            secret,
            "--encoding=UTF8",
            "--locale=C.UTF-8",
        )
    finally:
        secret.unlink(missing_ok=True)
if run("pg_ctl", "-D", data, "status", check=False).returncode != 0:
    run(
        "pg_ctl",
        "-D",
        data,
        "-l",
        runtime / "postgres.log",
        "-o",
        f"-h 127.0.0.1 -p 54329 -k {runtime} -c shared_preload_libraries=''",
        "start",
    )
# The private Unix socket uses local trust; TCP always requires the generated password.
result = subprocess.run(
    [
        str(bindir / "psql"),
        "-h",
        str(runtime),
        "-p",
        "54329",
        "-U",
        "frontiersignal",
        "-d",
        "postgres",
        "-Atc",
        "SELECT 1 FROM pg_database WHERE datname='frontiersignal'",
    ],
    env=env,
    check=True,
    capture_output=True,
    text=True,
)
if result.stdout.strip() != "1":
    run("createdb", "-h", runtime, "-p", "54329", "-U", "frontiersignal", "frontiersignal")
print("Local PostgreSQL available on 127.0.0.1:54329")
