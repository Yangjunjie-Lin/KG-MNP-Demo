"""Release candidate, review and publication gates.

All identity-bearing values are derived from records resolved inside the
registry.  Arguments named like package metadata are only compatibility
parameters and can never override package facts.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn

from .errors import LifecycleError
from .guards import (
    file_sha256,
    head,
    package_files,
    package_record,
    real_archive,
    record_by_id,
)
from .registry.events import append_event, read_events
from .registry.manifest import load_manifest
from .security import human
from .store import bind_identity, list_records, save


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _candidate(root: Path, identifier: str) -> dict[str, Any]:
    return record_by_id(root, "records/release-candidates", "release_candidate_id", identifier)


def _review(root: Path, identifier: str) -> dict[str, Any]:
    return record_by_id(root, "records/release-reviews", "review_id", identifier)


def create_release_candidate(
    workspace: Path | str,
    *,
    candidate_package_id: str,
    base_package_id: str | None = None,
    semantic_diff_id: str = "",
    version_compatibility_report_id: str = "",
    impact_analysis_id: str = "",
    regression_test_report_id: str = "",
    change_proposal_id: str = "",
    change_evaluation_id: str = "",
    release_policy_id: str = "",
    release_candidate_kind: str = "INITIAL",
    required_roles: list[str] | None = None,
    minimum_distinct_reviewers: int = 1,
    **extra: Any,
) -> dict[str, Any]:
    root = Path(workspace)
    manifest = load_manifest(root)
    required_roles = sorted(set(required_roles or ["RELEASE_MANAGER"]))
    if minimum_distinct_reviewers < 1:
        raise LifecycleError("RELEASE_CANDIDATE_INVALID", "reviewer quorum must be positive")
    if release_candidate_kind == "INITIAL" and base_package_id:
        raise LifecycleError("RELEASE_CANDIDATE_INVALID", "initial release cannot have a base package")
    if release_candidate_kind != "INITIAL" and not base_package_id:
        raise LifecycleError("RELEASE_CANDIDATE_INVALID", "successor release requires a base package")
    value = {
        "manifest_kind": "KG_MNP_RELEASE_CANDIDATE", "schema_version": "1.0.0", "registry_id": manifest["registry_id"],
        "release_candidate_kind": release_candidate_kind, "base_release_id": extra.pop("base_release_id", None),
        "base_package_id": base_package_id, "candidate_package_id": candidate_package_id,
        "change_proposal_id": change_proposal_id or None, "change_evaluation_id": change_evaluation_id or None,
        "semantic_diff_id": semantic_diff_id or None, "version_compatibility_report_id": version_compatibility_report_id or None,
        "impact_analysis_id": impact_analysis_id or None, "regression_test_report_id": regression_test_report_id or None,
        "release_policy_id": release_policy_id or stable_urn("release-policy", {"version": "1.0.0"}),
        "required_roles": required_roles, "alternative_roles": sorted(set(extra.pop("alternative_roles", []))),
        "minimum_distinct_reviewers": minimum_distinct_reviewers,
        "required_acknowledgements": sorted(set(extra.pop("required_acknowledgements", []))),
        "candidate_status": "SUBMITTED", **extra,
    }
    bind_identity(value, "release_candidate_id", "release-candidate")
    save(root, f"records/release-candidates/{value['release_candidate_id'].rsplit(':', 1)[1]}.json", value)
    append_event(root, "ReleaseCandidateCreated", {"subject_id": value["release_candidate_id"], "candidate_package_id": candidate_package_id})
    return value


def _quorum(candidate: dict[str, Any], actions: list[dict[str, Any]]) -> tuple[bool, set[str], set[str], set[str]]:
    approvals = [item for item in actions if item.get("action") == "APPROVE" and item.get("reviewer_type") == "HUMAN" and item.get("explicit_human_action") is True]
    reviewer_ids = {item.get("reviewer_id") for item in approvals}
    roles = {role for item in approvals for role in item.get("reviewer_roles", [])}
    acknowledgements = {ref for item in approvals for ref in item.get("acknowledgement_refs", [])}
    required = set(candidate.get("required_roles", []))
    alternatives = set(candidate.get("alternative_roles", []))
    role_ok = required.issubset(roles) or bool(alternatives & roles)
    ack_ok = set(candidate.get("required_acknowledgements", [])).issubset(acknowledgements)
    return bool(approvals) and role_ok and ack_ok and len(reviewer_ids) >= int(candidate.get("minimum_distinct_reviewers", 1)), roles, reviewer_ids, acknowledgements


def record_review(workspace: Path | str, release_candidate_id: str, *, reviewer_id: str, reviewer_roles: list[str], action: str = "APPROVE", rationale: str = "", explicit_human_action: bool = True, acknowledgement_refs: list[str] | None = None) -> dict[str, Any]:
    root = Path(workspace)
    candidate = _candidate(root, release_candidate_id)
    human(reviewer_id, "HUMAN", explicit_human_action)
    rows = [row for row in list_records(root, "records/release-reviews") if row.get("release_candidate_id") == release_candidate_id]
    if rows:
        log = rows[0]
        actions = list(log.get("actions", []))
    else:
        review_id = stable_urn("release-review", {"candidate": release_candidate_id})
        log = {"manifest_kind": "KG_MNP_RELEASE_REVIEW_DECISION_LOG", "schema_version": "1.0.0", "registry_id": candidate["registry_id"], "review_id": review_id, "review_log_id": review_id, "release_policy_id": candidate.get("release_policy_id"), "review_policy_id": None, "release_candidate_id": release_candidate_id, "actions": []}
        actions = []
    sequence = len(actions) + 1
    previous = actions[-1].get("action_hash") if actions else None
    previous_semantic = actions[-1].get("semantic_action_hash") if actions else None
    action_core = {
        "manifest_kind": "KG_MNP_RELEASE_REVIEW_ACTION", "schema_version": "1.0.0", "registry_id": candidate["registry_id"],
        "review_id": log["review_id"], "release_candidate_id": release_candidate_id, "sequence": sequence,
        "previous_action_hash": previous, "previous_semantic_action_hash": previous_semantic, "action": action,
        "reviewer_id": reviewer_id, "reviewer_roles": sorted(set(reviewer_roles)), "reviewer_type": "HUMAN",
        "explicit_human_action": explicit_human_action, "rationale": rationale, "acknowledgement_refs": sorted(set(acknowledgement_refs or [])), "observed_at": _now(),
    }
    semantic_core = {k: v for k, v in action_core.items() if k not in {"observed_at", "previous_action_hash", "previous_semantic_action_hash"}}
    action_core["semantic_action_hash"] = semantic_hash({**semantic_core, "previous_semantic_action_hash": previous_semantic})
    action_core["action_hash"] = semantic_hash({**action_core, "previous_action_hash": previous})
    action_core["content_digest"] = semantic_hash({k: v for k, v in action_core.items() if k not in {"content_digest", "action_hash", "semantic_action_hash"}})
    action_core["action_id"] = stable_urn("release-review-action", {"content_digest": action_core["content_digest"]})
    actions.append(action_core)
    quorum, roles, _reviewer_ids, _acks = _quorum(candidate, actions)
    log["actions"] = actions
    log["final_decision"] = action
    log["role_coverage"] = sorted(roles)
    log["quorum_satisfied"] = quorum
    log["finalized"] = quorum and action == "APPROVE"
    log["semantic_decision_hash"] = semantic_hash([{k: v for k, v in item.items() if k not in {"observed_at", "action_hash", "content_digest", "action_id"}} for item in actions])
    log["authority_digests"] = [{"artifact_id": candidate["release_candidate_id"], "content_digest": candidate["content_digest"]}]
    bind_identity(log, "review_log_id", "release-review-decision-log")
    save(root, f"records/release-reviews/{log['review_id'].rsplit(':', 1)[1]}.json", log)
    append_event(root, "ReleaseReviewRecorded", {"subject_id": log["review_id"], "release_candidate_id": release_candidate_id})
    return log


def _check_successor_closure(root: Path, candidate: dict[str, Any]) -> None:
    required = {"change_evaluation_id": "records/change-evaluations", "semantic_diff_id": "records/diffs", "impact_analysis_id": "records/impacts", "regression_test_report_id": "records/regressions"}
    for field, folder in required.items():
        identifier = candidate.get(field)
        if not identifier:
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", f"successor closure is missing {field}")
        row = record_by_id(root, folder, {"records/change-evaluations": "evaluation_id", "records/diffs": "diff_id", "records/impacts": "impact_id", "records/regressions": "report_id"}[folder], identifier)
        if field == "change_evaluation_id" and row.get("evaluation_status") != "COMPLETE":
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "change evaluation is not complete")
        if field == "semantic_diff_id" and row.get("overall_classification") == "UNKNOWN_REQUIRES_REVIEW":
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "semantic diff requires review")
        if field == "impact_analysis_id" and row.get("status") != "COMPLETE":
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "impact analysis is incomplete")
        if field == "regression_test_report_id" and (row.get("status") != "PASSED" or row.get("required_passed") is not True):
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "required regression tests did not pass")


def publish_release(workspace: Path | str, candidate: dict, review: dict, *, package_name: str | None = None, package_version: str | None = None, ontology_iri: str | None = None, version_iri: str | None = None, expected_registry_head_hash: str | None = None) -> dict:
    root = Path(workspace)
    if not expected_registry_head_hash or head(root).get("head_hash") != expected_registry_head_hash:
        raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "registry head is missing or stale")
    actual_candidate = _candidate(root, candidate.get("release_candidate_id"))
    actual_review = _review(root, review.get("review_id"))
    if actual_review.get("release_candidate_id") != actual_candidate.get("release_candidate_id"):
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "review does not belong to current candidate")
    if not actual_review.get("quorum_satisfied") or not actual_review.get("finalized"):
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "human review quorum is not satisfied")
    if actual_candidate.get("candidate_status") not in {"SUBMITTED", "APPROVED"}:
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "candidate is not publishable")
    package = package_record(root, actual_candidate.get("candidate_package_id"))
    manifest, lock, _package_root = package_files(root, package)
    derived = (manifest.get("package_name"), manifest.get("package_version"), manifest.get("ontology_identity", {}).get("ontology_iri"), manifest.get("ontology_identity", {}).get("version_iri"))
    supplied = (package_name, package_version, ontology_iri, version_iri)
    for requested, fact in zip(supplied, derived):
        if requested is not None and requested not in {fact, "", "0.0.0", "urn:kg-mnp:ontology", "urn:kg-mnp:version"}:
            raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "client metadata conflicts with package facts")
    if actual_candidate.get("release_candidate_kind") != "INITIAL":
        _check_successor_closure(root, actual_candidate)
    value = {
        "manifest_kind": "KG_MNP_RELEASE", "schema_version": "1.0.0", "registry_id": actual_candidate["registry_id"], "release_status": "RELEASED",
        "release_type": "INITIAL_RELEASE" if not actual_candidate.get("base_package_id") else actual_candidate.get("release_candidate_kind", "PATCH_COMPATIBLE"),
        "package_id": package["package_id"], "package_name": derived[0], "package_version": derived[1], "ontology_iri": derived[2], "version_iri": derived[3],
        "base_release_id": actual_candidate.get("base_release_id"), "change_proposal_id": actual_candidate.get("change_proposal_id"), "change_evaluation_id": actual_candidate.get("change_evaluation_id"),
        "semantic_diff_id": actual_candidate.get("semantic_diff_id"), "version_compatibility_report_id": actual_candidate.get("version_compatibility_report_id"), "impact_analysis_id": actual_candidate.get("impact_analysis_id"),
        "regression_test_report_id": actual_candidate.get("regression_test_report_id"), "release_candidate_id": actual_candidate["release_candidate_id"], "release_review_decision_log_id": actual_review["review_id"],
        "release_review_semantic_hash": actual_review.get("semantic_decision_hash"), "release_policy_id": actual_candidate.get("release_policy_id"), "package_lock_id": lock.get("lock_id"),
        "package_content_digest": manifest.get("content_digest"), "semantic_dataset_digest": manifest.get("semantic_summary", {}).get("semantic_dataset_digest"), "release_lineage": [],
    }
    bind_identity(value, "release_id", "release")
    filename = f"records/releases/{value['release_id'].rsplit(':', 1)[1]}.json"
    existing = Path(root / filename)
    if existing.is_file():
        prior = json_load(existing)
        if prior != value:
            raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "release identity already exists with different content")
        return {**prior, "status": "ALREADY_PUBLISHED"}
    save(root, filename, value)
    append_event(root, "ReleasePublished", {"subject_id": value["release_id"], "target_package_id": value["package_id"]})
    return value


def json_load(path: Path) -> dict[str, Any]:
    import json
    try:
        return json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "release record is invalid") from exc


def list_releases(workspace: Path | str) -> list[dict[str, Any]]:
    return list_records(workspace, "records/releases")


def attest_release(workspace: Path | str, release: dict, *, package_lock_id: str | None = None, package_archive_sha256: str | None = None, authority_records: list[dict] | None = None) -> dict:
    root = Path(workspace)
    actual_release = _release_from_argument(root, release)
    package = package_record(root, actual_release.get("package_id"))
    _manifest, lock, _package_root = package_files(root, package)
    archive = real_archive(root, package)
    review = _review(root, actual_release.get("release_review_decision_log_id"))
    candidate = _candidate(root, actual_release.get("release_candidate_id"))
    registry_head = head(root)
    publication_event = next((event for event in reversed(read_events(root)) if event.get("event_type") == "ReleasePublished" and event.get("payload", {}).get("subject_id") == actual_release["release_id"]), None)
    if publication_event is None:
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "release publication event is missing")
    pre_publication_registry_head_hash = semantic_hash({"registry_id": registry_head["registry_id"], "generation": publication_event["sequence"] - 1, "event_count": publication_event["sequence"] - 1, "head_event_hash": publication_event.get("previous_event_hash")})
    if not review.get("quorum_satisfied") or review.get("release_candidate_id") != candidate.get("release_candidate_id"):
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "release review is not a valid attestation source")
    if package_lock_id is not None and package_lock_id != lock.get("lock_id"):
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "client lock does not match package lock")
    if package_archive_sha256 is not None and package_archive_sha256 != package.get("archive_sha256"):
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "client archive digest does not match package archive")
    release_path = root / "records" / "releases" / f"{actual_release['release_id'].rsplit(':', 1)[1]}.json"
    if not release_path.is_file():
        raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "release manifest file is missing")
    value = {
        "manifest_kind": "KG_MNP_RELEASE_ATTESTATION", "schema_version": "1.0.0", "registry_id": actual_release["registry_id"], "release_id": actual_release["release_id"],
        "release_manifest_file_sha256": file_sha256(release_path), "release_manifest_semantic_sha256": semantic_hash({k: v for k, v in actual_release.items() if k not in {"release_id", "content_digest"}}),
        "package_id": package["package_id"], "package_lock_id": lock["lock_id"], "package_lock_content_digest": lock.get("content_digest"), "package_archive_sha256": file_sha256(archive),
        "release_candidate_id": candidate["release_candidate_id"], "review_log_id": review["review_id"], "review_semantic_hash": review.get("semantic_decision_hash"),
        "semantic_diff_id": actual_release.get("semantic_diff_id"), "impact_analysis_id": actual_release.get("impact_analysis_id"), "regression_report_id": actual_release.get("regression_test_report_id"),
        "pre_publication_registry_head_hash": pre_publication_registry_head_hash, "authority_records": authority_records or [], "attestation_status": "VERIFIED",
    }
    bind_identity(value, "attestation_id", "release-attestation")
    save(root, f"records/attestations/{value['attestation_id'].rsplit(':', 1)[1]}.json", value)
    return value


def _release_from_argument(root: Path, release: dict[str, Any]) -> dict[str, Any]:
    identifier = release.get("release_id")
    if identifier:
        return _release_record(root, identifier)
    raise LifecycleError("RELEASE_PUBLICATION_BLOCKED", "release identity is required")


def _release_record(root: Path, identifier: str) -> dict[str, Any]:
    return record_by_id(root, "records/releases", "release_id", identifier)
