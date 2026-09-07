import json

from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.sdk.http import HTTPClient
from kg_mnp.services import resource_cli
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def test_resource_cli_calls_the_actual_api_and_creates_a_real_workspace(tmp_path,monkeypatch,capsys):
    service=ApplicationService(ServiceConfiguration(str(tmp_path/'service')))
    token,_=service.tokens.create(principal_id='human',principal_type='HUMAN',permissions={'*'},project_ids=set(),created_by='synthetic-admin')
    monkeypatch.setenv('KG_MNP_TOKEN',token)
    body=tmp_path/'request.json'
    body.write_text(json.dumps({'name':'cli-real-project','domain_pack':'minimal','domain_pack_version':'0.1.0'}),encoding='utf-8')
    # In-process transport only; the actual API, authentication, service and
    # workspace implementation run unchanged. TCP is separately tested.
    monkeypatch.setattr(resource_cli,'HTTPClient',lambda url,credential,timeout:HTTPClient(url,credential,client=TestClient(create_app(service))))
    assert resource_cli.main('project',['create','--request',str(body),'--idempotency-key','create'])==0
    result=json.loads(capsys.readouterr().out)
    from kg_mnp.services.projects import get_project
    project=get_project(service.root,result['payload']['project_id'])
    assert project.owner_id=='human'
    assert (service.root/'service-projects.json').is_file()


def test_cli_identity_and_bypass_flags_do_not_reach_transport(tmp_path,monkeypatch,capsys):
    def forbidden(*args,**kwargs):
        raise AssertionError('identity override must be rejected before transport')
    monkeypatch.setattr(resource_cli,'HTTPClient',forbidden)
    body=tmp_path/'claim.json'
    body.write_text(json.dumps({'reviewer_roles':['RELEASE_MANAGER']}),encoding='utf-8')
    assert resource_cli.main('review',['decide','--request',str(body)])==2
    assert 'AUTH_IDENTITY_CLAIM_REJECTED' in capsys.readouterr().out
    assert resource_cli.main('review',['decide','--reviewer-id','forged','--force'])==42
    assert resource_cli.main('lifecycle',['release','review','--roles','RELEASE_MANAGER'])==42
