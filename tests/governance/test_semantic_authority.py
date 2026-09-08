"""Semantic authority documentation and policy marker tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_adr_accepted_and_lists_authority_chain():
    text = _read("docs/adr/ADR-001-semantic-authority.md")
    assert "## Status" in text
    assert "Accepted" in text
    for marker in (
        "CleanedPartialData",
        "OntologyBaseline@version",
        "MappingRules@version",
        "TerminologyProfile@version",
        "ModelingProposal",
        "ReviewDecisionLog",
        "ConfirmedModelingPackage",
    ):
        assert marker in text


def test_confirmed_package_is_authoritative_proposal_is_not():
    text = _read("docs/architecture/toolchain.md")
    assert "ConfirmedModelingPackage" in text
    assert "ModelingProposal" in text
    assert "只包含待审核候选" in text
    assert "明确人工审核闭合" in text and "正式编译" in text


def test_tools_are_not_editing_authorities():
    text = _read("docs/architecture/toolchain.md")
    lowered = text.lower()
    assert "GraphDB" in text
    assert "WebVOWL" in text
    assert "prot" in lowered
    assert "不是独立的本体编辑权威" in text
    assert "更新候选与审核输入、重新确认和编译" in text


def test_llm_auto_confirm_forbidden():
    adr = _read("docs/adr/ADR-001-semantic-authority.md")
    chain = _read("docs/architecture/toolchain.md")
    combined = (adr + "\n" + chain).lower()
    assert "llm" in combined
    assert "auto-confirm" in combined or "automatic confirmation" in combined
    assert "must not" in combined or "forbidden" in combined
