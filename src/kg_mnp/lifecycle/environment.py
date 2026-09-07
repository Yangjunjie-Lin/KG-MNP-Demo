"""Audited environment selection and explicit historical rollback."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash

from .errors import LifecycleError
from .guards import head, package_record, record_by_id, release_record
from .registry.events import append_event
from .registry.manifest import load_manifest
from .security import human
from .store import bind_identity, list_records, save


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def init_environment(workspace: Path | str, *, environment_name: str, environment_class: str = "DEVELOPMENT", allowed_package_names: list[str] | None = None, allowed_ontology_iris: list[str] | None = None, activation_roles: list[str] | None = None, activation_quorum: int = 1, rollback_roles: list[str] | None = None, rollback_quorum: int = 1, **extra) -> dict:
    root = Path(workspace)
    manifest = load_manifest(root)
    value = {"manifest_kind": "KG_MNP_ENVIRONMENT_MANIFEST", "schema_version": "1.0.0", "registry_id": manifest["registry_id"], "environment_name": environment_name, "environment_class": environment_class, "allowed_package_names": sorted(allowed_package_names or []), "allowed_ontology_iris": sorted(allowed_ontology_iris or []), "allowed_release_types": sorted(extra.pop("allowed_release_types", ["INITIAL_RELEASE", "PATCH_COMPATIBLE", "MINOR", "MAJOR"])), "activation_roles": sorted(activation_roles or ["RELEASE_MANAGER"]), "activation_quorum": activation_quorum, "rollback_roles": sorted(rollback_roles or ["RELEASE_MANAGER"]), "rollback_quorum": rollback_quorum, "breaking_release_policy": extra.pop("breaking_release_policy", "REQUIRE_EXPLICIT_ACK"), "pointer_policy": extra.pop("pointer_policy", "CAS_GENERATION"), "status": "ACTIVE", **extra}
    bind_identity(value, "environment_id", "environment-manifest")
    save(root, f"records/environments/{value['environment_id'].rsplit(':', 1)[1]}.json", value)
    pointer = {"manifest_kind": "KG_MNP_ENVIRONMENT_POINTER", "schema_version": "1.0.0", "registry_id": manifest["registry_id"], "environment_id": value["environment_id"], "generation": 0, "active_release_id": None, "active_package_id": None, "active_package_version": None, "active_release_attestation_id": None, "previous_pointer_hash": None, "selection_status": "NO_RELEASE_SELECTED"}
    bind_identity(pointer, "pointer_id", "environment-pointer")
    pointer["pointer_hash"] = pointer["content_digest"]
    save(root, f"state/environment-pointer-{value['environment_id'].rsplit(':', 1)[1]}.json", pointer)
    append_event(root, "EnvironmentCreated", {"subject_id": value["environment_id"]})
    return value


def _pointer(root: Path, environment_id: str) -> tuple[Path, dict[str, Any]]:
    path = root / "state" / f"environment-pointer-{environment_id.rsplit(':', 1)[1]}.json"
    if not path.is_file():
        raise LifecycleError("ENVIRONMENT_INVALID", "environment pointer not found")
    try:
        return path, json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "environment pointer is invalid") from exc


def _environment(root: Path, environment_id: str) -> dict[str, Any]:
    return record_by_id(root, "records/environments", "environment_id", environment_id)


def _proposal(root: Path, proposal_id: str) -> dict[str, Any]:
    return record_by_id(root, "records/activation-proposals", "activation_proposal_id", proposal_id)


def _decision(root: Path, decision_id: str) -> dict[str, Any]:
    return record_by_id(root, "records/activation-reviews", "decision_id", decision_id)


def _release_target(root: Path, release_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    release = release_record(root, release_id)
    package = package_record(root, release.get("package_id"))
    attestations = [item for item in list_records(root, "records/attestations") if item.get("release_id") == release_id and item.get("attestation_status") == "VERIFIED"]
    if not attestations:
        raise LifecycleError("ACTIVATION_BLOCKED", "release has no verified attestation")
    return release, package, attestations[-1]


def propose_activation(workspace: Path | str, *, environment_id: str, release_id: str, rationale: str, requested_by: str = "operator", activation_kind: str = "ACTIVATE") -> dict:
    root = Path(workspace)
    env = _environment(root, environment_id)
    _release_target(root, release_id)
    _path, pointer = _pointer(root, environment_id)
    if activation_kind == "ROLLBACK":
        historical = {item.get("target_release_id") for item in list_records(root, "records/activation-receipts") if item.get("environment_id") == environment_id and item.get("execution_status") == "APPLIED"}
        if release_id not in historical:
            raise LifecycleError("ROLLBACK_BLOCKED", "rollback target was never successfully activated in this environment")
    value = {"manifest_kind": "KG_MNP_ACTIVATION_PROPOSAL", "schema_version": "1.0.0", "registry_id": env["registry_id"], "environment_id": environment_id, "activation_kind": activation_kind, "base_pointer_generation": pointer["generation"], "base_pointer_hash": pointer["pointer_hash"], "target_release_id": release_id, "target_package_id": None, "release_attestation_id": None, "rationale": rationale, "requested_by": requested_by, "proposal_status": "PROPOSED"}
    release, package, attestation = _release_target(root, release_id)
    value["target_package_id"] = package["package_id"]
    value["release_attestation_id"] = attestation["attestation_id"]
    bind_identity(value, "activation_proposal_id", "activation-proposal")
    save(root, f"records/activation-proposals/{value['activation_proposal_id'].rsplit(':', 1)[1]}.json", value)
    append_event(root, "ActivationProposed", {"subject_id": value["activation_proposal_id"], "target_environment_id": environment_id, "target_release_id": release["release_id"]})
    return value


def review_activation(workspace: Path | str, *, proposal_id: str, decision: str, reviewer_id: str, reviewer_roles: list[str] | None = None, rationale: str = "", breaking_change_acknowledged: bool = False) -> dict:
    root = Path(workspace)
    proposal = _proposal(root, proposal_id)
    env = _environment(root, proposal["environment_id"])
    human(reviewer_id, "HUMAN", True)
    expected_roles = set(env["rollback_roles"] if proposal.get("activation_kind") == "ROLLBACK" else env["activation_roles"])
    actual_roles = sorted(set(reviewer_roles or []))
    if not expected_roles.intersection(actual_roles):
        raise LifecycleError("ACTIVATION_BLOCKED", "reviewer does not hold an environment approval role")
    allowed = {"APPROVE_ROLLBACK", "APPROVE"} if proposal.get("activation_kind") == "ROLLBACK" else {"APPROVE_ACTIVATION", "APPROVE"}
    if decision not in allowed | {"REJECT"}:
        raise LifecycleError("ACTIVATION_BLOCKED", "decision does not match operation")
    value = {"manifest_kind": "KG_MNP_ACTIVATION_REVIEW_DECISION", "schema_version": "1.0.0", "registry_id": proposal["registry_id"], "activation_proposal_id": proposal_id, "environment_id": proposal["environment_id"], "decision": decision, "reviewer_id": reviewer_id, "reviewer_roles": actual_roles, "reviewer_type": "HUMAN", "rationale": rationale, "explicit_human_action": True, "breaking_change_acknowledged": breaking_change_acknowledged, "semantic_decision_hash": semantic_hash({"proposal": proposal, "decision": decision, "reviewer": reviewer_id, "roles": actual_roles, "rationale": rationale}), "observed_at": _now()}
    bind_identity(value, "decision_id", "activation-review-decision")
    value["semantic_decision_hash"] = semantic_hash({k: v for k, v in value.items() if k not in {"semantic_decision_hash", "content_digest", "decision_id", "observed_at"}})
    save(root, f"records/activation-reviews/{value['decision_id'].rsplit(':', 1)[1]}.json", value)
    append_event(root, "ActivationReviewed", {"subject_id": value["decision_id"], "activation_proposal_id": proposal_id})
    return value


def execute_activation(workspace: Path | str, *, proposal_id: str, decision_id: str, expected_generation: int, expected_pointer_hash: str, expected_registry_head_hash: str, reviewer_id: str | None = None, breaking_change_acknowledged: bool = False) -> dict:
    root = Path(workspace)
    proposal = _proposal(root, proposal_id)
    decision = _decision(root, decision_id)
    env = _environment(root, proposal["environment_id"])
    if decision.get("activation_proposal_id") != proposal_id or decision.get("environment_id") != proposal["environment_id"]:
        raise LifecycleError("ACTIVATION_BLOCKED", "decision is not bound to current proposal and environment")
    if decision.get("reviewer_type") != "HUMAN" or decision.get("explicit_human_action") is not True:
        raise LifecycleError("ACTIVATION_BLOCKED", "human approval is required")
    allowed = {"APPROVE_ROLLBACK", "APPROVE"} if proposal.get("activation_kind") == "ROLLBACK" else {"APPROVE_ACTIVATION", "APPROVE"}
    if decision.get("decision") not in allowed:
        raise LifecycleError("ACTIVATION_BLOCKED", "activation review did not approve")
    if not breaking_change_acknowledged and not decision.get("breaking_change_acknowledged") and env.get("breaking_release_policy") == "REQUIRE_EXPLICIT_ACK":
        raise LifecycleError("ACTIVATION_BLOCKED", "explicit activation acknowledgement required")
    current_head = head(root)
    if current_head.get("head_hash") != expected_registry_head_hash:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "registry head changed")
    path, pointer = _pointer(root, proposal["environment_id"])
    if pointer.get("generation") != expected_generation or pointer.get("pointer_hash") != expected_pointer_hash:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "environment pointer changed")
    release, package, attestation = _release_target(root, proposal["target_release_id"])
    if proposal.get("target_package_id") != package.get("package_id") or proposal.get("release_attestation_id") != attestation.get("attestation_id"):
        raise LifecycleError("ACTIVATION_BLOCKED", "proposal target closure changed")
    old_hash = pointer.get("pointer_hash")
    new = {**pointer, "generation": pointer["generation"] + 1, "active_release_id": release["release_id"], "active_package_id": package["package_id"], "active_package_version": package["package_version"], "active_release_attestation_id": attestation["attestation_id"], "selection_status": "CONTROL_PLANE_SELECTED", "previous_pointer_hash": old_hash}
    bind_identity(new, "pointer_id", "environment-pointer")
    new["pointer_hash"] = new["content_digest"]
    save(root, path.relative_to(root).as_posix(), new)
    event = append_event(root, "RollbackApplied" if proposal.get("activation_kind") == "ROLLBACK" else "ActivationApplied", {"subject_id": proposal_id, "related_ids": [decision_id, release["release_id"], package["package_id"]], "target_environment_id": env["environment_id"]})
    receipt = {"manifest_kind": "KG_MNP_ACTIVATION_EXECUTION_RECEIPT", "schema_version": "1.0.0", "registry_id": env["registry_id"], "activation_proposal_id": proposal_id, "activation_review_decision_id": decision_id, "environment_id": env["environment_id"], "old_pointer_hash": old_hash, "new_pointer_hash": new["pointer_hash"], "old_generation": pointer["generation"], "new_generation": new["generation"], "target_release_id": release["release_id"], "target_package_id": package["package_id"], "verification_evidence": ["registry-head-cas-verified", "pointer-cas-verified", "release-attestation-verified"], "registry_event_id": event["event_id"], "execution_status": "ROLLED_BACK" if proposal.get("activation_kind") == "ROLLBACK" else "APPLIED", "observed_at": _now()}
    bind_identity(receipt, "execution_id", "activation-execution-receipt")
    save(root, f"records/activation-receipts/{receipt['execution_id'].rsplit(':', 1)[1]}.json", receipt)
    return receipt


def list_environments(workspace: Path | str):
    return list_records(workspace, "records/environments")


def activate(workspace: Path | str, *, environment_id: str, release_id: str, reviewer_id: str, reviewer_roles: list[str] | None = None, rationale: str = "", breaking_change_acknowledged: bool = False, expected_generation: int | None = None, expected_pointer_hash: str | None = None, proposal_id: str | None = None, decision_id: str | None = None, expected_registry_head_hash: str | None = None) -> dict:
    if not proposal_id or not decision_id or expected_generation is None or not expected_pointer_hash or not expected_registry_head_hash:
        raise LifecycleError("ACTIVATION_BLOCKED", "activation requires proposal, decision and complete CAS")
    proposal = _proposal(Path(workspace), proposal_id)
    if proposal.get("target_release_id") != release_id or proposal.get("environment_id") != environment_id:
        raise LifecycleError("ACTIVATION_BLOCKED", "activation arguments do not match approved proposal")
    return execute_activation(workspace, proposal_id=proposal_id, decision_id=decision_id, expected_generation=expected_generation, expected_pointer_hash=expected_pointer_hash, expected_registry_head_hash=expected_registry_head_hash, reviewer_id=reviewer_id, breaking_change_acknowledged=breaking_change_acknowledged)


def rollback(workspace: Path | str, *, environment_id: str, target_release_id: str, reviewer_id: str, proposal_id: str | None = None, decision_id: str | None = None, expected_generation: int | None = None, expected_pointer_hash: str | None = None, expected_registry_head_hash: str | None = None) -> dict:
    if not proposal_id or not decision_id or expected_generation is None or not expected_pointer_hash or not expected_registry_head_hash:
        raise LifecycleError("ROLLBACK_BLOCKED", "rollback requires an approved proposal and complete CAS")
    proposal = _proposal(Path(workspace), proposal_id)
    if proposal.get("activation_kind") != "ROLLBACK" or proposal.get("target_release_id") != target_release_id or proposal.get("environment_id") != environment_id:
        raise LifecycleError("ROLLBACK_BLOCKED", "rollback target does not match approved proposal")
    return execute_activation(workspace, proposal_id=proposal_id, decision_id=decision_id, expected_generation=expected_generation, expected_pointer_hash=expected_pointer_hash, expected_registry_head_hash=expected_registry_head_hash, reviewer_id=reviewer_id, breaking_change_acknowledged=True)
