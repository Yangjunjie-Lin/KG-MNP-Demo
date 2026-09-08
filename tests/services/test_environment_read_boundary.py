"""Missing identifiers and corrupted existing state have different semantics."""
import json

import pytest

from kg_mnp.lifecycle.environment import init_environment
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import get_project


def test_corrupt_existing_environment_is_integrity_error_not_missing(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path / "service")))
    _, principal = service.tokens.create(principal_id="synthetic-reader", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    project = service.execute(OperationRequest("project.create", parameters={"name":"read-boundary","domain_pack":"minimal","domain_pack_version":"0.1.0"}), principal).payload
    root = get_project(service.root, project["project_id"]).registry_root
    env = init_environment(root, environment_name="read-boundary")
    pointer = next((root / "state").glob("environment-pointer-*.json"))
    value = json.loads(pointer.read_bytes()); value["generation"] = "corrupt"
    pointer.write_text(json.dumps(value), encoding="utf-8")
    before = pointer.read_bytes()
    with pytest.raises(ServiceBoundaryError) as failure:
        service.execute(OperationRequest("environment.inspect", project["project_id"], {"environment_id":env["environment_id"]}), principal)
    assert failure.value.status_code == 409
    assert failure.value.code != "ARTIFACT_NOT_FOUND"
    assert pointer.read_bytes() == before
