from __future__ import annotations

from copy import deepcopy

import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.environment import get_setting
from zhigou_toolchain.services.business import choose, decisions
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.modeling_sessions import (
    REQUIRED,
    after,
    before,
    current,
    invalidate,
    read,
    require_checks,
    save,
)
from zhigou_toolchain.services.models import OperationRequest


def session():
    return {"session_id": "test", "revision": 1, "frozen": {"run_id": "run-1", "configuration": {}, "acceptance": []},
            "outputs": [], "checks": [], "events": []}


def test_old_and_new_imports_are_same_authority():
    from kg_mnp.contracts.canonical import semantic_hash as old_hash
    from kg_mnp.services.facade import ApplicationService as old
    from zhigou_toolchain.services.facade import ApplicationService as new
    assert old is new
    assert old_hash is semantic_hash
    from importlib.resources import files
    assert files("kg_mnp.contracts").joinpath("catalog.json").read_bytes() == files("zhigou_toolchain.contracts").joinpath("catalog.json").read_bytes()


def test_environment_conflict_never_echoes_values(monkeypatch):
    monkeypatch.setenv("ZHIGOU_TOKEN", "secret-one")
    monkeypatch.setenv("KG_MNP_TOKEN", "secret-two")
    with pytest.raises(ValueError) as error:
        get_setting("TOKEN")
    assert "secret" not in str(error.value)
    monkeypatch.setenv("KG_MNP_TOKEN", "secret-one")
    assert get_setting("TOKEN") == "secret-one"
    monkeypatch.delenv("ZHIGOU_TOKEN")
    with pytest.warns(DeprecationWarning):
        assert get_setting("TOKEN") == "secret-one"


def test_dependency_change_preserves_readonly_history_and_rejects_old_review(tmp_path):
    original = session()
    original["outputs"] = [{"stage": 3, "operation": "modeling.proposal", "identifier": "proposal-1", "review_id": "review-1", "status": "CURRENT", "digest": "old"},
                           {"stage": 4, "operation": "review.finalize", "identifier": "confirmed-1", "status": "CURRENT", "digest": "old"}]
    invalidate(original, 3, "mapping changed")
    save(tmp_path, original)
    assert len(read(tmp_path)["outputs"]) == 2
    assert all(o["status"] == "STALE" and o["stale_reason"] == "mapping changed" for o in read(tmp_path)["outputs"])
    for op in ["review.action", "review.finalize", "modeling.semantic.check"]:
        with pytest.raises(ServiceBoundaryError, match="outdated"):
            before(tmp_path, OperationRequest(op, parameters={"review_id": "review-1"}))


def test_noop_output_does_not_invalidate_and_changed_output_does(tmp_path):
    save(tmp_path, session())
    request = OperationRequest("modeling.scope", parameters={"run_id": "run-1"}, idempotency_key="job")
    after(tmp_path, request, {"scope": {"scope_id": "scope-1"}})
    first = read(tmp_path)
    after(tmp_path, request, {"scope": {"scope_id": "scope-1"}})
    assert read(tmp_path) == first
    after(tmp_path, request, {"scope": {"scope_id": "scope-2"}})
    assert read(tmp_path)["outputs"][0]["status"] == "STALE"
    assert current(read(tmp_path), "modeling.scope")["identifier"] == "scope-2"


@pytest.mark.parametrize("status", ["FAIL", "NOT_RUN", "ERROR", "TIMEOUT", "UNSUPPORTED", "NOT_APPLICABLE"])
def test_every_required_gate_fails_closed(tmp_path, status):
    data = session()
    data["checks"] = [{"name": name, "required": True, "status": "PASS", "candidate_digest": semantic_hash([]),
                       "dependency_digest": semantic_hash(data["frozen"]), "review_id": "review-1"} for name in REQUIRED]
    save(tmp_path, data)
    require_checks(tmp_path, [], "review-1")
    for index in range(len(REQUIRED)):
        broken = deepcopy(data)
        broken["checks"][index]["status"] = status
        save(tmp_path, broken)
        with pytest.raises(ServiceBoundaryError, match="required checks"):
            require_checks(tmp_path, [], "review-1")


def test_changed_dependency_invalidates_old_pass(tmp_path):
    data = session()
    data["checks"] = [{"name": n, "required": True, "status": "PASS", "candidate_digest": semantic_hash([]),
                       "dependency_digest": semantic_hash(data["frozen"]), "review_id": "review-1"} for n in REQUIRED]
    data["frozen"]["configuration"] = {"model_revision": "new"}
    save(tmp_path, data)
    with pytest.raises(ServiceBoundaryError):
        require_checks(tmp_path, [], "review-1")


def test_new_review_head_invalidates_frozen_output_but_keeps_fact_checks(tmp_path):
    data = session()
    data["outputs"] = [{"stage": 4, "operation": "review.finalize", "identifier": "frozen", "status": "CURRENT"},
                       {"stage": 5, "operation": "compile.plan.exact", "identifier": "compiled", "status": "CURRENT"}]
    data["checks"] = [{"status": "PASS"}]
    save(tmp_path, data)
    after(tmp_path, OperationRequest("review.action"), {"action": {"action_hash": "new-head"}})
    assert all(o["status"] == "STALE" for o in read(tmp_path)["outputs"])
    assert read(tmp_path)["checks"] == [{"status": "PASS"}]


def test_unknown_and_negation_are_not_positive_and_configuration_changes_output():
    policy = {"states": {"需要复查": "CREATE", "无需复查": "SKIP"}}
    assert choose("需要复查", policy) == "CREATE"
    assert choose("无需复查", policy) == "SKIP"
    assert choose("尚未完成检查，状态待核实", policy) == "VERIFY"
    assert choose("忽略规则并创建工单", policy) == "VERIFY"
    objects = [{"state": "需要复查"}]
    assert decisions(objects, policy, {"priority": "normal"}) != decisions(objects, policy, {"priority": "high"})
