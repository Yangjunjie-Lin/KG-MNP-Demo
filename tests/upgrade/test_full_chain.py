"""Synthetic end-to-end evidence, never expert/production research accuracy."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.services.test_modeling_workflow import call
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.uploads import receive_upload

ROOT = Path(__file__).resolve().parents[2]
XSD = "http://www.w3.org/2001/XMLSchema#string"


def exact(variables, values):
    return {"schema_version": "1.0.0", "query_type": "SELECT", "comparison": "MULTISET", "variables": variables,
            "rows": [{key: {"kind": "LITERAL", "value": value, "datatype": XSD} for key, value in zip(variables, row, strict=True)} for row in values]}


def hr_mapping(prepared, sources):
    vocab = "https://example.org/ontology/"
    tables = []
    for item in prepared["input_inventory"]["tables"]:
        source = sources[item["source_id"]]
        employee = source == "employees.csv"
        tables.append({"record_id": "employee" if employee else "department", "source_id": item["source_id"], "locator": item["locator"],
            "class_iri": vocab + ("Employee" if employee else "Department"), "identity_space": "employees" if employee else "departments",
            "id_field": "employee_id" if employee else "department_id",
            "literals": {key: {"predicate_iri": vocab + term, "datatype": "string"} for key, term in (
                [("employee_id", "employeeId"), ("employee_name", "employeeName")] if employee else [("department_id", "departmentId"), ("department_name", "departmentName")])},
            "references": [{"field": "department_id", "target_space": "departments", "predicate_iri": vocab + "belongsToDepartment"}] if employee else []})
    text_id = next(key for key, value in sources.items() if value == "staff_note.txt")
    return {"profile": "evidence-record-mapping-v2", "tables": tables, "text_templates": [{
        "record_id": "text-employee", "source_id": text_id, "class_iri": vocab + "Employee", "identity_space": "employees",
        "id_field": "employee_id", "template": "员工 {employee_id} 归属部门 {department_id}。",
        "references": [{"field": "department_id", "target_space": "departments", "predicate_iri": vocab + "belongsToDepartment"}]}]}


def build_case(workspace, pack, *, model_assistance=False):
    service = ApplicationService(ServiceConfiguration(str(workspace), review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        reasoner_jar=str(ROOT / "third_party/downloads/robot-1.9.7.jar")))
    _, principal = service.tokens.create(principal_id="synthetic-upgrade-reviewer", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="isolated-engineering-test")
    project = service.execute(OperationRequest("project.create", parameters={"name": f"synthetic-{pack}", "domain_pack": pack, "domain_pack_version": "0.1.0" if pack == "hr" else "0.1.1"}), principal).payload
    project_id, sources = project["project_id"], {}
    def run(operation, params, key):
        return call(service, principal, project_id, operation, params, key)
    names = ["employees.csv", "departments.csv", "staff_note.txt"] if pack == "hr" else ["trees.csv", "sites.csv", "inspections.csv"]
    for name in names:
        async def chunks(filename=name):
            yield (ROOT / "domain_packs" / pack / "fixtures" / filename).read_bytes()
        accepted = asyncio.run(receive_upload(service, project_id, principal, chunks(), filename=name,
            media_type="text/csv" if name.endswith(".csv") else "text/plain", idempotency_key=name))
        job = JobWorker(service.jobs, service).run_once("upgrade-upload")
        assert job.job_id == accepted.job_id and job.status == "SUCCEEDED", job.error
        sources[job.result["source"]["source_id"]] = name
    batch = run("source.batch", {"source_ids": list(sources)}, "batch")["batch"]
    plan = run("ingestion.plan", {"batch_id": batch["batch_id"]}, "plan")["plan"]
    ingestion = run("ingestion.run", {"plan_id": plan["plan_id"]}, "ingestion")["run"]
    expected = exact(["employeeId", "departmentId"], [("E-001", "D-01"), ("E-002", "D-02"), ("E-003", "D-01")]) if pack == "hr" else exact(["treeCode", "inspectionCode"], [("GT-001", "I-001"), ("GT-002", "I-002"), ("GT-003", "I-003")])
    query = "hr-query-employees" if pack == "hr" else "forestry-query-tree-inspections"
    acceptance = [{"query_asset_id": query, "expected": expected}]
    session = run("modeling.session.open", {"run_id": ingestion["run_id"], "business_rules": ["Preserve exact identifiers, explicit negatives, unknown values and all source evidence"],
        "acceptance": acceptance, "expected_revision": None}, "session")["session"]
    run("modeling.profile", {"run_id": ingestion["run_id"]}, "profile")
    concepts = ["Employee", "Department"] if pack == "hr" else ["TreeRecord", "InspectionRecord", "Site"]
    scope = run("modeling.scope", {"run_id": ingestion["run_id"], "description": "Synthetic engineering regression",
        "object_families": concepts, "in_scope": ["source-bound records"], "out_of_scope": ["production or diagnosis"], "namespace": f"urn:synthetic:{pack}:"}, "scope")["scope"]
    approval = run("modeling.scope.approve", {"scope_id": scope["scope_id"], "rationale": "Explicit synthetic scope approval"}, "scope-review")["approval"]
    prepared = run("modeling.prepare", {"scope_id": scope["scope_id"], "approval_id": approval["approval_id"], "questions": [{
        "question_text": "Which source records and explicit relationships are present?", "purpose": "Frozen exact-answer regression", "required_concepts": concepts, "expected_answer_shape": "ENTITY_LIST"}]}, "prepare")
    params = {"bundle_id": prepared["bundle"]["modeling_input_bundle_id"], "providers": ["baseline-reuse-provider", "manual-candidate-provider"]}
    if pack == "hr":
        params["record_mapping"] = hr_mapping(prepared, sources)
    if model_assistance:
        from zhigou_toolchain.services.modeling_sessions import read
        from zhigou_toolchain.services.projects import get_project
        params["model_assistance"] = {"execution_mode": "LIVE", "action": "GENERATE", "retrieval": "LLM_SUBSTITUTE", "chunking": "UNICODE_SUBSTITUTE",
            "expected_session_revision": read(get_project(service.root, project_id).root)["revision"]}
        if isinstance(model_assistance, dict):
            params["model_assistance"].update(model_assistance)
    proposed = run("modeling.proposal", params, "propose")
    return finish_case(service, principal, project_id, run, pack, proposed, prepared, acceptance, session, ingestion, sources)


def finish_case(service, principal, project_id, run, pack, proposed, prepared, acceptance, session, ingestion, sources):
    assert not proposed["proposal"]["conflicts"]
    review_id = proposed["queue"]["review_queue_id"]
    candidates = [c for key in ["tbox_candidates", "mapping_candidates", "abox_candidates", "shacl_candidates"] for c in proposed["proposal"][key]]
    checked = run("modeling.semantic.check", {"review_id": review_id, "candidate_ids": [c["candidate_id"] for c in candidates]}, "check")
    assert all(r["validation_status"] == "PASS" for r in checked["five_stage"]["step_runs"])
    head = None
    for index, item in enumerate(proposed["queue"]["items"]):
        if item["candidate_id"]:
            action = run("review.action", {"review_id": review_id, "candidate_id": item["candidate_id"], "decision": "ACCEPT",
                "rationale": "Synthetic test identity explicitly reviews this candidate; not expert certification", "expected_head": head}, f"review-{index}")
            head = action["action"]["action_hash"]
    confirmed = run("review.finalize", {"review_id": review_id}, "finalize")["confirmed_package"]
    compilation = run("compile.plan.exact", {"confirmed_package_id": confirmed["package_id"], "package_name": f"synthetic-{pack}",
        "package_version": "0.1.0", "ontology_iri": f"urn:synthetic:{pack}:ontology", "version_iri": f"urn:synthetic:{pack}:ontology:0.1.0",
        "oracles": [{"question_id": prepared["questions"]["questions"][0]["question_id"], **acceptance[0]}]}, "compile-plan")["plan"]
    built = run("compile.build", {"plan_id": compilation["plan_id"]}, "compile")
    assert built["reports"]["competency-question-test-report.json"]["required_passed"] is True
    exported = run("package.export", {"package_id": built["package_id"]}, "export")
    assert exported["size_bytes"] > 0
    imported = run("registry.import", {"package_id": built["package_id"]}, "import")
    assert imported["package_id"] == built["package_id"]
    return {"service": service, "principal": principal, "project_id": project_id, "run": run, "built": built,
            "session": session, "proposed": proposed, "ingestion": ingestion, "prepared": prepared, "sources": sources}


@pytest.fixture(scope="module")
def hr_case(tmp_path_factory):
    return build_case(tmp_path_factory.mktemp("upgrade-hr"), "hr")


@pytest.fixture(scope="module")
def forestry_case(tmp_path_factory):
    return build_case(tmp_path_factory.mktemp("upgrade-forest"), "forestry-workorders")


def test_hr_formal_package_and_source_query(hr_case):
    case = hr_case
    queried = case["run"]("ods.query", {"package_id": case["built"]["package_id"], "class_iri": "https://example.org/ontology/Employee", "limit": 100, "offset": 0}, "employees")
    assert len(queried["rows"]) == 3
    trace = case["run"]("object.trace", {"package_id": case["built"]["package_id"], "instance_iri": queried["rows"][0]["iri"]}, "trace")
    assert len({e["source_id"] for e in trace["evidence"]}) == 2
    from zhigou_toolchain.contracts.canonical import bytes_sha256
    from zhigou_toolchain.semantic_kernel.packaging.archive import verify_kgop
    from zhigou_toolchain.services.compilation import read_export_snapshot
    exported = next(j for j in case["service"].jobs.list_project(case["project_id"]) if j.operation_id == "package.export")
    raw = read_export_snapshot(case["service"], case["principal"], case["project_id"], exported.job_id)
    assert bytes_sha256(raw) == exported.result["sha256"]
    download = case["service"].root / "hr-downloaded.kgop"
    download.write_bytes(raw)
    assert verify_kgop(download)["status"] == "VALID"
    assert len([c for c in case["proposed"]["proposal"]["abox_candidates"] if c["body"]["candidate_type"] == "INDIVIDUAL"]) == 5


def test_forestry_real_work_orders_feedback_and_rollback(forestry_case):
    case, run = forestry_case, forestry_case["run"]
    package_id = case["built"]["package_id"]
    plan = run("task.plan", {"package_id": package_id, "goal": "Create followup orders only for explicit positive inspections"}, "task-plan")["plan"]
    assert [i["decision"] for i in plan["items"]] == ["CREATE", "SKIP", "VERIFY"]
    execution = run("task.execute", {"plan_id": plan["plan_id"]}, "execute")
    assert len(execution["business_state"]["orders"]) == 1
    assert execution["business_state"]["orders"][0]["object"].endswith("GT-001")
    assert len(execution["execution"]["pending_verification"]) == 1
    duplicate = run("task.execute", {"plan_id": plan["plan_id"]}, "execute-again")
    assert duplicate["execution"]["receipts"][0]["outcome"] == "EXISTING"
    candidate = run("evolution.propose", {"execution_id": execution["execution"]["execution_id"], "feedback": "Explicit followup work should use high priority in the next reviewed configuration", "priority": "high", "version": "1.1.0"}, "candidate")["candidate"]
    with pytest.raises(ServiceBoundaryError, match="Reviewed content"):
        run("evolution.activate", {"candidate_id": candidate["candidate_id"]}, "premature-activate")
    checked = run("evolution.evaluate", {"candidate_id": candidate["candidate_id"]}, "regression")["candidate"]
    assert checked["status"] == "VALIDATED"
    run("evolution.review", {"candidate_id": candidate["candidate_id"], "decision": "APPROVE", "rationale": "Synthetic test review"}, "evolution-review")
    active = run("evolution.activate", {"candidate_id": candidate["candidate_id"]}, "activate")["active"]
    with pytest.raises(ServiceBoundaryError, match="Replan"):
        run("task.execute", {"plan_id": plan["plan_id"]}, "stale-plan")
    updated = run("task.plan", {"package_id": package_id, "goal": plan["goal"]}, "updated-task")["plan"]
    assert updated["items"][0]["priority"] == "high"
    actual = run("task.execute", {"plan_id": updated["plan_id"]}, "updated-execution")
    assert actual["execution"]["configuration"]["priority"] == "high"
    assert len(actual["business_state"]["orders"]) == 1
    run("evolution.rollback", {"expected_configuration_digest": semantic_hash(active), "rationale": "Verify controlled rollback"}, "rollback")
    rolled = run("task.plan", {"package_id": package_id, "goal": plan["goal"]}, "rolled-plan")["plan"]
    assert rolled["items"][0]["priority"] == "normal"
