"""Start/stop the WSL background service with PID reuse and project identity checks."""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
STATE = RUNTIME / "backend-process.json"


def identity(pid):
    try:
        proc = Path("/proc") / str(pid)
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z" or (proc / "cwd").resolve() != ROOT:
            return None
        if b"frontiersignal.main:app" not in (proc / "cmdline").read_bytes().split(b"\0"):
            return None
        return fields[19]
    except (OSError, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("Use scripts/Start.ps1 on native Windows; this helper is for WSL/Linux")
    previous = json.loads(STATE.read_text()) if STATE.exists() else None
    active = previous and identity(previous["pid"]) == previous["start_time"]
    if args.stop:
        if active:
            os.kill(previous["pid"], signal.SIGINT)
            for _ in range(100):
                if identity(previous["pid"]) != previous["start_time"]:
                    break
                time.sleep(0.1)
            else:
                raise SystemExit("Service is still shutting down; no forced kill was attempted")
        STATE.unlink(missing_ok=True)
        print("Background service stopped (PostgreSQL remains running)")
        return
    if active:
        print(f"Existing service PID {previous['pid']}: http://localhost:8000")
        return
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", 8000))
        except OSError:
            raise SystemExit(
                "Port 8000 is occupied by another process; refusing to replace it"
            ) from None
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    with (RUNTIME / "backend.log").open("ab", buffering=0) as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "frontiersignal.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--workers",
                "1",
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    with httpx.Client(timeout=1, trust_env=False) as client:
        for _ in range(100):
            if process.poll() is not None:
                raise SystemExit("Backend failed to start; inspect .runtime/backend.log")
            try:
                if client.get("http://127.0.0.1:8000/api/health").status_code == 200:
                    token = identity(process.pid)
                    if not token:
                        raise RuntimeError("Unable to verify child process identity")
                    STATE.write_text(json.dumps({"pid": process.pid, "start_time": token}))
                    STATE.chmod(0o600)
                    print(f"Service ready, PID {process.pid}: http://localhost:8000")
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
    process.terminate()
    process.wait(timeout=10)
    raise SystemExit("Backend readiness check failed; inspect .runtime/backend.log")


if __name__ == "__main__":
    main()
