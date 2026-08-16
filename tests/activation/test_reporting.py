from __future__ import annotations

from copy import deepcopy

import pytest

from kg_mnp_demo.activation.contracts import validate_activation_contract
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.reporting import (
    ATTACK_COUNTER_FIELDS,
    aggregate_probe_records,
    build_application_phase06_attestation,
    build_probe_record,
    validate_probe_record,
)


def _hash(character: str) -> str:
    return character * 64


EXPECTED = {
    "activation_review": "APPROVED_FOR_ACTIVATION",
    "unverified_target": "UNVERIFIED_ACTIVATION_TARGET",
    "fixture_laundering": ("TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET"),
    "pointer_tamper": "POINTER_TAMPERED",
    "event_rehash": "REGISTRY_TAMPERED",
    "stale_pointer": "ACTIVATION_CONCURRENCY_CONFLICT",
    "concurrency": "ACTIVATION_CONCURRENCY_CONFLICT",
    "replay": "REPLAY_DETECTED",
    "missing_repository": "TARGET_REPOSITORY_UNAVAILABLE",
    "repository_mismatch": "TARGET_REPOSITORY_HASH_MISMATCH",
    "direct_graph_mutation": "DIRECT_GRAPH_MUTATION_BLOCKED",
    "semantic_escalation": "SEMANTIC_AUTHORITY_ESCALATION_BLOCKED",
    "auto_activation": "HUMAN_ACTIVATION_APPROVAL_REQUIRED",
    "unknown_rollback": "UNKNOWN_ROLLBACK_TARGET",
}


def _probe(attack: str, *, suffix: str = "primary") -> dict:
    expected = EXPECTED[attack]
    return build_probe_record(
        attack=attack,
        expected_code=expected,
        observed_code=expected,
        blocked=attack != "activation_review",
        details=f"Executed controlled {attack} probe {suffix}.",
    )


def _probes() -> list[dict]:
    return [_probe(attack) for attack in ATTACK_COUNTER_FIELDS]


def _identities() -> dict:
    return {
        "stage08_identity": "stage08-physical-identity",
        "phase01_identity": "phase01-physical-identity",
        "phase02_identity": "phase02-physical-identity",
        "phase03_identity": "phase03-physical-identity",
        "phase04_identity": "phase04-physical-identity",
        "phase05_identity": "phase05-physical-identity",
    }


def _production() -> dict:
    return {
        "production_base_publication_id": "urn:kg-mnp:e2e-publication:p0",
        "production_base_publication_hash": _hash("3"),
        "production_base_repository_id": "kg-mnp-production-p0",
        "production_base_repository_hash": _hash("4"),
        "production_activation_candidates": 0,
        "production_activation_cycles": 0,
        "production_rollback_cycles": 0,
        "production_pointer_initial_hash": _hash("5"),
        "production_pointer_final_hash": _hash("5"),
        "production_pointer_unchanged": True,
    }


def _controlled() -> dict:
    return {
        "controlled_fixture_hash": _hash("e"),
        "controlled_p0_publication_hash": _hash("a"),
        "controlled_p1_publication_hash": _hash("b"),
        "controlled_p0_repository_hash": _hash("c"),
        "controlled_p1_repository_hash": _hash("d"),
        "controlled_activation_cycles": 1,
        "controlled_rollback_cycles": 1,
        "controlled_initial_generation": 0,
        "controlled_post_activation_generation": 1,
        "controlled_final_generation": 2,
        "p0_repository_before_hash": _hash("c"),
        "p0_repository_after_activation_hash": _hash("c"),
        "p0_repository_after_rollback_hash": _hash("c"),
        "p1_repository_before_hash": _hash("d"),
        "p1_repository_after_activation_hash": _hash("d"),
        "p1_repository_after_rollback_hash": _hash("d"),
        "p0_publication_tree_before_hash": _hash("1"),
        "p0_publication_tree_after_hash": _hash("1"),
        "p1_publication_tree_before_hash": _hash("2"),
        "p1_publication_tree_after_hash": _hash("2"),
        "determinism_runs": 2,
        "determinism_passed": 2,
    }


def _attestation(probes=None, production=None, controlled=None) -> dict:
    return build_application_phase06_attestation(
        commit_sha="a" * 40,
        physical_identities=_identities(),
        production_evidence=production or _production(),
        controlled_evidence=controlled or _controlled(),
        probe_records=probes or _probes(),
    )


def test_probe_identity_is_deterministic_and_test_namespaced() -> None:
    first = _probe("pointer_tamper")
    second = _probe("pointer_tamper")
    assert first == second
    assert first["probe_id"].startswith("urn:kg-mnp:test-fixture:phase06:probe:")
    assert set(first) == {
        "probe_id",
        "attack",
        "expected_code",
        "observed_code",
        "blocked",
        "details",
    }


def test_all_counters_are_derived_from_actual_records() -> None:
    probes = _probes()
    probes.append(_probe("replay", suffix="second distinct execution"))
    counts = aggregate_probe_records(probes)
    assert counts["replay_attempts"] == counts["replay_blocked"] == 2
    assert counts["activation_review_attempts"] == 1
    assert counts["activation_review_approved"] == 1
    assert all(
        counts[attempt] == counts[success] == 1
        for attack, (attempt, success) in ATTACK_COUNTER_FIELDS.items()
        if attack not in {"activation_review", "replay"}
    )


def test_duplicate_and_unknown_probes_are_rejected() -> None:
    probe = _probe("replay")
    with pytest.raises(ActivationError) as duplicate:
        aggregate_probe_records([probe, deepcopy(probe)])
    assert duplicate.value.code == ActivationErrorCode.INVALID_ACTIVATION_REQUEST
    with pytest.raises(ActivationError) as unknown:
        build_probe_record(
            attack="invented_attack",
            expected_code="REPLAY_DETECTED",
            observed_code="REPLAY_DETECTED",
            blocked=True,
            details="Unknown attack category probe.",
        )
    assert unknown.value.code == ActivationErrorCode.INVALID_ACTIVATION_REQUEST


def test_probe_tampering_is_detected_even_when_shape_is_unchanged() -> None:
    probe = _probe("repository_mismatch")
    probe["observed_code"] = "TARGET_REPOSITORY_UNAVAILABLE"
    with pytest.raises(ActivationError) as caught:
        validate_probe_record(probe)
    assert caught.value.code == ActivationErrorCode.INVALID_ACTIVATION_REQUEST


@pytest.mark.parametrize(
    "details",
    [
        "timestamp=2026-08-16T01:02:03Z",
        "Evidence stored at C:\\runtime\\probe.json",
        "Evidence stored at /tmp/probe.json",
        "pid=1234",
    ],
)
def test_runtime_metadata_and_paths_cannot_enter_probe_identity(details) -> None:
    with pytest.raises(ActivationError) as caught:
        build_probe_record(
            attack="replay",
            expected_code="REPLAY_DETECTED",
            observed_code="REPLAY_DETECTED",
            blocked=True,
            details=details,
        )
    assert caught.value.code == ActivationErrorCode.INVALID_ACTIVATION_REQUEST


def test_attestation_is_schema_valid_and_uses_probe_counts() -> None:
    probes = _probes()
    probes.append(_probe("event_rehash", suffix="event deletion"))
    attestation = _attestation(probes=probes)
    validate_activation_contract("application-phase06-attestation", attestation)
    assert attestation["event_rehash_attempts"] == 2
    assert attestation["event_rehash_blocked"] == 2
    assert attestation["status"] == "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED"
    assert attestation["semantic_authority"] is False
    assert attestation["deployment_governance_only"] is True


def test_missing_or_failed_probe_cannot_produce_success_attestation() -> None:
    missing = [probe for probe in _probes() if probe["attack"] != "auto_activation"]
    with pytest.raises(ActivationError) as absent:
        _attestation(probes=missing)
    assert absent.value.code == ActivationErrorCode.PHASE06_NOT_VERIFIED

    failed = _probes()
    replacement = build_probe_record(
        attack="replay",
        expected_code="REPLAY_DETECTED",
        observed_code="NO_ERROR",
        blocked=False,
        details="Replay unexpectedly reached the execution boundary.",
    )
    failed = [replacement if item["attack"] == "replay" else item for item in failed]
    with pytest.raises(ActivationError) as not_blocked:
        _attestation(probes=failed)
    assert not_blocked.value.code == ActivationErrorCode.PHASE06_NOT_VERIFIED


def test_evidence_tampering_and_caller_supplied_counter_are_rejected() -> None:
    controlled = _controlled()
    controlled["p1_repository_after_rollback_hash"] = _hash("9")
    with pytest.raises(ActivationError) as drift:
        _attestation(controlled=controlled)
    assert drift.value.code == ActivationErrorCode.PHASE06_NOT_VERIFIED

    supplied_counter = _controlled()
    supplied_counter["replay_attempts"] = 99
    with pytest.raises(ActivationError) as injected:
        _attestation(controlled=supplied_counter)
    assert injected.value.code == ActivationErrorCode.INVALID_ACTIVATION_REQUEST
