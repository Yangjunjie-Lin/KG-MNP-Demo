from __future__ import annotations

import copy

import pytest

from kg_mnp.modeling.control_plane.artifacts import finalize_document
from kg_mnp.modeling.control_plane.errors import StaleModelingArtifactError
from kg_mnp.modeling.control_plane.input_bundle import verify_input_bundle
from kg_mnp.modeling.control_plane.limits import ModelingLimits
from kg_mnp.modeling.control_plane.run import (
    advance_modeling_run,
    build_modeling_run,
    verify_modeling_run,
)


def test_modeling_run_binds_finite_limits_and_advances_without_changing_id() -> None:
    run = build_modeling_run(
        project_lock_id="urn:kg-mnp:project-lock:" + "1" * 64,
        modeling_input_bundle_id="urn:kg-mnp:modeling-input-bundle:" + "2" * 64,
        limits=ModelingLimits(max_total_candidates=32),
    )
    proposed = advance_modeling_run(
        run,
        status="PROPOSED",
        proposal_id="urn:kg-mnp:ontology-modeling-proposal:" + "3" * 64,
    )
    assert proposed["modeling_run_id"] == run["modeling_run_id"]
    assert proposed["limits"]["max_total_candidates"] == 32
    assert proposed["content_digest"] != run["content_digest"]
    verify_modeling_run(proposed)


def test_modeling_run_tamper_and_incomplete_ready_state_fail_closed() -> None:
    run = build_modeling_run(
        project_lock_id="urn:kg-mnp:project-lock:" + "1" * 64,
        modeling_input_bundle_id="urn:kg-mnp:modeling-input-bundle:" + "2" * 64,
    )
    tampered = copy.deepcopy(run)
    tampered["limits"]["max_terms"] += 1
    with pytest.raises(StaleModelingArtifactError):
        verify_modeling_run(tampered)
    with pytest.raises(StaleModelingArtifactError, match="proposal"):
        advance_modeling_run(run, status="READY_FOR_COMPILATION")


def test_prompt03_catalog_binding_is_stale_after_prompt04_migration(
    prompt04_case: dict,
) -> None:
    stale = copy.deepcopy(prompt04_case["input_bundle"])
    stale["contract_catalog_digest"] = (
        "984c2031a36e6332c0c0a5724dc0dabbeb1f6f07f8389c3bda02e6744dccb5ed"
    )
    stale = finalize_document(
        stale,
        id_field="modeling_input_bundle_id",
        urn_kind="modeling-input-bundle",
    )
    with pytest.raises(ValueError, match="stale"):
        verify_input_bundle(stale)
