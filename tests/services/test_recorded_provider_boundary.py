import asyncio
import json

from kg_mnp.jobs.worker import JobWorker
from kg_mnp.modeling.control_plane.providers.models import candidate_draft
from kg_mnp.services.uploads import receive_upload
from tests.services.test_modeling_workflow import call, modeling_case  # noqa: F401


def test_recorded_output_is_bound_to_uploaded_bytes_and_remains_proposal_only(modeling_case):  # noqa: F811
    service,human,project,proposed=modeling_case
    original=proposed["proposal"]["tbox_candidates"][0]
    draft=candidate_draft(draft_ref="recorded-1",draft_kind=original["candidate_kind"],candidate_action=original["candidate_action"],body=original["body"],rationale="Recorded synthetic candidate",
        kg_ir_item_refs=original["kg_ir_item_refs"],evidence_refs=original["evidence_refs"],domain_asset_refs=original["domain_asset_refs"],baseline_element_refs=original["baseline_element_refs"])
    registered=[]
    for name,data,media in [("prompt.txt",b"Synthetic recorded prompt - no live model invocation","text/plain"),("response.json",json.dumps({"candidate_drafts":[draft]}).encode(),"application/json")]:
        async def chunks(content=data):yield content
        asyncio.run(receive_upload(service,project,human,chunks(),filename=name,media_type=media,idempotency_key=name))
        job=JobWorker(service.jobs,service).run_once("recorded-upload")
        assert job.status=="SUCCEEDED",job.error
        registered.append(job.result["source"])
    result=call(service,human,project,"modeling.proposal",{"bundle_id":proposed["proposal"]["modeling_input_bundle_id"],"providers":["recorded-model-output-provider"],
        "recorded_prompt_source_id":registered[0]["source_id"],"recorded_response_source_id":registered[1]["source_id"],"recorded_model_id":"synthetic-recorded","recorded_model_revision":"fixture-v1"},"recorded-proposal")
    assert result["proposal"]["authority_level"]=="PROPOSAL_ONLY"
    assert len(result["proposal"]["model_invocation_records"])==1
    assert result["queue"]["items"]
    from kg_mnp.modeling.control_plane.providers.recorded_model import (
        verify_model_invocation_record,
    )
    from kg_mnp.modeling.control_plane.service import ModelingWorkspaceService
    from kg_mnp.semantic_kernel.artifact_resolver import WorkspaceArtifactResolver
    from kg_mnp.services.projects import get_project
    workspace=ModelingWorkspaceService(get_project(service.root,project).root)
    invocation=WorkspaceArtifactResolver(workspace.root).resolve(result['proposal']['model_invocation_records'][0]).document
    verify_model_invocation_record(invocation,request_bytes=(workspace.root/invocation['request_artifact_ref']).read_bytes(),
        response_bytes=(workspace.root/invocation['response_artifact_ref']).read_bytes())
    assert invocation['prompt_template_sha256']==registered[0]['content_sha256']
    assert invocation['response_sha256']==registered[1]['content_sha256']
    assert invocation['determinism_class']=='RECORDED_BYTES_ONLY'
