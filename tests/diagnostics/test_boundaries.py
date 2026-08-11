from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_diagnostics_has_no_ai_mutation_repair_or_persistent_truth_store() -> None:
    production = [
        *sorted((ROOT / "src/kg_mnp_demo/diagnostics").glob("*.py")),
        *sorted((ROOT / "web/diagnostics").rglob("*")),
        ROOT / "config/diagnostics/diagnostic-policy-1.0.0.yaml",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in production
        if path.is_file()
    )
    forbidden = (
        "openai",
        "graphrag",
        "embedding",
        "vector database",
        "natural-language-to-sparql",
        "sqlite",
        "postgresql",
        "innerhtml",
        "dangerouslysetinnerhtml",
        "document.write",
        "new function",
        "localstorage",
        "indexeddb",
        "/repositories/",
        "sparqlwrapper",
    )
    assert all(marker not in text for marker in forbidden)


def test_browser_bundle_uses_only_local_assets() -> None:
    html = (ROOT / "web/diagnostics/index.html").read_text(encoding="utf-8")
    assert 'src="/assets/app.js"' in html
    assert 'href="/assets/styles.css"' in html
    assert "https://" not in html
    assert "http://" not in html
    assert "<form" not in html
