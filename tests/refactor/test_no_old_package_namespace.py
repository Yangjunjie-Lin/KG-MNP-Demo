from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED_ROOTS = ("src", "tests", "scripts", ".github", "deploy", "config")
SCANNED_FILES = ("Makefile", "pyproject.toml")
OLD_NAMESPACE = "kg_" + "mnp_demo"


def _tracked_active_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = {
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    }
    candidates = [
        ROOT / path
        for path in tracked
        if path in SCANNED_FILES
        or any(path.startswith(f"{root_name}/") for root_name in SCANNED_ROOTS)
    ]
    return [path for path in candidates if path.is_file()]


def test_old_namespace_is_absent_from_active_repository_surfaces() -> None:
    findings: list[str] = []
    for path in _tracked_active_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD_NAMESPACE in text:
            findings.append(path.relative_to(ROOT).as_posix())
    assert findings == []


def test_old_package_cannot_be_imported() -> None:
    import importlib.util

    assert importlib.util.find_spec(OLD_NAMESPACE) is None
