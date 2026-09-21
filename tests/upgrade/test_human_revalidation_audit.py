"""Human approval stays human; its real computational rechecks still get audited."""
from tests.upgrade.test_full_chain import build_case
from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT
from zhigou_toolchain.services.modeling_audit import read_events


def test_human_finalize_does_not_bypass_inner_identity_audit(tmp_path, monkeypatch):
    from zhigou_toolchain.services import modeling
    observed = []
    original = modeling.mixed_mapping_drafts
    def spy(**kwargs):
        audit = ACTIVE_AUDIT.get()
        if audit and audit.binding["operation_id"] == "review.finalize":
            observed.append(audit.binding["job_id"])
        return original(**kwargs)
    monkeypatch.setattr(modeling, "mixed_mapping_drafts", spy)
    case = build_case(tmp_path, "hr", record_step_content=True)
    assert len(observed) == 1
    job = case["service"].jobs.get(observed[0])
    events = read_events(case["service"], job)
    assert events[0]["metadata"]["actor"] == "AUTHORIZED_REVIEWER"
    assert any(e["phase"] == "BEFORE" and e["metadata"].get("method_id") == "3.5" for e in events)
    assert all(r["tool_id"] != "review.finalize" for r in job.result["agent_execution"]["records"])
