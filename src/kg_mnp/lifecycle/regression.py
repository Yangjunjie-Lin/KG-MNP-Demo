"""Closed-set regression planning and execution for release admission."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash
from kg_mnp.semantic_kernel.packaging.verifier import verify_package
from kg_mnp.semantic_kernel.validators.competency_questions import execute_cq_test_plan

from .errors import LifecycleError
from .guards import package_files, package_record, record_by_id
from .registry.manifest import load_manifest
from .store import bind_identity, next_id, save


def execute_packaged_cq(plan_root: Path, target_root: Path) -> dict[str, Any]:
    """Execute the frozen query/Oracle plan against actual target dataset bytes.

    Query bytes are selected from the verified package's embedded Pack Locks.
    No local path or remote URL comes from the caller, and cached CQ results
    cannot substitute for this execution.
    """
    verify_package(plan_root)
    verify_package(target_root)
    plan=json.loads((plan_root/"validation/competency-question-test-plan.json").read_bytes())
    dataset=json.loads((target_root/"dataset/rdf-dataset-manifest.json").read_bytes())
    queries={}
    for lock_path in (plan_root/"baseline/domain-pack-locks").glob("*.json"):
        lock=json.loads(lock_path.read_bytes())
        for asset in lock["assets"]:
            relative=asset.get("path",asset.get("asset_path"))
            if relative and relative.endswith(".rq"):
                path=plan_root/"baseline/assets"/lock["pack_id"]/relative
                content=path.read_bytes()
                if __import__("hashlib").sha256(content).hexdigest()!=asset["sha256"]:
                    raise LifecycleError("REGRESSION_FAILED","packaged query hash mismatch")
                queries[asset["asset_id"]]=content
                queries[relative]=content
    if not plan["required_question_ids"] or not plan["tests"]:
        raise LifecycleError("REGRESSION_FAILED","CQ plan has no required Oracle")
    try:
        return execute_cq_test_plan(plan,dataset_nquads=(target_root/"dataset/dataset.nq").read_bytes(),
            query_loader=lambda ref:queries[ref],graph_iris={g["role"]:g["graph_iri"] for g in dataset["graphs"]})
    except KeyError as exc:
        raise LifecycleError("REGRESSION_FAILED","locked CQ query not packaged") from exc

_KNOWN_CATEGORIES = {
    "PACKAGE_INTEGRITY", "PACKAGE", "CANDIDATE_CQ", "BASE_REQUIRED_CQ",
    "CONSUMER_QUERY", "TERM_CONTRACT", "MAPPING_CONTRACT", "PROVENANCE",
    "VERSION_COMPATIBILITY",
}


def _normalise_test(candidate: str, index: int, value: dict[str, Any]) -> dict[str, Any]:
    expected = value.get("expected_result")
    if expected is None:
        expected = {"assertion_type": value.get("assertion_type", "PACKAGE_STATUS"), "boolean_value": None, "integer_value": None, "string_values": [], "semantic_hash": None}
    return {
        "test_id": value.get("test_id") or next_id("regression-test", {"candidate": candidate, "index": index}),
        "test_category": value.get("test_category", "PACKAGE_INTEGRITY"),
        "source_artifact_ref": value.get("source_artifact_ref"),
        "target_package_id": value.get("target_package_id", candidate),
        "query_type": value.get("query_type"),
        "assertion_type": value.get("assertion_type", expected.get("assertion_type", "PACKAGE_STATUS")),
        "expected_result": expected,
        "requirement_level": value.get("requirement_level", "REQUIRED"),
        "affected_iris": sorted(set(value.get("affected_iris", []))),
        "consumer_ref": value.get("consumer_ref"),
        "timeout_seconds": int(value.get("timeout_seconds", 30)),
        "result_limit": int(value.get("result_limit", 100)),
    }


def plan_regression(workspace: Path | str, *, base_package_id: str, candidate_package_id: str, semantic_diff_id: str = "", impact_analysis_id: str = "", tests: list[dict] | None = None, policy_id: str = "") -> dict:
    root = Path(workspace)
    if not candidate_package_id:
        raise LifecycleError("REGRESSION_FAILED", "candidate package is required")
    supplied = tests or [{"test_category": "PACKAGE_INTEGRITY", "assertion_type": "PACKAGE_STATUS"}]
    normalised = [_normalise_test(candidate_package_id, i, item) for i, item in enumerate(supplied)]
    value = {
        "manifest_kind": "KG_MNP_REGRESSION_TEST_PLAN", "schema_version": "1.0.0",
        "registry_id": load_manifest(root)["registry_id"], "base_package_id": base_package_id,
        "candidate_package_id": candidate_package_id, "semantic_diff_id": semantic_diff_id or None,
        "impact_analysis_id": impact_analysis_id or None, "policy_id": policy_id or next_id("regression-policy", {"version": "1.0.0"}),
        "tests": normalised, "required_test_count": sum(t.get("requirement_level") == "REQUIRED" for t in normalised),
        "optional_test_count": sum(t.get("requirement_level") != "REQUIRED" for t in normalised),
        "resource_limits": {"max_query_characters": 100000, "max_query_results": 100000, "max_query_seconds": 60, "max_query_path_depth": 16},
    }
    bind_identity(value, "test_plan_id", "regression-test-plan")
    save(root, f"records/regressions/{value['test_plan_id'].rsplit(':', 1)[1]}.json", value)
    return value


def _package_check(root: Path, package_id: str, package_verifier: Callable[[str], Any] | None) -> dict[str, Any]:
    record = package_record(root, package_id)
    _manifest, _lock, package_root = package_files(root, record)
    verified = verify_package(package_root)
    if verified.get("package_id") != package_id or verified.get("status") != "VALID":
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package verifier did not confirm the target package")
    if package_verifier is not None:
        package_verifier(package_id)
    return {"package_id": package_id, "package_root": str(package_root), "verification": verified}


def _execute_test(root: Path, test: dict[str, Any], package_verifier: Callable[[str], Any] | None, *, base_package_id: str | None = None) -> tuple[str, list[str], dict[str, Any]]:
    category = str(test.get("test_category", ""))
    if category not in _KNOWN_CATEGORIES:
        return "UNVERIFIED", [f"unknown-test-category:{category}"], {}
    expected = test.get("expected_result")
    if not isinstance(expected, dict) or not expected.get("assertion_type"):
        return "UNVERIFIED", ["oracle-missing"], {}
    try:
        evidence = _package_check(root, test["target_package_id"], package_verifier)
        package_root = Path(evidence["package_root"])
        if category in {"PACKAGE_INTEGRITY", "PACKAGE"}:
            actual = True
        elif category == "VERSION_COMPATIBILITY":
            actual = bool(record_by_id(root, "records/version-compatibility", "report_id", test.get("source_artifact_ref")))
        elif category in {"CANDIDATE_CQ", "BASE_REQUIRED_CQ", "CONSUMER_QUERY"}:
            if category=="CONSUMER_QUERY":
                return "UNVERIFIED", ["consumer-query-executor-required"], evidence
            plan_root=package_root
            if category=="BASE_REQUIRED_CQ":
                if not base_package_id:
                    return "UNVERIFIED",["base-package-required"],evidence
                plan_root=package_files(root,package_record(root,base_package_id))[2]
            cq=execute_packaged_cq(plan_root,package_root)
            evidence={**evidence,"cq_report":cq}
            actual=cq["required_passed"] is True and cq["status"]=="PASSED"
        elif category == "TERM_CONTRACT":
            actual = bool(test.get("affected_iris")) and (package_root / "ontology").is_dir()
        elif category == "MAPPING_CONTRACT":
            actual = (package_root / "mappings" / "mapping-plan.json").is_file()
        elif category == "PROVENANCE":
            actual = any((package_root / part).exists() for part in ("provenance", "evidence", "manifest.json"))
        else:  # pragma: no cover
            return "UNVERIFIED", ["executor-not-configured"], evidence
        expected_value = expected.get("boolean_value")
        if not isinstance(expected_value, bool):
            return "UNVERIFIED", ["boolean-oracle-missing"], evidence
        if actual != expected_value:
            return "FAILED", ["assertion-mismatch"], {**evidence, "actual": actual, "expected": expected_value}
        return "PASSED", [], {**evidence, "actual": actual, "expected": expected_value}
    except LifecycleError as exc:
        return "FAILED", [exc.code], {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return "ENGINE_FAILED", [type(exc).__name__], {}


def run_regression(workspace: Path | str, plan: dict, *, package_verifier: Callable[[str], Any] | None = None) -> dict:
    root = Path(workspace)
    if not plan.get("test_plan_id") or plan.get("registry_id") != load_manifest(root).get("registry_id"):
        raise LifecycleError("REGRESSION_FAILED", "test plan is not bound to this registry")
    tests = plan.get("tests")
    if not isinstance(tests, list) or not tests:
        raise LifecycleError("REGRESSION_FAILED", "test plan has no executable tests")
    results = []
    for test in tests:
        status, issues, evidence = _execute_test(root, test, package_verifier, base_package_id=plan["base_package_id"])
        results.append({"test_id": test["test_id"], "status": status, "evidence_digest": semantic_hash(evidence) if evidence else None, "issues": issues})
    passed = sum(item["status"] == "PASSED" for item in results)
    failed = sum(item["status"] in {"FAILED", "ENGINE_FAILED", "TIMEOUT"} for item in results)
    incomplete = len(results) - passed - failed
    required_indexes = [i for i, test in enumerate(tests) if test.get("requirement_level") == "REQUIRED"]
    required_passed = bool(required_indexes) and all(results[i]["status"] == "PASSED" for i in required_indexes)
    status = "PASSED" if required_passed and failed == 0 and incomplete == 0 else ("FAILED" if failed else "INCOMPLETE")
    report = {
        "manifest_kind": "KG_MNP_REGRESSION_TEST_REPORT", "schema_version": "1.0.0", "registry_id": plan["registry_id"],
        "test_plan_id": plan["test_plan_id"], "base_package_id": plan["base_package_id"], "candidate_package_id": plan["candidate_package_id"],
        "tests": results, "summary": {"total": len(results), "passed": passed, "failed": failed, "incomplete": incomplete},
        "required_passed": required_passed,
        "important_passed": all(result["status"] == "PASSED" for test, result in zip(tests, results) if test.get("requirement_level") == "IMPORTANT"),
        "status": status,
    }
    bind_identity(report, "report_id", "regression-test-report")
    save(root, f"records/regressions/{report['report_id'].rsplit(':', 1)[1]}.json", report)
    return report
