"""Real Worker/CAS/compiler plus MockTransport; synthetic identities only."""
from unittest.mock import patch

import pytest

from tests.upgrade.expert_spy import ExpertSpy
from tests.upgrade.test_full_chain import build_case
from zhigou_toolchain.services.modeling_audit import read_events
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.projects import get_project


def test_synthetic_expert_worker_chain(tmp_path):
    spy = ExpertSpy(revise_scope=True)
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        case = build_case(tmp_path / "service", "hr", expert_mode=True, record_trace=True, record_step_content=True)
    service, project_id = case["service"], case["project_id"]
    session = read(get_project(service.root, project_id).root)
    loops = session["expert"]["loops"]
    assert all(r["decision"] == "PASS" for r in loops), [(r["operation"], r["stop_reason"]) for r in loops]
    scope = next(r for r in loops if r["operation"] == "modeling.scope")
    assert scope["revision_round"] == 1
    assert [r["methods"][0]["decision"] for r in scope["rounds"]] == ["REVISE", "PASS"]
    model_events = [e for job in service.jobs.list_project(project_id) for e in read_events(service, job)
                    if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "MODEL"]
    assert len(model_events) == len(spy.requests) == sum(r["token_usage"]["physical_calls"] for r in loops)
    assert {m["stage_id"] for r in loops for m in r["methods"]} == set(range(1, 6))
    assert all(r["human_approval"] == "NOT_GRANTED" for r in loops)
    assert case["built"]["reports"]["competency-question-test-report.json"]["required_passed"]
    from zhigou_toolchain.services.compilation import read_archive, read_export_snapshot
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    with pytest.raises(ServiceBoundaryError) as wrong:
        read_archive(service, case["principal"], project_id, "urn:kg-mnp:ontology-package:" + "0" * 64)
    assert wrong.value.code == "EXPERT_PACKAGE_STALE"
    exported_job = next(j for j in service.jobs.list_project(project_id) if j.operation_id == "package.export")
    assert read_export_snapshot(service, case["principal"], project_id, exported_job.job_id)
    version = session["expert"]["stages"]["5"]
    case["run"]("modeling.expert.save", {"expected_revision": session["revision"], "expected_configuration_digest": version["digest"],
        "confirm": True, "configuration": {**version["configuration"], "post_review_prompt": "Synthetic changed delivery condition"}}, "changed-delivery-condition")
    for reader in (lambda: read_archive(service, case["principal"], project_id, case["built"]["package_id"]),
                   lambda: read_export_snapshot(service, case["principal"], project_id, exported_job.job_id)):
        with pytest.raises(ServiceBoundaryError) as stale:
            reader()
        assert stale.value.code in {"EXPERT_PACKAGE_STALE", "EXPERT_REVIEW_REQUIRED", "EXPERT_REVIEW_STALE", "EXPERT_EXPORT_REVIEW_STALE"}


@pytest.mark.parametrize("stage", [2, 3, 4, 5])
def test_actual_stage_patch_renormalizes_rechecks_and_preserves_human_gates(tmp_path, stage):
    from tests.upgrade.test_no_baseline import run_new_ontology
    spy = ExpertSpy(revise_stage=stage)
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        case = run_new_ontology(tmp_path, expert_stage=stage, record_audit=True, return_runtime=True)
    loops = case["session"]["expert"]["loops"]
    repaired = [r for r in loops if r["revision_round"] == 1]
    assert repaired and all(r["decision"] == "PASS" for r in repaired)
    assert all(r["human_approval"] == "NOT_GRANTED" for r in loops)
    assert case["built"]["reports"]["competency-question-test-report.json"]["required_passed"]
    if stage == 4:
        assert any(r.get("routed_proposal") for r in repaired)
