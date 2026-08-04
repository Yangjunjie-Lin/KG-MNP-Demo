#!/usr/bin/env python3
"""Start, smoke-test, and always clean up the full-stack Compose project."""

from __future__ import annotations

import subprocess
import sys


COMPOSE = ["docker", "compose", "-f", "docker-compose.fullstack.yml"]

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, text=True)
    except OSError as exc:
        print(f"无法执行 {' '.join(command)}：{exc}", file=sys.stderr)
        return None


def main() -> int:
    result = 1
    try:
        startup = run_command([*COMPOSE, "up", "-d", "--build", "--wait"])
        if startup is None:
            result = 127
        elif startup.returncode:
            result = startup.returncode
        else:
            smoke = run_command([sys.executable, "scripts/docker_fullstack_smoke.py"])
            result = 127 if smoke is None else smoke.returncode
    finally:
        cleanup = run_command([*COMPOSE, "down", "-v", "--remove-orphans"])
        if result == 0 and (cleanup is None or cleanup.returncode != 0):
            print("Docker Compose 清理失败。", file=sys.stderr)
            result = 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
