"""Versioned historical probe and attestation projections; no runtime executor."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from kg_mnp.modeling.canonical_json import semantic_hash


def project_historical_artifact_documents(
    *,
    commit_sha: str,
    authority: Any,
    production_initial_registry: dict[str, Any],
    production_initial_pointer: dict[str, Any],
    production_final_registry: dict[str, Any],
    production_final_pointer: dict[str, Any],
    production_final_state: dict[str, Any],
    fixture: dict[str, Any],
    workflow: dict[str, Any],
    probes: list[dict[str, Any]],
    supplemental_probes: list[dict[str, Any]],
    race: dict[str, Any],
    repository_hashes: dict[str, str],
    publication_hashes: dict[str, str],
    cleanup: dict[str, Any],
    determinism_runs: int,
    determinism_passed: int,
) -> dict[str, dict[str, Any]]:
    controlled_authority = fixture["authority"]
    p0 = controlled_authority.base_publication
    p1 = controlled_authority.activation_candidates[0]
    final_state = workflow["final_state"]
    production_pointer_unchanged = bool(
        production_initial_registry == production_final_registry
        and production_initial_pointer == production_final_pointer
    )
    production_evidence = {
        "production_base_publication_id": authority.base_publication.publication_id,
        "production_base_publication_hash": (
            authority.base_publication.publication_semantic_hash
        ),
        "production_base_repository_id": authority.base_publication.repository_id,
        "production_base_repository_hash": (
            authority.base_publication.repository_semantic_hash
        ),
        "production_activation_candidates": (
            authority.production_activation_candidate_count
        ),
        "production_activation_cycles": production_final_state["activation_cycles"],
        "production_rollback_cycles": production_final_state["rollback_cycles"],
        "production_pointer_initial_hash": production_initial_pointer["pointer_hash"],
        "production_pointer_final_hash": production_final_pointer["pointer_hash"],
        "production_pointer_unchanged": production_pointer_unchanged,
    }
    controlled_evidence = {
        "controlled_fixture_hash": controlled_authority.controlled_fixture_hash,
        "controlled_p0_publication_hash": p0.publication_semantic_hash,
        "controlled_p1_publication_hash": p1.publication_semantic_hash,
        "controlled_p0_repository_hash": p0.repository_semantic_hash,
        "controlled_p1_repository_hash": p1.repository_semantic_hash,
        "controlled_activation_cycles": final_state["activation_cycles"],
        "controlled_rollback_cycles": final_state["rollback_cycles"],
        "controlled_initial_generation": workflow["initial_pointer"]["generation"],
        "controlled_post_activation_generation": workflow["post_activation_state"][
            "current_pointer"
        ]["generation"],
        "controlled_final_generation": workflow["final_pointer"]["generation"],
        "p0_repository_before_hash": repository_hashes["p0_before"],
        "p0_repository_after_activation_hash": repository_hashes["p0_after_activation"],
        "p0_repository_after_rollback_hash": repository_hashes["p0_after_rollback"],
        "p1_repository_before_hash": repository_hashes["p1_before"],
        "p1_repository_after_activation_hash": repository_hashes["p1_after_activation"],
        "p1_repository_after_rollback_hash": repository_hashes["p1_after_rollback"],
        "p0_publication_tree_before_hash": publication_hashes["p0_before"],
        "p0_publication_tree_after_hash": publication_hashes["p0_after"],
        "p1_publication_tree_before_hash": publication_hashes["p1_before"],
        "p1_publication_tree_after_hash": publication_hashes["p1_after"],
        "determinism_runs": determinism_runs,
        "determinism_passed": determinism_passed,
    }
    physical_identities = {
        "stage08_identity": authority.stage08_artifact_tree_sha256,
        "phase01_identity": authority.phase01_artifact_tree_sha256,
        "phase02_identity": authority.phase02_artifact_tree_sha256,
        "phase03_identity": authority.phase03_artifact_tree_sha256,
        "phase04_identity": authority.phase04_artifact_tree_sha256,
        "phase05_identity": authority.phase05_artifact_tree_sha256,
    }
    attestation = build_application_phase06_attestation(
        commit_sha=commit_sha,
        physical_identities=physical_identities,
        production_evidence=production_evidence,
        controlled_evidence=controlled_evidence,
        probe_records=probes,
    )
    production_summary = {
        "activation_candidates": authority.production_activation_candidate_count,
        "activation_cycles": production_final_state["activation_cycles"],
        "rollback_cycles": production_final_state["rollback_cycles"],
        "initial_pointer": production_initial_pointer,
        "final_pointer": production_final_pointer,
        "pointer_unchanged": production_pointer_unchanged,
        "bootstrap_registry": production_initial_registry,
        "status": "PRODUCTION_BOOTSTRAP_CURRENT_REFERENCE_VERIFIED",
    }
    controlled_summary = {
        "fixture_id": controlled_authority.fixture_id,
        "controlled_fixture_hash": controlled_authority.controlled_fixture_hash,
        "test_only": True,
        "production_authority": False,
        "p0": p0.descriptor,
        "p1": p1.descriptor,
        "initial_pointer": workflow["initial_pointer"],
        "activation_proposal": workflow["activation_proposal"],
        "activation_review_decision": workflow["activation_review_decision"],
        "activation_receipt": workflow["activation_receipt"],
        "post_activation_pointer": workflow["post_activation_state"]["current_pointer"],
        "resolved_p1": workflow["resolved_p1"],
        "final_registry": workflow["final_registry"],
        "final_pointer": workflow["final_pointer"],
        "status": "CONTROLLED_ACTIVATION_VERIFIED",
    }
    activation_summary = {
        "contract_version": "1.0",
        "production_activation_summary": production_summary,
        "controlled_activation_summary": controlled_summary,
        "controlled_registry_hash": final_state["registry_hash"],
        "controlled_head_event_hash": final_state["head_event_hash"],
        "status": "PASS",
    }
    rollback_summary = {
        "contract_version": "1.0",
        "test_only": True,
        "production_authority": False,
        "rollback_is_pointer_selection_only": True,
        "rdf_reverse_patch_used": False,
        "repository_mutation_by_controller": False,
        "from_publication_id": p1.publication_id,
        "to_publication_id": p0.publication_id,
        "rollback_proposal": workflow["rollback_proposal"],
        "rollback_review_decision": workflow["rollback_review_decision"],
        "rollback_receipt": workflow["rollback_receipt"],
        "generation_sequence": [0, 1, 2],
        "repository_hashes": repository_hashes,
        "publication_tree_hashes": publication_hashes,
        "final_active_publication_id": workflow["resolved_p0"]["active_publication_id"],
        "status": "CONTROLLED_ROLLBACK_VERIFIED",
    }
    security_summary = {
        "contract_version": "1.0",
        "test_only": True,
        "production_authority": False,
        "probe_records": probes,
        "supplemental_probe_records": supplemental_probes,
        "counters": aggregate_probe_records(probes),
        "concurrency_result": race,
        "activation_controller_graphdb_access": [
            "repository_info",
            "export_explicit_nquads",
        ],
        "cleanup": cleanup,
        "status": "PASS",
    }
    return {
        "application-phase06-attestation.json": attestation,
        "activation-summary.json": activation_summary,
        "rollback-summary.json": rollback_summary,
        "authority-binding.json": {
            "contract_version": "1.0",
            **authority.binding,
            "status": "PASS",
        },
        "security-summary.json": security_summary,
    }

from .contracts import (
    APPLICATION_PHASE06_STATUS,
    ActivationContractError,
    validate_activation_contract,
)
from .errors import ActivationError, ActivationErrorCode

PROBE_FIELDS = frozenset(
    {"probe_id", "attack", "expected_code", "observed_code", "blocked", "details"}
)
PROBE_PREFIX = "urn:kg-mnp:test-fixture:phase06:probe:"
PROBE_ID = re.compile(r"^urn:kg-mnp:test-fixture:phase06:probe:[0-9a-f]{64}$")
MACHINE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_FORBIDDEN_DETAILS = re.compile(
    r"(?ix)"
    r"(?:\b(?:timestamp|hostname|process[ _-]?id|pid|port|container[ _-]?id)\b\s*[:=])"
    r"|(?:\bfile://)"
    r"|(?:[a-z]:[\\/])"
    r"|(?:(?:^|\s)/(?:home|tmp|var|users?|workspace)/)"
    r"|(?:(?:^|[\\/])\.\.(?:[\\/]|$))"
    r"|(?:%2e|%2f|%5c)"
    r"|(?:\b\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2})"
)

# The attack name is the stable aggregation category.  Multiple executed probes
# may share a category when their deterministic ``details`` distinguish the
# actual attack (for example event insertion, deletion, reorder, and rehash).
ATTACK_COUNTER_FIELDS: dict[str, tuple[str, str]] = {
    "activation_review": ("activation_review_attempts", "activation_review_approved"),
    "unverified_target": (
        "unverified_target_attempts",
        "unverified_target_blocked",
    ),
    "fixture_laundering": (
        "fixture_laundering_attempts",
        "fixture_laundering_blocked",
    ),
    "pointer_tamper": ("pointer_tamper_attempts", "pointer_tamper_blocked"),
    "event_rehash": ("event_rehash_attempts", "event_rehash_blocked"),
    "stale_pointer": ("stale_pointer_attempts", "stale_pointer_blocked"),
    "concurrency": ("concurrency_attempts", "concurrency_blocked"),
    "replay": ("replay_attempts", "replay_blocked"),
    "missing_repository": (
        "missing_repository_attempts",
        "missing_repository_blocked",
    ),
    "repository_mismatch": (
        "repository_mismatch_attempts",
        "repository_mismatch_blocked",
    ),
    "direct_graph_mutation": (
        "direct_graph_mutation_attempts",
        "direct_graph_mutation_blocked",
    ),
    "semantic_escalation": (
        "semantic_escalation_attempts",
        "semantic_escalation_blocked",
    ),
    "auto_activation": (
        "auto_activation_attempts",
        "auto_activation_blocked",
    ),
    "unknown_rollback": (
        "unknown_rollback_attempts",
        "unknown_rollback_blocked",
    ),
}

EXPECTED_CODES: dict[str, frozenset[str]] = {
    "activation_review": frozenset(
        {
            "APPROVE_FOR_ACTIVATION",
            "APPROVED_FOR_ACTIVATION",
            "REJECT",
            "REJECTED",
            "DEFER",
            "DEFERRED",
        }
    ),
    "unverified_target": frozenset({"UNVERIFIED_ACTIVATION_TARGET"}),
    "fixture_laundering": frozenset(
        {
            "AUTHORITY_MISMATCH",
            "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET",
        }
    ),
    "pointer_tamper": frozenset({"POINTER_TAMPERED", "REGISTRY_TAMPERED"}),
    "event_rehash": frozenset(
        {"EVENT_CHAIN_TAMPERED", "REGISTRY_TAMPERED", "AUTHORITY_MISMATCH"}
    ),
    "stale_pointer": frozenset({"ACTIVATION_CONCURRENCY_CONFLICT"}),
    "concurrency": frozenset({"ACTIVATION_CONCURRENCY_CONFLICT"}),
    "replay": frozenset({"REPLAY_DETECTED"}),
    "missing_repository": frozenset({"TARGET_REPOSITORY_UNAVAILABLE"}),
    "repository_mismatch": frozenset({"TARGET_REPOSITORY_HASH_MISMATCH"}),
    "direct_graph_mutation": frozenset(
        {"DIRECT_GRAPH_MUTATION_BLOCKED", "INVALID_ACTIVATION_REQUEST"}
    ),
    "semantic_escalation": frozenset(
        {"SEMANTIC_AUTHORITY_ESCALATION_BLOCKED", "INVALID_ACTIVATION_REQUEST"}
    ),
    "auto_activation": frozenset(
        {"AUTO_ACTIVATION_BLOCKED", "HUMAN_ACTIVATION_APPROVAL_REQUIRED"}
    ),
    "unknown_rollback": frozenset({"UNKNOWN_ROLLBACK_TARGET"}),
}

_APPROVED_REVIEW_CODES = frozenset(
    {"APPROVE_FOR_ACTIVATION", "APPROVED_FOR_ACTIVATION"}
)

PHYSICAL_IDENTITY_FIELDS = frozenset(
    {
        "stage08_identity",
        "phase01_identity",
        "phase02_identity",
        "phase03_identity",
        "phase04_identity",
        "phase05_identity",
    }
)
PRODUCTION_EVIDENCE_FIELDS = frozenset(
    {
        "production_base_publication_id",
        "production_base_publication_hash",
        "production_base_repository_id",
        "production_base_repository_hash",
        "production_activation_candidates",
        "production_activation_cycles",
        "production_rollback_cycles",
        "production_pointer_initial_hash",
        "production_pointer_final_hash",
        "production_pointer_unchanged",
    }
)
CONTROLLED_EVIDENCE_FIELDS = frozenset(
    {
        "controlled_fixture_hash",
        "controlled_p0_publication_hash",
        "controlled_p1_publication_hash",
        "controlled_p0_repository_hash",
        "controlled_p1_repository_hash",
        "controlled_activation_cycles",
        "controlled_rollback_cycles",
        "controlled_initial_generation",
        "controlled_post_activation_generation",
        "controlled_final_generation",
        "p0_repository_before_hash",
        "p0_repository_after_activation_hash",
        "p0_repository_after_rollback_hash",
        "p1_repository_before_hash",
        "p1_repository_after_activation_hash",
        "p1_repository_after_rollback_hash",
        "p0_publication_tree_before_hash",
        "p0_publication_tree_after_hash",
        "p1_publication_tree_before_hash",
        "p1_publication_tree_after_hash",
        "determinism_runs",
        "determinism_passed",
    }
)


def probe_identity_content(probe: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "attack": probe["attack"],
        "expected_code": probe["expected_code"],
        "observed_code": probe["observed_code"],
        "blocked": probe["blocked"],
        "details": probe["details"],
    }


def _probe_id(probe: Mapping[str, Any]) -> str:
    return PROBE_PREFIX + semantic_hash(probe_identity_content(probe))


def validate_probe_record(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one immutable executed probe and reconstruct its identity."""

    try:
        if not isinstance(probe, Mapping) or set(probe) != PROBE_FIELDS:
            raise ValueError("probe field set mismatch")
        value = deepcopy(dict(probe))
        attack = value["attack"]
        expected = value["expected_code"]
        observed = value["observed_code"]
        details = value["details"]
        if attack not in ATTACK_COUNTER_FIELDS:
            raise ValueError("unknown Phase06 probe attack")
        if (
            not isinstance(expected, str)
            or not MACHINE_CODE.fullmatch(expected)
            or expected not in EXPECTED_CODES[attack]
            or not isinstance(observed, str)
            or not MACHINE_CODE.fullmatch(observed)
            or type(value["blocked"]) is not bool
            or not isinstance(details, str)
            or not details
            or details != details.strip()
            or len(details) > 4096
            or _FORBIDDEN_DETAILS.search(details)
            or not isinstance(value["probe_id"], str)
            or not PROBE_ID.fullmatch(value["probe_id"])
            or value["probe_id"] != _probe_id(value)
        ):
            raise ValueError("invalid or tampered Phase06 probe")
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            "invalid deterministic Phase06 probe record",
        ) from exc
    return value


def build_probe_record(
    *,
    attack: str,
    expected_code: str,
    observed_code: str,
    blocked: bool,
    details: str,
) -> dict[str, Any]:
    """Build one deterministic test-namespace record from an executed outcome."""

    value = {
        "attack": attack,
        "expected_code": expected_code,
        "observed_code": observed_code,
        "blocked": blocked,
        "details": details,
    }
    value["probe_id"] = _probe_id(value)
    return validate_probe_record(value)


def aggregate_probe_records(
    probes: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Derive every attestation counter exclusively from executed records."""

    attempts: Counter[str] = Counter()
    successes: Counter[str] = Counter()
    identifiers: set[str] = set()
    for supplied in probes:
        probe = validate_probe_record(supplied)
        identifier = probe["probe_id"]
        if identifier in identifiers:
            raise ActivationError(
                ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
                "duplicate Phase06 probe record",
            )
        identifiers.add(identifier)
        attack = probe["attack"]
        attempts[attack] += 1
        outcome_matches = probe["observed_code"] == probe["expected_code"]
        if attack == "activation_review":
            if outcome_matches and probe["observed_code"] in _APPROVED_REVIEW_CODES:
                successes[attack] += 1
        elif outcome_matches and probe["blocked"] is True:
            successes[attack] += 1

    result: dict[str, int] = {}
    for attack, (attempt_field, success_field) in ATTACK_COUNTER_FIELDS.items():
        result[attempt_field] = attempts[attack]
        result[success_field] = successes[attack]
    return result


def _closed_mapping(
    value: Mapping[str, Any], fields: frozenset[str], label: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            f"{label} field set mismatch",
        )
    return deepcopy(dict(value))


def _require_success_invariants(
    production: Mapping[str, Any],
    controlled: Mapping[str, Any],
    counts: Mapping[str, int],
) -> None:
    security_pairs = [
        fields
        for attack, fields in ATTACK_COUNTER_FIELDS.items()
        if attack != "activation_review"
    ]
    production_closed = bool(
        production["production_activation_candidates"] == 0
        and production["production_activation_cycles"] == 0
        and production["production_rollback_cycles"] == 0
        and production["production_pointer_unchanged"] is True
        and production["production_pointer_initial_hash"]
        == production["production_pointer_final_hash"]
    )
    controlled_closed = bool(
        controlled["controlled_activation_cycles"] == 1
        and controlled["controlled_rollback_cycles"] == 1
        and controlled["controlled_initial_generation"] == 0
        and controlled["controlled_post_activation_generation"] == 1
        and controlled["controlled_final_generation"] == 2
        and controlled["controlled_p0_publication_hash"]
        != controlled["controlled_p1_publication_hash"]
        and controlled["controlled_p0_repository_hash"]
        != controlled["controlled_p1_repository_hash"]
        and controlled["controlled_p0_repository_hash"]
        == controlled["p0_repository_before_hash"]
        == controlled["p0_repository_after_activation_hash"]
        == controlled["p0_repository_after_rollback_hash"]
        and controlled["controlled_p1_repository_hash"]
        == controlled["p1_repository_before_hash"]
        == controlled["p1_repository_after_activation_hash"]
        == controlled["p1_repository_after_rollback_hash"]
        and controlled["p0_publication_tree_before_hash"]
        == controlled["p0_publication_tree_after_hash"]
        and controlled["p1_publication_tree_before_hash"]
        == controlled["p1_publication_tree_after_hash"]
        and type(controlled["determinism_runs"]) is int
        and controlled["determinism_runs"] >= 2
        and controlled["determinism_passed"] == controlled["determinism_runs"]
    )
    probes_closed = bool(
        counts["activation_review_attempts"] > 0
        and 0
        < counts["activation_review_approved"]
        <= counts["activation_review_attempts"]
        and all(
            counts[attempt] > 0 and counts[attempt] == counts[blocked]
            for attempt, blocked in security_pairs
        )
    )
    if not production_closed or not controlled_closed or not probes_closed:
        raise ActivationError(
            ActivationErrorCode.PHASE06_NOT_VERIFIED,
            "Phase06 attestation success invariants are not closed",
        )


def build_application_phase06_attestation(
    *,
    commit_sha: str,
    physical_identities: Mapping[str, Any],
    production_evidence: Mapping[str, Any],
    controlled_evidence: Mapping[str, Any],
    probe_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the sole successful Phase 06 attestation from physical evidence."""

    identities = _closed_mapping(
        physical_identities, PHYSICAL_IDENTITY_FIELDS, "physical identities"
    )
    production = _closed_mapping(
        production_evidence, PRODUCTION_EVIDENCE_FIELDS, "production evidence"
    )
    controlled = _closed_mapping(
        controlled_evidence, CONTROLLED_EVIDENCE_FIELDS, "controlled evidence"
    )
    counts = aggregate_probe_records(probe_records)
    _require_success_invariants(production, controlled, counts)
    value = {
        "contract_version": "1.0",
        "commit_sha": commit_sha,
        **identities,
        **production,
        **controlled,
        **counts,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "status": APPLICATION_PHASE06_STATUS,
    }
    try:
        validate_activation_contract("application-phase06-attestation", value)
    except ActivationContractError as exc:
        raise ActivationError(
            ActivationErrorCode.INVALID_CONTRACT,
            "application Phase06 attestation contract failed",
        ) from exc
    return value
