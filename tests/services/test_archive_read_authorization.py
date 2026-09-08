"""Download identity/project checks run before reading and again before return."""
import json
import shutil

import pytest

from kg_mnp.semantic_kernel.identifiers import package_storage_key
from kg_mnp.services.compilation import read_archive
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import get_project
from tests.package_archive.test_snapshot_export import package


def test_archive_download_does_not_return_after_revocation_or_cross_project_access(tmp_path, monkeypatch):
    service = ApplicationService(ServiceConfiguration(str(tmp_path / "service")))
    _, human = service.tokens.create(principal_id="download-human", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "download", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), human).payload
    source = package(tmp_path)
    identifier = json.loads((source / "ontology-package.json").read_bytes())["package_id"]
    destination = get_project(service.root, project["project_id"]).root
    shutil.copytree(source, __import__("pathlib").Path(destination) / "artifacts/packages" / package_storage_key(identifier))
    _, outsider = service.tokens.create(principal_id="outsider", principal_type="HUMAN", permissions={"package:read", "package:export"}, project_ids=set(), created_by="synthetic-test")
    with pytest.raises(ServiceBoundaryError, match="authorized"):
        read_archive(service, outsider, project["project_id"], identifier)
    from kg_mnp.semantic_kernel.packaging import archive
    original = archive.archive_bytes
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        service.tokens.revoke(human.token_id)
        return result
    monkeypatch.setattr(archive, "archive_bytes", revoked)
    with pytest.raises(ServiceBoundaryError) as denied:
        read_archive(service, human, project["project_id"], identifier)
    assert denied.value.code == "AUTH_TOKEN_REVOKED"
