"""Replacement guarantees for the retired three static browser bundles."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration

ROOT=Path(__file__).resolve().parents[2]


def test_only_the_current_local_bundle_is_a_product_frontend():
    html=(ROOT/'workbench/index.html').read_text(encoding='utf-8')
    assert 'https://' not in html and 'http://' not in html
    assert 'src="/src/main.tsx"' in html
    assert all(not (ROOT/'web'/name/'index.html').exists() for name in ('workbench','diagnostics','governance'))


def test_client_does_not_execute_untrusted_markup_or_persist_credentials():
    files=[path for path in (ROOT/'workbench/src').glob('*') if path.suffix in {'.ts','.tsx'} and '.test.' not in path.name]
    source='\n'.join(path.read_text(encoding='utf-8') for path in files)
    for forbidden in ('dangerouslySetInnerHTML','innerHTML','eval(','new Function','document.write','localStorage','sessionStorage','indexedDB','serviceWorker'):
        assert forbidden not in source


@pytest.mark.parametrize('path',['/workbench','/workbench/api/view/entity','/diagnostics','/diagnostics/trace','/governance','/governance/proposals'])
def test_old_browser_urls_are_explicitly_retired(tmp_path,path):
    with TestClient(create_app(ApplicationService(ServiceConfiguration(str(tmp_path))))) as client:
        response=client.get(path)
        assert response.status_code==410
        assert response.json()['error']['code']=='UI_RETIRED'
