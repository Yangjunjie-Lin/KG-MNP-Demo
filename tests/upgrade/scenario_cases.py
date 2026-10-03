"""Explicit synthetic sources and independent pre-generation answers; never LIVE."""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from tests.services.test_modeling_workflow import call
from tests.upgrade.expert_spy import ExpertSpy
from tests.upgrade.test_full_chain import exact, finish_case
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.modeling.five_stage.scenarios import load_scene, resolve
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.uploads import receive_upload

ROOT = Path(__file__).resolve().parents[2]


def acceptance_for(identifier, configuration):
    """Expected rows declared from the synthetic fixture specification, not output."""
    if identifier == "organization_management":
        answer = exact(["employeeId", "departmentId"], [["E-001", "D-01"]])
    elif identifier == "equipment_maintenance":
        answer = exact(["device_id", "organization_id", "location_id"], [["EQ-001", "ORG-001", "LOC-001"]])
    else:
        answer = exact(["tree", "treeCode", "inspection", "inspectionCode", "site"], [])
        if "inspections" in configuration["stages"]["S3"]["selected_capabilities"]:
            ns = "urn:scenario:ancient_tree_inspection:"
            for event in ("INSP-001", "INSP-002"):
                answer["rows"].append({"tree": {"kind": "IRI", "value": ns + "trees:GT-001"},
                    "treeCode": {"kind": "LITERAL", "value": "GT-001", "datatype": "http://www.w3.org/2001/XMLSchema#string"},
                    "inspection": {"kind": "IRI", "value": ns + "inspections:" + event},
                    "inspectionCode": {"kind": "LITERAL", "value": event, "datatype": "http://www.w3.org/2001/XMLSchema#string"},
                    "site": {"kind": "IRI", "value": ns + "sites:LOC-001"}})
    return [{"query_asset_id": load_scene(identifier)["query_asset_id"], "expected": answer}]


def build_scenario_case(workspace, identifier, *, finish=True, configure_only=False, spy=None):
    scene = load_scene(identifier)
    selection = {"scenario_id": identifier, "scenario_version": scene["scenario_version"]}
    configuration = resolve(selection)
    service = ApplicationService(ServiceConfiguration(str(workspace), review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        ontology_trace_enabled=True, modeling_audit_content_enabled=True,
        reasoner_jar=str(ROOT / "third_party/downloads/robot-1.9.7.jar")))
    _, principal = service.tokens.create(principal_id="synthetic-scene-reviewer", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="isolated-scenario-engineering")
    project_id = service.execute(OperationRequest("project.create", parameters={"name": "synthetic-" + identifier,
        "domain_pack": scene["domain_pack"]["pack_id"], "domain_pack_version": scene["domain_pack"]["pack_version"]}), principal).payload["project_id"]
    results = []
    def run(operation, params, key):
        result = call(service, principal, project_id, operation, params, key)
        results.append({"operation": operation, "result": result})
        return result
    sources = {}
    for path in sorted((ROOT / scene["fixture_ref"]).glob("*.csv")):
        async def chunks(p=path):
            yield p.read_bytes()
        accepted = asyncio.run(receive_upload(service, project_id, principal, chunks(), filename=path.name,
            media_type="text/csv", idempotency_key=path.name))
        job = JobWorker(service.jobs, service).run_once("scenario-upload")
        assert job.job_id == accepted.job_id and job.status == "SUCCEEDED", job.error
        sources[job.result["source"]["source_id"]] = path.name
    batch = run("source.batch", {"source_ids": list(sources)}, "batch")["batch"]
    plan = run("ingestion.plan", {"batch_id": batch["batch_id"]}, "ingestion-plan")["plan"]
    ingestion = run("ingestion.run", {"plan_id": plan["plan_id"]}, "ingestion")["run"]
    acceptance = acceptance_for(identifier, configuration)
    session = run("modeling.session.open", {"run_id": ingestion["run_id"], "business_rules": [
        "Preserve exact identifiers, explicit negatives, unknown values and all source evidence",
        "Scenario vocabulary is an explicit synthetic design proposal, never automatic expert approval"],
        "acceptance": acceptance, "expected_revision": None, "scenario": selection,
        "scenario_acceptance": json.loads((ROOT / "tests/fixtures/scenario_acceptance" / (identifier + ".json")).read_bytes())}, "session")["session"]
    if configure_only:
        return {"service": service, "principal": principal, "project_id": project_id, "run": run,
            "session": session, "effective": configuration, "ingestion": ingestion, "sources": sources}
    for stage in range(1, 6):
        version = session["expert"]["stages"][str(stage)]
        session = run("modeling.expert.save", {"expected_revision": session["revision"], "expected_configuration_digest": version["digest"],
            # Explicit synthetic expert budget. Production limits stay unchanged. The prior
            # 200000-token reservation refusal remains a retained negative run.
            "confirm": True, "configuration": {**version["configuration"], "coverage_confirmed": True,
                "budget": {**version["configuration"]["budget"], "max_tokens": 600000}}}, f"confirm-{stage}")["session"]
    spy = spy or ExpertSpy(qwen=identifier != "organization_management", revise_scope=True)
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        run("modeling.profile", {"run_id": ingestion["run_id"]}, "profile")
        scope = run("modeling.scope", {"run_id": ingestion["run_id"], "description": "Synthetic engineering regression",
            "object_families": configuration["stages"]["S1"]["enabled_object_families"], "in_scope": ["source-bound selected scene capabilities"],
            "out_of_scope": ["production actions or inferred facts"], "namespace": configuration["namespace"]}, "scope")["scope"]
        approved = run("modeling.scope.approve", {"scope_id": scope["scope_id"], "rationale": "Synthetic explicit scene scope review"}, "approve")["approval"]
        prepared = run("modeling.prepare", {"scope_id": scope["scope_id"], "approval_id": approved["approval_id"], "questions": [{
            "question_text": "Which declared source-bound identities and relationships are present?", "purpose": "Independent frozen synthetic query",
            "required_concepts": configuration["stages"]["S1"]["enabled_object_families"], "expected_answer_shape": "ENTITY_LIST"}]}, "prepare")
        proposed = run("modeling.proposal", {"bundle_id": prepared["bundle"]["modeling_input_bundle_id"],
            "providers": ["baseline-reuse-provider", "manual-candidate-provider"]}, "propose")
        assert proposed["expert_loop"]["decision"] == "PASS", proposed["expert_loop"]
        if finish:
            case = finish_case(service, principal, project_id, run, identifier.replace("_", "-"), proposed, prepared, acceptance, session, ingestion, sources)
            from zhigou_toolchain.services.modeling_sessions import read
            from zhigou_toolchain.services.projects import get_project
            case["quality"] = run("modeling.scenario.quality", {"package_id": case["built"]["package_id"],
                "expected_revision": read(get_project(service.root, project_id).root)["revision"]}, "independent-quality")
        else:
            case = {"service": service, "principal": principal, "project_id": project_id, "run": run, "proposed": proposed, "session": session}
    return {**case, "spy": spy, "results": results, "effective": configuration}
