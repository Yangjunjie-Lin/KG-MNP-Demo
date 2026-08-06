"""Deterministic ConfirmedModelingPackage builder for Stage 05."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping

from .canonical_json import semantic_hash
from .package_validation import (
    assertion_object_candidate_id,
    assertion_subject_id,
    build_confirmed_envelope,
    load_functional_property_iris,
    load_term_type_index,
    proposal_candidates_by_id,
)
from .review_identifiers import confirmed_package_id, package_semantic_hash
from .review_log import (
    decision_target_id,
    is_log_completed,
    review_coverage,
)
from .review_policy import load_default_review_policy, review_policy_hash
from .semantic_validation import (
    SemanticValidationError,
    validate_cleaned_partial_data_semantics,
    validate_confirmed_modeling_package_semantics,
    validate_modeling_proposal_semantics,
    validate_review_decision_log_semantics,
)


class PackageBuildError(SemanticValidationError):
    """Confirmed package construction failed closed."""


def _raise_build(errors: list[str]) -> None:
    if errors:
        raise PackageBuildError(errors)


def _effective_candidate(
    envelope: Mapping[str, Any],
    source_candidates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    confirmed = envelope["confirmed_candidate"]
    mode = confirmed["confirmation_mode"]
    source_id = confirmed["source_candidate_id"]
    if mode == "ORIGINAL":
        return dict(source_candidates[source_id])
    content = deepcopy(confirmed["semantic_content"])
    content["candidate_id"] = confirmed["effective_candidate_id"]
    return content


def build_confirmed_modeling_package(
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any] | None = None,
    *,
    allow_blocked: bool = False,
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the unique ConfirmedModelingPackage from a final review log."""

    del terminology_profile, proposal_policy  # binding checked via proposal snapshot
    policy = review_policy if review_policy is not None else load_default_review_policy()
    types = dict(term_types) if term_types is not None else load_term_type_index()
    functional = load_functional_property_iris()

    validate_cleaned_partial_data_semantics(cleaned_partial_data)
    validate_modeling_proposal_semantics(
        proposal,
        cleaned_partial_data,
        mapping_rules,
    )
    snapshot = proposal.get("dependency_snapshot", {})
    if snapshot.get("ontology_baseline_id") != ontology_baseline.get("baseline_id"):
        raise PackageBuildError(["proposal ontology baseline id mismatch"])
    if snapshot.get("ontology_version") != ontology_baseline.get("ontology_version"):
        raise PackageBuildError(["proposal ontology version mismatch"])
    if snapshot.get("ontology_release_source_hash") != ontology_baseline.get(
        "release_source_hash"
    ):
        raise PackageBuildError(["proposal ontology release hash mismatch"])
    if snapshot.get("mapping_rules_hash") != semantic_hash(mapping_rules):
        raise PackageBuildError(["proposal mapping rules hash mismatch"])

    validate_review_decision_log_semantics(
        decision_log,
        proposal,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        review_policy=policy,
        require_final=True,
        term_types=types,
    )
    if not is_log_completed(decision_log):
        raise PackageBuildError(["ReviewDecisionLog must be finalized before package build"])
    coverage = review_coverage(proposal, decision_log)
    if not coverage["coverage_complete"]:
        raise PackageBuildError(["review coverage is incomplete"])

    candidates = proposal_candidates_by_id(proposal)
    issues = {item["issue_id"]: item for item in proposal.get("issues", [])}
    decisions = {
        decision_target_id(item): item for item in decision_log.get("decisions", [])
    }

    confirmed_abox: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    deferred_items: list[dict[str, Any]] = []
    confirmed_envelopes: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for target, decision in sorted(decisions.items()):
        value = decision.get("decision")
        if target in candidates:
            if value in {"CONFIRM", "MODIFY_AND_CONFIRM"}:
                try:
                    envelope = build_confirmed_envelope(
                        decision=decision,
                        source_candidate=candidates[target],
                        term_types=types,
                    )
                except SemanticValidationError as exc:
                    errors.extend(exc.errors)
                    continue
                confirmed_abox.append(envelope)
                confirmed_envelopes[target] = envelope
            elif value == "REJECT":
                rejected_items.append(
                    {
                        "decision_id": decision["decision_id"],
                        "candidate_id": target,
                        "decision": "REJECT",
                    }
                )
            elif value == "DEFER":
                deferred_items.append(
                    {
                        "decision_id": decision["decision_id"],
                        "candidate_id": target,
                        "decision": "DEFER",
                    }
                )
            else:
                errors.append(f"unsupported candidate decision: {value}")
        elif target in issues:
            if value == "REJECT":
                issue = issues[target]
                if not decision.get("rationale"):
                    errors.append(f"REJECT issue requires rationale: {target}")
                if issue.get("blocking"):
                    has_evidence = bool(decision.get("evidence_refs"))
                    related = set(issue.get("related_candidate_ids") or [])
                    related_resolution = any(
                        decisions.get(candidate_id, {}).get("decision")
                        in {"MODIFY_AND_CONFIRM", "REJECT"}
                        for candidate_id in related
                    )
                    # Conflict issues often lack related_candidate_ids; allow
                    # explicit evidence_refs or any MODIFY/REJECT in the same log
                    # when evidence is present.
                    if not has_evidence and not related_resolution:
                        if not has_evidence:
                            errors.append(
                                "blocking issue REJECT requires evidence_refs or "
                                f"related candidate MODIFY_AND_CONFIRM/REJECT: {target}"
                            )
                rejected_items.append(
                    {
                        "decision_id": decision["decision_id"],
                        "issue_id": target,
                        "decision": "REJECT",
                    }
                )
            elif value == "DEFER":
                deferred_items.append(
                    {
                        "decision_id": decision["decision_id"],
                        "issue_id": target,
                        "decision": "DEFER",
                    }
                )
            else:
                errors.append(f"unsupported issue decision: {value}")
        else:
            errors.append(f"decision targets unknown proposal item: {target}")

    _raise_build(errors)

    # Reference closure over confirmed assertions.
    confirmed_source_ids = set(confirmed_envelopes)
    # Map effective entity IDs as well for modified subjects/objects.
    confirmed_effective_ids = {
        envelope["confirmed_candidate"]["effective_candidate_id"]
        for envelope in confirmed_envelopes.values()
    }
    deferred_candidate_ids = {
        item["candidate_id"]
        for item in deferred_items
        if "candidate_id" in item
    }
    rejected_candidate_ids = {
        item["candidate_id"]
        for item in rejected_items
        if "candidate_id" in item
    }
    unconfirmed_dependencies: list[str] = []
    for source_id, envelope in confirmed_envelopes.items():
        effective = _effective_candidate(envelope, candidates)
        kind = effective.get("candidate_kind", "ENTITY")
        if kind == "ENTITY":
            continue
        subject = assertion_subject_id(effective)
        if subject is not None:
            subject_ok = (
                subject in confirmed_source_ids or subject in confirmed_effective_ids
            )
            if not subject_ok:
                unconfirmed_dependencies.append(subject)
                if subject in rejected_candidate_ids or subject in deferred_candidate_ids:
                    errors.append(
                        f"confirmed assertion {source_id} depends on non-confirmed subject {subject}"
                    )
                else:
                    errors.append(
                        f"confirmed assertion {source_id} references unknown/unconfirmed subject {subject}"
                    )
        if kind == "OBJECT_PROPERTY_ASSERTION":
            obj = assertion_object_candidate_id(effective)
            if obj is not None:
                object_ok = obj in confirmed_source_ids or obj in confirmed_effective_ids
                if not object_ok:
                    unconfirmed_dependencies.append(obj)
                    if obj in rejected_candidate_ids or obj in deferred_candidate_ids:
                        errors.append(
                            f"confirmed assertion {source_id} depends on non-confirmed object {obj}"
                        )
                    else:
                        errors.append(
                            f"confirmed assertion {source_id} references unknown/unconfirmed object {obj}"
                        )
    _raise_build(errors)

    # Duplicate / functional conflicts among confirmed content.
    item_ids = [
        item["confirmed_candidate"]["confirmed_item_id"] for item in confirmed_abox
    ]
    if len(item_ids) != len(set(item_ids)):
        errors.append("duplicate confirmed_item_id values in package")
    proposed_iris: list[str] = []
    triple_keys: list[str] = []
    data_values: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for envelope in confirmed_abox:
        effective = _effective_candidate(envelope, candidates)
        if effective.get("candidate_kind", "ENTITY") == "ENTITY":
            iri = effective.get("proposed_iri")
            if isinstance(iri, str):
                proposed_iris.append(iri)
            continue
        subject = assertion_subject_id(effective) or ""
        predicate = str(effective.get("predicate_iri") or effective.get("class_iri") or "")
        obj = effective.get("object")
        if isinstance(obj, Mapping):
            object_key = semantic_hash(obj)
        else:
            object_key = str(obj)
        triple_keys.append(f"{subject}|{predicate}|{object_key}")
        if effective.get("candidate_kind") == "DATA_PROPERTY_ASSERTION":
            data_values[(subject, predicate)].append(object_key)
    if len(proposed_iris) != len(set(proposed_iris)):
        errors.append("duplicate confirmed entity proposed_iri values")
    if len(triple_keys) != len(set(triple_keys)):
        errors.append("duplicate confirmed assertion triples")
    for (subject, predicate), values in sorted(data_values.items()):
        if predicate in functional and len(set(values)) > 1:
            errors.append(
                f"FunctionalProperty conflict for {predicate} on subject {subject}"
            )
    _raise_build(errors)

    deferred_issue_details = []
    for item in deferred_items:
        issue_id = item.get("issue_id")
        if not issue_id:
            continue
        issue = issues[issue_id]
        deferred_issue_details.append(
            {
                "issue_id": issue_id,
                "decision_id": item["decision_id"],
                "blocking": bool(issue.get("blocking")),
                "issue_type": issue.get("issue_type"),
                "description": issue.get("description"),
            }
        )
    unresolved_blocking = sorted(
        detail["issue_id"]
        for detail in deferred_issue_details
        if detail.get("blocking")
    )
    blocked = bool(unresolved_blocking) or bool(unconfirmed_dependencies)
    # Dependency on deferred candidates already failed above; blocked also covers
    # deferred blocking issues.
    package_status = "BLOCKED" if blocked else "READY_FOR_COMPILATION"
    compile_allowed = package_status == "READY_FOR_COMPILATION"
    if package_status == "BLOCKED" and not allow_blocked:
        raise PackageBuildError(
            [
                "package is BLOCKED; pass allow_blocked=True / --allow-blocked to emit "
                "an audit-only blocked package",
                *(
                    [f"unresolved_blocking_issue_ids={unresolved_blocking}"]
                    if unresolved_blocking
                    else []
                ),
            ]
        )

    confirmed_abox_sorted = sorted(
        confirmed_abox,
        key=lambda item: (
            item["candidate_id"],
            item["decision_id"],
            item["confirmed_candidate"]["confirmed_item_id"],
        ),
    )
    rejected_sorted = sorted(
        rejected_items,
        key=lambda item: (
            "candidate" if "candidate_id" in item else "issue",
            item.get("candidate_id") or item.get("issue_id") or "",
            item["decision_id"],
        ),
    )
    deferred_sorted = sorted(
        deferred_items,
        key=lambda item: (
            "candidate" if "candidate_id" in item else "issue",
            item.get("candidate_id") or item.get("issue_id") or "",
            item["decision_id"],
        ),
    )

    publication_manifest = {
        "package_status": package_status,
        "compile_allowed": compile_allowed,
        "confirmed_abox_count": len(confirmed_abox_sorted),
        "confirmed_schema_delta_count": 0,
        "rejected_item_count": len(rejected_sorted),
        "deferred_item_count": len(deferred_sorted),
        "review_coverage_complete": True,
        "unresolved_blocking_issue_ids": unresolved_blocking,
        "unconfirmed_dependency_candidate_ids": sorted(set(unconfirmed_dependencies)),
        "deferred_issue_details": sorted(
            deferred_issue_details,
            key=lambda item: item["issue_id"],
        ),
        "ontology_version": ontology_baseline.get("ontology_version"),
        "ontology_release_source_hash": ontology_baseline.get("release_source_hash"),
        "review_policy_id": policy.get("policy_id"),
        "review_policy_version": policy.get("policy_version"),
        "review_policy_hash": review_policy_hash(policy),
    }

    package: dict[str, Any] = {
        "contract_version": "1.0",
        "source_proposal_id": proposal["proposal_id"],
        "source_proposal_hash": proposal["proposal_semantic_hash"],
        "review_decision_log_id": decision_log["decision_log_id"],
        "review_decision_log_hash": decision_log["log_hash"],
        "ontology_baseline": {
            "ontology_baseline_id": ontology_baseline.get("baseline_id"),
            "ontology_version": ontology_baseline.get("ontology_version"),
            "ontology_release_source_hash": ontology_baseline.get("release_source_hash"),
        },
        "confirmed_abox_decisions": confirmed_abox_sorted,
        "confirmed_schema_delta": [],
        "rejected_items": rejected_sorted,
        "deferred_items": deferred_sorted,
        "publication_manifest": publication_manifest,
    }
    digest = package_semantic_hash(package)
    package["package_semantic_hash"] = digest
    package["package_id"] = confirmed_package_id(digest)

    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        decision_log,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        review_policy=policy,
        term_types=types,
        require_complete=True,
    )
    return package
