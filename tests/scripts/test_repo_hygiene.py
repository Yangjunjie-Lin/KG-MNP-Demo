"""Tests for scripts/check_repo_hygiene.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    path = ROOT / "scripts" / "check_repo_hygiene.py"
    spec = importlib.util.spec_from_file_location("check_repo_hygiene", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_venv_path_is_rejected():
    mod = _load_module()
    failures = mod.check_tracked_paths([".venv311/pyvenv.cfg"])
    assert failures == ["tracked virtual environment: .venv311/pyvenv.cfg"]


def test_windows_absolute_path_is_rejected(tmp_path: Path):
    mod = _load_module()
    sample = tmp_path / "frontend" / "src" / "example.ts"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        'const root = "C:\\Users\\demo\\workspace";\n',
        encoding="utf-8",
    )
    failures = mod.check_absolute_paths(
        ["frontend/src/example.ts"],
        root=tmp_path,
    )
    assert failures == ["local absolute path in frontend/src/example.ts:1"]


def test_relative_path_is_allowed(tmp_path: Path):
    mod = _load_module()
    sample = tmp_path / "README.md"
    sample.write_text("See ./frontend/src/app for sources.\n", encoding="utf-8")
    failures = mod.run_checks(["README.md"], root=tmp_path)
    assert failures == []


def test_https_url_is_allowed(tmp_path: Path):
    mod = _load_module()
    sample = tmp_path / "docs" / "links.md"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        "https://github.com/Yangjunjie-Lin/KG-MNP-Demo\n",
        encoding="utf-8",
    )
    failures = mod.check_absolute_paths(["docs/links.md"], root=tmp_path)
    assert failures == []


def test_current_repository_passes():
    mod = _load_module()
    assert mod.run_checks() == []
