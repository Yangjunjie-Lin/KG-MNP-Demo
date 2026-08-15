from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from kg_mnp_demo.amendment.artifact_verifier import (
    Phase05ArtifactVerificationError,
    verify_application_phase05_artifact,
)
from kg_mnp_demo.amendment.authority_binding import (
    PRODUCTION_AUTHORITY_TYPE,
    ProductionPhase05Authority,
    load_production_phase05_authority,
    require_production_authority,
)
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.fixture import ControlledAmendmentFixture


def test_artifact_verifier_requires_exact_upstream_paths(tmp_path: Path) -> None:
    with pytest.raises(Phase05ArtifactVerificationError):
        verify_application_phase05_artifact(tmp_path)


def test_production_loader_has_no_caller_injected_request_or_workspace() -> None:
    parameters = set(inspect.signature(load_production_phase05_authority).parameters)
    assert (
        not {
            "approved_amendment_request",
            "phase04_workspace",
            "governance_authority",
            "authority",
        }
        & parameters
    )


def test_controlled_fixture_is_not_a_production_authority() -> None:
    with pytest.raises(AmendmentError) as error:
        ControlledAmendmentFixture.create().as_production_authority()
    assert (
        error.value.code
        == AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
    )


def test_forged_production_authority_without_exact_source_is_rejected() -> None:
    forged = object.__new__(ProductionPhase05Authority)
    object.__setattr__(forged, "authority_type", PRODUCTION_AUTHORITY_TYPE)
    object.__setattr__(forged, "_production_source", None)
    with pytest.raises(AmendmentError) as error:
        require_production_authority(forged)
    assert error.value.code == AmendmentErrorCode.AUTHORITY_MISMATCH
