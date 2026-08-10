from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase02_contains_no_ai_write_review_or_persistent_data_surface() -> None:
    production = [
        *sorted((ROOT / "src/kg_mnp_demo/workbench").glob("*.py")),
        *sorted((ROOT / "web/workbench").rglob("*")),
        ROOT / "config/workbench/workbench-runtime-1.0.0.yaml",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="strict").casefold()
        for path in production
        if path.is_file()
    )
    forbidden = (
        "openai",
        "graphrag",
        "embedding",
        "vector database",
        "natural-language-to-sparql",
        "workbench write",
        "workbench approve",
        "workbench update",
        "sqlite",
        "postgresql",
        "google fonts",
        "analytics",
        "telemetry",
    )
    assert all(marker not in text for marker in forbidden)


def test_browser_bundle_has_only_local_assets_and_internal_navigation() -> None:
    html = (ROOT / "web/workbench/index.html").read_text(encoding="utf-8")
    assert 'src="/assets/app.js"' in html
    assert 'href="/assets/styles.css"' in html
    assert "https://" not in html
    assert "http://" not in html
    assert "target=" not in html
    assert "<form" not in html
