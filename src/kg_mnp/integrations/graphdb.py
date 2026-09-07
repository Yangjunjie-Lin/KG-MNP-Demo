from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from .protocol import (
    AdapterManifest,
    AdapterSnapshot,
    IntegrationApproval,
    IntegrationPlan,
    IntegrationReceipt,
    IntegrationTarget,
)
from .targets import validate_endpoint


class GraphDBAdapter:
    manifest = AdapterManifest("graphdb", "1.0.0", "GRAPHDB", ("availability", "import", "explicit-export", "readonly-query", "reconcile"), "ALLOWLISTED", "APPROVED_WRITE")

    def validate_target(self, target: IntegrationTarget, *, allowed_hosts: set[str] | None = None) -> None:
        if target.scheme == "local":
            if target.host not in {"", "127.0.0.1", "localhost", "::1"}:
                raise ValueError("local GraphDB target has an unexpected host")
            return
        validate_endpoint(f"{target.scheme}://{target.host}:{target.port or 443}{target.base_path}", allowed_hosts=allowed_hosts or set(), allow_local_graphdb=False)

    def snapshot(self, target: IntegrationTarget) -> AdapterSnapshot:
        if target.target_type != "GRAPHDB":
            raise ValueError("GraphDB adapter requires a GRAPHDB target")
        return AdapterSnapshot("graphdb", "1.0.0", semantic_hash(asdict(target)), semantic_hash(asdict(self.manifest)))

    def plan_import(self, *, project_id: str, release_id: str, package_id: str, target: IntegrationTarget, package_root: Path | str, pointer_generation: int | None = None) -> IntegrationPlan:
        if verify_package(Path(package_root)).get("status") != "VALID":
            raise ValueError("verified package required")
        snapshot = self.snapshot(target)
        return IntegrationPlan("plan_" + semantic_hash({"project": project_id, "release": release_id, "package": package_id, "target": target.target_id}), project_id, release_id, package_id, target.target_id, target.target_revision, snapshot, semantic_hash({"package_id": package_id}), "IMPORT_EXPLICIT_GRAPHS", pointer_generation, None, ("target-revision-unchanged", "package-verified"))

    def execute(self, plan: IntegrationPlan, approval: IntegrationApproval, *, target: IntegrationTarget, package_root: Path | str, transport=None) -> IntegrationReceipt:
        if approval.plan_id != plan.plan_id or approval.payload_digest != plan.payload_digest or approval.target_revision != target.target_revision:
            raise ValueError("integration approval does not bind the plan")
        if transport is None:
            return IntegrationReceipt(plan_id=plan.plan_id, status="RECONCILIATION_REQUIRED", desired_release_id=plan.release_id, last_verification_status="UNKNOWN_EXTERNAL_RESULT", details={"reason": "external transport not configured"})
        # A supplied transport is an integration protocol object, never a URL
        # passthrough.  It must report explicit graph verification separately.
        try:
            result = transport.import_verified_package(Path(package_root), plan)
            if not result.get("explicit_digest_verified"):
                return IntegrationReceipt(plan_id=plan.plan_id, status="FAILED", desired_release_id=plan.release_id, last_verification_status="DIGEST_MISMATCH")
            return IntegrationReceipt(plan_id=plan.plan_id, status="DEPLOYMENT_VERIFIED", desired_release_id=plan.release_id, observed_deployed_release_id=plan.release_id, observed_dataset_digest=result.get("explicit_dataset_digest"), last_verification_status="VERIFIED")
        except TimeoutError:
            return IntegrationReceipt(plan_id=plan.plan_id, status="RECONCILIATION_REQUIRED", desired_release_id=plan.release_id, last_verification_status="UNKNOWN_EXTERNAL_RESULT")
