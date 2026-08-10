from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_real_browser_harness_is_frozen_to_existing_browser_identity() -> None:
    script = ROOT / "scripts/workbench_browser_smoke.py"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert 'EXPECTED_BROWSER_NAME = "chromium"' in text
    assert 'EXPECTED_BROWSER_VERSION = "131.0.6778.33"' in text
    assert 'EXPECTED_BROWSER_REVISION = "1148"' in text
    assert "service_workers=\"block\"" in text
    assert "example.invalid" in text
