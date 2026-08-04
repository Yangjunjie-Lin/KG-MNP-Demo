#!/usr/bin/env python3
"""Regenerate OpenAPI and fail only when the checked-in file was stale."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "docs" / "api" / "openapi.json"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def main() -> int:
    before = OPENAPI.read_bytes() if OPENAPI.exists() else None
    completed = subprocess.run(
        [sys.executable, "scripts/export_openapi.py"],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode:
        return completed.returncode
    after = OPENAPI.read_bytes()
    if before != after:
        print(
            "OpenAPI 漂移：docs/api/openapi.json 与当前后端 Schema 不一致，已重新生成。",
            file=sys.stderr,
        )
        return 1
    print("OpenAPI 无漂移。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
