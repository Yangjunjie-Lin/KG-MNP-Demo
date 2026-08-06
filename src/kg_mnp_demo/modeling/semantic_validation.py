"""Cross-object semantic validation beyond JSON Schema expressiveness."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Any

from .canonical_json import semantic_hash
from .identifiers import (
    candidate_id,
    input_id,
    input_semantic_hash,
    issue_id,
    proposal_id,
    proposal_semantic_hash,
)
from .selectors import MISSING, resolve_pointer, validate_json_pointer
from .transformations import TRANSFORMATION_IDS


class SemanticValidationError(ValueError):
    """One or more contract-level cross-reference invariants failed."""

    def __init__(self, errors: Sequence[str]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _raise(errors: list[str]) -> None:
    if errors:
        raise SemanticValidationError(errors)


def _schema_validate(contract_name: str, payload: Mapping[str, Any]) -> None:
    # Import lazily so the semantic layer stays importable while registry
    # configuration errors are reported through the registry itself.
    from .registry import validate_contract

    validate_contract(contract_name, payload)


def _duplicate_values(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _source_refs_from_input(payload: Mapping[str, Any]) -> set[str]:
    return {
        source["source_id"]
        for source in payload.get("sources", [])
        if isinstance(source, Mapping) and isinstance(source.get("source_id"), str)
    }


def validate_cleaned_partial_data_semantics(payload: Mapping[str, Any]) -> None:
    _schema_validate("cleaned-partial-data", payload)
    errors: list[str] = []
    sources = _source_refs_from_input(payload)
    source_ids = [
        source.get("source_id")
        for source in payload.get("sources", [])
        if isinstance(source, Mapping)
    ]
    for duplicate in _duplicate_values([item for item in source_ids if isinstance(item, str)]):
        errors.append(f"duplicate source_id: {duplicate}")
    data = payload.get("data")
    metadata_paths: list[str] = []

    for index, metadata in enumerate(payload.get("field_metadata", [])):
        path = metadata.get("path")
        try:
            validate_json_pointer(path)
        except (TypeError, ValueError) as exc:
            errors.append(f"field_metadata[{index}].path: {exc}")
            continue
        metadata_paths.append(path)
        value = resolve_pointer(data, path)
        if value is MISSING:
            errors.append(f"field_metadata path does not exist in data: {path}")
        presence = metadata.get("presence")
        if presence == "NULL" and value is not None and value is not MISSING:
            errors.append(f"field_metadata presence NULL does not match value at {path}")
        if presence == "PRESENT" and value is None:
            errors.append(f"field_metadata presence PRESENT does not match null at {path}")
        for source_ref in metadata.get("source_refs", []):
            if source_ref not in sources:
                errors.append(f"unknown source_id {source_ref!r} at {path}")
    for duplicate in _duplicate_values(metadata_paths):
        errors.append(f"duplicate field_metadata path: {duplicate}")

    missing_ids: list[str] = []
    missing_paths: list[str] = []
    for index, item in enumerate(payload.get("declared_missing_items", [])):
        missing_id_value = item.get("missing_id")
        if isinstance(missing_id_value, str):
            missing_ids.append(missing_id_value)
        path = item.get("expected_path")
        try:
            validate_json_pointer(path)
        except (TypeError, ValueError) as exc:
            errors.append(f"declared_missing_items[{index}].expected_path: {exc}")
            continue
        missing_paths.append(path)
        if resolve_pointer(data, path) is not MISSING:
            errors.append(f"declared missing path exists in data: {path}")
        for source_ref in item.get("source_refs", []):
            if source_ref not in sources:
                errors.append(f"unknown source_id {source_ref!r} for missing path {path}")
    for duplicate in _duplicate_values(missing_ids):
        errors.append(f"duplicate missing_id: {duplicate}")
    for duplicate in _duplicate_values(missing_paths):
        errors.append(f"duplicate declared missing path: {duplicate}")

    conflict_ids: list[str] = []
    conflict_paths: list[str] = []
    for index, conflict in enumerate(payload.get("declared_conflicts", [])):
        conflict_id_value = conflict.get("conflict_id")
        if isinstance(conflict_id_value, str):
            conflict_ids.append(conflict_id_value)
        path = conflict.get("path")
        try:
            validate_json_pointer(path)
        except (TypeError, ValueError) as exc:
            errors.append(f"declared_conflicts[{index}].path: {exc}")
        else:
            conflict_paths.append(path)
        alternative_hashes: set[str] = set()
        for alternative in conflict.get("alternatives", []):
            try:
                alternative_hashes.add(semantic_hash(alternative.get("value")))
            except (TypeError, ValueError):
                errors.append(f"conflict {path} contains a non-canonical JSON value")
            for source_ref in alternative.get("source_refs", []):
                if source_ref not in sources:
                    errors.append(f"unknown source_id {source_ref!r} in conflict {path}")
        if len(alternative_hashes) < 2:
            errors.append(f"conflict {path} must preserve at least two distinct values")
    for duplicate in _duplicate_values(conflict_ids):
        errors.append(f"duplicate conflict_id: {duplicate}")
    for duplicate in _duplicate_values(conflict_paths):
        errors.append(f"duplicate declared conflict path: {duplicate}")
    for path in sorted(set(missing_paths) & set(conflict_paths)):
        errors.append(f"path cannot be both declared missing and conflicting: {path}")
    _raise(errors)


def _term_set(
    ontology_baseline: Mapping[str, Any] | None,
    term_iris: Collection[str] | None,
) -> set[str]:
    if term_iris is not None:
        return set(term_iris)
    if ontology_baseline:
        embedded = ontology_baseline.get("term_iris") or ontology_baseline.get("term_inventory")
        if isinstance(embedded, list):
            return {str(item) for item in embedded}
    return set()


def validate_mapping_rules_semantics(
    mapping_rules: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any] | None = None,
    terminology_profile: Mapping[str, Any] | None = None,
    *,
    term_iris: Collection[str] | None = None,
) -> None:
    _schema_validate("mapping-rules", mapping_rules)
    errors: list[str] = []
    rules = mapping_rules.get("rules", [])
    rule_ids = [rule.get("rule_id") for rule in rules]
    for duplicate in _duplicate_values([item for item in rule_ids if isinstance(item, str)]):
        errors.append(f"duplicate rule_id: {duplicate}")
    by_id = {
        rule["rule_id"]: rule
        for rule in rules
        if isinstance(rule, Mapping) and isinstance(rule.get("rule_id"), str)
    }
    terms = _term_set(ontology_baseline, term_iris)
    profile_terms = {
        entry.get("term_iri")
        for entry in (terminology_profile or {}).get("entries", [])
        if isinstance(entry, Mapping)
    }
    exemptions = set((terminology_profile or {}).get("target_term_exemptions", []))
    for rule in rules:
        rule_id_value = rule.get("rule_id", "<unknown>")
        transform = rule.get("transformation_id")
        if transform not in TRANSFORMATION_IDS:
            errors.append(f"{rule_id_value}: unknown transformation_id {transform!r}")
        target = rule.get("target_term_iri")
        if terms and target not in terms:
            errors.append(f"{rule_id_value}: target term is absent from ontology baseline: {target}")
        if terminology_profile is not None and target not in profile_terms | exemptions:
            errors.append(f"{rule_id_value}: target term is absent from terminology profile: {target}")
        for field in ("subject_entity_rule_id", "object_entity_rule_id"):
            referenced = rule.get(field)
            if referenced is None:
                continue
            referenced_rule = by_id.get(referenced)
            if referenced_rule is None:
                errors.append(f"{rule_id_value}: unknown {field} {referenced!r}")
            elif referenced_rule.get("candidate_kind") != "ENTITY":
                errors.append(f"{rule_id_value}: {field} must reference an ENTITY rule")
        kind = rule.get("candidate_kind")
        if kind in {
            "DATA_PROPERTY_ASSERTION",
            "CLASS_ASSERTION",
            "OBJECT_PROPERTY_ASSERTION",
            "MAPPING_ASSERTION",
        }:
            if not rule.get("subject_entity_rule_id"):
                errors.append(f"{rule_id_value}: {kind} requires subject_entity_rule_id")
        if kind == "OBJECT_PROPERTY_ASSERTION" and not rule.get("object_entity_rule_id"):
            errors.append(f"{rule_id_value}: OBJECT_PROPERTY_ASSERTION requires object_entity_rule_id")
    baseline_version = (ontology_baseline or {}).get("ontology_version")
    if baseline_version and mapping_rules.get("ontology_baseline_version") != baseline_version:
        errors.append("mapping rules ontology_baseline_version does not match baseline")
    if terminology_profile and mapping_rules.get("terminology_profile_version") != terminology_profile.get("profile_version"):
        errors.append("mapping rules terminology_profile_version does not match profile")
    _raise(errors)


def _normalized_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_terminology_profile_semantics(
    terminology_profile: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any] | None = None,
    *,
    term_iris: Collection[str] | None = None,
) -> None:
    _schema_validate("terminology-profile", terminology_profile)
    errors: list[str] = []
    terms = _term_set(ontology_baseline, term_iris)
    entries = terminology_profile.get("entries", [])
    baseline_version = (ontology_baseline or {}).get("ontology_version")
    if baseline_version and terminology_profile.get("ontology_version") != baseline_version:
        errors.append("terminology profile ontology_version does not match baseline")
    supported_locales = set(terminology_profile.get("supported_locales", []))
    if terminology_profile.get("default_locale") not in supported_locales:
        errors.append("terminology profile default_locale is not supported")
    entry_iris = [entry.get("term_iri") for entry in entries]
    for duplicate in _duplicate_values([item for item in entry_iris if isinstance(item, str)]):
        errors.append(f"duplicate terminology term_iri: {duplicate}")
    aliases: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        term = entry.get("term_iri")
        if terms and term not in terms:
            errors.append(f"terminology term is absent from ontology baseline: {term}")
        if entry.get("language") not in supported_locales:
            errors.append(f"terminology entry language is not supported: {term}")
        label_locales = set(entry.get("preferred_labels", {}))
        if not label_locales <= supported_locales:
            errors.append(f"terminology entry uses an unsupported label locale: {term}")
        normalized_forms = set(entry.get("normalized_forms", []))
        for form in normalized_forms:
            if form != _normalized_alias(form):
                errors.append(f"terminology normalized form is not normalized: {form}")
        for alias in [*entry.get("aliases", []), *entry.get("normalized_forms", [])]:
            aliases[_normalized_alias(alias)].add(term)
    declared: dict[str, set[str]] = {}
    for group in terminology_profile.get("ambiguity_groups", []):
        normalized = _normalized_alias(group.get("normalized_form", ""))
        if normalized in declared:
            errors.append(f"duplicate ambiguity group: {normalized}")
        declared[normalized] = set(group.get("term_iris", []))
    for alias, matched_terms in sorted(aliases.items()):
        if len(matched_terms) > 1 and declared.get(alias) != matched_terms:
            errors.append(f"ambiguous alias is not exactly declared: {alias}")
    for alias, declared_terms in sorted(declared.items()):
        if aliases.get(alias) != declared_terms or len(declared_terms) < 2:
            errors.append(f"ambiguity group does not match profile entries: {alias}")
    _raise(errors)


def validate_proposal_policy_semantics(proposal_policy: Mapping[str, Any]) -> None:
    """Validate the non-Schema policy dependency and its frozen Stage 04 values."""

    errors: list[str] = []
    required_values = {
        "generator_version": "1.0.0",
        "default_run_mode": "DATASET_MODELING",
        "confidence_combination_policy": "MINIMUM_AVAILABLE_SCORE",
        "unmapped_field_policy": "RECORD_AND_REQUIRE_REVIEW",
        "conflict_policy": "PRESERVE_ALL_AND_REQUIRE_REVIEW",
        "null_policy": "PRESERVE_EXPLICIT_NULL",
        "missing_policy": "NEVER_TREAT_AS_FALSE",
        "tbox_candidate_policy": "FORBIDDEN",
    }
    for field, expected in required_values.items():
        if proposal_policy.get(field) != expected:
            errors.append(f"proposal policy {field} must equal {expected!r}")
    policy_version = proposal_policy.get("policy_version")
    if not isinstance(policy_version, str) or re.fullmatch(
        r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)",
        policy_version,
    ) is None:
        errors.append("proposal policy policy_version must be a semantic version")
    if proposal_policy.get("confidence_levels") != ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
        errors.append("proposal policy confidence_levels are not frozen")
    if proposal_policy.get("issue_severity") != ["INFO", "WARNING", "ERROR", "BLOCKING"]:
        errors.append("proposal policy issue_severity is not frozen")
    ranges = proposal_policy.get("confidence_score_ranges")
    if not isinstance(ranges, Mapping):
        errors.append("proposal policy confidence_score_ranges must be an object")
    else:
        for level in ("HIGH", "MEDIUM", "LOW"):
            bounds = ranges.get(level)
            if not isinstance(bounds, Mapping):
                errors.append(f"proposal policy has no numeric range for {level}")
                continue
            minimum, maximum = bounds.get("minimum"), bounds.get("maximum")
            if (
                not isinstance(minimum, (int, float))
                or isinstance(minimum, bool)
                or not isinstance(maximum, (int, float))
                or isinstance(maximum, bool)
                or not 0 <= float(minimum) <= float(maximum) <= 1
            ):
                errors.append(f"proposal policy has an invalid score range for {level}")
        unknown = ranges.get("UNKNOWN")
        if not isinstance(unknown, Mapping) or unknown.get("score_allowed") is not False:
            errors.append("proposal policy UNKNOWN confidence must forbid a score")
    _raise(errors)


def validate_modeling_proposal_semantics(
    proposal: Mapping[str, Any],
    cleaned_partial_data: Mapping[str, Any] | None = None,
    mapping_rules: Mapping[str, Any] | None = None,
) -> None:
    _schema_validate("modeling-proposal", proposal)
    errors: list[str] = []
    candidates = [
        *proposal.get("candidate_entities", []),
        *proposal.get("candidate_assertions", []),
    ]
    candidate_ids = [candidate.get("candidate_id") for candidate in candidates]
    for duplicate in _duplicate_values([item for item in candidate_ids if isinstance(item, str)]):
        errors.append(f"duplicate candidate_id: {duplicate}")
    candidate_set = {item for item in candidate_ids if isinstance(item, str)}
    entity_set = {
        item.get("candidate_id")
        for item in proposal.get("candidate_entities", [])
        if isinstance(item.get("candidate_id"), str)
    }
    for candidate in candidates:
        if candidate.get("review_status") != "PROPOSED":
            errors.append(f"candidate must remain PROPOSED: {candidate.get('candidate_id')}")
        expected = candidate_id(candidate)
        if candidate.get("candidate_id") != expected:
            errors.append(f"candidate_id does not match semantic content: {candidate.get('candidate_id')}")
    for assertion in proposal.get("candidate_assertions", []):
        subject_ref = assertion.get("subject_ref")
        if isinstance(subject_ref, str) and subject_ref.startswith("urn:kg-mnp:candidate:"):
            if subject_ref not in entity_set:
                errors.append(f"assertion references unknown subject candidate_id: {subject_ref}")
        object_ref = assertion.get("object")
        if isinstance(object_ref, str) and object_ref.startswith("urn:kg-mnp:candidate:"):
            if object_ref not in entity_set:
                errors.append(f"assertion references unknown object candidate_id: {object_ref}")
    if proposal.get("schema_delta_candidates") != []:
        errors.append("schema_delta_candidates must be empty in Stage 04")

    issues = proposal.get("issues", [])
    issue_ids = [issue.get("issue_id") for issue in issues]
    for duplicate in _duplicate_values([item for item in issue_ids if isinstance(item, str)]):
        errors.append(f"duplicate issue_id: {duplicate}")
    for issue in issues:
        if issue.get("review_status") != "PROPOSED":
            errors.append(f"issue must remain PROPOSED: {issue.get('issue_id')}")
        if issue.get("publication_scope") != "REVIEW_ONLY":
            errors.append(f"issue must be REVIEW_ONLY: {issue.get('issue_id')}")
        if issue.get("issue_id") != issue_id(issue):
            errors.append(f"issue_id does not match semantic content: {issue.get('issue_id')}")
        for related in issue.get("related_candidate_ids", []):
            if related not in candidate_set:
                errors.append(f"issue references unknown candidate_id: {related}")

    if proposal.get("proposal_semantic_hash") != proposal_semantic_hash(proposal):
        errors.append("proposal_semantic_hash does not match semantic content")
    if proposal.get("proposal_id") != proposal_id(proposal):
        errors.append("proposal_id does not match proposal semantic hash")

    if cleaned_partial_data is not None:
        sources = _source_refs_from_input(cleaned_partial_data)
        snapshot = proposal.get("input_snapshot", {})
        expected_snapshot = {
            "input_id": input_id(cleaned_partial_data),
            "document_id": cleaned_partial_data.get("document_id"),
            "dataset_id": cleaned_partial_data.get("dataset_id"),
            "input_contract_version": cleaned_partial_data.get("contract_version"),
            "input_semantic_hash": input_semantic_hash(cleaned_partial_data),
        }
        for field, expected in expected_snapshot.items():
            if snapshot.get(field) != expected:
                errors.append(f"input_snapshot.{field} does not match CleanedPartialData")
        for candidate in candidates:
            for source_ref in candidate.get("business_fact_evidence_refs", []):
                if source_ref not in sources:
                    errors.append(f"candidate references unknown business source: {source_ref}")
            for path in candidate.get("source_paths", []):
                if resolve_pointer(cleaned_partial_data.get("data"), path) is MISSING:
                    errors.append(f"candidate source path is absent from input data: {path}")
        for issue in issues:
            for source_ref in issue.get("source_refs", []):
                if source_ref not in sources:
                    errors.append(f"issue references unknown source: {source_ref}")
        for field in proposal.get("unmapped_fields", []):
            if resolve_pointer(cleaned_partial_data.get("data"), field.get("path")) is MISSING:
                errors.append(f"unmapped field path is absent from input data: {field.get('path')}")
            for source_ref in field.get("source_refs", []):
                if source_ref not in sources:
                    errors.append(f"unmapped field references unknown source: {source_ref}")
    if mapping_rules is not None:
        rules_by_id = {
            rule.get("rule_id"): rule
            for rule in mapping_rules.get("rules", [])
            if isinstance(rule.get("rule_id"), str)
        }
        for candidate in candidates:
            referenced_rules = []
            for rule_id in candidate.get("mapping_rule_ids", []):
                rule = rules_by_id.get(rule_id)
                if rule is None:
                    errors.append(f"candidate references unknown mapping rule: {rule_id}")
                    continue
                if rule.get("status") != "CONFIRMED":
                    errors.append(f"candidate references non-confirmed mapping rule: {rule_id}")
                referenced_rules.append(rule)
            evidence = {
                reference
                for rule in referenced_rules
                for reference in rule.get("modeling_evidence_refs", [])
            }
            for reference in candidate.get("modeling_evidence_refs", []):
                if reference not in evidence:
                    errors.append(f"candidate references unknown modeling evidence: {reference}")
        dependency_snapshot = proposal.get("dependency_snapshot", {})
        expected_mapping_snapshot = {
            "mapping_set_id": mapping_rules.get("mapping_set_id"),
            "mapping_set_version": mapping_rules.get("mapping_set_version"),
            "mapping_rules_hash": semantic_hash(mapping_rules),
        }
        for field, expected in expected_mapping_snapshot.items():
            if dependency_snapshot.get(field) != expected:
                errors.append(f"dependency_snapshot.{field} does not match MappingRules")
    summary = proposal.get("summary", {})
    expected_counts = {
        "candidate_entity_count": len(proposal.get("candidate_entities", [])),
        "candidate_assertion_count": len(proposal.get("candidate_assertions", [])),
        "issue_count": len(issues),
        "unmapped_field_count": len(proposal.get("unmapped_fields", [])),
        "schema_delta_count": 0,
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            errors.append(f"summary.{key} must equal {expected}")
    _raise(errors)


def validate_review_decision_log_semantics(
    decision_log: Mapping[str, Any],
    proposal: Mapping[str, Any],
    cleaned_partial_data: Mapping[str, Any] | None = None,
    ontology_baseline: Mapping[str, Any] | None = None,
    mapping_rules: Mapping[str, Any] | None = None,
    *,
    review_policy: Mapping[str, Any] | None = None,
    require_final: bool = False,
    verify_draft_integrity: bool = False,
    term_types: Mapping[str, str] | None = None,
) -> None:
    del cleaned_partial_data, ontology_baseline, mapping_rules
    _schema_validate("review-decision-log", decision_log)
    errors: list[str] = []
    if decision_log.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("decision log proposal_id does not match proposal")
    if decision_log.get("proposal_semantic_hash") != proposal.get("proposal_semantic_hash"):
        errors.append("decision log proposal_semantic_hash does not match proposal")

    from .review_identifiers import decision_log_hash, decision_log_id, review_decision_id
    from .review_log import (
        decision_sort_key,
        is_log_completed,
        review_coverage,
    )
    from .review_policy import (
        ReviewPolicyError,
        decision_allowed_for_target,
        load_default_review_policy,
    )
    from .review_actions import validate_modified_candidate

    if review_policy is not None:
        active_policy = review_policy
    else:
        try:
            active_policy = load_default_review_policy()
        except ReviewPolicyError as exc:
            raise SemanticValidationError(
                [f"review policy load failed closed: {exc}"]
            ) from exc
        except Exception as exc:
            raise SemanticValidationError(
                [f"review policy load failed closed: {exc}"]
            ) from exc

    enforce_identity = require_final or verify_draft_integrity

    candidates = {
        item["candidate_id"]: item
        for item in [*proposal.get("candidate_entities", []), *proposal.get("candidate_assertions", [])]
    }
    issues = {item["issue_id"]: item for item in proposal.get("issues", [])}
    decision_ids: list[str] = []
    targets: list[str] = []
    reviewer_id = decision_log.get("reviewer", {}).get("reviewer_id")
    session = decision_log.get("review_session") or {}
    started_at = session.get("started_at")
    completed_at = session.get("completed_at")

    if require_final and not is_log_completed(decision_log):
        errors.append("final ReviewDecisionLog requires completed_at")
    if isinstance(started_at, str) and isinstance(completed_at, str):
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            if end < start:
                errors.append("completed_at must not be earlier than started_at")
        except ValueError:
            errors.append("review session timestamps are not valid date-time values")

    for decision in decision_log.get("decisions", []):
        decision_ids.append(decision.get("decision_id"))
        target = decision.get("candidate_id") or decision.get("issue_id")
        targets.append(target)
        if decision.get("candidate_id") and decision["candidate_id"] not in candidates:
            errors.append(f"decision references unknown candidate_id: {decision['candidate_id']}")
        if decision.get("issue_id") and decision["issue_id"] not in issues:
            errors.append(f"decision references unknown issue_id: {decision['issue_id']}")
        if decision.get("reviewer_id") != reviewer_id:
            errors.append(f"decision reviewer_id does not match log reviewer: {target}")
        has_modified = "modified_candidate" in decision
        if has_modified != (decision.get("decision") == "MODIFY_AND_CONFIRM"):
            errors.append("modified_candidate is required only for MODIFY_AND_CONFIRM")
        target_kind = "candidate" if decision.get("candidate_id") else "issue"
        decision_value = decision.get("decision")
        if isinstance(decision_value, str):
            if not decision_allowed_for_target(
                target_kind=target_kind,
                decision=decision_value,
                policy=active_policy,
            ):
                errors.append(
                    f"decision {decision_value} is not allowed for {target_kind} targets"
                )
        if decision_value == "DEPRECATE":
            errors.append(f"DEPRECATE is forbidden in dataset modeling review: {target}")
        if (
            decision_value == "MODIFY_AND_CONFIRM"
            and decision.get("candidate_id") in candidates
            and isinstance(decision.get("modified_candidate"), Mapping)
        ):
            try:
                validate_modified_candidate(
                    candidates[decision["candidate_id"]],
                    decision["modified_candidate"],
                    term_types=term_types,
                )
            except SemanticValidationError as exc:
                errors.extend(exc.errors)
        if isinstance(decision.get("decision_id"), str) and isinstance(target, str):
            expected_decision_id = review_decision_id(
                proposal_id=str(proposal["proposal_id"]),
                target_id=target,
                decision=str(decision.get("decision")),
                rationale=str(decision.get("rationale")),
                reviewer_id=str(decision.get("reviewer_id")),
                decided_at=str(decision.get("decided_at")),
                evidence_refs=list(decision.get("evidence_refs") or []),
                modified_candidate=decision.get("modified_candidate"),
            )
            if enforce_identity and decision.get("decision_id") != expected_decision_id:
                errors.append(f"decision_id does not match semantic content: {target}")
        if isinstance(decision.get("decided_at"), str) and isinstance(started_at, str):
            try:
                decided = datetime.fromisoformat(
                    decision["decided_at"].replace("Z", "+00:00")
                )
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                if decided < start:
                    errors.append(f"decided_at earlier than session start: {target}")
                if isinstance(completed_at, str):
                    end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    if decided > end:
                        errors.append(f"decided_at later than session completion: {target}")
            except ValueError:
                errors.append(f"decision decided_at is not a valid date-time: {target}")

    for duplicate in _duplicate_values([item for item in decision_ids if isinstance(item, str)]):
        errors.append(f"duplicate decision_id: {duplicate}")
    for duplicate in _duplicate_values([item for item in targets if isinstance(item, str)]):
        errors.append(f"multiple review decisions target the same proposal item: {duplicate}")

    coverage = review_coverage(proposal, decision_log)
    if require_final and not coverage["coverage_complete"]:
        errors.append("final ReviewDecisionLog coverage is incomplete")
    if enforce_identity:
        expected_log_id = decision_log_id(
            proposal_id=str(proposal["proposal_id"]),
            proposal_semantic_hash=str(proposal["proposal_semantic_hash"]),
            reviewer_id=str(reviewer_id),
            session_id=str(session.get("session_id")),
            review_policy_version=str(active_policy["policy_version"]),
        )
        if decision_log.get("decision_log_id") != expected_log_id:
            errors.append("decision_log_id does not match review session binding")
        if decision_log.get("log_hash") != decision_log_hash(decision_log):
            errors.append("log_hash does not match decision log semantic content")
    if require_final:
        ordered = list(decision_log.get("decisions", []))
        if ordered != sorted(ordered, key=decision_sort_key):
            errors.append("final ReviewDecisionLog decisions are not stably sorted")
    _raise(errors)


def validate_confirmed_modeling_package_semantics(
    package: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    cleaned_partial_data: Mapping[str, Any] | None = None,
    ontology_baseline: Mapping[str, Any] | None = None,
    mapping_rules: Mapping[str, Any] | None = None,
    terminology_profile: Mapping[str, Any] | None = None,
    proposal_policy: Mapping[str, Any] | None = None,
    *,
    review_policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
    functional_property_iris: frozenset[str] | None = None,
    require_complete: bool = False,
) -> None:
    _schema_validate("confirmed-modeling-package", package)
    validate_review_decision_log_semantics(
        decision_log,
        proposal,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        review_policy=review_policy,
        require_final=require_complete,
        term_types=term_types,
    )
    errors: list[str] = []
    if package.get("source_proposal_id") != proposal.get("proposal_id"):
        errors.append("package source_proposal_id does not match proposal")
    if package.get("source_proposal_hash") != proposal.get("proposal_semantic_hash"):
        errors.append("package source_proposal_hash does not match proposal")
    if package.get("review_decision_log_id") != decision_log.get("decision_log_id"):
        errors.append("package review_decision_log_id does not match decision log")
    if package.get("review_decision_log_hash") != decision_log.get("log_hash"):
        errors.append("package review_decision_log_hash does not match decision log")

    from .review_identifiers import confirmed_package_id, package_semantic_hash

    if require_complete:
        if package.get("package_semantic_hash") != package_semantic_hash(package):
            errors.append("package_semantic_hash does not match package semantic content")
        if package.get("package_id") != confirmed_package_id(package):
            errors.append("package_id does not match package semantic hash")

    decisions: dict[str, Mapping[str, Any]] = {}
    for decision in decision_log.get("decisions", []):
        target = decision.get("candidate_id") or decision.get("issue_id")
        decisions[target] = decision
    proposal_items = {
        item["candidate_id"]
        for item in [*proposal.get("candidate_entities", []), *proposal.get("candidate_assertions", [])]
    } | {item["issue_id"] for item in proposal.get("issues", [])}

    def target_id(item: Mapping[str, Any]) -> str | None:
        return item.get("candidate_id") or item.get("issue_id")

    proposal_baseline = proposal.get("dependency_snapshot", {})
    package_baseline = package.get("ontology_baseline", {})
    for package_field, proposal_field in (
        ("ontology_baseline_id", "ontology_baseline_id"),
        ("ontology_version", "ontology_version"),
        ("ontology_release_source_hash", "ontology_release_source_hash"),
    ):
        if package_baseline.get(package_field) != proposal_baseline.get(proposal_field):
            errors.append(f"package ontology_baseline.{package_field} does not match proposal")

    section_targets: dict[str, str] = {}

    if package.get("confirmed_schema_delta") not in (None, []):
        if require_complete or package.get("confirmed_schema_delta"):
            if package.get("confirmed_schema_delta") != []:
                errors.append("confirmed_schema_delta must be empty in Stage 05 dataset modeling")

    for section in ("confirmed_abox_decisions", "confirmed_schema_delta"):
        for item in package.get(section, []):
            target = target_id(item)
            if target in section_targets:
                errors.append(
                    f"package item appears in both {section_targets[target]} and {section}: {target}"
                )
            else:
                section_targets[target] = section
            if target not in proposal_items:
                errors.append(f"{section} contains an item absent from proposal: {target}")
            decision = decisions.get(target, {})
            if decision.get("decision") not in {"CONFIRM", "MODIFY_AND_CONFIRM"}:
                errors.append(f"{section} item lacks an effective confirmation: {target}")
            if item.get("decision_id") != decision.get("decision_id"):
                errors.append(f"{section} item does not reference its review decision: {target}")
            if item.get("decision") != decision.get("decision"):
                errors.append(f"{section} item decision differs from review log: {target}")
            if section == "confirmed_schema_delta" and item.get("publication_scope") != "TBOX":
                errors.append(f"confirmed schema delta must have TBOX scope: {target}")
            if section == "confirmed_abox_decisions" and item.get("publication_scope") != "ABOX":
                errors.append(f"confirmed abox item must have ABOX scope: {target}")
            if decision.get("decision") == "REJECT":
                errors.append(f"REJECT decision cannot enter confirmed section: {target}")
            if decision.get("decision") == "DEFER":
                errors.append(f"DEFER decision cannot enter confirmed section: {target}")
            if target and target.startswith("urn:kg-mnp:issue:"):
                errors.append(f"issue cannot enter confirmed section: {target}")
            confirmed = item.get("confirmed_candidate")
            if require_complete:
                if not isinstance(confirmed, Mapping):
                    errors.append(f"confirmed abox item lacks confirmed_candidate envelope: {target}")
                else:
                    if confirmed.get("source_candidate_id") != item.get("candidate_id"):
                        errors.append(
                            f"confirmed_candidate.source_candidate_id mismatch: {target}"
                        )
                    if decision.get("decision") == "CONFIRM":
                        if confirmed.get("confirmation_mode") != "ORIGINAL":
                            errors.append(f"CONFIRM must use ORIGINAL confirmation mode: {target}")
                        if confirmed.get("effective_candidate_id") != item.get("candidate_id"):
                            errors.append(
                                f"CONFIRM effective_candidate_id must equal source: {target}"
                            )
                    if decision.get("decision") == "MODIFY_AND_CONFIRM":
                        if confirmed.get("confirmation_mode") != "MODIFIED":
                            errors.append(
                                f"MODIFY_AND_CONFIRM must use MODIFIED confirmation mode: {target}"
                            )
                        modified = decision.get("modified_candidate") or {}
                        if confirmed.get("effective_candidate_id") != modified.get("candidate_id"):
                            errors.append(
                                f"MODIFY_AND_CONFIRM effective_candidate_id mismatch: {target}"
                            )
    for section, expected in (("rejected_items", "REJECT"), ("deferred_items", "DEFER")):
        for item in package.get(section, []):
            target = target_id(item)
            if target in section_targets:
                errors.append(
                    f"package item appears in both {section_targets[target]} and {section}: {target}"
                )
            else:
                section_targets[target] = section
            if target not in proposal_items:
                errors.append(f"{section} contains an item absent from proposal: {target}")
            decision = decisions.get(target, {})
            if decision.get("decision") != expected:
                errors.append(f"{section} item lacks {expected} decision: {target}")
            if item.get("decision_id") != decision.get("decision_id"):
                errors.append(f"{section} item does not reference its review decision: {target}")

    if require_complete:
        missing = sorted(proposal_items - set(section_targets))
        for target in missing:
            errors.append(f"proposal item missing from package sections: {target}")
        manifest = package.get("publication_manifest") or {}
        expected_counts = {
            "confirmed_abox_count": len(package.get("confirmed_abox_decisions", [])),
            "confirmed_schema_delta_count": len(package.get("confirmed_schema_delta", [])),
            "rejected_item_count": len(package.get("rejected_items", [])),
            "deferred_item_count": len(package.get("deferred_items", [])),
        }
        for field, expected in expected_counts.items():
            if manifest.get(field) != expected:
                errors.append(f"publication_manifest.{field} must equal {expected}")
        status = manifest.get("package_status")
        compile_allowed = manifest.get("compile_allowed")
        if status not in {"READY_FOR_COMPILATION", "BLOCKED"}:
            errors.append("publication_manifest.package_status is invalid")
        if status == "READY_FOR_COMPILATION" and compile_allowed is not True:
            errors.append("READY_FOR_COMPILATION requires compile_allowed=true")
        if status == "BLOCKED" and compile_allowed is not False:
            errors.append("BLOCKED requires compile_allowed=false")
        if manifest.get("review_coverage_complete") is not True:
            errors.append("publication_manifest.review_coverage_complete must be true")
        if review_policy is not None:
            if manifest.get("review_policy_version") != review_policy.get("policy_version"):
                errors.append("publication_manifest.review_policy_version mismatch")
            from .review_policy import review_policy_hash

            if manifest.get("review_policy_hash") != review_policy_hash(review_policy):
                errors.append("publication_manifest.review_policy_hash mismatch")

        authority_missing = [
            name
            for name, value in (
                ("cleaned_partial_data", cleaned_partial_data),
                ("ontology_baseline", ontology_baseline),
                ("mapping_rules", mapping_rules),
                ("terminology_profile", terminology_profile),
                ("proposal_policy", proposal_policy),
            )
            if value is None
        ]
        if authority_missing:
            errors.append(
                "complete package validation requires authoritative inputs: "
                + ", ".join(authority_missing)
            )
            _raise(errors)
            return

        from .confirmation import (
            complete_confirmed_package,
            derive_confirmed_package_content,
            packages_deterministically_equal,
        )
        from .package_validation import load_functional_property_iris, load_term_type_index
        from .review_policy import load_default_review_policy

        policy = review_policy if review_policy is not None else load_default_review_policy()
        types = dict(term_types) if term_types is not None else load_term_type_index()
        functional = (
            functional_property_iris
            if functional_property_iris is not None
            else load_functional_property_iris()
        )
        try:
            expected_content = derive_confirmed_package_content(
                cleaned_partial_data,
                proposal,
                decision_log,
                ontology_baseline,
                mapping_rules,
                terminology_profile,
                proposal_policy,
                policy,
                allow_blocked=True,
                term_types=types,
                functional_property_iris=functional,
            )
            expected_package = complete_confirmed_package(expected_content)
        except SemanticValidationError as exc:
            errors.extend(exc.errors)
            _raise(errors)
            return
        mismatches = packages_deterministically_equal(package, expected_package)
        if mismatches:
            preview = ", ".join(mismatches[:12])
            errors.append(
                "package does not match deterministic reconstruction from authoritative "
                f"inputs; differing paths: {preview}"
            )
            expected_manifest = expected_package.get("publication_manifest") or {}
            if manifest.get("package_status") != expected_manifest.get("package_status"):
                errors.append(
                    "publication_manifest.package_status does not match readiness derivation"
                )
            if manifest.get("compile_allowed") != expected_manifest.get("compile_allowed"):
                errors.append(
                    "publication_manifest.compile_allowed does not match readiness derivation"
                )
            if manifest.get("unresolved_blocking_issue_ids") != expected_manifest.get(
                "unresolved_blocking_issue_ids"
            ):
                errors.append(
                    "publication_manifest.unresolved_blocking_issue_ids does not match "
                    "readiness derivation"
                )
            if manifest.get("unconfirmed_dependency_candidate_ids") != expected_manifest.get(
                "unconfirmed_dependency_candidate_ids"
            ):
                errors.append(
                    "publication_manifest.unconfirmed_dependency_candidate_ids does not match "
                    "reference closure derivation"
                )
    _raise(errors)


def validate_confirmed_package_against_authorities(
    package: Mapping[str, Any],
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any] | None = None,
    *,
    term_types: Mapping[str, str] | None = None,
    functional_property_iris: frozenset[str] | None = None,
) -> None:
    """Independently re-derive the expected package and compare byte-for-byte."""

    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        decision_log,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        terminology_profile=terminology_profile,
        proposal_policy=proposal_policy,
        review_policy=review_policy,
        term_types=term_types,
        functional_property_iris=functional_property_iris,
        require_complete=True,
    )
