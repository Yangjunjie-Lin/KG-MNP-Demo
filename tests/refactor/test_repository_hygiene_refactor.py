from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.check_repo_hygiene import run_checks

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_PREFIXES = (
    "demo_outputs/",
    "runtime/",
    "runtime_outputs/",
    "runtime_reports/",
    "runtime_logs/",
)


def _tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item and (ROOT / item.decode("utf-8", errors="surrogateescape")).is_file()
    ]


def test_refactor_hygiene_gate_passes_for_tracked_tree() -> None:
    tracked = _tracked_paths()
    assert run_checks(tracked, root=ROOT) == []
    assert not any(path.startswith(FORBIDDEN_PREFIXES) for path in tracked)


def test_reviewed_golden_locations_are_explicit() -> None:
    tracked = _tracked_paths()
    golden_paths = [
        path
        for path in tracked
        if any(
            marker in path.replace("\\", "/").split("/")
            for marker in ("fixtures", "golden", "goldens", "expected")
        )
    ]
    assert golden_paths
    assert all(
        path.startswith(("tests/", "examples/"))
        or (path.startswith("domain_packs/") and "/fixtures/" in path)
        for path in golden_paths
    )
