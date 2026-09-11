"""Versioned Ontology Package manifest construction."""

from __future__ import annotations

import copy
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from ..artifacts import artifact_record

IDENTITY_GRAPH_ROLES = (
    "abox",
    "compilation-activity",
    "compiled-shapes",
    "effective-shapes",
    "effective-tbox",
    "evidence-lineage",
    "mapping-provenance",
    "review-audit",
    "statement-provenance",
)


def semantic_payload_identity_digest(
    *,
    graph_digests: dict[str, str],
    mapping_plan_digest: str,
    cq_test_plan_digest: str,
    attestation_digest: str,
    baseline_assets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> str:
    """Digest the package-ID-independent semantic payload closure.

    Package-derived graph IRIs, the ontology-module package reference, locks,
    manifests, and validation report IDs are intentionally excluded to avoid a
    cryptographic fixed point. Their independently verified source semantics
    are represented by the normalized role graph digests and control artifacts.
    """

    missing = sorted(set(IDENTITY_GRAPH_ROLES) - set(graph_digests))
    if missing:
        raise ValueError("semantic payload identity lacks graph roles: " + ", ".join(missing))
    basis = {
        "identity_profile": "KG-MNP Normalized Semantic Payload Identity v1",
        "graphs": [
            {"role": role, "semantic_sha256": graph_digests[role]}
            for role in IDENTITY_GRAPH_ROLES
        ],
        "mapping_plan_digest": mapping_plan_digest,
        "cq_test_plan_digest": cq_test_plan_digest,
        "attestation_digest": attestation_digest,
        "baseline_assets": [
            {
                "pack_lock_id": item["pack_lock_id"],
                "asset_path": item["asset_path"],
                "semantic_sha256": item["semantic_sha256"],
            }
            for item in sorted(
                baseline_assets,
                key=lambda item: (item["pack_lock_id"], item["asset_path"]),
            )
        ],
    }
    return semantic_hash(basis)


def package_id_for_plan(
    *,
    plan_id: str,
    confirmed_package_id: str,
    compiler_snapshot_id: str,
    identity_payload_digest: str,
) -> str:
    """Return the non-circular package identity bound to its deterministic build inputs.

    The normalized semantic payload digest commits to every authoritative role
    graph plus mapping, CQ, attestation, and locked baseline semantics while
    omitting only package-derived identity fields and derived reports.
    """

    return stable_urn(
        "ontology-package",
        {
            "plan_id": plan_id,
            "confirmed_package_id": confirmed_package_id,
            "compiler_snapshot_id": compiler_snapshot_id,
            "identity_payload_digest": identity_payload_digest,
        },
    )


def verify_package_manifest(
    manifest: dict[str, Any],
    *,
    plan: dict[str, Any] | None = None,
) -> None:
    """Verify manifest content and, when supplied, its non-circular Package ID."""

    validate_contract("ontology-package-manifest", manifest)
    preimage = copy.deepcopy(manifest)
    actual_digest = preimage.pop("content_digest", None)
    preimage.pop("package_id", None)
    if actual_digest != semantic_hash(preimage):
        raise ValueError("ontology package manifest content digest mismatch")
    if plan is not None:
        expected = package_id_for_plan(
            plan_id=plan["plan_id"],
            confirmed_package_id=plan["confirmed_package_id"],
            compiler_snapshot_id=plan["compiler_snapshot_id"],
            identity_payload_digest=manifest["semantic_summary"][
                "identity_payload_digest"
            ],
        )
        if manifest["package_id"] != expected:
            raise ValueError("ontology package ID does not match its compilation plan")
        identity = plan["package_identity"]
        if (
            manifest["package_name"] != identity["package_name"]
            or manifest["package_version"] != identity["package_version"]
        ):
            raise ValueError("ontology package identity differs from its compilation plan")


def build_package_manifest(
    *,
    package_id: str,
    plan: dict[str, Any],
    confirmed_package: dict[str, Any],
    compiler_snapshot: dict[str, Any],
    compiler_policy: dict[str, Any],
    project_lock: dict[str, Any],
    baseline_assets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    dataset_manifest: dict[str, Any],
    mapping_plan: dict[str, Any],
    validation_reports: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    provenance_manifest: dict[str, Any],
    artifacts: dict[str, bytes],
    semantic_summary: dict[str, Any],
) -> dict[str, Any]:
    artifact_rows = [artifact_record(path, data, role="PACKAGE_PAYLOAD") for path, data in sorted(artifacts.items())]
    report_rows = [{"report_id": report["report_id"], "status": str(report.get("status", "PASSED")), "content_digest": report["content_digest"]} for report in validation_reports]
    provenance_rows = [{"report_id": provenance_manifest["provenance_manifest_id"], "status": "PASSED", "content_digest": provenance_manifest["content_digest"]}]
    identity = plan["package_identity"]
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_PACKAGE", "schema_version": "1.0.0", "package_format_version": "1.0.0",
        "package_name": identity["package_name"], "package_version": identity["package_version"], "package_status": "VALIDATED_UNPUBLISHED",
        "ontology_identity": plan["ontology_identity"], "source_confirmed_package": confirmed_package["package_id"], "compiler_snapshot": compiler_snapshot["snapshot_id"], "compiler_policy": compiler_policy["policy_id"],
        "project_lock_id": project_lock["lock_id"], "contract_catalog_digest": project_lock["contract_catalog_digest"], "domain_pack_locks": sorted(item["pack_lock_id"] for item in project_lock["resolved_domain_packs"]),
        "baseline_dependencies": list(baseline_assets), "graphs": dataset_manifest["graphs"], "mapping_plan": mapping_plan["mapping_plan_id"],
        "validation_reports": sorted(report_rows, key=lambda item: item["report_id"]), "provenance": provenance_rows, "artifacts": artifact_rows, "semantic_summary": semantic_summary,
    }
    manifest = {**core, "content_digest": semantic_hash(core), "package_id": package_id}
    validate_contract("ontology-package-manifest", manifest)
    return manifest
