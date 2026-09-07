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
    normalized = " ".join(readme.split())
    assert "# KG-MNP Ontology Toolchain" in readme
    # The current-status line must describe the real P8 entry result, not pin a
    # superseded P5 heading (already absent at the fixed P7 source).
    assert "Prompt 8 backend remediation in progress" in readme
    assert "NO_GO_BACKEND_NOT_READY" in readme
    assert "KG-MNP Ontology Workbench" in readme
    assert "What is implemented now" in readme
    assert "What is not implemented yet" in readme
    assert "Forestry Domain" in readme
    assert "planning scaffold only" in readme
    assert "No Agent or LLM is an ontology authority" in normalized
    assert "Image and WAV support is metadata-only" in readme
    assert "Stage 09" not in readme
    assert "Phase 07" not in readme


def test_prompt05_documents_state_implemented_and_deferred_capabilities() -> None:
    matrix = (ROOT / "docs/product/current-capability-matrix.md").read_text(
        encoding="utf-8"
    )
    for capability in (
        "Public Contract Catalog",
        "Offline Contract Registry",
        "DomainPackLock v1",
        "Project Workspace v1",
        "Plugin SDK v1",
        "Source Content Store",
        "EvidenceRecord",
        "Deterministic Ingestion Planner",
        "KG-IR",
        "Ingestion CLI",
        "Ontology Scope and Approval",
        "Modeling Provider API 1.1",
        "Formal Prevalidation",
        "Human Review Control Plane",
        "Prompt 4 Confirmed Modeling Package",
        "Compiler Input Attestation",
        "Semantic Compiler Policy and Snapshot",
        "Deterministic Compilation Plan",
        "Generic semantic compilation",
        "Canonical named RDF dataset",
        "Formal validation gates",
        "Versioned Ontology Package",
        "Deterministic `.kgop` export",
    ):
        assert capability in matrix
    for planned in (
        "LLM Ingestion Planner",
        "OCR/Vision/ASR/Video providers",
        "Live LLM Proposal Provider",
        "Package Registry Rewrite",
        "Automatic SemVer Classification",
        "Release Publication",
        "Forestry Domain Pack Implementation",
    ):
        assert planned in matrix

    required_prompt02_docs = (
        "docs/contracts/public-contract-policy.md",
        "docs/contracts/schema-catalog.md",
        "docs/contracts/artifact-model-v1.md",
        "docs/contracts/canonicalization-and-digests.md",
        "docs/domain-packs/domain-pack-contract-v1.md",
        "docs/domain-packs/domain-pack-lock-v1.md",
        "docs/workspaces/project-manifest-v1.md",
        "docs/workspaces/project-workspace-v1.md",
        "docs/workspaces/project-lock-v1.md",
        "docs/architecture/contract-and-workspace-kernel.md",
        "docs/adr/ADR-0002-public-contract-domain-pack-and-workspace.md",
    )
    assert all((ROOT / path).is_file() for path in required_prompt02_docs)

    required_prompt03_docs = (
        "docs/plugins/plugin-sdk-v1.md",
        "docs/plugins/plugin-manifest-v1.md",
        "docs/plugins/plugin-trust-and-security.md",
        "docs/ingestion/source-asset-v1.md",
        "docs/ingestion/source-locator-v1.md",
        "docs/ingestion/evidence-record-v1.md",
        "docs/ingestion/kg-ir-v1.md",
        "docs/ingestion/ingestion-plan-and-run-v1.md",
        "docs/ingestion/quality-gates-v1.md",
        "docs/ingestion/supported-format-matrix.md",
        "docs/architecture/plugin-driven-ingestion-architecture.md",
        "docs/adr/ADR-0003-plugin-driven-evidence-bound-ingestion.md",
    )
    assert all((ROOT / path).is_file() for path in required_prompt03_docs)

    required_prompt04_docs = (
        "docs/modeling/ontology-scope-v1.md",
        "docs/modeling/competency-questions-v1.md",
        "docs/modeling/baseline-and-terminology.md",
        "docs/modeling/term-alignment.md",
        "docs/modeling/modeling-provider-api.md",
        "docs/modeling/ontology-candidate-model.md",
        "docs/modeling/formal-prevalidation.md",
        "docs/modeling/human-review-workflow.md",
        "docs/modeling/confirmed-modeling-package.md",
        "docs/modeling/recorded-model-output.md",
        "docs/architecture/evidence-grounded-modeling-architecture.md",
        "docs/adr/ADR-0004-evidence-grounded-ontology-modeling.md",
        "docs/research/ontology-modeling-evaluation-protocol.md",
    )
    assert all((ROOT / path).is_file() for path in required_prompt04_docs)

    required_prompt05_docs = (
        "docs/compilation/semantic-compiler-policy-v1.md",
        "docs/compilation/compiler-input-attestation-v1.md",
        "docs/compilation/semantic-compilation-plan-v1.md",
        "docs/compilation/tbox-compilation.md",
        "docs/compilation/abox-compilation.md",
        "docs/compilation/shacl-compilation.md",
        "docs/compilation/mapping-plan-v1.md",
        "docs/compilation/rdf-canonical-profile-v1.md",
        "docs/compilation/owl-validation.md",
        "docs/compilation/shacl-final-validation.md",
        "docs/compilation/competency-question-testing.md",
        "docs/compilation/provenance-and-evidence-lineage.md",
        "docs/compilation/ontology-package-format-v1.md",
        "docs/compilation/kgop-archive-format-v1.md",
        "docs/architecture/deterministic-semantic-kernel-architecture.md",
        "docs/adr/ADR-0005-deterministic-semantic-compilation-and-packaging.md",
        "docs/research/semantic-compilation-evaluation-protocol.md",
    )
    assert all((ROOT / path).is_file() for path in required_prompt05_docs)


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
