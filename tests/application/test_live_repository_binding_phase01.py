from __future__ import annotations

from copy import copy

import pytest
from rdflib import URIRef

from kg_mnp.application.errors import ApplicationError, ErrorCode
from kg_mnp.application.query_reader import HistoricalQueryReader
from kg_mnp.application.query_registry import QueryRegistry

from ._phase01_helpers import DatasetClient, synthetic_binding


def _service(client: DatasetClient, *, binding=None) -> HistoricalQueryReader:
    binding = binding or synthetic_binding()
    return HistoricalQueryReader(
        binding=binding,
        registry=QueryRegistry.load(),
        dataset=client.export_explicit_nquads(binding.repository_id),
    )


def _assert_not_ready(service: HistoricalQueryReader) -> None:
    with pytest.raises(ApplicationError) as caught:
        service.verify_input()
    assert caught.value.code == ErrorCode.APPLICATION_NOT_READY


def _tampered_binding(**changes):
    binding = copy(synthetic_binding())
    for name, value in changes.items():
        object.__setattr__(binding, name, value)
    return binding


def test_reader_binds_the_captured_explicit_dataset_semantic_hash():
    service = _service(DatasetClient())

    readiness = service.verify_input()

    assert readiness["status"] == "HISTORICAL_DATASET_VERIFIED"
    assert readiness["external_deployment_observed"] is False
    assert readiness["repository_semantic_identity_verified"] is True
    assert (
        readiness["expected_graphdb_semantic_hash"]
        == readiness["dataset_semantic_hash"]
        == service.binding.graphdb_semantic_hash
    )
    assert readiness["publication_authority_reconstruction"]["status"] == "PASS"


def test_reader_has_no_live_client_or_readiness_claim():
    with pytest.raises(TypeError):
        HistoricalQueryReader(binding=synthetic_binding(), registry=QueryRegistry.load(), client=DatasetClient())
    with pytest.raises(ApplicationError) as failure:
        HistoricalQueryReader(binding=synthetic_binding(), registry=QueryRegistry.load(), dataset={"healthy": True})
    assert failure.value.code == ErrorCode.INVALID_PARAMETER


def test_reader_requires_verified_attestation_and_authority_reconstruction():
    client = DatasetClient()
    unverified = _tampered_binding(attestation={"status": "FAILED"})
    invalid_scenario = _tampered_binding(
        publication_scenario="attacker-controlled"
    )

    _assert_not_ready(
        _service(client, binding=unverified)
    )
    _assert_not_ready(
        _service(
            DatasetClient(),
            binding=invalid_scenario,
        )
    )


def test_reader_rejects_one_added_explicit_triple_with_same_repository_id():
    client = DatasetClient()
    _, _, _, graph = next(iter(client.dataset.quads((None, None, None, None))))
    client.dataset.add(
        (
            URIRef("urn:kg-mnp:attack:added-subject"),
            URIRef("urn:kg-mnp:attack:predicate"),
            URIRef("urn:kg-mnp:attack:object"),
            graph,
        )
    )

    _assert_not_ready(_service(client))


def test_reader_rejects_one_deleted_explicit_triple_with_same_repository_id():
    client = DatasetClient()
    quad = next(iter(client.dataset.quads((None, None, None, None))))
    before = len(list(client.dataset.quads((None, None, None, None))))
    client.dataset.remove(quad)
    assert len(list(client.dataset.quads((None, None, None, None)))) == before - 1

    _assert_not_ready(_service(client))


def test_reader_rejects_equal_count_replacement():
    client = DatasetClient()
    quad = next(iter(client.dataset.quads((None, None, None, None))))
    graph = quad[3]
    before = len(list(client.dataset.quads((None, None, None, None))))
    client.dataset.remove(quad)
    client.dataset.add(
        (
            URIRef("urn:kg-mnp:attack:replacement-subject"),
            URIRef("urn:kg-mnp:attack:predicate"),
            URIRef("urn:kg-mnp:attack:replacement-object"),
            graph,
        )
    )
    assert len(list(client.dataset.quads((None, None, None, None)))) == before
    service = _service(client)

    _assert_not_ready(service)


@pytest.mark.parametrize("status", ["TIMEOUT", "ERROR"])
def test_failed_local_query_is_never_an_empty_success(monkeypatch, status):
    monkeypatch.setattr("kg_mnp.application.query_reader._execute", lambda *args: (status, None))
    reader = HistoricalQueryReader(binding=None, registry=None, dataset=b"captured test bytes")
    with pytest.raises(ApplicationError, match="historical query execution " + status):
        reader._select("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1", timeout=1)
