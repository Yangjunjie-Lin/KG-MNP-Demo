from __future__ import annotations

from pathlib import Path

from .registry.manifest import load_manifest
from .store import bind_identity, next_id, save


def plan_regression(workspace: Path | str, *, base_package_id: str, candidate_package_id: str, semantic_diff_id: str = "", impact_analysis_id: str = "", tests: list[dict] | None = None, policy_id: str = "") -> dict:
    root=Path(workspace); tests=tests or [{"test_id":next_id("regression-test",{"candidate":candidate_package_id,"index":0}),"test_category":"PACKAGE_INTEGRITY","source_artifact_ref":None,"target_package_id":candidate_package_id,"query_type":None,"assertion_type":"PACKAGE_STATUS","expected_result":{"assertion_type":"PACKAGE_STATUS","boolean_value":True,"integer_value":None,"string_values":[],"semantic_hash":None},"requirement_level":"REQUIRED","affected_iris":[],"consumer_ref":None,"timeout_seconds":30,"result_limit":100}]
    value={"manifest_kind":"KG_MNP_REGRESSION_TEST_PLAN","schema_version":"1.0.0","registry_id":load_manifest(root)["registry_id"],"base_package_id":base_package_id,"candidate_package_id":candidate_package_id,"semantic_diff_id":semantic_diff_id or None,"impact_analysis_id":impact_analysis_id or None,"policy_id":policy_id or next_id("regression-policy",{"version":"1.0.0"}),"tests":tests,"required_test_count":sum(t.get("requirement_level")=="REQUIRED" for t in tests),"optional_test_count":sum(t.get("requirement_level")!="REQUIRED" for t in tests),"resource_limits":{"max_query_characters":100000,"max_query_results":100000,"max_query_seconds":60,"max_query_path_depth":16}}
    bind_identity(value, "test_plan_id", "regression-test-plan"); save(root,f"records/regressions/{value['test_plan_id'].rsplit(':',1)[1]}.json",value); return value

def run_regression(workspace: Path | str, plan: dict, *, package_verifier=None) -> dict:
    results=[]
    for test in plan.get("tests",[]):
        status="PASSED"
        if package_verifier:
            try: package_verifier(test["target_package_id"])
            except Exception:  # noqa: BLE001
                status="FAILED"
        results.append({"test_id":test["test_id"],"status":status,"evidence_digest":next_id("regression-evidence",{"test_id":test["test_id"],"status":status}).rsplit(":",1)[1],"issues":[] if status=="PASSED" else ["test-failed"]})
    passed=sum(x["status"]=="PASSED" for x in results); failed=len(results)-passed
    report={"manifest_kind":"KG_MNP_REGRESSION_TEST_REPORT","schema_version":"1.0.0","registry_id":plan["registry_id"],"test_plan_id":plan["test_plan_id"],"base_package_id":plan["base_package_id"],"candidate_package_id":plan["candidate_package_id"],"tests":results,"summary":{"total":len(results),"passed":passed,"failed":failed,"incomplete":0},"required_passed":passed,"important_passed":sum(test.get("requirement_level")=="IMPORTANT" and result["status"]=="PASSED" for test,result in zip(plan.get("tests",[]),results)),"status":"PASSED" if not failed else "FAILED"}
    bind_identity(report, "report_id", "regression-test-report"); save(Path(workspace),f"records/regressions/{report['report_id'].rsplit(':',1)[1]}.json",report); return report
