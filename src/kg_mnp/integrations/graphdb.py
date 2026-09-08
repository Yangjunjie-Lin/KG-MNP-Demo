from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from kg_mnp.contracts.canonical import semantic_hash
from kg_mnp.graphdb.client import GraphDBClientError
from kg_mnp.graphdb.rdf_semantics import graphdb_semantic_hash_nquads
from kg_mnp.graphdb.repository_config import (
    render_repository_config_ttl,
    repository_config_document,
)
from kg_mnp.semantic_kernel.packaging.archive import read_verified_package_files

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
        self.validate_target(target)
        _files, verified = read_verified_package_files(package_root, expected_package_id=package_id)
        if verified.get("status") != "VALID":
            raise ValueError("verified package required")
        snapshot = self.snapshot(target)
        return IntegrationPlan("plan_" + semantic_hash({"project": project_id, "release": release_id, "package": package_id, "target": target.target_id}), project_id, release_id, package_id, target.target_id, target.target_revision, snapshot, semantic_hash({"package_id": package_id}), "IMPORT_EXPLICIT_GRAPHS", pointer_generation, None, ("target-revision-unchanged", "package-verified"))

    def execute(self, plan: IntegrationPlan, approval: IntegrationApproval, *, target: IntegrationTarget, package_root: Path | str, transport=None) -> IntegrationReceipt:
        self.validate_target(target)
        if (approval.plan_id != plan.plan_id or approval.payload_digest != plan.payload_digest
                or approval.target_revision != target.target_revision or plan.target_revision != target.target_revision
                or plan.target_id != target.target_id or plan.adapter_snapshot != self.snapshot(target)
                or approval.project_id != plan.project_id or approval.approved_effect != plan.allowed_effect
                or plan.allowed_effect != "IMPORT_EXPLICIT_GRAPHS"
                or plan.payload_digest != semantic_hash({"package_id": plan.package_id})):
            raise ValueError("integration approval does not bind the plan")
        for expiry in (plan.expiry, approval.expires_at):
            if expiry is not None:
                expires = datetime.fromisoformat(expiry)
                if expires.tzinfo is None or expires <= datetime.now(UTC):
                    raise ValueError("integration approval or plan has expired")
        if transport is None:
            return IntegrationReceipt(plan_id=plan.plan_id, status="RECONCILIATION_REQUIRED", desired_release_id=plan.release_id, last_verification_status="UNKNOWN_EXTERNAL_RESULT", details={"reason": "external transport not configured"})
        # Explicitly supplied protocol client, never an arbitrary request URL.
        # Creation/import are not safely retryable after an uncertain response.
        if getattr(transport, "retries", 0) != 0:
            raise ValueError("GraphDB write transport must disable automatic retries")
        if hasattr(transport, "base_url"):
            actual = urlsplit(transport.base_url)
            expected_endpoint = ("http" if target.scheme == "local" else target.scheme, target.host or "127.0.0.1", target.port or 7200, target.base_path.rstrip("/"))
            if (actual.username or actual.password or actual.query or actual.fragment
                    or (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme == "https" else 80), actual.path.rstrip("/")) != expected_endpoint):
                raise ValueError("GraphDB transport endpoint differs from approved target")
        for method in ("list_repositories", "create_repository", "inspect_repository", "count_repository_statements", "import_nquads", "export_nquads", "get_default_graph"):
            if not callable(getattr(transport, method, None)):
                raise TypeError("GraphDB transport protocol is incomplete")
        files, verified = read_verified_package_files(package_root, expected_package_id=plan.package_id)
        if verified.get("status") != "VALID":
            raise ValueError("verified package required")
        data = files["dataset/dataset.nq"]
        expected = graphdb_semantic_hash_nquads(data)
        repository_id = "kg-mnp-" + semantic_hash({"plan_id": plan.plan_id, "package_id": plan.package_id})[:20]
        def failed(reason):
            return IntegrationReceipt(plan_id=plan.plan_id, status="FAILED", desired_release_id=plan.release_id,
                last_verification_status=reason, details={"repository_id": repository_id, "cleanup": "NOT_AUTOMATIC"})
        try:
            if repository_id in transport.list_repositories():
                return failed("EXISTING_REPOSITORY_NOT_OVERWRITTEN")
            transport.create_repository(render_repository_config_ttl(repository_config_document(repository_id)))
            info = transport.inspect_repository(repository_id)
            ruleset = info.get("params", {}).get("ruleset", {})
            if isinstance(ruleset, dict): ruleset = ruleset.get("value")
            if info.get("id", info.get("repositoryID")) != repository_id or ruleset != "empty":
                return failed("REPOSITORY_POLICY_MISMATCH")
            if transport.count_repository_statements(repository_id) != 0:
                return failed("FRESH_REPOSITORY_NOT_EMPTY")
            transport.import_nquads(repository_id, data)
            explicit = graphdb_semantic_hash_nquads(transport.export_nquads(repository_id, include_inferred=False))
            complete = graphdb_semantic_hash_nquads(transport.export_nquads(repository_id, include_inferred=True))
            if explicit != expected or complete != expected:
                return failed("EXPLICIT_OR_INFERRED_DATASET_MISMATCH")
            if transport.get_default_graph(repository_id).statement_count != 0:
                return failed("PHYSICAL_DEFAULT_GRAPH_NOT_EMPTY")
            return IntegrationReceipt(plan_id=plan.plan_id, status="DEPLOYMENT_VERIFIED", desired_release_id=plan.release_id,
                observed_deployed_release_id=plan.release_id, observed_dataset_digest=explicit, last_verification_status="VERIFIED",
                details={"repository_id":repository_id,"explicit_complete_equal":True,"physical_default_graph_empty":True})
        except (TimeoutError, OSError, GraphDBClientError):
            return IntegrationReceipt(plan_id=plan.plan_id, status="RECONCILIATION_REQUIRED", desired_release_id=plan.release_id,
                last_verification_status="UNKNOWN_EXTERNAL_RESULT", details={"repository_id":repository_id,"retry":"EXPLICIT_RECONCILIATION_REQUIRED"})
        except ValueError:
            return failed("INVALID_EXPORTED_RDF")
