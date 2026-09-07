"""Initial local registry/release flow, with real records and mandatory CAS."""
from __future__ import annotations

from pathlib import Path

from kg_mnp.integrations.local_rdf import LocalRDFQueryAdapter
from kg_mnp.integrations.oms import OMSMetadataService
from kg_mnp.lifecycle.contracts import verify
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.guards import package_record, record_by_id
from kg_mnp.lifecycle.registry.import_package import import_package
from kg_mnp.lifecycle.registry.replay import verify_registry
from kg_mnp.lifecycle.release import (
    _quorum,
    attest_release,
    create_release_candidate,
    publish_release,
    record_review,
)
from kg_mnp.lifecycle.store import list_records
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from .compilation import package_path
from .errors import ServiceBoundaryError
from .projects import load_catalog

OPERATIONS = frozenset({"registry.import", "release.candidate", "release.review", "release.publish", "oms.metadata", "ods.query"})


def execute(app, project, request, principal):
    root, name, params = project.registry_root, request.operation_id, request.parameters
    try:
        if name == "registry.import":
            return import_package(root, package_path(project, params["package_id"]), source_project_lock=Path(project.root) / "project.lock.json")
        if name in {"oms.metadata", "ods.query"}:
            path = package_path(project, params["package_id"])
            if name == "oms.metadata":
                result = OMSMetadataService(path).metadata(limit=params.get("limit", 100), offset=params.get("offset", 0))
                result["view"] = "VALIDATED_UNPUBLISHED"
                return result
            if bool(params.get("class_iri")) == bool(params.get("instance_iri")):
                raise ServiceBoundaryError("QUERY_INVALID", "select exactly one class or instance", status_code=422)
            # Closed query primitives: no user SPARQL, UPDATE, SERVICE or FROM.
            query = LocalRDFQueryAdapter(path, max_results=1001000)
            offset, limit = params.get("offset", 0), params.get("limit", 100)
            result = query.instances_by_class(params["class_iri"], limit=offset + limit + 1) if params.get("class_iri") else query.instance(params["instance_iri"], limit=offset + limit + 1)
            rows = sorted(result["rows"], key=lambda row: str(sorted(row.items())))
            return {"package_id": params["package_id"], "rows": rows[offset:offset + limit],
                    "page": {"offset": offset, "limit": limit, "truncated": len(rows) > offset + limit or result["truncated"]}}
        if name == "release.candidate":
            record = package_record(root, params["package_id"])
            verify_package(root / record["package_storage_ref"])
            # Successors must use the separately governed change/regression
            # workflow; never relabel a successor as an initial release.
            if any(row["package_name"] == record["package_name"] for row in list_records(root, "records/releases")):
                raise ServiceBoundaryError("SUCCESSOR_CLOSURE_REQUIRED", "existing lineage requires diff/impact/regression candidate closure", status_code=409)
            return create_release_candidate(root, candidate_package_id=params["package_id"], required_roles=["RELEASE_MANAGER"], minimum_distinct_reviewers=1)
        if name == "release.review":
            if not principal.can("review:role:RELEASE_MANAGER"):
                raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN", "release manager grant required", status_code=403)
            return record_review(root, params["candidate_id"], reviewer_id=principal.principal_id, reviewer_roles=["RELEASE_MANAGER"],
                                 action=params["decision"], rationale=params["rationale"], explicit_human_action=True)
        candidate = record_by_id(root, "records/release-candidates", "release_candidate_id", params["candidate_id"])
        review = record_by_id(root, "records/release-reviews", "review_id", params["review_id"])
        verify(review, contract="release-review-decision-log", registry_id=candidate["registry_id"])
        quorum, _roles, _reviewers, _acks = _quorum(candidate, review["actions"])
        if not quorum or review["quorum_satisfied"] != quorum:
            raise ServiceBoundaryError("REVIEW_QUORUM_INVALID", "release review quorum failed replay", status_code=409)
        receipts = list(load_catalog(app.root).get("commits", {}).values())
        for action in review["actions"]:
            proven = [receipt for receipt in receipts if receipt["context"]["operation_id"] == "release.review"
                      and receipt["context"]["project_id"] == project.project_id
                      and action in receipt["result"].get("actions", [])
                      and receipt["context"]["principal_id"] == action["reviewer_id"]]
            if not proven:
                raise ServiceBoundaryError("REVIEW_IDENTITY_UNPROVEN", "release action lacks a server credential-bound commit", status_code=409)
            actor = app.tokens.resolve(proven[0]["context"]["grant_reference"])
            if actor.principal_type != "HUMAN" or not actor.can("release:review") or not actor.can("review:role:RELEASE_MANAGER"):
                raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN", "release reviewer is no longer authorized", status_code=403)
        # Verify package/event/record closure independently of cached flags.
        if verify_registry(root)["status"] != "VALID":
            raise ServiceBoundaryError("REGISTRY_INVALID", "registry replay did not validate", status_code=409)
        released = publish_release(root, candidate, review, expected_registry_head_hash=params["expected_registry_head_hash"])
        attestation = attest_release(root, released)
        return {"release": released, "attestation": attestation}
    except LifecycleError as exc:
        raise ServiceBoundaryError(exc.code, "lifecycle authority or state precondition failed", status_code=409) from exc
