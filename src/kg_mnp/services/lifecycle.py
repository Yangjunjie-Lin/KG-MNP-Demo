"""Initial local registry/release flow, with real records and mandatory CAS."""
from __future__ import annotations

from pathlib import Path

from kg_mnp.integrations.local_rdf import LocalRDFQueryAdapter
from kg_mnp.integrations.oms import OMSMetadataService
from kg_mnp.lifecycle.changes import (
    attach_candidate_package,
    create_change_proposal,
    evaluate_change,
    submit_change_proposal,
)
from kg_mnp.lifecycle.contracts import verify
from kg_mnp.lifecycle.diff.engine import create_diff
from kg_mnp.lifecycle.diff.versioning import check_version
from kg_mnp.lifecycle.environment import (
    execute_activation,
    init_environment,
    propose_activation,
    review_activation,
)
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.guards import package_files, package_record, record_by_id
from kg_mnp.lifecycle.impact import analyze_impact
from kg_mnp.lifecycle.policy import load_policy
from kg_mnp.lifecycle.registry.head import read_head
from kg_mnp.lifecycle.registry.import_package import import_package
from kg_mnp.lifecycle.registry.manifest import load_manifest
from kg_mnp.lifecycle.registry.replay import verify_registry
from kg_mnp.lifecycle.regression import plan_regression, run_regression
from kg_mnp.lifecycle.release import (
    _quorum,
    attest_release,
    create_release_candidate,
    publish_release,
    record_review,
)
from kg_mnp.lifecycle.store import list_records, save
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

from .compilation import package_path
from .errors import ServiceBoundaryError
from .projects import load_catalog

OPERATIONS = frozenset({"registry.import", "release.candidate", "release.review", "release.publish", "oms.metadata", "ods.query",
                       "change.diff","change.impact","change.regression","change.evaluate",
                       "environment.create","environment.propose","environment.review","environment.activate","environment.rollback"})
OPERATIONS=OPERATIONS|{"object.trace","feedback.add","consumer.register"}


def _record(root,folder,field,identifier):
    row=record_by_id(root,"records/"+folder,field,identifier)
    return row


def _diff(root,identifier):
    from kg_mnp.lifecycle.diff.engine import verify_diff
    report=_record(root,"diffs","diff_id",identifier)
    verify_diff(report)
    return report


def _change(root,request,principal):
    name,params=request.operation_id,request.parameters
    if name=="change.diff":
        base=package_record(root,params["base_package_id"]); candidate=package_record(root,params["candidate_package_id"])
        report=create_diff(package_files(root,base)[2],package_files(root,candidate)[2],registry_id=load_manifest(root)["registry_id"],
            base_package_id=base["package_id"],candidate_package_id=candidate["package_id"],base_version=base["package_version"],candidate_version=candidate["package_version"])
        save(root,f"records/diffs/{report['diff_id'].rsplit(':',1)[1]}.json",report)
        version=check_version(base["package_version"],candidate["package_version"],report,registry_id=report["registry_id"],semantic_diff_id=report["diff_id"])
        save(root,f"records/version-compatibility/{version['report_id'].rsplit(':',1)[1]}.json",version)
        return {"diff":report,"version":version}
    report=_diff(root,params["diff_id"])
    if name=="change.impact":return analyze_impact(root,semantic_diff=report)
    impact=_record(root,"impacts","impact_id",params["impact_id"])
    if impact["semantic_diff_id"]!=report["diff_id"]:
        raise ServiceBoundaryError("LIFECYCLE_BINDING_INVALID","impact belongs to another diff",status_code=409)
    if name=="change.regression":
        oracle={"assertion_type":"BOOLEAN_EQUALS","boolean_value":True,"integer_value":None,"string_values":[],"semantic_hash":None}
        plan=plan_regression(root,base_package_id=report["base_package_id"],candidate_package_id=report["candidate_package_id"],
            semantic_diff_id=report["diff_id"],impact_analysis_id=impact["impact_id"],tests=[{"test_category":category,"expected_result":oracle}
            for category in ["PACKAGE_INTEGRITY","CANDIDATE_CQ","BASE_REQUIRED_CQ"]])
        return {"plan":plan,"report":run_regression(root,plan)}
    regression=_record(root,"regressions","report_id",params["regression_report_id"])
    if (regression["base_package_id"],regression["candidate_package_id"])!=(report["base_package_id"],report["candidate_package_id"]):
        raise ServiceBoundaryError("LIFECYCLE_BINDING_INVALID","regression pair differs",status_code=409)
    versions=[r for r in list_records(root,"records/version-compatibility") if r["semantic_diff_id"]==report["diff_id"]]
    if len(versions)!=1:raise ServiceBoundaryError("VERSION_REPORT_REQUIRED","unambiguous version report required",status_code=409)
    proposal=create_change_proposal(root,base_package_id=report["base_package_id"],submitted_by=principal.principal_id,
        requested_outcomes=[params["rationale"]],affected_iris=report["affected_iris"])
    submit_change_proposal(root,proposal["change_proposal_id"])
    attach_candidate_package(root,proposal["change_proposal_id"],report["candidate_package_id"])
    return evaluate_change(root,proposal["change_proposal_id"],candidate_package_id=report["candidate_package_id"],
        semantic_diff_id=report["diff_id"],version_compatibility_report_id=versions[0]["report_id"],impact_analysis_id=impact["impact_id"],regression_test_report_id=regression["report_id"])


def _environment(app,project,request,principal):
    root,name,params=project.registry_root,request.operation_id,request.parameters
    if name=="environment.create":
        policy=load_policy("activation-policy-1.0.0.yaml")
        return init_environment(root,environment_name=params["name"],activation_roles=policy["activation_roles"],activation_quorum=policy["activation_quorum"],
            rollback_roles=policy["rollback_roles"],rollback_quorum=policy["rollback_quorum"])
    if name=="environment.propose":
        return propose_activation(root,environment_id=params["environment_id"],release_id=params["release_id"],rationale=params["rationale"],
                                  requested_by=principal.principal_id,activation_kind=params["kind"])
    proposal=_record(root,"activation-proposals","activation_proposal_id",params["proposal_id"])
    env=_record(root,"environments","environment_id",proposal["environment_id"])
    required=env["rollback_roles"] if proposal["activation_kind"]=="ROLLBACK" else env["activation_roles"]
    if name=="environment.review":
        roles=[role for role in required if principal.can("review:role:"+role)]
        return review_activation(root,proposal_id=params["proposal_id"],decision=params["decision"],reviewer_id=principal.principal_id,
            reviewer_roles=roles,rationale=params["rationale"],breaking_change_acknowledged=params["breaking_change_acknowledged"])
    if (name=="environment.rollback")!=(proposal["activation_kind"]=="ROLLBACK"):
        raise ServiceBoundaryError("ACTIVATION_KIND_INVALID","execution operation differs from approved intent",status_code=409)
    decision=_record(root,"activation-reviews","decision_id",params["decision_id"])
    receipts=list(load_catalog(app.root).get("commits",{}).values())
    identities=set()
    for review in list_records(root,"records/activation-reviews"):
        if review["activation_proposal_id"]!=proposal["activation_proposal_id"] or review["decision"]!="APPROVE":continue
        proven=[receipt for receipt in receipts if receipt["context"]["project_id"]==project.project_id
            and receipt["context"]["operation_id"]=="environment.review" and receipt["result"]==review]
        if not proven:raise ServiceBoundaryError("REVIEW_IDENTITY_UNPROVEN","environment review lacks credential-bound commit",status_code=409)
        actor=app.tokens.resolve(proven[0]["context"]["grant_reference"])
        if actor.principal_type!="HUMAN" or actor.principal_id!=review["reviewer_id"] or not actor.can("environment:review") or not any(actor.can("review:role:"+role) for role in required):
            raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN","environment reviewer no longer authorized",status_code=403)
        identities.add(actor.principal_id)
    quorum=env["rollback_quorum"] if proposal["activation_kind"]=="ROLLBACK" else env["activation_quorum"]
    if len(identities)<quorum or decision["activation_proposal_id"]!=proposal["activation_proposal_id"]:
        raise ServiceBoundaryError("REVIEW_QUORUM_INVALID","environment quorum or decision binding incomplete",status_code=409)
    result=execute_activation(root,proposal_id=params["proposal_id"],decision_id=params["decision_id"],expected_generation=params["expected_generation"],
        expected_pointer_hash=params["expected_pointer_hash"],expected_registry_head_hash=params["expected_registry_head_hash"])
    return {"receipt":result,"registry_head":read_head(root)["head_hash"]}


def execute(app, project, request, principal):
    root, name, params = project.registry_root, request.operation_id, request.parameters
    try:
        if name=="feedback.add":
            from kg_mnp.lifecycle.feedback import add_feedback
            record=package_record(root,params["package_id"])
            verify_package(package_files(root,record)[2])
            return add_feedback(root,feedback_type="DEFECT",target_package_id=params["package_id"],observations=params["observations"],severity=params.get("severity","INFO"),reported_by=principal.principal_id)
        if name=="consumer.register":
            from kg_mnp.lifecycle.consumer import register_consumer
            record=package_record(root,params["package_id"])
            verify_package(package_files(root,record)[2])
            return register_consumer(root,consumer_name=params["name"],ontology_iri=record["ontology_iri"],owner_label=principal.principal_id,
                required_term_iris=params.get("required_term_iris",[]),package_constraints={"package_names":[record["package_name"]],"minimum_version":record["package_version"],"maximum_version_exclusive":None,"package_ids":[record["package_id"]]})
        if name=="object.trace":
            import json

            from rdflib import URIRef

            from kg_mnp.ingestion.evidence import verify_evidence_closure
            from kg_mnp.ingestion.limits import DEFAULT_LIMITS
            from kg_mnp.ingestion.source_store import SourceStore
            from kg_mnp.semantic_kernel.artifact_resolver import (
                WorkspaceArtifactResolver,
            )
            path=package_path(project,params["package_id"])
            manifest=json.loads((path/"provenance/statement-provenance-manifest.json").read_bytes())
            statements=[row for row in manifest["statements"] if row["subject"]==URIRef(params["instance_iri"]).n3()]
            resolver=WorkspaceArtifactResolver(project.root);store=SourceStore(project.root);evidence=[]
            for identifier in sorted({ref for row in statements for ref in row["evidence_record_refs"]}):
                record=resolver.resolve(identifier).document
                source=store.verify_source(record["source_id"])
                snapshot=resolver.resolve(record["plugin_snapshot_id"]).document
                transforms=tuple(resolver.resolve(ref).document for ref in record["transformation_ids"])
                verify_evidence_closure(records=(record,),transformations=transforms,snapshots=(snapshot,),
                    sources={source["source_id"]:(source,store.blob_for(source).read_bytes())},limits=DEFAULT_LIMITS)
                evidence.append(record)
            return {"package_id":params["package_id"],"instance_iri":params["instance_iri"],"statements":statements,"evidence":evidence}
        if name.startswith("change."):return _change(root,request,principal)
        if name.startswith("environment."):return _environment(app,project,request,principal)
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
                evaluation=_record(root,"change-evaluations","evaluation_id",params.get("change_evaluation_id"))
                if evaluation["candidate_package_id"]!=record["package_id"] or evaluation["evaluation_status"]!="COMPLETE":
                    raise ServiceBoundaryError("SUCCESSOR_CLOSURE_REQUIRED","complete current change evaluation required",status_code=409)
                version=_record(root,"version-compatibility","report_id",evaluation["version_compatibility_report_id"])
                if not version["compatible"]:raise ServiceBoundaryError("VERSION_INCOMPATIBLE","version policy not satisfied",status_code=409)
                return create_release_candidate(root,candidate_package_id=record["package_id"],base_package_id=evaluation["base_package_id"],
                    semantic_diff_id=evaluation["semantic_diff_id"],version_compatibility_report_id=version["report_id"],impact_analysis_id=evaluation["impact_analysis_id"],
                    regression_test_report_id=evaluation["regression_test_report_id"],change_proposal_id=evaluation["change_proposal_id"],change_evaluation_id=evaluation["evaluation_id"],
                    release_candidate_kind="PATCH_COMPATIBLE",required_roles=["RELEASE_MANAGER"],minimum_distinct_reviewers=1)
            return create_release_candidate(root, candidate_package_id=params["package_id"], required_roles=["RELEASE_MANAGER"], minimum_distinct_reviewers=1)
        if name == "release.review":
            if not principal.can("review:role:RELEASE_MANAGER"):
                raise ServiceBoundaryError("REVIEW_ROLE_FORBIDDEN", "release manager grant required", status_code=403)
            return record_review(root, params["candidate_id"], reviewer_id=principal.principal_id, reviewer_roles=["RELEASE_MANAGER"],
                                 action=params["decision"], rationale=params["rationale"], explicit_human_action=True)
        candidate = record_by_id(root, "records/release-candidates", "release_candidate_id", params["candidate_id"])
        registered=package_record(root,candidate["candidate_package_id"])
        verify_package(package_files(root,registered)[2])
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
