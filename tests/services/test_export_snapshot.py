"""A task-bound snapshot is verified once by export and byte-bound on download."""
import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.contracts.canonical import bytes_sha256
from kg_mnp.semantic_kernel.identifiers import package_storage_key
from kg_mnp.services.compilation import read_export_snapshot
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import get_project, load_catalog
from tests.package_archive.test_snapshot_export import package
from tests.services.test_modeling_workflow import call


def test_export_snapshot_is_project_bound_tamper_checked_and_revocable(tmp_path,monkeypatch):
    service=ApplicationService(ServiceConfiguration(str(tmp_path/'service')))
    _,human=service.tokens.create(principal_id='synthetic-exporter',principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='test')
    project=service.execute(OperationRequest('project.create',parameters={'name':'export','domain_pack':'minimal','domain_pack_version':'0.1.0'}),human).payload['project_id']
    fixture=package(tmp_path)
    package_id=json.loads((fixture/'ontology-package.json').read_bytes())['package_id']
    target=Path(get_project(service.root,project).root)/'artifacts/packages'/package_storage_key(package_id)
    shutil.copytree(fixture,target)
    exported=call(service,human,project,'package.export',{'package_id':package_id},'prepare')
    job_id=next(j.job_id for j in service.jobs.list_project(project) if j.operation_id=='package.export')
    raw=read_export_snapshot(service,human,project,job_id)
    assert bytes_sha256(raw)==exported['sha256'] and len(raw)==exported['size_bytes']
    other=service.execute(OperationRequest('project.create',parameters={'name':'other','domain_pack':'minimal','domain_pack_version':'0.1.0'}),human).payload['project_id']
    with pytest.raises(ServiceBoundaryError,match='another resource'):
        read_export_snapshot(service,human,other,job_id)
    original=Path.read_bytes
    def revoke_during_read(path):
        value=original(path)
        if path.suffix=='.kgop':
            service.tokens.revoke(human.token_id)
        return value
    monkeypatch.setattr(Path,'read_bytes',revoke_during_read)
    with pytest.raises(ServiceBoundaryError,match='revoked'):
        read_export_snapshot(service,human,project,job_id)
    monkeypatch.setattr(Path,'read_bytes',original)
    _,replacement=service.tokens.create(principal_id='synthetic-exporter',principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='test')
    generation=Path(load_catalog(service.root)['commits'][job_id]['root'])
    archive=generation/'artifacts/builds/exports'/(package_storage_key(package_id)+'.kgop')
    archive.write_bytes(raw+b'tampered')
    with pytest.raises(ServiceBoundaryError):
        read_export_snapshot(service,replacement,project,job_id)
