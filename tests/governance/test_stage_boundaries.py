"""Stage boundary guards: Stage 02 must not implement later stages."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_STAGE_03_PLUS = (
    "schemas/modeling/modeling_proposal.schema.json",
    "schemas/modeling/review_decision_log.schema.json",
    "schemas/modeling/confirmed_modeling_package.schema.json",
    "schemas/modeling/cleaned_partial_data.schema.json",
)


def test_modeling_schemas_not_introduced():
    for relative in FORBIDDEN_STAGE_03_PLUS:
        path = ROOT / relative
        assert not path.exists(), f"Stage drift: unexpected {relative}"


def test_graphdb_and_webvowl_integrations_absent():
    markers = [
        ROOT / "src" / "kg_mnp_demo" / "graphdb.py",
        ROOT / "src" / "kg_mnp_demo" / "webvowl.py",
        ROOT / "graphdb-local",
        ROOT / "webvowl",
    ]
    for path in markers:
        assert not path.exists(), path


def test_no_generate_modeling_proposal_implementation():
    src = ROOT / "src" / "kg_mnp_demo"
    matches = []
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "def generate_modeling_proposal" in text:
            matches.append(path.relative_to(ROOT).as_posix())
        if "def build_confirmed_modeling_package" in text:
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []


def test_stage_02_report_defers_example_org_migration():
    report = (ROOT / "docs" / "migration" / "stage-02-semantic-governance.md").read_text(
        encoding="utf-8"
    )
    assert "Existing TTL migration deferred to Stage 03" in report or (
        "example.org" in report and "Stage 03" in report
    )
    assert "Domain/Range" in report
