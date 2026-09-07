"""Nonempty source -> approved scope -> candidates -> per-item review -> confirmation."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.uploads import receive_upload


def call(service, principal, project_id, operation, params, key):
    result = service.execute(OperationRequest(operation, project_id, params, key), principal)
    if not result.job_id:
        return result.payload
    observed = []
    original = service.execute_job
    def capture(job, parameters):
        try:
            return original(job, parameters)
        except Exception as exc:
            observed.append(exc)
            raise
    service.execute_job = capture
    try:
        job = JobWorker(service.jobs, service).run_once("modeling-test")
    finally:
        service.execute_job = original
    if observed:
        raise observed[0]
    assert job.status == "SUCCEEDED", job.error
    return job.result


@pytest.fixture
def modeling_case(tmp_path):
    jar = Path(__file__).parents[2] / "third_party/downloads/robot-1.9.7.jar"
    service = ApplicationService(ServiceConfiguration(str(tmp_path), review_profile="DEVELOPMENT_SINGLE_REVIEWER", reasoner_jar=str(jar)))
    _, principal = service.tokens.create(principal_id="synthetic-human", principal_type="HUMAN", permissions={"*"},
                                         project_ids=set(), created_by="explicit-development-test")
    project_id = service.execute(OperationRequest("project.create", parameters={"name": "modeling", "domain_pack": "minimal",
        "domain_pack_version": "0.1.0"}), principal).payload["project_id"]
    async def chunks():
        yield b"entity,label\nsynthetic,Synthetic entity\n"
    accepted = asyncio.run(receive_upload(service, project_id, principal, chunks(), filename="synthetic.csv",
                                          media_type="text/csv", idempotency_key="upload"))
    job = JobWorker(service.jobs, service).run_once("upload")
    assert job.job_id == accepted.job_id and job.status == "SUCCEEDED", job.error
    plan = call(service, principal, project_id, "ingestion.plan", {"batch_id": job.result["batch"]["batch_id"]}, "plan")["plan"]
    run = call(service, principal, project_id, "ingestion.run", {"plan_id": plan["plan_id"]}, "ingest")["run"]
    scope = call(service, principal, project_id, "modeling.scope", {
        "run_id": run["run_id"], "description": "Synthetic minimal label modeling", "object_families": ["Entity"],
        "in_scope": ["entity labels"], "out_of_scope": ["production deployment"], "namespace": "urn:synthetic:example:",
    }, "scope")["scope"]
    approval = call(service, principal, project_id, "modeling.scope.approve", {"scope_id": scope["scope_id"],
        "rationale": "Explicit human approval of the synthetic scope"}, "approve")["approval"]
    prepared = call(service, principal, project_id, "modeling.prepare", {"scope_id": scope["scope_id"],
        "approval_id": approval["approval_id"], "questions": [{"question_text": "Which entities and labels are present?",
        "purpose": "structural retrieval and traceability", "required_concepts": ["Entity"], "expected_answer_shape": "ENTITY_LIST"}]}, "prepare")
    proposed = call(service, principal, project_id, "modeling.proposal", {"bundle_id": prepared["bundle"]["modeling_input_bundle_id"],
        "providers": ["baseline-reuse-provider", "rule-mapping-provider"]}, "proposal")
    return service, principal, project_id, proposed


def run_confirmed_initial_chain(modeling_case):
    service, principal, project_id, proposed = modeling_case
    queue = proposed["queue"]
    assert proposed["proposal"]["abox_candidates"]
    from kg_mnp.services.errors import ServiceBoundaryError
    with pytest.raises(ServiceBoundaryError):
        call(service, principal, project_id, "review.finalize", {"review_id": queue["review_queue_id"]}, "unreviewed")
    head = None
    for index, item in enumerate(queue["items"]):
        if item["candidate_id"] is None:
            continue
        result = call(service, principal, project_id, "review.action", {"review_id": queue["review_queue_id"],
            "candidate_id": item["candidate_id"], "expected_head": head, "decision": "ACCEPT",
            "rationale": f"Synthetic test human decision for candidate {index}"}, f"review-{index}")
        head = result["action"]["action_hash"]
    result = call(service, principal, project_id, "review.finalize", {"review_id": queue["review_queue_id"]}, "confirmed")
    assert result["confirmed_package"]["package_status"] == "READY_FOR_COMPILATION"
    assert result["confirmed_package"]["confirmed_abox"]
    package_id = result["confirmed_package"]["package_id"]
    question_id = proposed["coverage"]["coverage"][0]["question_id"]
    plan = call(service, principal, project_id, "compile.plan", {"confirmed_package_id": package_id,
        "package_name": "synthetic-minimal", "package_version": "0.1.0", "ontology_iri": "urn:synthetic:ontology",
        "version_iri": "urn:synthetic:ontology:0.1.0", "oracles": [{"question_id": question_id,
        "query_asset_id": "minimal-query-list-entities", "min_rows": 1, "required_bindings": ["entity", "label"]}]}, "compile-plan")["plan"]
    built = call(service, principal, project_id, "compile.build", {"plan_id": plan["plan_id"]}, "compile-build")
    assert built["manifest"]["package_status"] == "VALIDATED_UNPUBLISHED"
    assert built["reports"]["competency-question-test-report.json"]["required_passed"] is True
    verified = call(service, principal, project_id, "package.verify", {"package_id":built["package_id"]}, "verify")
    assert verified["status"] == "VERIFIED"
    exported = call(service, principal, project_id, "package.export", {"package_id":built["package_id"]}, "export")
    assert exported["size_bytes"] > 0 and len(exported["sha256"]) == 64
    registered = call(service, principal, project_id, "registry.import", {"package_id": built["package_id"]}, "register")
    assert registered["status"] == "IMPORTED_VERIFIED"
    candidate = call(service, principal, project_id, "release.candidate", {"package_id": built["package_id"]}, "release-candidate")
    reviewed = call(service, principal, project_id, "release.review", {"candidate_id": candidate["release_candidate_id"],
        "decision": "APPROVE", "rationale": "Human synthetic release approval"}, "release-review")
    from kg_mnp.lifecycle.registry.head import read_head
    from kg_mnp.services.projects import get_project
    head = read_head(get_project(service.root, project_id).registry_root)["head_hash"]
    released = call(service, principal, project_id, "release.publish", {"candidate_id": candidate["release_candidate_id"],
        "review_id": reviewed["review_id"], "expected_registry_head_hash": head}, "publish")
    assert released["release"]["release_status"] == "RELEASED"
    inspected = call(service, principal, project_id, "release.inspect", {"release_id":released["release"]["release_id"]}, "inspect-release")
    assert inspected["release_id"] == released["release"]["release_id"]
    view=call(service,principal,project_id,"visualization.export",{"package_id":built["package_id"]},"visualization")
    assert view["nodes"] and view["status"]=="CONVERTED"
    integration=call(service,principal,project_id,"integration.plan",{"release_id":released["release"]["release_id"],"target_id":"local-graphdb"},"integration-plan")
    approval=call(service,principal,project_id,"integration.review",{"plan_id":integration["plan"]["plan_id"],"rationale":"Synthetic plan review, not deployment"},"integration-review")
    assert "grant_reference" not in approval
    observed=call(service,principal,project_id,"integration.execute",{"plan_id":integration["plan"]["plan_id"],"approval_id":approval["approval"]["approval_id"]},"integration-observe")
    assert observed["status"]=="BLOCKED_BY_OFFLINE_POLICY" and observed["external_request_attempted"] is False
    invocation=call(service,principal,project_id,"workflow.enqueue",{"release_id":released["release"]["release_id"],"action_id":"request-source-review","note":"Synthetic follow-up request"},"workflow")
    assert invocation["status"]=="REQUEST_ENQUEUED" and invocation["last_verification_status"]=="NOT_EXECUTED"
    return {"service":service,"principal":principal,"project_id":project_id,"confirmed_id":package_id,"question_id":question_id,
            "package":built,"release":released["release"]}


def test_nonempty_review_confirmed_workflow(modeling_case):
    run_confirmed_initial_chain(modeling_case)
