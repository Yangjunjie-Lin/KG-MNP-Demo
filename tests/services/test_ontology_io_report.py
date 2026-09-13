import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from tests.upgrade.test_ontology_io import empty_report
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.projects import get_project


def test_report_import_uses_real_auth_flat_api_and_does_not_mutate_project(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    owner_token, owner = service.tokens.create(principal_id="report-owner", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    other_token, _ = service.tokens.create(principal_id="other", principal_type="HUMAN", permissions={"project:read"}, project_ids=set(), created_by="test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "report boundary", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), owner).payload["project_id"]
    root = Path(get_project(service.root, project).root)

    def digest():
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}

    before = digest()
    with TestClient(create_app(service)) as client:
        endpoint = "/api/v1/operations/ontology.io.inspect"
        request = {"project_id": project, "report": empty_report()}
        assert client.post(endpoint, json=request).status_code == 401
        assert client.post(endpoint, json=request, headers={"Authorization": "Bearer " + other_token}).status_code == 403
        headers = {"Authorization": "Bearer " + owner_token}
        response = client.post(endpoint, json=request, headers=headers)
        assert response.status_code == 200
        result = response.json()["payload"]
        assert result["production_allowed"] is False and result["source_authenticity"] == "UNVERIFIED_EXTERNAL_REPORT"
        assert client.post(endpoint, json={"project_id": project, "parameters": {"report": empty_report()}}, headers=headers).status_code == 422
        request["report"]["nested"] = {"private_gold": ["SENTINEL"]}
        response = client.post(endpoint, json=request, headers=headers)
        assert response.status_code == 422 and "SENTINEL" not in response.text
    assert digest() == before
