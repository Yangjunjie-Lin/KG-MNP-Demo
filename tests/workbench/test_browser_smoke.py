from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_only_current_locked_browser_harness_is_supported() -> None:
    assert not (ROOT / "scripts/workbench_browser_smoke.py").exists()
    manifest = json.loads((ROOT / "workbench/package.json").read_bytes())
    lock = json.loads((ROOT / "workbench/package-lock.json").read_bytes())
    version = manifest["devDependencies"]["@playwright/test"]
    assert lock["packages"]["node_modules/@playwright/test"]["version"] == version
    assert lock["packages"]["node_modules/playwright-core"]["version"] == version
    config = (ROOT / "workbench/playwright.config.ts").read_text(encoding="utf-8")
    assert "serviceWorkers:'block'" in config
    probe = (ROOT / "workbench/tests/security.e2e.ts").read_text(encoding="utf-8")
    assert "securitypolicyviolation" in probe and "external.invalid" in probe
