"""Cross-stage guards retained after the Stage 04 implementation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_graphdb_and_webvowl_integrations_absent():
    markers = [
        ROOT / "src" / "kg_mnp_demo" / "graphdb.py",
        ROOT / "src" / "kg_mnp_demo" / "webvowl.py",
        ROOT / "graphdb-local",
        ROOT / "webvowl",
    ]
    for path in markers:
        assert not path.exists(), path


def test_no_review_confirmation_or_compiler_implementation():
    src = ROOT / "src" / "kg_mnp_demo"
    matches = []
    forbidden = (
        "def build_confirmed_modeling_package",
        "def auto_confirm",
        "def confirm_all",
        "def compile_owl",
        "def compile_shacl",
        "def compile_rdf",
    )
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden):
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
