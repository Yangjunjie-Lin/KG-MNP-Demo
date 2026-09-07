from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.regression import plan_regression, run_regression
from kg_mnp.lifecycle.store import save
from kg_mnp.services.lifecycle import _record


def test_regression_plan_lookup_does_not_select_report_with_same_foreign_key(tmp_path):
    init_registry(tmp_path)
    identifier = "urn:kg-mnp:ontology-package:" + "a" * 64
    plan = plan_regression(tmp_path, base_package_id=identifier, candidate_package_id=identifier)
    report = run_regression(tmp_path, plan)
    assert report["status"] == "FAILED"
    save(tmp_path, "records/regressions/000-first-report.json", report)
    assert _record(tmp_path, "regressions", "test_plan_id", plan["test_plan_id"]) == plan
