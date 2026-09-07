import time

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from tests.services.test_core_fencing import pending  # noqa: F401


def test_expired_uncommitted_local_job_has_explicit_authenticated_recovery(pending):  # noqa: F811
    service, principal, _, job_id = pending
    token, operator = service.tokens.create(principal_id=principal.principal_id, principal_type="HUMAN",
        permissions={"*"},project_ids=set(),created_by="synthetic-recovery-test")
    abandoned = service.jobs.claim(worker_id="abandoned", lease_seconds=0.001)
    time.sleep(0.01)
    restarted = ApplicationService(service.configuration)
    with TestClient(create_app(restarted)) as client:
        response = client.post(f"/api/v1/jobs/{job_id}/recovery",headers={"Authorization":"Bearer "+token},
            json={"mode":"RETRY_LOCAL","expected_attempt":abandoned.attempt})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "QUEUED"
    assert any(event['payload'].get('requested_by')==principal.principal_id for event in restarted.jobs.events(job_id) if event['event_type']=='JOB_LOCAL_RETRY_REQUESTED')
    recovered = JobWorker(restarted.jobs,restarted).run_once("replacement")
    assert recovered.status == "SUCCEEDED"
    assert recovered.attempt == abandoned.attempt+1
    assert recovered.fencing_token > abandoned.fencing_token
    with TestClient(create_app(restarted)) as client:
        response=client.post(f"/api/v1/jobs/{job_id}/recovery",headers={"Authorization":"Bearer "+token},
            json={"mode":"RECOVER_COMMITTED","expected_attempt":abandoned.attempt})
        assert response.status_code==200 and response.json()["status"]=="SUCCEEDED"
        assert client.post(f"/api/v1/jobs/{job_id}/recovery",json={"mode":"RETRY_LOCAL","expected_attempt":abandoned.attempt}).status_code==401
    assert operator.principal_id==principal.principal_id


@pytest.mark.parametrize("fault", ["active", "cancelled", "revoked", "external"])
def test_recovery_cannot_override_current_authority_or_external_uncertainty(pending, fault):  # noqa: F811
    service, principal, project_id, job_id = pending
    if fault == "external":
        service.jobs.cancel(job_id)
        job, _ = service.jobs.create(operation_id="integration.execute",project_id=project_id,
            parameters={"__principal":{"principal_id":principal.principal_id,"token_id":principal.token_id}})
        job_id = job.job_id
    abandoned = service.jobs.claim(worker_id="original",lease_seconds=30 if fault=="active" else 0.001)
    if fault != "active":
        time.sleep(0.01)
    if fault == "cancelled":
        service.jobs.cancel(job_id)
        service.jobs.claim(worker_id="recover-expiry")
    actor=principal
    if fault=="revoked":
        service.tokens.revoke(principal.token_id)
        _, actor=service.tokens.create(principal_id=principal.principal_id,principal_type="HUMAN",permissions={"*"},project_ids=set(),created_by="synthetic-recovery-operator")
    with pytest.raises(ServiceBoundaryError):
        service.request_job_recovery(job_id,actor,mode="RETRY_LOCAL",expected_attempt=abandoned.attempt)
    assert service.jobs.get(job_id).status != "QUEUED"
