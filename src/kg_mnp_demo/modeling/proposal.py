"""Pure, deterministic Stage 04 ModelingProposal generation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical_json import semantic_hash
from .identifiers import (
    candidate_id,
    input_id,
    input_semantic_hash,
    proposal_id,
    proposal_semantic_hash,
)
from .issues import issue_sort_key, make_issue
from .selectors import MISSING, iter_leaf_fields, json_value_type, resolve_pointer
from .semantic_validation import (
    validate_cleaned_partial_data_semantics,
    validate_mapping_rules_semantics,
    validate_modeling_proposal_semantics,
    validate_proposal_policy_semantics,
    validate_terminology_profile_semantics,
)
from .transformations import TransformationError, transform_value

GENERATOR_VERSION = "1.0.0"
RUN_MODE = "DATASET_MODELING"

_XSD = "http://www.w3.org/2001/XMLSchema#"
_DEFAULT_DATATYPES = {
    "string": _XSD + "string",
    "boolean": _XSD + "boolean",
    "integer": _XSD + "integer",
    "number": _XSD + "decimal",
    "null": _XSD + "string",
}


def _dependency_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(value)


def _metadata_index(cleaned: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        metadata["path"]: metadata
        for metadata in cleaned.get("field_metadata", [])
        if isinstance(metadata, Mapping) and isinstance(metadata.get("path"), str)
    }


def _source_refs(metadata: Mapping[str, Any] | None) -> list[str]:
    if not metadata:
        return []
    return sorted(set(metadata.get("source_refs", [])))


def _level_for_score(score: float | None, policy: Mapping[str, Any]) -> str:
    if score is None:
        return "UNKNOWN"
    configured = policy.get("confidence_score_ranges", {})
    for level in ("HIGH", "MEDIUM", "LOW"):
        bounds = configured.get(level)
        if isinstance(bounds, Mapping):
            minimum, maximum = bounds.get("minimum"), bounds.get("maximum")
        elif isinstance(bounds, Sequence) and not isinstance(bounds, (str, bytes)) and len(bounds) == 2:
            minimum, maximum = bounds
        else:
            minimum, maximum = {
                "HIGH": (0.8, 1.0),
                "MEDIUM": (0.5, 0.799999999999),
                "LOW": (0.0, 0.499999999999),
            }[level]
        if minimum is not None and maximum is not None and float(minimum) <= score <= float(maximum):
            return level
    return "UNKNOWN"


def _confidence(
    rule: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    rule_value = rule.get("confidence") if isinstance(rule.get("confidence"), Mapping) else None
    source_value = (
        metadata.get("confidence")
        if metadata and isinstance(metadata.get("confidence"), Mapping)
        else None
    )
    components: list[dict[str, Any]] = []
    scores: list[float] = []
    if rule_value:
        component = {"component": "MAPPING_RULE", **deepcopy(dict(rule_value))}
        components.append(component)
        if isinstance(rule_value.get("score"), (int, float)):
            scores.append(float(rule_value["score"]))
    if source_value:
        component = {"component": "SOURCE_METADATA", **deepcopy(dict(source_value))}
        components.append(component)
        if isinstance(source_value.get("score"), (int, float)):
            scores.append(float(source_value["score"]))
    score = min(scores) if scores else None
    if rule_value and source_value:
        basis = "RULE_AND_SOURCE"
    elif rule_value:
        basis = "RULE_DECLARED"
    elif source_value:
        basis = "SOURCE_DECLARED"
    else:
        basis = "UNKNOWN"
    result: dict[str, Any] = {
        "level": _level_for_score(score, policy),
        "basis": basis,
        "components": components,
    }
    if score is not None:
        result["score"] = score
    return result


def _validate_declared_confidences(
    cleaned: Mapping[str, Any],
    rules: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    declarations: list[tuple[str, Mapping[str, Any]]] = []
    declarations.extend(
        (f"field metadata {item.get('path')}", item["confidence"])
        for item in cleaned.get("field_metadata", [])
        if isinstance(item.get("confidence"), Mapping)
    )
    declarations.extend(
        (f"mapping rule {rule.get('rule_id')}", rule["confidence"])
        for rule in rules.get("rules", [])
        if isinstance(rule.get("confidence"), Mapping)
    )
    for label, confidence in declarations:
        score = confidence.get("score")
        expected = _level_for_score(float(score), policy) if score is not None else "UNKNOWN"
        if confidence.get("level") != expected:
            raise ValueError(
                f"{label} confidence level {confidence.get('level')!r} "
                f"does not match policy score range {expected!r}"
            )


def _candidate_common(
    rule: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "review_status": "PROPOSED",
        "publication_scope": "ABOX",
        "source_paths": [rule["source_selector"]],
        "mapping_rule_ids": [rule["rule_id"]],
        "business_fact_evidence_refs": _source_refs(metadata),
        "modeling_evidence_refs": sorted(set(rule.get("modeling_evidence_refs", []))),
        "confidence": _confidence(rule, metadata, policy),
        "rationale": rule["description"],
    }


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    target = candidate.get("predicate_iri") or candidate.get("class_iri") or ""
    subject = candidate.get("subject_ref", {})
    if isinstance(subject, Mapping):
        subject_value = subject.get("candidate_id") or subject.get("proposed_iri") or ""
    else:
        subject_value = str(subject)
    return (
        candidate.get("candidate_kind", "ENTITY"),
        subject_value,
        target,
        tuple(candidate.get("source_paths", [])),
        candidate.get("candidate_id", ""),
    )


def _add_candidate_id(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["candidate_id"] = candidate_id(candidate)
    return candidate


def _matches_source_type(value: Any, expected: str) -> bool:
    actual = json_value_type(value)
    if expected == "number":
        return actual in {"integer", "number"}
    return actual == expected


def _metadata_state_issue(
    rule: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    presence = metadata.get("presence")
    if presence not in {"UNKNOWN", "REDACTED"}:
        return None
    return make_issue(
        "MISSING_INFORMATION",
        "WARNING" if presence == "UNKNOWN" else "ERROR",
        f"{rule['source_selector']} is marked {presence}; no value candidate was generated.",
        source_paths=[rule["source_selector"]],
        source_refs=_source_refs(metadata),
        details={"presence": presence, "rule_id": rule["rule_id"]},
    )


def _missing_severity(requiredness: str) -> tuple[str, bool]:
    if requiredness == "REQUIRED_FOR_PROPOSAL":
        return "BLOCKING", True
    return "WARNING", False


def _term_alias_matches(path: str, profile: Mapping[str, Any]) -> list[str]:
    label = path.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
    normalized = " ".join(label.replace("_", " ").replace("-", " ").casefold().split())
    matches: set[str] = set()
    for entry in profile.get("entries", []):
        forms = [*entry.get("aliases", []), *entry.get("normalized_forms", [])]
        if any(" ".join(str(item).casefold().split()) == normalized for item in forms):
            matches.add(entry["term_iri"])
    return sorted(matches)


def _dependency_snapshot(
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "ontology_baseline_id": ontology_baseline.get("baseline_id")
        or ontology_baseline.get("manifest_id")
        or f"ontology-baseline-{ontology_baseline['ontology_version']}",
        "ontology_version": ontology_baseline["ontology_version"],
        "ontology_release_source_hash": ontology_baseline["release_source_hash"],
        "mapping_set_id": mapping_rules["mapping_set_id"],
        "mapping_set_version": mapping_rules["mapping_set_version"],
        "mapping_rules_hash": _dependency_hash(mapping_rules),
        "terminology_profile_id": terminology_profile["profile_id"],
        "terminology_profile_version": terminology_profile["profile_version"],
        "terminology_profile_hash": _dependency_hash(terminology_profile),
        "proposal_policy_version": proposal_policy["policy_version"],
        "proposal_policy_hash": _dependency_hash(proposal_policy),
        "generator_version": GENERATOR_VERSION,
    }


def generate_modeling_proposal(
    cleaned_partial_data: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    *,
    term_iris: set[str] | None = None,
    run_mode: str = RUN_MODE,
) -> dict[str, Any]:
    """Generate a review-only proposal without I/O, clocks, randomness, or mutation."""

    if run_mode != RUN_MODE:
        raise ValueError("UNSUPPORTED_IN_STAGE_04: only DATASET_MODELING is available")
    cleaned = deepcopy(dict(cleaned_partial_data))
    baseline = deepcopy(dict(ontology_baseline))
    rules_document = deepcopy(dict(mapping_rules))
    profile = deepcopy(dict(terminology_profile))
    policy = deepcopy(dict(proposal_policy))
    validate_cleaned_partial_data_semantics(cleaned)
    validate_proposal_policy_semantics(policy)
    validate_terminology_profile_semantics(profile, baseline, term_iris=term_iris)
    validate_mapping_rules_semantics(
        rules_document,
        baseline,
        profile,
        term_iris=term_iris,
    )
    _validate_declared_confidences(cleaned, rules_document, policy)
    if rules_document.get("ontology_baseline_version") != baseline.get("ontology_version"):
        raise ValueError("mapping rules and ontology baseline versions are incompatible")
    if rules_document.get("terminology_profile_version") != profile.get("profile_version"):
        raise ValueError("mapping rules and terminology profile versions are incompatible")
    if policy.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("proposal policy generator_version is incompatible")
    if policy.get("default_run_mode") != RUN_MODE:
        raise ValueError("proposal policy default_run_mode is incompatible")
    if policy.get("tbox_candidate_policy") != "FORBIDDEN":
        raise ValueError("Stage 04 requires tbox_candidate_policy FORBIDDEN")

    data = cleaned["data"]
    metadata_by_path = _metadata_index(cleaned)
    declared_missing = {
        item["expected_path"]: item for item in cleaned.get("declared_missing_items", [])
    }
    conflicts = {item["path"]: item for item in cleaned.get("declared_conflicts", [])}
    confirmed_rules = sorted(
        (rule for rule in rules_document["rules"] if rule["status"] == "CONFIRMED"),
        key=lambda rule: rule["rule_id"],
    )
    executable_paths = {rule["source_selector"] for rule in confirmed_rules}
    generated_entities: dict[str, dict[str, Any]] = {}
    candidate_entities: list[dict[str, Any]] = []
    candidate_assertions: list[dict[str, Any]] = []
    issues: dict[str, dict[str, Any]] = {}

    def add_issue(value: dict[str, Any]) -> None:
        issues[value["issue_id"]] = value

    # Preserve explicitly declared absence and conflicts before mapping.
    for path, missing in sorted(declared_missing.items()):
        matching = [rule for rule in confirmed_rules if rule["source_selector"] == path]
        requiredness = matching[0]["requiredness"] if matching else "EXPECTED"
        severity, blocking = _missing_severity(requiredness)
        add_issue(
            make_issue(
                "MISSING_INFORMATION",
                severity,
                f"Input explicitly declares expected field {path} as missing.",
                source_paths=[path],
                source_refs=missing.get("source_refs", []),
                blocking=blocking,
                details={
                    "missing_id": missing["missing_id"],
                    "reason": missing["reason"],
                    "expected_semantic_role": missing.get("expected_semantic_role"),
                },
            )
        )
    for path, conflict in sorted(conflicts.items()):
        refs = {
            ref
            for alternative in conflict["alternatives"]
            for ref in alternative.get("source_refs", [])
        }
        add_issue(
            make_issue(
                "CONFLICT",
                "BLOCKING",
                f"Conflicting alternatives at {path} require human review; no winner was selected.",
                source_paths=[path],
                source_refs=refs,
                blocking=True,
                details={
                    "conflict_id": conflict["conflict_id"],
                    "alternatives": deepcopy(conflict["alternatives"]),
                    "winner": None,
                },
            )
        )

    # First pass: entity candidates establish references for assertion rules.
    for rule in confirmed_rules:
        if rule["candidate_kind"] != "ENTITY":
            continue
        path = rule["source_selector"]
        if path in conflicts:
            continue
        value = resolve_pointer(data, path)
        metadata = metadata_by_path.get(path)
        if value is MISSING:
            if path not in declared_missing and rule["requiredness"] != "OPTIONAL":
                severity, blocking = _missing_severity(rule["requiredness"])
                add_issue(
                    make_issue(
                        "MISSING_INFORMATION",
                        severity,
                        f"Confirmed mapping rule {rule['rule_id']} expected absent field {path}.",
                        source_paths=[path],
                        blocking=blocking,
                        details={"rule_id": rule["rule_id"], "requiredness": rule["requiredness"]},
                    )
                )
            continue
        if metadata:
            state_issue = _metadata_state_issue(rule, metadata)
            if state_issue:
                add_issue(state_issue)
                continue
        if value is None:
            add_issue(
                make_issue(
                    "MISSING_INFORMATION",
                    "ERROR",
                    f"Explicit null at {path} cannot identify an entity.",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"value_state": "EXPLICIT_NULL", "rule_id": rule["rule_id"]},
                )
            )
            continue
        if not _matches_source_type(value, rule["source_value_type"]):
            add_issue(
                make_issue(
                    "UNSUPPORTED",
                    "ERROR",
                    f"{path} does not match source_value_type {rule['source_value_type']}.",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"actual_type": json_value_type(value), "rule_id": rule["rule_id"]},
                )
            )
            continue
        try:
            proposed_iri = transform_value(
                rule["transformation_id"],
                value,
                context=rule,
            )
        except TransformationError as exc:
            add_issue(
                make_issue(
                    "UNSUPPORTED",
                    "ERROR",
                    f"Transform failed for {path}: {exc}",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"rule_id": rule["rule_id"], "original_value": value},
                )
            )
            continue
        candidate = _candidate_common(rule, metadata, policy)
        candidate.update({"proposed_iri": proposed_iri, "class_iri": rule["target_term_iri"]})
        _add_candidate_id(candidate)
        generated_entities[rule["rule_id"]] = candidate
        candidate_entities.append(candidate)

    # Second pass: only finite, explicitly wired assertion rules execute.
    for rule in confirmed_rules:
        if rule["candidate_kind"] == "ENTITY":
            continue
        path = rule["source_selector"]
        if path in conflicts:
            continue
        value = resolve_pointer(data, path)
        metadata = metadata_by_path.get(path)
        if value is MISSING:
            if path not in declared_missing and rule["requiredness"] != "OPTIONAL":
                severity, blocking = _missing_severity(rule["requiredness"])
                add_issue(
                    make_issue(
                        "MISSING_INFORMATION",
                        severity,
                        f"Confirmed mapping rule {rule['rule_id']} expected absent field {path}.",
                        source_paths=[path],
                        blocking=blocking,
                        details={"rule_id": rule["rule_id"], "requiredness": rule["requiredness"]},
                    )
                )
            continue
        if metadata:
            state_issue = _metadata_state_issue(rule, metadata)
            if state_issue:
                add_issue(state_issue)
                continue
        if value is None and not rule.get("allow_null", False):
            add_issue(
                make_issue(
                    "MISSING_INFORMATION",
                    "ERROR",
                    f"Explicit null at {path} is preserved and rejected by rule {rule['rule_id']}.",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"value_state": "EXPLICIT_NULL", "rule_id": rule["rule_id"]},
                )
            )
            continue
        if value is not None and not _matches_source_type(value, rule["source_value_type"]):
            add_issue(
                make_issue(
                    "UNSUPPORTED",
                    "ERROR",
                    f"{path} does not match source_value_type {rule['source_value_type']}.",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"actual_type": json_value_type(value), "rule_id": rule["rule_id"]},
                )
            )
            continue
        subject = generated_entities.get(rule.get("subject_entity_rule_id"))
        if subject is None:
            add_issue(
                make_issue(
                    "MISSING_INFORMATION",
                    "BLOCKING" if rule["requiredness"] == "REQUIRED_FOR_PROPOSAL" else "WARNING",
                    f"Assertion rule {rule['rule_id']} has no generated subject entity.",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    blocking=rule["requiredness"] == "REQUIRED_FOR_PROPOSAL",
                    details={"rule_id": rule["rule_id"], "subject_entity_rule_id": rule.get("subject_entity_rule_id")},
                )
            )
            continue
        common = _candidate_common(rule, metadata, policy)
        candidate: dict[str, Any] = {
            **common,
            "candidate_kind": rule["candidate_kind"],
            "subject_ref": subject["candidate_id"],
        }
        try:
            transformed = (
                None
                if value is None
                else transform_value(rule["transformation_id"], value, context=rule)
            )
        except TransformationError as exc:
            add_issue(
                make_issue(
                    "UNSUPPORTED",
                    "ERROR",
                    f"Transform failed for {path}: {exc}",
                    source_paths=[path],
                    source_refs=_source_refs(metadata),
                    details={"rule_id": rule["rule_id"], "original_value": value},
                )
            )
            continue
        kind = rule["candidate_kind"]
        if kind == "DATA_PROPERTY_ASSERTION":
            candidate["predicate_iri"] = rule["target_term_iri"]
            candidate["object"] = {
                "value": transformed,
                "datatype_iri": rule.get("target_datatype")
                or _DEFAULT_DATATYPES.get(json_value_type(value), _XSD + "string"),
            }
        elif kind == "OBJECT_PROPERTY_ASSERTION":
            obj = generated_entities.get(rule.get("object_entity_rule_id"))
            if obj is None:
                add_issue(
                    make_issue(
                        "MISSING_INFORMATION",
                        "WARNING",
                        f"Assertion rule {rule['rule_id']} has no generated object entity.",
                        source_paths=[path],
                        source_refs=_source_refs(metadata),
                        details={"rule_id": rule["rule_id"], "object_entity_rule_id": rule.get("object_entity_rule_id")},
                    )
                )
                continue
            candidate["predicate_iri"] = rule["target_term_iri"]
            candidate["object"] = obj["candidate_id"]
        elif kind == "CLASS_ASSERTION":
            candidate["class_iri"] = rule["target_term_iri"]
        elif kind == "MAPPING_ASSERTION":
            candidate["predicate_iri"] = rule["target_term_iri"]
            candidate["object"] = {"value": transformed}
        else:
            raise ValueError(f"unsupported Stage 04 candidate kind: {kind}")
        _add_candidate_id(candidate)
        candidate_assertions.append(candidate)

    candidate_entities.sort(key=_candidate_sort_key)
    candidate_assertions.sort(key=_candidate_sort_key)

    # Evidence gaps and low confidence remain issues, never decisions.
    for candidate in [*candidate_entities, *candidate_assertions]:
        if not candidate["business_fact_evidence_refs"]:
            add_issue(
                make_issue(
                    "INCONSISTENT_SOURCE",
                    "WARNING",
                    "Candidate has no field-level business source reference.",
                    source_paths=candidate["source_paths"],
                    related_candidate_ids=[candidate["candidate_id"]],
                )
            )
        if candidate["confidence"]["level"] in {"LOW", "UNKNOWN"}:
            add_issue(
                make_issue(
                    "LOW_CONFIDENCE",
                    "WARNING",
                    "Candidate confidence is insufficient for unattended use and still requires review.",
                    source_paths=candidate["source_paths"],
                    source_refs=candidate["business_fact_evidence_refs"],
                    related_candidate_ids=[candidate["candidate_id"]],
                    details={"confidence": deepcopy(candidate["confidence"])},
                )
            )

    unmapped_fields: list[dict[str, Any]] = []
    for path, value in iter_leaf_fields(data):
        if path in executable_paths:
            continue
        metadata = metadata_by_path.get(path)
        term_matches = _term_alias_matches(path, profile)
        field = {
            "path": path,
            "value_type": json_value_type(value),
            "source_refs": _source_refs(metadata),
            "reason": "NO_CONFIRMED_MAPPING_RULE",
            "candidate_term_matches": term_matches,
            "review_required": True,
        }
        unmapped_fields.append(field)
        add_issue(
            make_issue(
                "AMBIGUOUS" if len(term_matches) > 1 else "UNSUPPORTED",
                "WARNING",
                f"No confirmed mapping rule covers {path}; no ontology term was minted.",
                source_paths=[path],
                source_refs=field["source_refs"],
                details={"candidate_term_matches": term_matches},
            )
        )
    unmapped_fields.sort(key=lambda item: item["path"])
    sorted_issues = sorted(issues.values(), key=issue_sort_key)

    proposal: dict[str, Any] = {
        "contract_version": "1.0",
        "run_mode": RUN_MODE,
        "input_snapshot": {
            "input_id": input_id(cleaned),
            "document_id": cleaned["document_id"],
            "dataset_id": cleaned["dataset_id"],
            "input_contract_version": cleaned["contract_version"],
            "input_semantic_hash": input_semantic_hash(cleaned),
        },
        "dependency_snapshot": _dependency_snapshot(baseline, rules_document, profile, policy),
        "candidate_entities": candidate_entities,
        "candidate_assertions": candidate_assertions,
        "schema_delta_candidates": [],
        "issues": sorted_issues,
        "unmapped_fields": unmapped_fields,
        "summary": {
            "candidate_entity_count": len(candidate_entities),
            "candidate_assertion_count": len(candidate_assertions),
            "issue_count": len(sorted_issues),
            "unmapped_field_count": len(unmapped_fields),
            "schema_delta_count": 0,
        },
    }
    proposal["proposal_semantic_hash"] = proposal_semantic_hash(proposal)
    proposal["proposal_id"] = proposal_id(proposal)
    validate_modeling_proposal_semantics(proposal, cleaned, rules_document)
    return proposal
