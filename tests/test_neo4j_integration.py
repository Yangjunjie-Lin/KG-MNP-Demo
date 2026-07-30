"""Neo4j integration tests — skipped when Neo4j is unavailable."""

from __future__ import annotations

import pytest

from kg_mnp_demo.neo4j_client import ping

pytestmark = pytest.mark.neo4j


def _require_neo4j():
    status = ping()
    if not status.get("ok"):
        pytest.skip(f"Neo4j unavailable: {status}")


@pytest.fixture(scope="module")
def neo4j_ready():
    _require_neo4j()


def test_neo4j_ping(neo4j_ready):
    status = ping()
    assert status["ok"] is True


def test_case_03_contract_block_in_neo4j(neo4j_ready):
    from kg_mnp_demo.neo4j_pipeline import neo4j_load_case
    from kg_mnp_demo.neo4j_trace import blocking_reasons

    loaded = neo4j_load_case("CASE-03", reset=True)
    assert loaded["decision"] == "BLOCKED"
    rows = blocking_reasons("CASE-03")
    assert rows
    assert rows[0]["reasonCode"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert rows[0]["ruleId"] == "MNP-ELIG-004"
    assert rows[0]["clauseId"] == "REG-MNP-CLAUSE-04"
    assert rows[0]["actionCode"] == "WAIT_OR_TERMINATE_CONTRACT"


def test_case_04_two_blocking_chains(neo4j_ready):
    from kg_mnp_demo.neo4j_pipeline import neo4j_load_case
    from kg_mnp_demo.neo4j_trace import blocking_reasons

    neo4j_load_case("CASE-04", reset=False)
    codes = sorted(r["reasonCode"] for r in blocking_reasons("CASE-04"))
    assert codes == ["ACTIVE_CONTRACT_RESTRICTION", "OUTSTANDING_BALANCE"]


def test_case_06_affected_assessments(neo4j_ready):
    from kg_mnp_demo.neo4j_pipeline import neo4j_load_case
    from kg_mnp_demo.neo4j_trace import affected_assessments

    neo4j_load_case("CASE-06", reset=False)
    rows = affected_assessments()
    assert rows
    assert any(
        (r.get("assessmentId") or "").endswith("CASE-06-HIST")
        or r.get("oldVersion") == "1.0"
        for r in rows
    )
