from __future__ import annotations

import time

import pytest

from kg_mnp.semantic_kernel.security import assert_read_only_query
from kg_mnp.semantic_kernel.validators import competency_questions as cq_validator


def _sleeping_query_worker(*_args) -> None:
    time.sleep(30)


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE SILENT {}",
        "DELETE WHERE { ?s ?p ?o }",
        "LOAD <https://example.test/data>",
        "SELECT * WHERE { SERVICE <https://example.test/sparql> { ?s ?p ?o } }",
        "SELECT * FROM NAMED <https://example.test/graph> WHERE { GRAPH ?g { ?s ?p ?o } }",
    ],
)
def test_mutating_networked_and_remote_dataset_queries_are_rejected(query: str) -> None:
    with pytest.raises(ValueError):
        assert_read_only_query(query)


def test_query_character_and_property_path_limits_are_finite() -> None:
    with pytest.raises(ValueError, match="character"):
        assert_read_only_query("SELECT * WHERE { ?s ?p ?o }", max_characters=5)
    with pytest.raises(ValueError, match="complexity"):
        assert_read_only_query("SELECT * WHERE { ?s <urn:a>/<urn:b>/<urn:c> ?o }", max_path_depth=1)


def test_query_timeout_terminates_child_process(monkeypatch) -> None:
    monkeypatch.setattr(cq_validator, "_query_worker", _sleeping_query_worker)
    started = time.monotonic()
    status, value = cq_validator._execute(
        b"",
        "ASK {}",
        "ASK",
        timeout=1,
        max_results=10,
    )
    assert time.monotonic() - started < 10
    assert status == "TIMEOUT"
    assert value is None
