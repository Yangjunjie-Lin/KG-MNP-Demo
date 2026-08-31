from __future__ import annotations

import copy

import pytest

from kg_mnp.modeling.control_plane.artifacts import finalize_document
from kg_mnp.modeling.control_plane.errors import (
    ScopeInvalidError,
    ScopeNotApprovedError,
)
from kg_mnp.modeling.control_plane.scope import build_scope
from kg_mnp.modeling.control_plane.scope_approval import (
    approve_scope,
    verify_scope_approval,
)


def test_scope_and_approval_are_deterministic(prompt04_case: dict) -> None:
    scope = prompt04_case["scope"]
    rebuilt = build_scope(
        project_id="prompt04-test-project",
        project_lock_id=scope["project_lock_id"],
        domain_pack_lock_ids=scope["domain_pack_locks"],
        kg_ir_dataset_ids=scope["kg_ir_dataset_ids"],
        modeling_intent="MIXED_MODELING",
        domain_description="Minimal non-production ontology modeling test.",
        target_object_families=["Entity"],
        in_scope=["entity labels"],
        out_of_scope=["publication"],
        target_artifacts=["TBOX", "MAPPING", "ABOX", "SHACL", "TERMINOLOGY"],
        default_namespace="urn:kg-mnp:project:prompt04-test-project:",
    )
    assert rebuilt == scope
    assert approve_scope(
        scope,
        reviewer_id="reviewer-1",
        reviewer_role="Development Reviewer",
        rationale="bounded test scope approved by a human fixture",
        decided_at="2026-01-01T00:00:00Z",
    )["approval_id"] == prompt04_case["approval"]["approval_id"]


def test_scope_mutation_makes_approval_stale(prompt04_case: dict) -> None:
    mutated = copy.deepcopy(prompt04_case["scope"])
    mutated["domain_description"] = "Changed scope"
    mutated = finalize_document(mutated, id_field="scope_id", urn_kind="ontology-scope")
    with pytest.raises(ScopeNotApprovedError, match="STALE"):
        verify_scope_approval(mutated, prompt04_case["approval"])


def test_provider_cannot_approve_and_reserved_namespace_cannot_be_minted(
    prompt04_case: dict,
) -> None:
    with pytest.raises(ScopeInvalidError, match="provider"):
        approve_scope(
            prompt04_case["scope"],
            reviewer_id="provider",
            reviewer_role="modeling-provider",
            rationale="forbidden",
        )
    with pytest.raises(ScopeInvalidError, match="reserved"):
        build_scope(
            project_id="test",
            project_lock_id=prompt04_case["project_lock"]["lock_id"],
            domain_pack_lock_ids=prompt04_case["scope"]["domain_pack_locks"],
            kg_ir_dataset_ids=[prompt04_case["dataset"]["dataset_id"]],
            modeling_intent="MIXED_MODELING",
            domain_description="test",
            target_object_families=["Entity"],
            in_scope=["x"],
            out_of_scope=["y"],
            target_artifacts=["TBOX"],
            default_namespace="http://www.w3.org/2002/07/owl#",
        )
