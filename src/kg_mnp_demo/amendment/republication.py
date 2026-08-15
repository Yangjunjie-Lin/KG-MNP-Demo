"""Deterministic re-entry orchestration over the frozen publication pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.compilation.compiler import build_artifact_set
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal
from kg_mnp_demo.modeling.semantic_validation import (
    validate_cleaned_partial_data_semantics,
)

from .authority_binding import ProductionPhase05Authority, require_production_authority
from .candidate_binding import bind_amendment_to_proposal
from .errors import AmendmentError, AmendmentErrorCode
from .intake import validate_intake
from .review_bridge import (
    build_and_validate_confirmed_package,
    require_explicit_review,
)


@dataclass(frozen=True, slots=True)
class ReentryResult:
    status: str
    intake: dict[str, Any]
    proposal: dict[str, Any] | None
    decision_log: dict[str, Any] | None
    confirmed_package: dict[str, Any] | None
    compilation: dict[str, Any] | None
    publication: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "intake": deepcopy(self.intake),
            "proposal": deepcopy(self.proposal),
            "decision_log": deepcopy(self.decision_log),
            "confirmed_package": deepcopy(self.confirmed_package),
            "compilation": deepcopy(self.compilation),
            "publication": deepcopy(self.publication),
        }


def _assert_request(
    request: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    base_publication_id: str,
    base_publication_hash: str,
) -> None:
    if request.get("amendment_request_id") != manifest.get(
        "approved_amendment_request_id"
    ):
        raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
    if request.get("governance_status") != "APPROVED_FOR_FUTURE_AMENDMENT":
        raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
    if request.get("status") != "APPROVED_FOR_FUTURE_MODELING_AMENDMENT":
        raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
    if (
        request.get("publication_id") != base_publication_id
        or request.get("publication_semantic_hash") != base_publication_hash
        or manifest.get("base_publication_id") != base_publication_id
        or manifest.get("base_publication_semantic_hash") != base_publication_hash
    ):
        raise AmendmentError(AmendmentErrorCode.STALE_AMENDMENT_BASE)


def prepare_reentry(
    *,
    amendment_request: Mapping[str, Any],
    intake_manifest: Mapping[str, Any],
    base_cleaned_data: Mapping[str, Any],
    revised_cleaned_data: Mapping[str, Any],
    base_publication_id: str,
    base_publication_semantic_hash: str,
    dependencies: Mapping[str, Any] | None = None,
) -> ReentryResult:
    """Validate intake and generate a normal Stage 04 ModelingProposal."""

    _assert_request(
        amendment_request,
        intake_manifest,
        base_publication_id=base_publication_id,
        base_publication_hash=base_publication_semantic_hash,
    )
    validate_intake(
        intake_manifest,
        base_cleaned_data=base_cleaned_data,
        revised_cleaned_data=revised_cleaned_data,
        approved_request=amendment_request,
        base_publication_id=base_publication_id,
        base_publication_semantic_hash=base_publication_semantic_hash,
    )
    amendment_type = str(amendment_request["amendment_type"])
    if amendment_type == "NO_CHANGE_RECOMMENDED":
        return ReentryResult(
            "NO_REENTRY_REQUIRED", dict(intake_manifest), None, None, None, None, None
        )
    if amendment_type == "PROPOSE_CONSTRAINT_REVIEW":
        raise AmendmentError(
            AmendmentErrorCode.TBOX_AMENDMENT_NOT_EXECUTABLE_IN_PHASE05
        )
    validate_cleaned_partial_data_semantics(revised_cleaned_data)
    deps = dict(dependencies or load_modeling_dependencies())
    proposal = generate_modeling_proposal(
        revised_cleaned_data,
        deps["ontology_baseline"],
        deps["mapping_rules"],
        deps["terminology_profile"],
        deps["proposal_policy"],
        term_iris=set(deps["term_iris"]),
    )
    bind_amendment_to_proposal(
        amendment_request=amendment_request,
        proposal=proposal,
        revised_cleaned_data_hash=intake_manifest["revised_cleaned_data_hash"],
        declared_changed_json_pointers=intake_manifest[
            "declared_changed_json_pointers"
        ],
        target_json_pointers=intake_manifest.get("target_json_pointers", []),
    )
    return ReentryResult(
        "REENTRY_PROPOSAL_READY",
        dict(intake_manifest),
        proposal,
        None,
        None,
        None,
        None,
    )


def prepare_production_reentry(
    *,
    authority: ProductionPhase05Authority,
    amendment_request_id: str,
    intake_manifest: Mapping[str, Any],
    base_cleaned_data: Mapping[str, Any],
    revised_cleaned_data: Mapping[str, Any],
    base_publication_id: str,
    base_publication_semantic_hash: str,
    dependencies: Mapping[str, Any] | None = None,
) -> ReentryResult:
    """Production-only entry point; request is extracted from exact authority."""

    verified = require_production_authority(authority)
    request = verified.require_request(amendment_request_id)
    return prepare_reentry(
        amendment_request=request,
        intake_manifest=intake_manifest,
        base_cleaned_data=base_cleaned_data,
        revised_cleaned_data=revised_cleaned_data,
        base_publication_id=base_publication_id,
        base_publication_semantic_hash=base_publication_semantic_hash,
        dependencies=dependencies,
    )


def complete_reentry(
    prepared: ReentryResult,
    *,
    decision_log: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    revised_cleaned_data: Mapping[str, Any],
    publication_builder: Callable[..., Mapping[str, Any]] | None = None,
    diagnostic_runner: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    base_publication_bytes: bytes | None = None,
    base_publication_bytes_after: bytes | None = None,
    base_repository_hash_before: str | None = None,
    base_repository_hash_after: str | None = None,
) -> ReentryResult:
    if prepared.status != "REENTRY_PROPOSAL_READY" or prepared.proposal is None:
        raise AmendmentError(
            AmendmentErrorCode.INVALID_REQUEST, "proposal is not ready for completion"
        )
    require_explicit_review(decision_log)
    candidate_decisions = [
        item
        for item in decision_log.get("decisions", [])
        if isinstance(item, Mapping) and "candidate_id" in item
    ]
    if any(item.get("decision") in {"REJECT", "DEFER"} for item in candidate_decisions):
        outcome = (
            "REVIEW_REJECTED"
            if any(item.get("decision") == "REJECT" for item in candidate_decisions)
            else "REVIEW_DEFERRED"
        )
        return ReentryResult(
            outcome,
            prepared.intake,
            prepared.proposal,
            dict(decision_log),
            None,
            None,
            None,
        )
    deps = dict(dependencies)
    package = build_and_validate_confirmed_package(
        cleaned_partial_data=revised_cleaned_data,
        proposal=prepared.proposal,
        decision_log=decision_log,
        ontology_baseline=deps["ontology_baseline"],
        mapping_rules=deps["mapping_rules"],
        terminology_profile=deps["terminology_profile"],
        proposal_policy=deps["proposal_policy"],
        review_policy=deps["review_policy"],
        term_types=deps.get("term_types"),
    )
    if (
        base_publication_bytes is not None
        and base_publication_bytes_after is not None
        and base_publication_bytes != base_publication_bytes_after
    ):
        raise AmendmentError(AmendmentErrorCode.PUBLICATION_IMMUTABILITY_VIOLATION)
    if (
        base_repository_hash_before is not None
        and base_repository_hash_after is not None
        and base_repository_hash_before != base_repository_hash_after
    ):
        raise AmendmentError(AmendmentErrorCode.GRAPHDB_INPLACE_MUTATION_BLOCKED)
    artifacts, compilation_manifest = build_artifact_set(
        revised_cleaned_data,
        prepared.proposal,
        decision_log,
        package,
        deps["ontology_baseline"],
        deps["mapping_rules"],
        deps["terminology_profile"],
        deps["proposal_policy"],
        deps["review_policy"],
        deps.get("compiler_policy"),
    )
    publication = None
    if publication_builder is not None:
        publication = dict(
            publication_builder(
                cleaned_partial_data=revised_cleaned_data,
                proposal=prepared.proposal,
                review_decision_log=decision_log,
                confirmed_modeling_package=package,
                compilation_manifest=compilation_manifest,
                compilation_artifacts=artifacts,
                base_publication_id=prepared.intake["base_publication_id"],
            )
        )
        if publication.get("publication_id") == prepared.intake["base_publication_id"]:
            raise AmendmentError(AmendmentErrorCode.PUBLICATION_IMMUTABILITY_VIOLATION)
        if diagnostic_runner is None:
            raise AmendmentError(
                AmendmentErrorCode.PHASE05_NOT_VERIFIED,
                "new publication must be independently reconstructed by Phase03",
            )
        publication["phase03_diagnostics"] = dict(diagnostic_runner(publication))
    elif publication_builder is None:
        raise AmendmentError(
            AmendmentErrorCode.PHASE05_NOT_VERIFIED,
            "controlled re-entry requires a new publication builder",
        )
    return ReentryResult(
        "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
        prepared.intake,
        prepared.proposal,
        dict(decision_log),
        package,
        compilation_manifest,
        publication,
    )


def new_repository_identity(publication_semantic_hash: str) -> str:
    if not isinstance(publication_semantic_hash, str):
        raise AmendmentError(AmendmentErrorCode.INVALID_REQUEST)
    return f"urn:kg-mnp:graphdb-repository:{publication_semantic_hash}"


def assert_abox_only_invariants(
    *,
    old_tbox_hash: str,
    new_tbox_hash: str,
    old_shacl_hash: str,
    new_shacl_hash: str,
    old_abox_hash: str,
    new_abox_hash: str,
    old_publication_hash: str,
    new_publication_hash: str,
    old_webvowl_hash: str,
    new_webvowl_hash: str,
) -> None:
    if old_tbox_hash != new_tbox_hash or old_shacl_hash != new_shacl_hash:
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
            "ABox amendment changed TBox/SHACL",
        )
    if old_abox_hash == new_abox_hash or old_publication_hash == new_publication_hash:
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
            "ABox/publication hash did not change",
        )
    if old_webvowl_hash != new_webvowl_hash:
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
            "ABox-only amendment changed WebVOWL",
        )


def evaluate_target_diagnostic_resolution(
    *,
    target_diagnostic_id: str,
    before_phase03: Mapping[str, Any],
    after_phase03: Mapping[str, Any],
) -> str:
    """Classify a target only from independent before/after Phase03 output."""

    before = next(
        (
            issue
            for issue in before_phase03.get("issues", [])
            if issue.get("diagnostic_id") == target_diagnostic_id
        ),
        None,
    )
    after = next(
        (
            issue
            for issue in after_phase03.get("issues", [])
            if issue.get("diagnostic_id") == target_diagnostic_id
        ),
        None,
    )
    if before is not None and after is None:
        return "RESOLVED"
    if before is not None and after is not None:
        if before.get("classification") == after.get("classification"):
            return "STILL_PRESENT"
        return "RECLASSIFIED"
    if after is None:
        return "RESOLVED"
    return "RECLASSIFIED"
