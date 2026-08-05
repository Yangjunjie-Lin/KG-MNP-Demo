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
    text = _read("docs/architecture/semantic-authority-chain.md")
    assert "ConfirmedModelingPackage" in text
    assert "Yes" in text
    assert "ModelingProposal" in text
    assert "candidates" in text.lower() or "No" in text
    assert "formal compilation" in text.lower() or "Formal compilation" in text


def test_tools_are_not_editing_authorities():
    text = _read("docs/architecture/semantic-authority-chain.md")
    lowered = text.lower()
    assert "GraphDB" in text
    assert "WebVOWL" in text
    assert "prot" in lowered
    assert "ontology editing authority" in lowered or "forbidden role" in text
    assert "write-back" in lowered or "update authoritative inputs" in text


def test_llm_auto_confirm_forbidden():
    adr = _read("docs/adr/ADR-001-semantic-authority.md")
    chain = _read("docs/architecture/semantic-authority-chain.md")
    combined = (adr + "\n" + chain).lower()
    assert "llm" in combined
    assert "auto-confirm" in combined or "automatic confirmation" in combined
    assert "must not" in combined or "forbidden" in combined
