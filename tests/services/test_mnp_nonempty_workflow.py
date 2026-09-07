from __future__ import annotations

import asyncio
from pathlib import Path

from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.uploads import receive_upload
from tests.services.test_modeling_workflow import call


def test_mnp_mapping_record_is_nonempty_evidence_bound_and_conforms(tmp_path):
    root=Path(__file__).parents[2]; terms="https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
    service=ApplicationService(ServiceConfiguration(str(tmp_path),review_profile="DEVELOPMENT_SINGLE_REVIEWER",reasoner_jar=str(root/"third_party/downloads/robot-1.9.7.jar")))
    _,human=service.tokens.create(principal_id="synthetic-mnp-reviewer",principal_type="HUMAN",permissions={"*"},project_ids=set(),created_by="test")
    project=service.execute(OperationRequest("project.create",parameters={"name":"mnp-evidence","domain_pack":"mnp","domain_pack_version":"1.0.0"}),human).payload["project_id"]
    async def chunks():yield b'mappingCode,sourceApi,sourceFieldPath,targetTerm,mappingReviewStatus\nSYN-M01,Synthetic source,sample.field,Subscriber,SYNTHETIC_TEST\n'
    asyncio.run(receive_upload(service,project,human,chunks(),filename="mapping.csv",media_type="text/csv",idempotency_key="upload"))
    registered=JobWorker(service.jobs,service).run_once("upload").result
    plan=call(service,human,project,"ingestion.plan",{"batch_id":registered["batch"]["batch_id"]},"plan")["plan"]
    run=call(service,human,project,"ingestion.run",{"plan_id":plan["plan_id"]},"run")["run"]
    scope=call(service,human,project,"modeling.scope",{"run_id":run["run_id"],"description":"Synthetic MNP mapping compatibility, not eligibility judgement","object_families":["MappingRecord"],"in_scope":["mapping trace"],"out_of_scope":["eligibility decisions"],"namespace":"urn:synthetic:mnp:"},"scope")["scope"]
    approval=call(service,human,project,"modeling.scope.approve",{"scope_id":scope["scope_id"],"rationale":"Synthetic mapping scope"},"approve")["approval"]
    prepared=call(service,human,project,"modeling.prepare",{"scope_id":scope["scope_id"],"approval_id":approval["approval_id"],"questions":[{"question_text":"Which MappingRecord exists?","purpose":"nonempty compatibility and provenance","required_concepts":["MappingRecord"],"expected_answer_shape":"ENTITY_LIST"}]},"prepare")
    rules={"profile":"evidence-record-mapping-v1","tables":[{"table_id":"mappings","source_name":"mapping.csv","class_iri":terms+"MappingRecord","id_field":"mappingCode",
        "literals":{field:terms+field for field in ["sourceApi","sourceFieldPath","targetTerm","mappingReviewStatus"]},"references":[]}]}
    proposed=call(service,human,project,"modeling.proposal",{"bundle_id":prepared["bundle"]["modeling_input_bundle_id"],"providers":["manual-candidate-provider"],"record_mapping":rules},"propose")
    head=None
    for index,item in enumerate(proposed["queue"]["items"]):
        if item["candidate_id"]:
            action=call(service,human,project,"review.action",{"review_id":proposed["queue"]["review_queue_id"],"candidate_id":item["candidate_id"],"decision":"ACCEPT","rationale":"Per-item synthetic human decision","expected_head":head},f"review-{index}")["action"]
            head=action["action_hash"]
    confirmed=call(service,human,project,"review.finalize",{"review_id":proposed["queue"]["review_queue_id"]},"confirm")["confirmed_package"]
    plan=call(service,human,project,"compile.plan",{"confirmed_package_id":confirmed["package_id"],"package_name":"synthetic-mnp-mapping","package_version":"0.1.0","ontology_iri":"urn:synthetic:mnp:ontology","version_iri":"urn:synthetic:mnp:ontology:0.1.0",
        "oracles":[{"question_id":prepared["questions"]["questions"][0]["question_id"],"query_asset_id":"mnp-queries-source-alignment","min_rows":1,"required_bindings":["term","mapApi","mapField","mapTarget","mapReview"]}]},"compile-plan")["plan"]
    built=call(service,human,project,"compile.build",{"plan_id":plan["plan_id"]},"build")
    assert built["reports"]["shacl-validation-report.json"]["status"]=="CONFORMS"
    result=call(service,human,project,"ods.query",{"package_id":built["package_id"],"class_iri":terms+"MappingRecord","limit":100,"offset":0},"query")
    assert len(result["rows"])==1
