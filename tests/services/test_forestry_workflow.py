from __future__ import annotations

import asyncio
from pathlib import Path

from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.uploads import receive_upload
from tests.services.test_modeling_workflow import call


def test_synthetic_forestry_nonempty_confirmed_compile_and_query(tmp_path):
    root=Path(__file__).parents[2]
    service=ApplicationService(ServiceConfiguration(str(tmp_path),review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        reasoner_jar=str(root/"third_party/downloads/robot-1.9.7.jar")))
    _,principal=service.tokens.create(principal_id="synthetic-forest-reviewer",principal_type="HUMAN",permissions={"*"},project_ids=set(),created_by="test")
    project=service.execute(OperationRequest("project.create",parameters={"name":"synthetic-forest","domain_pack":"forestry","domain_pack_version":"0.2.0"}),principal).payload
    project_id=project["project_id"]; sources=[]
    for filename in ["sites.csv","trees.csv","inspections.csv"]:
        async def chunks(name=filename):yield (root/"domain_packs/forestry/fixtures"/name).read_bytes()
        accepted=asyncio.run(receive_upload(service,project_id,principal,chunks(),filename=filename,media_type="text/csv",idempotency_key=filename))
        job=JobWorker(service.jobs,service).run_once("forest-upload")
        assert job.job_id==accepted.job_id and job.status=="SUCCEEDED",job.error
        sources.append(job.result["source"]["source_id"])
    batch=call(service,principal,project_id,"source.batch",{"source_ids":sources},"batch")["batch"]
    plan=call(service,principal,project_id,"ingestion.plan",{"batch_id":batch["batch_id"]},"plan")["plan"]
    run=call(service,principal,project_id,"ingestion.run",{"plan_id":plan["plan_id"]},"ingestion")["run"]
    scope=call(service,principal,project_id,"modeling.scope",{"run_id":run["run_id"],"description":"Synthetic tree inspection and site example",
        "object_families":["TreeRecord","InspectionRecord","Site"],"in_scope":["tree inspection records"],"out_of_scope":["field diagnosis"],"namespace":"urn:synthetic:forest:"},"scope")["scope"]
    approval=call(service,principal,project_id,"modeling.scope.approve",{"scope_id":scope["scope_id"],"rationale":"Synthetic record scope"},"approve")["approval"]
    prepared=call(service,principal,project_id,"modeling.prepare",{"scope_id":scope["scope_id"],"approval_id":approval["approval_id"],
        "questions":[{"question_text":"Which synthetic trees have inspections and sites?","purpose":"relational retrieval and evidence","required_concepts":["TreeRecord","InspectionRecord","Site"],"expected_answer_shape":"ENTITY_LIST"}]},"prepare")
    proposed=call(service,principal,project_id,"modeling.proposal",{"bundle_id":prepared["bundle"]["modeling_input_bundle_id"],
        "providers":["baseline-reuse-provider","manual-candidate-provider"]},"propose")
    assert proposed["proposal"]["abox_candidates"]
    head=None
    for index,item in enumerate(proposed["queue"]["items"]):
        if not item["candidate_id"]:continue
        decision=call(service,principal,project_id,"review.action",{"review_id":proposed["queue"]["review_queue_id"],"candidate_id":item["candidate_id"],
            "decision":"ACCEPT","rationale":"Synthetic test human per-item review","expected_head":head},f"decision-{index}")
        head=decision["action"]["action_hash"]
    confirmed=call(service,principal,project_id,"review.finalize",{"review_id":proposed["queue"]["review_queue_id"]},"confirm")["confirmed_package"]
    compilation=call(service,principal,project_id,"compile.plan",{"confirmed_package_id":confirmed["package_id"],"package_name":"synthetic-forestry",
        "package_version":"0.2.0","ontology_iri":"urn:synthetic:forest:ontology","version_iri":"urn:synthetic:forest:ontology:0.2.0",
        "oracles":[{"question_id":prepared["questions"]["questions"][0]["question_id"],"query_asset_id":"forestry-query-tree-inspections","min_rows":6,
        "required_bindings":["tree","treeCode","inspection","inspectionCode","site"]}]},"compilation-plan")["plan"]
    built=call(service,principal,project_id,"compile.build",{"plan_id":compilation["plan_id"]},"build")
    assert built["reports"]["shacl-validation-report.json"]["status"]=="CONFORMS"
    queried=call(service,principal,project_id,"ods.query",{"package_id":built["package_id"],"class_iri":"https://example.invalid/forestry#TreeRecord","limit":100,"offset":0},"query")
    assert len(queried["rows"])==6
    traced=call(service,principal,project_id,"object.trace",{"package_id":built["package_id"],"instance_iri":queried["rows"][0]["iri"]},"trace")
    assert traced["evidence"] and all(record["source_id"] in sources for record in traced["evidence"])
