from __future__ import annotations

import pytest

from kg_mnp_demo.amendment.authority_binding import require_production_authority
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.fixture import ControlledAmendmentFixture
from kg_mnp_demo.amendment.intake import ReplayGuard
from kg_mnp_demo.amendment.republication import prepare_reentry
from kg_mnp_demo.amendment.validator import (
    validate_new_repository_identity,
    validate_no_direct_mutation,
)


def test_stale_base_is_rejected_before_modeling() -> None:
    fixture = ControlledAmendmentFixture.create()
    request = fixture.approved_amendment_request
    manifest = {
        "approved_amendment_request_id": request["amendment_request_id"],
        "base_publication_id": request["publication_id"],
        "base_publication_semantic_hash": request["publication_semantic_hash"],
    }
    with pytest.raises(AmendmentError) as error:
        prepare_reentry(
            amendment_request=request,
            intake_manifest=manifest,
            base_cleaned_data=fixture.base_cleaned_data,
            revised_cleaned_data=fixture.revised_cleaned_data,
            base_publication_id="urn:kg-mnp:test-fixture:phase05:publication:stale",
            base_publication_semantic_hash="f" * 64,
        )
    assert error.value.code == AmendmentErrorCode.STALE_AMENDMENT_BASE


def test_replay_is_detected_deterministically() -> None:
    guard = ReplayGuard()
    manifest = {
        "approved_amendment_request_id": "urn:request",
        "base_publication_id": "urn:p0",
        "base_publication_semantic_hash": "a" * 64,
        "revised_cleaned_data_hash": "b" * 64,
    }
    guard.check(manifest, "urn:p1")
    with pytest.raises(AmendmentError) as error:
        guard.check(manifest, "urn:p1")
    assert error.value.code == AmendmentErrorCode.REPLAY_DETECTED


def test_fixture_laundering_is_rejected() -> None:
    with pytest.raises(AmendmentError) as error:
        require_production_authority(ControlledAmendmentFixture.create())
    assert (
        error.value.code
        == AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
    )


def test_direct_mutation_and_inplace_repository_are_blocked() -> None:
    with pytest.raises(AmendmentError) as error:
        validate_no_direct_mutation("graph store patch")
    assert error.value.code == AmendmentErrorCode.DIRECT_RDF_MUTATION_BLOCKED
    with pytest.raises(AmendmentError) as error:
        validate_new_repository_identity(
            old_repository_id="urn:repo:same",
            new_repository_id="urn:repo:same",
            new_publication_hash="a" * 64,
        )
    assert error.value.code == AmendmentErrorCode.GRAPHDB_INPLACE_MUTATION_BLOCKED
