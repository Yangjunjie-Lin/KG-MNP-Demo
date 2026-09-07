from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.services import projects
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from tests.services.test_core_fencing import pending  # noqa: F401


def test_job_state_reuses_only_current_request_project_authorization(tmp_path,monkeypatch):
    service=ApplicationService(ServiceConfiguration(str(tmp_path)))
    token,principal=service.tokens.create(principal_id="human",principal_type="HUMAN",permissions={"*"},project_ids=set(),created_by="test")
    project=service.execute(OperationRequest("project.create",parameters={"name":"state","domain_pack":"minimal","domain_pack_version":"0.1.0"}),principal).payload
    for i in range(20):service.jobs.create(operation_id="source.register",project_id=project["project_id"],parameters={"__principal":{"principal_id":principal.principal_id,"token_id":principal.token_id}},idempotency_key=str(i))
    reads=[];original=projects.load_catalog
    def count(root):reads.append(root);return original(root)
    monkeypatch.setattr(projects,"load_catalog",count)
    with TestClient(create_app(service)) as client:
        response=client.get(f"/api/v1/projects/{project['project_id']}/state",headers={"Authorization":f"Bearer {token}"})
        assert response.status_code==200 and len(response.json()["jobs"])==20
        assert response.json()["project"]["validation_status"]=="NOT_RUN_BY_STATE_PROJECTION"
        assert len(reads)<10
        service.tokens.revoke(principal.token_id)
        assert client.get(f"/api/v1/projects/{project['project_id']}/state",headers={"Authorization":f"Bearer {token}"}).status_code==401


def test_state_handle_and_commit_receipts_use_one_catalog_snapshot(pending, monkeypatch):  # noqa: F811
    from kg_mnp.jobs.worker import JobWorker
    service, principal, project_id, _ = pending
    before = projects.load_catalog(service.root)
    assert JobWorker(service.jobs,service).run_once('writer').status=='SUCCEEDED'
    after = projects.load_catalog(service.root)
    assert before['projects'][project_id]['authority_revision'] < after['projects'][project_id]['authority_revision']
    token, _ = service.tokens.create(principal_id=principal.principal_id,principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='synthetic-reader')
    reads=[]
    def crossing_commit(_root):
        reads.append(1)
        return before if len(reads)==1 else after
    monkeypatch.setattr(projects,'load_catalog',crossing_commit)
    with TestClient(create_app(service)) as client:
        response=client.get(f'/api/v1/projects/{project_id}/state',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200
    state=response.json()
    assert len(reads)==1
    assert all(row['revision']<=state['project']['authority_revision'] for row in state['results'])
