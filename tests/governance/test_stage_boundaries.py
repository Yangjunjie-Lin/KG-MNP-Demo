"""Cross-stage guards retained after Stage 05 human review."""

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


def test_no_auto_confirmation_or_compiler_implementation():
    """Stage 05 may build confirmed packages; auto-confirm and compilers remain forbidden."""

    src = ROOT / "src" / "kg_mnp_demo"
    matches = []
    forbidden = (
        "def auto_confirm",
        "def confirm_all",
        "def compile_owl",
        "def compile_shacl",
        "def compile_rdf",
        "def build_trig",
        "def graphdb_import",
        "def webvowl_export",
        "def llm_reviewer",
    )
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []
    assert (src / "modeling" / "confirmation.py").is_file()


def test_stage_02_report_defers_example_org_migration():
    report = (ROOT / "docs" / "migration" / "stage-02-semantic-governance.md").read_text(
        encoding="utf-8"
    )
    assert "Existing TTL migration deferred to Stage 03" in report or (
        "example.org" in report and "Stage 03" in report
    )
    assert "Domain/Range" in report
