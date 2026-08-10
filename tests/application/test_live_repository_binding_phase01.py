from __future__ import annotations

from copy import copy

import pytest
from rdflib import URIRef

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.http import create_app
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.service import ApplicationService

from ._phase01_helpers import DatasetClient, synthetic_binding


def _service(client: DatasetClient) -> ApplicationService:
    return ApplicationService(
        binding=synthetic_binding(),
        registry=QueryRegistry.load(),
        client=client,
    )


def _assert_not_ready(service: ApplicationService) -> None:
    with pytest.raises(ApplicationError) as caught:
        service.runtime_check()
    assert caught.value.code == ErrorCode.APPLICATION_NOT_READY


def _tampered_binding(**changes):
    binding = copy(synthetic_binding())
    for name, value in changes.items():
        object.__setattr__(binding, name, value)
    return binding


def test_runtime_check_binds_the_live_explicit_dataset_semantic_hash():
    service = _service(DatasetClient())

    readiness = service.runtime_check()

    assert readiness["status"] == "APPLICATION_READY"
    assert readiness["repository_semantic_identity_verified"] is True
    assert (
        readiness["expected_graphdb_semantic_hash"]
        == readiness["live_graphdb_semantic_hash"]
        == service.binding.graphdb_semantic_hash
    )
    assert readiness["publication_authority_reconstruction"]["status"] == "PASS"


def test_runtime_check_requires_health_and_an_exact_reported_repository_id():
    class UnhealthyClient(DatasetClient):
        def health(self):
            return {"healthy": False, "repository_count": 0}

    class MissingRepositoryIdentityClient(DatasetClient):
        def repository_info(self, repository_id):
            return {"params": {"ruleset": {"value": "empty"}}}

    _assert_not_ready(_service(UnhealthyClient()))
    _assert_not_ready(_service(MissingRepositoryIdentityClient()))


def test_runtime_check_requires_verified_attestation_and_authority_reconstruction():
    registry = QueryRegistry.load()
    client = DatasetClient()
    unverified = _tampered_binding(attestation={"status": "FAILED"})
    invalid_scenario = _tampered_binding(
        publication_scenario="attacker-controlled"
    )

    _assert_not_ready(
        ApplicationService(binding=unverified, registry=registry, client=client)
    )
    _assert_not_ready(
        ApplicationService(
            binding=invalid_scenario,
            registry=registry,
            client=DatasetClient(),
        )
    )


def test_runtime_check_rejects_one_added_explicit_triple_with_same_repository_id():
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


def test_runtime_check_rejects_one_deleted_explicit_triple_with_same_repository_id():
    client = DatasetClient()
    quad = next(iter(client.dataset.quads((None, None, None, None))))
    before = len(list(client.dataset.quads((None, None, None, None))))
    client.dataset.remove(quad)
    assert len(list(client.dataset.quads((None, None, None, None)))) == before - 1

    _assert_not_ready(_service(client))


def test_runtime_check_rejects_equal_count_replacement_and_startup_fails_closed():
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
    with pytest.raises(ApplicationError) as caught:
        create_app(service)
    assert caught.value.code == ErrorCode.APPLICATION_NOT_READY
