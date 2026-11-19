"""Run three consecutive Playwright suites, each against a fresh test database."""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "frontend"
BACKEND = ROOT / "backend"
STOP = ROOT / "var/t14-browser.stop"


def wait_http(url: str, server: subprocess.Popen) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline and server.poll() is None:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.3)
    raise RuntimeError(f"Server did not become ready at {url}")


def start(command, cwd: Path, log: Path, env: dict[str, str]) -> subprocess.Popen:
    with log.open("wb") as output:
        return subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)


def run(rounds: int, only_t33: bool) -> None:
    if STOP.exists():
        raise RuntimeError(f"Fixture stop file already exists at {STOP}")
    for port in (3000, 8000):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise RuntimeError(f"Cannot bind 127.0.0.1:{port}") from None
    if not (WEB / ".next/BUILD_ID").exists():
        raise RuntimeError("Build the frontend first")
    with urlopen("http://127.0.0.1:8025/api/v1/messages", timeout=3):
        pass
    logs = ROOT / "var" / f"e2e-{uuid4().hex}"
    logs.mkdir(parents=True)
    print(f"Run logs and traces: {logs}", flush=True)
    env = {
        **os.environ,
        "T33_MAILPIT_URL": "http://127.0.0.1:8025",
        "DATABASE_URL": "postgresql+psycopg://hr:hr@127.0.0.1:5432/hr_ats",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "FRONTEND_ORIGIN": "http://localhost:3000",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": "1025",
        "SMTP_TLS": "false",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        "SMTP_FROM": "HR ATS E2E <test@example.invalid>",
        "IMAP_ENABLED": "false",
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    web = start(
        ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1"],
        WEB,
        logs / "web.log",
        env,
    )
    try:
        wait_http("http://localhost:3000/login", web)
        for index in range(1, rounds + 1):
            api = start(
                [sys.executable, "-m", "tests.ranking_browser_server"],
                BACKEND,
                logs / f"api-{index}.log",
                env,
            )
            try:
                wait_http("http://localhost:8000/api/v1/health", api)
                command = [
                    "node",
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "--workers=2",
                    "--retries=0",
                    "--global-timeout=600000",
                    f"--output={logs / f'round-{index}'}",
                ]
                if only_t33:
                    command.append("t33-regression.spec.ts")
                started = time.monotonic()
                subprocess.run(command, cwd=WEB, env=env, check=True, timeout=610)
                elapsed = time.monotonic() - started
                if elapsed >= 600:
                    raise RuntimeError(f"Round {index} exceeded 10 minutes")
                print(f"Round {index}/{rounds} passed in {elapsed:.1f}s", flush=True)
            finally:
                if api.poll() is None:
                    STOP.touch()
                    api.wait(timeout=30)
                if api.returncode != 0:
                    raise RuntimeError(f"Fixture exited with {api.returncode}")
    finally:
        if web.poll() is None:
            web.terminate()
        web.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only-t33", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    run(args.runs, args.only_t33)
