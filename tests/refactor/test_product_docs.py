from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_DOCUMENTS = (
    "README.md",
    "docs/product/product-charter.md",
    "docs/product/current-capability-matrix.md",
    "docs/product/research-to-product-alignment.md",
    "docs/architecture/ontology-toolchain-target-architecture.md",
    "docs/adr/ADR-0001-reposition-as-ontology-toolchain.md",
)


def test_product_foundation_documents_exist() -> None:
    assert all((ROOT / path).is_file() for path in REQUIRED_DOCUMENTS)


def test_readme_states_current_identity_and_capability_limits() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "# KG-MNP Ontology Toolchain" in readme
    assert "Toolchain Refactor Foundation — Prompt 1" in readme
    assert "What is implemented now" in readme
    assert "What is not implemented yet" in readme
    assert "Forestry Domain Pack is a planning" in readme
    assert "scaffold only" in readme
    assert "No Agent or LLM is an ontology authority" in readme
    assert "Stage 09" not in readme
    assert "Phase 07" not in readme


def test_current_product_documents_do_not_extend_retired_route() -> None:
    roots = (
        ROOT / "README.md",
        ROOT / "docs" / "product",
        ROOT / "docs" / "architecture",
        ROOT / "docs" / "adr",
    )
    files = [roots[0]]
    for root in roots[1:]:
        files.extend(path for path in root.rglob("*.md") if path.is_file())
    forbidden = ("Stage 09", "Application Phase 07", "Phase 07")
    findings = [
        f"{path.relative_to(ROOT).as_posix()}: {term}"
        for path in files
        for term in forbidden
        if term in path.read_text(encoding="utf-8")
    ]
    assert findings == []
