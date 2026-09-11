from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.contracts.canonical import semantic_hash
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import load_catalog
from tests.services.test_modeling_workflow import (
    call,
    modeling_case,  # noqa: F401
)


def retain_synthetic_result(name, value):
    root=os.environ.get('KG_MNP_RECEIPT_ROOT')
    if root:
        # Only synthetic public operation results; no token, URL or host path.
        target=Path(root)/'synthetic-artifacts'
        target.mkdir(exist_ok=True)
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def test_new_sandbox_runs_real_ingestion_profiles_and_has_no_approvals(tmp_path,monkeypatch):
    service=ApplicationService(ServiceConfiguration(str(tmp_path),review_profile='DEVELOPMENT_SINGLE_REVIEWER'))
    token,principal=service.tokens.create(principal_id='synthetic-human',principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='test')
    project=service.execute(OperationRequest('project.create',parameters={'name':'five stage','domain_pack':'minimal','domain_pack_version':'0.1.0'}),principal).payload['project_id']
    before=load_catalog(service.root)
    assert service.execute(OperationRequest('modeling.tutorial',project),principal).payload['execution_source']=='TUTORIAL_FIXTURE'
    assert load_catalog(service.root)==before
    result=call(service,principal,project,'modeling.tutorial.seed',{},'seed')
    retain_synthetic_result('real-input-profile.json',result)
    assert result['approval']=='NOT_GRANTED'
    assert [r['step_id'] for r in result['five_stage']['step_runs']]==['1.1','1.2']
    profile=result['five_stage']['artifacts'][-1]['content']
    assert profile['fields'] and profile['texts']
    assert any('E-001' in p['examples'] for p in profile['fields'])
    for item in result['five_stage']['artifacts']:
        assert semantic_hash(item['content'])==item['ref']['content_hash']
    assert result['five_stage']['step_runs'][0]['output_artifact_refs'][0] in result['five_stage']['step_runs'][1]['input_artifact_refs']
    replay=service.execute(OperationRequest('modeling.tutorial.seed',project,{},'seed'),principal)
    assert service.jobs.get(replay.job_id).result==result
    assert JobWorker(service.jobs,service).run_once('idempotency-replay') is None
    rerun=call(service,principal,project,'modeling.profile',{'run_id':result['run']['run_id']},'explicit-new-profile-run')
    first_steps=result['five_stage']['step_runs']
    next_steps=rerun['five_stage']['step_runs']
    assert first_steps[0]['job_id']==replay.job_id
    assert next_steps[0]['job_id']!=first_steps[0]['job_id']
    assert next_steps[0]['run_id']!=first_steps[0]['run_id']
    assert next_steps[0]['output_artifact_refs']==first_steps[0]['output_artifact_refs']
    assert next_steps[1]['input_artifact_refs']==first_steps[1]['input_artifact_refs']
    with pytest.raises(ServiceBoundaryError,match='new empty'):
        call(service,principal,project,'modeling.tutorial.seed',{},'second-seed')
    with TestClient(create_app(service)) as client:
        headers={'Authorization':'Bearer '+token}
        state=client.get(f'/api/v1/projects/{project}/state',headers=headers).json()
        methods=state['modeling_flow']['methods']
        # The failed second seed must not be hidden by the first successful
        # receipt. History remains downloadable, current attempt is failed.
        assert [m['method_id'] for m in methods if m['receipt_count']==2]==['1.1','1.2']
        assert [m['method_id'] for m in methods if m['status']=='FAILED']==['1.1','1.2']
        assert all('SANDBOX_NOT_EMPTY' in m['reason'] for m in methods[:2])
        assert not any(r['operation'] in {'review.action','review.finalize','modeling.scope.approve'} for r in state['results'])
        ref=result['five_stage']['artifacts'][-1]['ref']
        downloaded=client.get(f'/api/v1/projects/{project}/modeling/artifacts/{ref["artifact_id"]}',headers=headers)
        assert downloaded.status_code==200 and semantic_hash(downloaded.json())==ref['content_hash']
        assert client.get(f'/api/v1/projects/{project}/modeling/tutorial/files/not-allowed.json',headers=headers).status_code==404
        other=service.execute(OperationRequest('project.create',parameters={'name':'other','domain_pack':'minimal','domain_pack_version':'0.1.0'}),principal).payload['project_id']
        assert client.get(f'/api/v1/projects/{other}/modeling/artifacts/{ref["artifact_id"]}',headers=headers).status_code==404
    for key in ('KG_MNP_QWEN_ENDPOINT','KG_MNP_QWEN_MODEL','KG_MNP_QWEN_REVISION','ZHIGOU_QWEN_ENDPOINT','ZHIGOU_QWEN_MODEL','ZHIGOU_QWEN_REVISION','OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_TEXT_MODEL'):
        monkeypatch.delenv(key,raising=False)
    accepted=service.execute(OperationRequest('modeling.scope.draft',project,{'run_id':result['run']['run_id'],'business_goal':'查询归属','business_rules':['当前快照']},'qwen'),principal)
    assert accepted.status=='ACCEPTED'
    job=JobWorker(service.jobs,service).run_once('qwen-missing')
    assert job.status=='FAILED' and job.error['code']=='BLOCKED_BY_PROVIDER'
    assert 'LIVE' not in json.dumps(result)


def test_new_operations_reject_client_roles_and_cross_project(tmp_path):
    service=ApplicationService(ServiceConfiguration(str(tmp_path)))
    _,owner=service.tokens.create(principal_id='owner',principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='test')
    _,other=service.tokens.create(principal_id='other',principal_type='HUMAN',permissions={'project:read','model:propose','source:read'},project_ids=set(),created_by='test')
    project=service.execute(OperationRequest('project.create',parameters={'name':'private','domain_pack':'minimal','domain_pack_version':'0.1.0'}),owner).payload['project_id']
    with pytest.raises(ServiceBoundaryError):
        service.execute(OperationRequest('modeling.methods',project),other)
    with pytest.raises(ServiceBoundaryError):
        service.execute(OperationRequest('modeling.profile',project,{'run_id':'urn:kg-mnp:ingestion-run:'+'0'*64,'reviewer_role':'admin'},'bad'),owner)


def test_selected_candidates_run_shared_compiler_checks_without_approval(modeling_case):  # noqa: F811
    service,principal,project,proposed=modeling_case
    candidates=[c for key in ('tbox_candidates','abox_candidates','mapping_candidates','shacl_candidates') for c in proposed['proposal'][key]]
    result=call(service,principal,project,'modeling.semantic.check',{'review_id':proposed['queue']['review_queue_id'],
                'candidate_ids':[c['candidate_id'] for c in candidates]},'semantic-check')
    runs=result['five_stage']['step_runs']
    assert [r['step_id'] for r in runs]==['4.1','4.2']
    report=result['five_stage']['artifacts'][-1]['content']
    assert report['checks']['hermit']['status']=='CONSISTENT'
    assert report['checks']['owl_profile']['status']=='PASSED'
    assert report['checks']['shacl']['conforms'] is True
    assert report['checks']['explicit_target_coverage']['target_count']>0
    assert report['status']=='PASS' and report['approval']=='NOT_GRANTED'
    retain_synthetic_result('real-candidate-semantic-check.json',result)
    review=call(service,principal,project,'review.replay',{'review_id':proposed['queue']['review_queue_id']},'read')
    assert review['actions']==[]
    with pytest.raises(ServiceBoundaryError):
        call(service,principal,project,'review.finalize',{'review_id':proposed['queue']['review_queue_id']},'not-approved')
