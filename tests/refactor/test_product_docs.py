"""Current product documentation, not assertions freezing historical prose."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_DOCUMENTS = (
    "README.md", "docs/index.md", "docs/architecture/toolchain.md",
    "docs/security/authority-boundaries.md", "docs/research/implementation-evidence.md",
    "docs/migration/final-retirement-ledger.json",
    "docs/verification/final-requirements.json", "docs/verification/final-verification.json",
)

def test_product_foundation_documents_exist():
    assert all((ROOT / path).is_file() for path in REQUIRED_DOCUMENTS)

def test_readme_states_current_identity_and_capability_limits():
    text=(ROOT/"README.md").read_text(encoding="utf-8")
    for required in ("KG-MNP Ontology Toolchain", "EXPERIMENTAL", "Provider 只生成候选", "VALIDATED_UNPUBLISHED", "CONTROL_PLANE_SELECTED", "Recorded Provider 不是 Live LLM"):
        assert required in text
    for obsolete in ("planning scaffold only", "What is not implemented yet", "Stage 09", "Phase 07"):
        assert obsolete not in text

def test_current_architecture_records_distinct_authorities_not_execution_claims():
    text=(ROOT/"docs/architecture/toolchain.md").read_text(encoding="utf-8")
    assert text.count("```mermaid")==4
    for boundary in ("不是同一对象", "不能证明部署", "旧 Worker", "RECOVERY_REQUIRED"):
        assert boundary in text

def test_current_product_documents_do_not_extend_retired_route():
    for relative in REQUIRED_DOCUMENTS:
        if not relative.endswith(".md"):
            continue
        text=(ROOT/relative).read_text(encoding="utf-8")
        assert "Application Phase 07" not in text and "Stage 09" not in text
