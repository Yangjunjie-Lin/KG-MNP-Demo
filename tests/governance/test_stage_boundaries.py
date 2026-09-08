"""Cross-stage guards retained after Stage 05 human review."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_graphdb_and_webvowl_integrations_absent():
    markers = [
        ROOT / "src" / "kg_mnp" / "graphdb.py",
        ROOT / "src" / "kg_mnp" / "webvowl.py",
        ROOT / "graphdb-local",
        ROOT / "webvowl",
    ]
    for path in markers:
        assert not path.exists(), path


def test_no_auto_confirmation_or_compiler_implementation():
    """Auto-confirm remains forbidden; Prompt 5 compilers stay in their authority boundary."""

    src = ROOT / "src" / "kg_mnp"
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
    compiler_markers = {"def compile_owl", "def compile_shacl", "def compile_rdf"}
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        for marker in forbidden:
            if marker not in text:
                continue
            if marker in compiler_markers and relative.startswith(
                "src/kg_mnp/semantic_kernel/"
            ):
                continue
            matches.append(f"{relative}: {marker}")
    assert matches == []
    assert (src / "modeling" / "control_plane" / "confirmation.py").is_file()


def test_current_architecture_keeps_open_and_closed_world_semantics_distinct():
    report = (ROOT / "docs" / "architecture" / "toolchain.md").read_text(
        encoding="utf-8"
    )
    assert "Domain/Range" in report
    assert "不是数据库列类型检查" in report
    assert "SHACL violation 不等于 OWL inconsistency" in report
