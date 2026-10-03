"""Actual scene mapping/Worker/loop integration, with independent Mock HTTP."""
from tests.upgrade.scenario_cases import build_scenario_case


def test_scene_mapping_real_worker_smoke(tmp_path):
    case = build_scenario_case(tmp_path / "scene", "organization_management", finish=False)
    rows = case["proposed"]["scenario_outputs"]
    assert [r["stage_id"] for r in rows] == [2, 3]
    assert rows[1]["observed_counts"]["INDIVIDUAL"] == 4
    assert all(row["independent_quality"]["status"] == "NOT_EVALUATED_NO_INDEPENDENT_LABELS" for row in rows)
    assert case["spy"].revised
    assert all(call["messages"] for call in case["spy"].requests)


def test_scene_s4_routes_real_candidate_revision_and_requires_new_human_review(tmp_path):
    from tests.upgrade.scenario_spy import ScenarioRepairSpy
    spy = ScenarioRepairSpy()
    case = build_scenario_case(tmp_path / "scene-repair", "organization_management", spy=spy)
    check = next(r["result"] for r in case["results"] if r["operation"] == "modeling.semantic.check")
    assert check["expert_loop"]["decision"] == "PASS" and check["expert_loop"]["revision_round"] == 1
    assert check["expert_routed_review_id"] == check["queue"]["review_queue_id"]
    assert check["human_approval"] == "NEW_REVIEW_REQUIRED"
    assert spy.revised
