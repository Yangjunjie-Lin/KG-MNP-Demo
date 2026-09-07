import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


@pytest.mark.parametrize("host", ["testserver/sources?ignored=", "testserver#fragment", "testserver@other.invalid", "testserver\\share"])
def test_invalid_host_is_rejected_before_security_url_reconstruction(tmp_path, host):
    with TestClient(create_app(ApplicationService(ServiceConfiguration(str(tmp_path))))) as client:
        result=client.post('/api/v1/projects',headers={'host':host},content=b'{}')
    assert result.status_code==400
    assert result.headers['x-content-type-options']=='nosniff'
    assert result.json()['error']['code']=='REQUEST_TARGET_INVALID'


def test_windows_unc_static_request_never_reaches_filesystem_resolution(tmp_path, monkeypatch):
    import os
    static=tmp_path/'static'
    static.mkdir()
    (static/'assets').mkdir()
    (static/'index.html').write_text('<!doctype html><title>Synthetic</title>',encoding='utf-8')
    service=ApplicationService(ServiceConfiguration(str(tmp_path/'service'),workbench_root=str(static)))
    with TestClient(create_app(service)) as client:
        original=os.path.realpath
        def confined(path,*args,**kwargs):
            assert not str(path).startswith('\\\\'), 'UNC resolution must never occur'
            return original(path,*args,**kwargs)
        monkeypatch.setattr(os.path,'realpath',confined)
        result=client.get('/assets/%5C%5Cexample.invalid/share')
        assert result.status_code==400
