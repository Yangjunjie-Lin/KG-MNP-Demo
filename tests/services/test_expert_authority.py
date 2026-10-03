"""Synthetic local authority failures: real sessions, JobStore and CAS."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from tests.services.test_modeling_workflow import call
from tests.upgrade.expert_spy import ExpertSpy
from tests.upgrade.test_full_chain import exact
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.projects import get_project


@pytest.fixture
def expert_case(tmp_path):
    app = ApplicationService(ServiceConfiguration(str(tmp_path), review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        ontology_trace_enabled=True, modeling_audit_content_enabled=True))
    _, user = app.tokens.create(principal_id="synthetic-expert", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    project = app.execute(OperationRequest("project.create", parameters={"name": "expert authority", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), user).payload["project_id"]
    run = call(app, user, project, "modeling.tutorial.seed", {}, "seed")["run"]["run_id"]
    session = call(app, user, project, "modeling.session.open", {"run_id": run, "business_rules": ["Use source evidence"],
        "acceptance": [{"query_asset_id": "synthetic", "expected": exact(["id"], [["synthetic"]])}], "expected_revision": None, "expert_loop_enabled": True}, "open")["session"]
    return app, user, project, run, session


def confirm(case, *, suffix="", change=None):
    app, user, project, _, _ = case
    session = read(get_project(app.root, project).root)
    config = session["expert"]["stages"]["1"]
    value = deepcopy(config["configuration"])
    value["coverage_confirmed"] = True
    if change:
        value.update(change)
    return call(app, user, project, "modeling.expert.save", {"expected_revision": session["revision"],
        "expected_configuration_digest": config["digest"], "configuration": value, "confirm": True}, "confirm" + suffix)["session"]


def test_unconfirmed_direct_api_never_calls_model(expert_case):
    app, user, project, run, _ = expert_case
    spy = ExpertSpy()
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client), pytest.raises((ServiceBoundaryError, ValueError)):
        call(app, user, project, "modeling.profile", {"run_id": run}, "blocked")
    assert spy.requests == []


def test_s1_update_invalidates_scope_and_cannot_downgrade(expert_case):
    app, user, project, run, _ = expert_case
    confirm(expert_case)
    spy = ExpertSpy()
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        call(app, user, project, "modeling.profile", {"run_id": run}, "profile")
        result = call(app, user, project, "modeling.scope", {"run_id": run, "description": "synthetic scope", "object_families": ["Record"],
            "in_scope": ["source records"], "namespace": "urn:synthetic:expert:"}, "scope")
    assert result["expert_loop"]["decision"] == "PASS"
    updated = confirm(expert_case, suffix="-v2", change={"pre_guidance_prompt": "New synthetic source scope requirement"})
    assert all(o["status"] == "STALE" for o in updated["outputs"])
    assert all(not loop["current"] for loop in updated["expert"]["loops"])
    assert updated["expert"]["history"][-1]["configuration"]["pre_guidance_prompt"] != "New synthetic source scope requirement"
    with pytest.raises(ServiceBoundaryError):
        call(app, user, project, "modeling.scope.approve", {"scope_id": result["scope"]["scope_id"], "rationale": "cannot bypass"}, "deny-approval")
    opened = call(app, user, project, "modeling.session.open", {"run_id": run, "business_rules": ["New frozen rule"],
        "acceptance": updated["frozen"]["acceptance"], "expected_revision": updated["revision"], "expert_loop_enabled": False}, "no-downgrade")["session"]
    assert opened["expert"]["enabled"] is True


@pytest.mark.parametrize("fault", ["cancel", "revoke", "supersede", "audit_failure"])
def test_loop_checks_authority_between_requests_and_never_commits(expert_case, fault):
    app, user, project, run, _ = expert_case
    confirm(expert_case)
    before = get_project(app.root, project)
    job = app.execute(OperationRequest("modeling.profile", project, {"run_id": run}, "race"), user)
    spy = ExpertSpy()
    original = spy.transport
    def transport(request):
        response = original(request)
        if request.method == "POST":
            if fault == "cancel":
                app.jobs.cancel(job.job_id)
            elif fault == "revoke":
                app.tokens.revoke(user.token_id)
            elif fault == "supersede":
                import sqlite3
                with sqlite3.connect(app.jobs.path) as connection:
                    connection.execute("UPDATE jobs SET fencing_token=fencing_token+1 WHERE job_id=?", (job.job_id,))
            else:
                raise OSError("synthetic audit/transport interruption")
        return response
    spy.transport = transport
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        outcome = JobWorker(app.jobs, app).run_once("expert-test")
    assert outcome.status != "SUCCEEDED"
    assert get_project(app.root, project) == before
    assert len(spy.requests) == 1


def test_configuration_conflict_private_feedback_and_cross_project(expert_case):
    app, user, project, run, session = expert_case
    updated = confirm(expert_case)
    stale = session["expert"]["stages"]["1"]
    with pytest.raises(ServiceBoundaryError):
        call(app, user, project, "modeling.expert.save", {"expected_revision": session["revision"],
            "expected_configuration_digest": stale["digest"], "configuration": stale["configuration"], "confirm": False}, "stale")
    with pytest.raises(ValueError, match="PRIVATE"):
        confirm(expert_case, suffix="private", change={"post_review_prompt": '{"corrected_answer":"private canary"}'})
    _, outsider = app.tokens.create(principal_id="outsider", principal_type="HUMAN", permissions={"model:propose", "source:read"}, project_ids=set(), created_by="test")
    with pytest.raises(ServiceBoundaryError):
        app.execute(OperationRequest("modeling.profile", project, {"run_id": run}, "cross-project"), outsider)
    assert read(get_project(app.root, project).root)["revision"] == updated["revision"]


def test_review_only_version_change_reaudits_exact_candidate_and_idempotent_commit(expert_case):
    app, user, project, run, _ = expert_case
    confirm(expert_case)
    spy = ExpertSpy()
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        call(app, user, project, "modeling.profile", {"run_id": run}, "profile")
        result = call(app, user, project, "modeling.scope", {"run_id": run, "description": "synthetic scope", "object_families": ["Record"],
            "in_scope": ["source records"], "namespace": "urn:synthetic:expert:"}, "scope")
        old_job = next(j for j in app.jobs.list_project(project) if j.operation_id == "modeling.scope")
        updated = confirm(expert_case, suffix="-review-v2", change={"post_review_prompt": "Synthetic new review condition: preserve provenance"})
        params = {"expected_revision": updated["revision"], "job_id": old_job.job_id,
            "candidate_digest": result["expert_loop"]["rounds"][-1]["candidate_digest"], "feedback": "Check frozen provenance only"}
        reviewed = call(app, user, project, "modeling.expert.reaudit", params, "reaudit")
        assert reviewed["expert_loop"]["decision"] == "PASS", reviewed
        count = len(spy.requests)
        replay = app.execute(OperationRequest("modeling.expert.reaudit", project, params, "reaudit"), user)
        assert app.jobs.get(replay.job_id).result == reviewed
        assert JobWorker(app.jobs, app).run_once("idempotent") is None
        assert len(spy.requests) == count
    current = read(get_project(app.root, project).root)
    assert current["expert"]["loops"][-1]["methods"][0]["configuration_version"] == 2
    assert next(o for o in current["outputs"] if o["operation"] == "modeling.scope")["status"] == "CURRENT"
