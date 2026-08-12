from __future__ import annotations

import copy
from pathlib import Path

import pytest

from kg_mnp_demo.governance.artifact_verifier import (
    FILES,
    Phase04ArtifactVerificationError,
    verify_application_phase04_artifact,
)
from kg_mnp_demo.governance.attestation import (
    CATEGORY_FIELDS,
    build_application_phase04_attestation,
)
from kg_mnp_demo.governance.workspace import GovernanceWorkspace
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from ._helpers import authority, proposal_arguments


COMMIT = "1" * 40


def probe(category: str) -> dict:
    outcome = f"{category}_BLOCKED"
    return {
        "probe_id": "urn:kg-mnp:phase04-probe:" + semantic_hash({"category": category}),
        "category": category,
        "attack": f"executed {category} attack",
        "expected_outcome": outcome,
        "actual_outcome": outcome,
        "blocked": True,
        "status": "PASS",
    }


def artifact(tmp_path: Path):
    auth = authority()
    workspace = GovernanceWorkspace.initialize(auth)
    decisions = [
        "APPROVE_FOR_AMENDMENT",
        "APPROVE_FOR_AMENDMENT",
        "APPROVE_FOR_AMENDMENT",
        "REJECT",
        "DEFER",
    ]
    for index, decision in enumerate(decisions, start=1):
        arguments = proposal_arguments(auth)
        arguments["rationale"] += f" Proposal lineage {index}."
        proposal = workspace.create_proposal(
            expected_workspace_revision=workspace.value["workspace_revision"],
            **arguments,
        )
        workspace.submit_proposal(
            proposal["proposal_id"],
            expected_workspace_revision=workspace.value["workspace_revision"],
        )
        workspace.review_proposal(
            proposal["proposal_id"],
            decision=decision,
            review_note="Explicit human review for future amendment only",
            reviewed_by_label="operator-supplied reviewer label",
            explicit_human_action=True,
            expected_workspace_revision=workspace.value["workspace_revision"],
        )
    probes = [probe(category) for category in CATEGORY_FIELDS]
    attestation = build_application_phase04_attestation(
        commit_sha=COMMIT,
        upstream_verification_mode="EXACT_SHA_REMOTE_LICENSED_EVIDENCE",
        authority=auth,
        workspace=workspace.value,
        probes=probes,
        repository_before_hash=auth.repository_semantic_hash,
        repository_after_hash=auth.repository_semantic_hash,
        diagnostic_hash_before=auth.diagnostic_package_hash,
        diagnostic_hash_after=auth.diagnostic_package_hash,
    )
    result = workspace.reconstruct()
    root = tmp_path / "artifact"
    documents = {
        "application-phase04-attestation.json": attestation,
        "governance-summary.json": {
            "contract_version": "1.0",
            "workspace": workspace.value,
            "workspace_hash": workspace.value["workspace_hash"],
            "workspace_revision": workspace.value["workspace_revision"],
            "proposals_created": attestation["proposals_created"],
            "proposals_submitted": attestation["proposals_submitted"],
            "reviews_approved": attestation["reviews_approved"],
            "reviews_rejected": attestation["reviews_rejected"],
            "reviews_deferred": attestation["reviews_deferred"],
            "approved_amendment_requests": attestation["approved_amendment_requests"],
            "status": "PASS",
        },
        "state-machine-summary.json": {
            "contract_version": "1.0",
            "valid_transitions": [
                "DRAFT->SUBMITTED",
                "SUBMITTED->APPROVED_FOR_AMENDMENT",
                "SUBMITTED->REJECTED",
                "SUBMITTED->DEFERRED",
            ],
            "invalid_transition_probes": [
                item["probe_id"]
                for item in probes
                if item["category"] == "ILLEGAL_TRANSITION"
            ],
            "status": "PASS",
        },
        "authority-binding.json": {
            "contract_version": "1.0",
            **auth.binding,
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            "probes": probes,
            "external_requests": 0,
            "service_workers": 0,
            "status": "PASS",
        },
    }
    root.mkdir()
    for name, value in documents.items():
        (root / name).write_bytes(canonical_json_bytes(value) + b"\n")
    assert set(documents) == FILES
    assert len(result["approved_amendment_requests"]) == 3
    return root, auth, documents


def rewrite(root: Path, name: str, value: dict) -> None:
    (root / name).write_bytes(canonical_json_bytes(value) + b"\n")


def test_exact_artifact_reconstructs(tmp_path: Path) -> None:
    root, auth, documents = artifact(tmp_path)
    result = verify_application_phase04_artifact(
        root,
        authority=auth,
        expected_commit_sha=COMMIT,
        expected_workspace_hash=documents["governance-summary.json"]["workspace_hash"],
    )
    assert result["status"] == "APPLICATION_HUMAN_GOVERNANCE_VERIFIED"
    assert result["artifact_files"] == sorted(FILES)


def test_closed_set_and_commit_binding_fail_closed(tmp_path: Path) -> None:
    root, auth, _ = artifact(tmp_path)
    (root / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(Phase04ArtifactVerificationError, match="closed set"):
        verify_application_phase04_artifact(root, authority=auth)
    (root / "unexpected.json").unlink()
    with pytest.raises(Phase04ArtifactVerificationError, match="commit"):
        verify_application_phase04_artifact(
            root, authority=auth, expected_commit_sha="2" * 40
        )


def test_probe_counters_cannot_be_filled_or_forged(tmp_path: Path) -> None:
    root, auth, documents = artifact(tmp_path)
    security = copy.deepcopy(documents["security-summary.json"])
    security["probes"][0]["blocked"] = False
    rewrite(root, "security-summary.json", security)
    with pytest.raises(Phase04ArtifactVerificationError, match="probe"):
        verify_application_phase04_artifact(root, authority=auth)


def test_self_consistent_workspace_rehash_fails_attested_head_anchor(
    tmp_path: Path,
) -> None:
    root, auth, documents = artifact(tmp_path)
    trusted_head = documents["governance-summary.json"]["workspace_hash"]
    summary = copy.deepcopy(documents["governance-summary.json"])
    workspace = summary["workspace"]
    workspace["events"][2]["payload"]["review_note"] = "changed and rehashed"
    previous = "GENESIS"
    for sequence, event in enumerate(workspace["events"], start=1):
        event["sequence"] = sequence
        event["previous_event_hash"] = previous
        event["payload_hash"] = semantic_hash(event["payload"])
        event["event_id"] = semantic_hash(
            {
                "sequence": sequence,
                "previous_event_hash": previous,
                "event_type": event["event_type"],
                "payload_hash": event["payload_hash"],
            }
        )
        previous = event["event_id"]
    workspace["head_event_hash"] = previous
    workspace["workspace_hash"] = semantic_hash(
        {
            "contract_version": workspace["contract_version"],
            "workspace_id": workspace["workspace_id"],
            "authority_binding": workspace["authority_binding"],
            "events": workspace["events"],
            "workspace_revision": workspace["workspace_revision"],
            "head_event_hash": workspace["head_event_hash"],
            "status": workspace["status"],
        }
    )
    summary["workspace_hash"] = workspace["workspace_hash"]
    rewrite(root, "governance-summary.json", summary)
    attestation = copy.deepcopy(documents["application-phase04-attestation.json"])
    attestation["governance_workspace_hash"] = workspace["workspace_hash"]
    rewrite(root, "application-phase04-attestation.json", attestation)
    with pytest.raises(Exception):
        verify_application_phase04_artifact(
            root,
            authority=auth,
            expected_workspace_hash=trusted_head,
        )


@pytest.mark.parametrize(
    "value", ["C:/Users/alice/private", "GRAPHDB_LICENSE_CONTENT=secret"]
)
def test_absolute_paths_and_secrets_are_rejected(tmp_path: Path, value: str) -> None:
    root, auth, documents = artifact(tmp_path)
    security = copy.deepcopy(documents["security-summary.json"])
    security["probes"][0]["attack"] = value
    rewrite(root, "security-summary.json", security)
    with pytest.raises(Phase04ArtifactVerificationError, match="secret or absolute"):
        verify_application_phase04_artifact(root, authority=auth)
