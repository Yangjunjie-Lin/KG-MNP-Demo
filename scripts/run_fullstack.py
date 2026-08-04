#!/usr/bin/env python
"""Run the local API and Vite development server as one process group."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DEFAULT_DB = ROOT / "runtime_data" / "kg_mnp.sqlite3"
EXPECTED_CASE_IDS = {f"CASE-{index:02d}" for index in range(1, 10)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local KG-MNP full stack.")
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Do not seed demo history when the database is missing or incomplete.",
    )
    parser.add_argument(
        "--reset-seed",
        action="store_true",
        help="Remove runtime_data and seed a deterministic E2E database before startup.",
    )
    parser.add_argument(
        "--playwright",
        action="store_true",
        help="Run the local Playwright suite after both services are ready, then stop.",
    )
    return parser.parse_args()


def process_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def npm_command(arguments: list[str]) -> list[str]:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm was not found; install Node.js 20 first.")
    if os.name != "nt":
        return [npm, *arguments]

    command = subprocess.list2cmdline([npm, *arguments])
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]


def start(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(command, cwd=cwd, env=env, **process_options())


def stop_process_tree(process: subprocess.Popen[bytes], grace_seconds: float = 3.0) -> None:
    if process.poll() is not None:
        return

    try:
        if os.name == "nt":
            # npm is launched through cmd.exe, whose prompt can block graceful shutdown.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=grace_seconds)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def wait_for_url(
    url: str,
    process: subprocess.Popen[bytes],
    service_name: str,
    timeout_seconds: float = 45.0,
    validator: Callable[[bytes], bool] | None = None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"{service_name} exited early with code {return_code}.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = response.read()
                if 200 <= response.status < 400 and (
                    validator is None or validator(payload)
                ):
                    return
        except (json.JSONDecodeError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {service_name}: {last_error}")


def database_seed_complete(path: Path = DEFAULT_DB) -> bool:
    """Return whether all nine demo cases and both CASE-06 histories exist."""
    if not path.exists():
        return False
    try:
        database_uri = f"{path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True)) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "executions"),
            ).fetchone()
            if table is None:
                return False
            counts = dict(
                connection.execute(
                    "SELECT case_id, COUNT(*) FROM executions GROUP BY case_id"
                ).fetchall()
            )
    except sqlite3.Error:
        return False
    return EXPECTED_CASE_IDS.issubset(counts) and int(counts.get("CASE-06", 0)) >= 2


def database_needs_seed() -> bool:
    return not database_seed_complete()


def ready_response(payload: bytes) -> bool:
    data = json.loads(payload)
    return data.get("status") == "ready" and data.get("sqlite") is True


def seed_if_needed(skip_seed: bool) -> None:
    if skip_seed or not database_needs_seed():
        return
    print("Initializing or repairing the nine demo cases and assessment history...", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo_data.py")],
        cwd=ROOT,
        check=True,
    )
    if not database_seed_complete():
        raise RuntimeError(
            "Demo seed is incomplete: expected CASE-01 through CASE-09 and two CASE-06 histories."
        )


def reset_runtime_data() -> None:
    runtime_root = DEFAULT_DB.parent.resolve()
    expected = (ROOT / "runtime_data").resolve()
    if runtime_root != expected or runtime_root == ROOT.resolve():
        raise RuntimeError(f"Refusing to reset unexpected runtime path: {runtime_root}")
    if runtime_root.exists():
        shutil.rmtree(runtime_root)


def main() -> int:
    args = parse_args()
    processes: list[subprocess.Popen[bytes]] = []
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, request_stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, request_stop)

    try:
        if args.skip_seed and args.reset_seed:
            raise RuntimeError("--skip-seed and --reset-seed cannot be used together.")
        if args.reset_seed:
            reset_runtime_data()
        seed_if_needed(args.skip_seed)

        environment = os.environ.copy()
        environment.setdefault("KG_MNP_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
        environment.setdefault("VITE_API_BASE_URL", "/api/v1")
        environment.setdefault("VITE_DATA_SOURCE", "api")
        environment.setdefault("VITE_ENABLE_TECHNICAL_VIEW", "false")
        api = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "kg_mnp_demo.api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT,
            environment,
        )
        processes.append(api)
        api_url = "http://127.0.0.1:8000"
        wait_for_url(
            f"{api_url}/api/v1/ready",
            api,
            "API",
            validator=ready_response,
        )

        frontend = start(
            npm_command(
                [
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5173",
                    "--strictPort",
                ]
            ),
            FRONTEND,
            environment,
        )
        processes.append(frontend)
        frontend_url = "http://127.0.0.1:5173"
        wait_for_url(frontend_url, frontend, "frontend")

        print(f"Frontend: {frontend_url}", flush=True)
        print(f"API health: {api_url}/api/v1/health", flush=True)
        if args.playwright:
            environment["PLAYWRIGHT_EXTERNAL_SERVERS"] = "true"
            completed = subprocess.run(
                npm_command(["exec", "--", "playwright", "test"]),
                cwd=FRONTEND,
                env=environment,
                check=False,
            )
            return completed.returncode

        print("Press Ctrl+C to stop both services.", flush=True)

        while not stopping:
            for name, process in (("API", api), ("frontend", frontend)):
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"{name} exited with code {return_code}.")
            time.sleep(0.25)
        return 0
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            stop_process_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
