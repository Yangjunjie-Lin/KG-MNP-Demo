"""Scene metadata cannot change authority, frozen revisions or input evidence."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from tests.upgrade.scenario_cases import build_scenario_case
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.models import OperationRequest
from zhigou_toolchain.services.projects import get_project


@pytest.fixture(scope="module")
def configured(tmp_path_factory):
    return build_scenario_case(tmp_path_factory.mktemp("scene-authority"), "organization_management", configure_only=True)


def test_readonly_preview_and_http_router_are_real(configured):
    c = configured
    app, user, pid = c["service"], c["principal"], c["project_id"]
    before = get_project(app.root, pid)
    view = app.execute(OperationRequest("modeling.scenario.preview", pid, {"selection": c["effective"]["selection"]}), user).payload
    assert view["status"] == "AVAILABLE" and view["model_calls"] == 0
    assert get_project(app.root, pid) == before
    token, identity = app.tokens.create(principal_id="synthetic-http-scene", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    try:
        with TestClient(create_app(app)) as client:
            result = client.post(f"/api/v1/projects/{pid}/toolchain/modeling.scenario.preview",
                json={"selection": c["effective"]["selection"]}, headers={"Authorization": "Bearer " + token})
            assert result.status_code == 200 and result.json()["status"] == "AVAILABLE"
            missing = client.post(f"/api/v1/projects/{pid}/toolchain/modeling.expert.save", json={}, headers={"Authorization": "Bearer " + token, "Idempotency-Key": "closed-expert-dto"})
            assert missing.status_code == 422  # Real closed DTO, no longer a missing UI route.
    finally:
        app.tokens.revoke(identity.token_id)


def test_conflicts_wrong_pack_and_unknown_fields_fail_closed(configured):
    c = configured
    for choice in (
        {"scenario_id": "equipment_maintenance", "scenario_version": "2.0.0"},
    ):
        result = c["service"].execute(OperationRequest("modeling.scenario.preview", c["project_id"], {"selection": choice}), c["principal"]).payload
        assert result["status"] == "BLOCKED"
    for extra in ({"confirmed_by": "admin"}, {"manual_overrides": {"S3": {"level": "DETAILED"}}}, {"excluded_capabilities": ["core"]}):
        with pytest.raises(ServiceBoundaryError):
            c["service"].execute(OperationRequest("modeling.scenario.preview", c["project_id"], {"selection": {**c["effective"]["selection"], **extra}}), c["principal"])


def test_same_preset_save_is_noop_and_expert_edit_versions_stale_reviews(configured):
    c = configured
    before = read(get_project(c["service"].root, c["project_id"]).root)
    saved = c["run"]("modeling.scenario.save", {"selection": c["effective"]["selection"], "expected_revision": before["revision"]}, "save-same-preset")["session"]
    assert saved == before
    version = before["expert"]["stages"]["4"]
    original = deepcopy(version["configuration"])
    changed = {**original, "post_review_prompt": original["post_review_prompt"] + "\n核对当前来源身份。"}
    result = c["run"]("modeling.expert.save", {"configuration": changed, "confirm": False,
        "expected_configuration_digest": version["digest"], "expected_revision": before["revision"]}, "change-review-prompt")["session"]
    assert result["scenario"] == before["scenario"]
    assert result["expert"]["stages"]["4"]["configuration"]["pre_guidance_prompt"] == original["pre_guidance_prompt"]
    assert result["expert"]["stages"]["4"]["status"] == "DRAFT"
    assert result["events"][-1]["from_stage"] == 4
    assert result["expert"]["stages"]["1"] == before["expert"]["stages"]["1"]
    with pytest.raises(ServiceBoundaryError):
        c["run"]("modeling.scenario.save", {"selection": c["effective"]["selection"], "expected_revision": before["revision"]}, "stale-scene-edit")


def test_unconfirmed_scene_cannot_run_or_downgrade(configured):
    c = configured
    with pytest.raises((ServiceBoundaryError, ValueError)):
        c["run"]("modeling.profile", {"run_id": c["ingestion"]["run_id"]}, "deny-unconfirmed")
    current = read(get_project(c["service"].root, c["project_id"]).root)
    with pytest.raises(ServiceBoundaryError):
        c["run"]("modeling.session.revise", {"configuration": {}, "expected_revision": current["revision"]}, "deny-generic-config")


def test_missing_optional_and_required_fields_are_distinct(configured):
    from zhigou_toolchain.services.modeling_scenarios import (
        inspect_inputs,
        source_names,
    )
    from zhigou_toolchain.services.sources import verified_run
    c = configured
    project = get_project(c["service"].root, c["project_id"])
    data = verified_run(project.root, c["ingestion"]["run_id"]).dataset
    names = source_names(project.root, [data])
    source = next(s for s, name in names.items() if name == "employees.csv")
    for column, required in ((4, False), (1, True)):
        missing = deepcopy(data)
        missing["items"] = [i for i in missing["items"] if not (i["item_kind"] == "table-cell" and source in i["source_ids"] and i["payload"]["column"] == column)]
        gaps = inspect_inputs(c["effective"], [missing], names)["gaps"]
        assert gaps and any(g["required"] is required for g in gaps)


def test_scene_configuration_writes_require_original_human_scope_permission(configured):
    c = configured
    _, outsider = c["service"].tokens.create(principal_id="synthetic-reader", principal_type="HUMAN",
        permissions={"project:read", "source:read", "model:propose"}, project_ids={c["project_id"]}, created_by="test")
    with pytest.raises(ServiceBoundaryError):
        c["service"].execute(OperationRequest("modeling.scenario.save", c["project_id"],
            {"selection": c["effective"]["selection"], "expected_revision": 1}, "deny-scene-editor"), outsider)


def test_inflight_model_cannot_commit_over_new_scene_configuration(tmp_path):
    from unittest.mock import patch

    from tests.upgrade.expert_spy import ExpertSpy
    from zhigou_toolchain.jobs.worker import JobWorker
    c = build_scenario_case(tmp_path / "inflight", "organization_management", configure_only=True)
    app, user, project_id = c["service"], c["principal"], c["project_id"]
    session = c["session"]
    for stage in range(1, 6):
        version = session["expert"]["stages"][str(stage)]
        session = c["run"]("modeling.expert.save", {"expected_revision": session["revision"],
            "expected_configuration_digest": version["digest"], "confirm": True,
            "configuration": {**version["configuration"], "coverage_confirmed": True}}, f"race-confirm-{stage}")["session"]
    job = app.execute(OperationRequest("modeling.profile", project_id, {"run_id": c["ingestion"]["run_id"]}, "inflight-old-scene"), user)
    spy = ExpertSpy()
    original_transport = spy.transport
    def transport(request):
        result = original_transport(request)
        if request.method == "POST":
            version = session["expert"]["stages"]["1"]
            c["run"]("modeling.expert.save", {"expected_revision": session["revision"], "expected_configuration_digest": version["digest"],
                "configuration": {**version["configuration"], "pre_guidance_prompt": version["configuration"]["pre_guidance_prompt"] + "\n重新核对来源。"},
                "confirm": False}, "new-prompt-during-request")
        return result
    spy.transport = transport
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        outcome = JobWorker(app.jobs, app).run_once("inflight-scene-test")
    assert outcome.job_id == job.job_id and outcome.status != "SUCCEEDED"
    current = read(get_project(app.root, project_id).root)
    assert current["scenario"]["effective"] == c["effective"]
    assert current["expert"]["stages"]["1"]["version"] > session["expert"]["stages"]["1"]["version"]
    assert current["expert"]["stages"]["1"]["status"] == "DRAFT"
    assert len(spy.requests) == 1


def test_unadapted_freeform_scope_draft_is_explicitly_blocked_before_any_model(configured):
    from unittest.mock import patch

    from tests.upgrade.expert_spy import ExpertSpy
    c = configured
    session = read(get_project(c["service"].root, c["project_id"]).root)
    version = session["expert"]["stages"]["1"]
    c["run"]("modeling.expert.save", {"expected_revision": session["revision"], "expected_configuration_digest": version["digest"],
        "configuration": {**version["configuration"], "coverage_confirmed": True}, "confirm": True}, "confirm-scope-before-unsupported")
    spy = ExpertSpy()
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client), pytest.raises(ServiceBoundaryError) as error:
        c["run"]("modeling.scope.draft", {"run_id": c["ingestion"]["run_id"], "business_goal": "Synthetic unsupported free scope",
            "business_rules": ["Preserve declared source scope"]}, "unsupported-free-scope")
    assert error.value.code == "SCENARIO_USE_CONFIGURED_SCOPE" and spy.requests == []
