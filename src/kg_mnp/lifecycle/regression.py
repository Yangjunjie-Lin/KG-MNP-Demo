"""Closed-set regression planning and execution for release admission."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.semantic_kernel.packaging.verifier import verify_package
from kg_mnp.semantic_kernel.validators.competency_questions import (
    build_cq_test_plan,
    execute_cq_test_plan,
)

from . import regression_checks
from .contracts import canonicalize, verify
from .errors import LifecycleError
from .guards import package_files, package_record, record_by_id
from .registry.manifest import load_manifest
from .store import bind_identity, list_records, next_id, save


def declared_consumer_tests(root: Path, package_id: str) -> list[dict]:
    """All active local contracts for this ontology; an empty query is not PASS."""
    record = package_record(root, package_id)
    oracle = {"assertion_type": "BOOLEAN_EQUALS", "boolean_value": True,
              "integer_value": None, "string_values": [], "semantic_hash": None}
    tests = []
    for consumer in list_records(root, "records/consumers"):
        verify(consumer, contract="consumer-manifest")
        if consumer["status"] != "ACTIVE" or consumer["ontology_iri"] != record["ontology_iri"]:
            continue
        tests.append({"test_category": "CONSUMER_CONTRACT", "consumer_ref": consumer["consumer_id"], "expected_result": oracle})
        for query in consumer["query_contracts"]:
            tests.append({"test_category": "CONSUMER_QUERY", "consumer_ref": consumer["consumer_id"],
                          "source_artifact_ref": query["query_id"], "query_type": query["query_type"],
                          "timeout_seconds": query["resource_limits"]["max_query_seconds"],
                          "result_limit": query["resource_limits"]["max_query_results"], "expected_result": oracle})
    return tests


def require_consumer_coverage(root: Path, plan: dict) -> None:
    expected = {(t["test_category"], t["consumer_ref"], t.get("source_artifact_ref"))
                for t in declared_consumer_tests(root, plan["candidate_package_id"])}
    actual = {(t["test_category"], t.get("consumer_ref"), t.get("source_artifact_ref"))
              for t in plan["tests"] if t["requirement_level"] == "REQUIRED"}
    if not expected.issubset(actual):
        raise LifecycleError("REGRESSION_FAILED", "current registered consumer contracts are missing from regression")


def execute_consumer_query(root: Path, package_root: Path, test: dict) -> dict:
    """Adapt a registered, digest-bound contract to the same isolated CQ engine."""
    consumer = record_by_id(root, "records/consumers", "consumer_id", test.get("consumer_ref"))
    verify(consumer, contract="consumer-manifest")
    manifest = json.loads((package_root / "ontology-package.json").read_bytes())
    if consumer["status"] != "ACTIVE" or consumer["ontology_iri"] != manifest["ontology_identity"]["ontology_iri"]:
        raise LifecycleError("REGRESSION_FAILED", "consumer is inactive or bound to another ontology")
    queries = [q for q in consumer["query_contracts"] if q["query_id"] == test.get("source_artifact_ref")]
    if len(queries) != 1:
        raise LifecycleError("REGRESSION_FAILED", "unambiguous registered query contract required")
    query = queries[0]
    from .policy import load_policy
    caps = load_policy("regression-policy-1.0.0.yaml")["resource_limits"]
    limits = {key: min(query["resource_limits"][key], maximum) for key, maximum in caps.items()}
    limits["max_query_seconds"] = min(limits["max_query_seconds"], test["timeout_seconds"])
    limits["max_query_results"] = min(limits["max_query_results"], test["result_limit"])
    content = query["query_text"].encode("utf-8")
    plan = build_cq_test_plan([{
        "question_id": stable_urn("competency-question", {"consumer_query": query["query_id"]}),
        "query_artifact_ref": query["query_id"], "query_type": query["query_type"],
        "expected_answer_shape": {"ASK": "BOOLEAN", "SELECT": "TABLE", "CONSTRUCT": "GRAPH"}[query["query_type"]],
        "target_graph_roles": query["target_graph_roles"], "assertions": query["assertions"],
        "requirement": "REQUIRED", "resource_limits": [{"name": k, "value": v} for k, v in limits.items()],
    }], query_loader=lambda _ref: content)
    dataset = json.loads((package_root / "dataset/rdf-dataset-manifest.json").read_bytes())
    return execute_cq_test_plan(plan, dataset_nquads=(package_root / "dataset/dataset.nq").read_bytes(),
        query_loader=lambda _ref: content, graph_iris={g["role"]: g["graph_iri"] for g in dataset["graphs"]})


def _term_contract(package_root: Path, iris: list[str]) -> bool:
    from rdflib import Dataset, URIRef
    dataset = Dataset()
    dataset.parse(data=(package_root / "dataset/dataset.nq").read_bytes().decode(), format="nquads")
    dataset.default_union = True
    return bool(iris) and all(any(dataset.triples((URIRef(iri), None, None))) for iri in iris)


def _all_strings(value):
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*(_all_strings(item) for item in value))
    return set()


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
    "VERSION_COMPATIBILITY", "CONSUMER_CONTRACT", "DIFF_EXPECTATION",
    "DEPENDENCY_RESOLUTION", "IMPACT_TARGET_CHECK", "RELEASE_METADATA_CHECK",
}
_CATEGORY_ALIASES = {"PACKAGE_REVERIFY": "PACKAGE_INTEGRITY", "CANDIDATE_INTERNAL_CQ": "CANDIDATE_CQ",
                     "BASE_REQUIRED_CQ_CARRY_FORWARD": "BASE_REQUIRED_CQ", "PROVENANCE_CLOSURE": "PROVENANCE"}


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
    value = canonicalize(value)
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


def _execute_test(root: Path, test: dict[str, Any], package_verifier: Callable[[str], Any] | None, *, base_package_id: str | None = None, plan: dict | None = None) -> tuple[str, list[str], dict[str, Any]]:
    category = _CATEGORY_ALIASES.get(test.get("test_category"), str(test.get("test_category", "")))
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
        elif category == "DEPENDENCY_RESOLUTION":
            actual = regression_checks.dependencies(package_root)
        elif category == "DIFF_EXPECTATION":
            from .diff.engine import create_diff
            diff = record_by_id(root, "records/diffs", "diff_id", plan["semantic_diff_id"])
            verify(diff, contract="semantic-diff-report")
            base = package_record(root, base_package_id)
            candidate = package_record(root, test["target_package_id"])
            computed = create_diff(package_files(root, base)[2], package_root, policy_id=diff["policy_id"], registry_id=diff["registry_id"],
                base_package_id=base["package_id"], candidate_package_id=candidate["package_id"],
                base_version=base["package_version"], candidate_version=candidate["package_version"])
            actual = computed == diff and not computed["unknown_constructs"]
        elif category == "IMPACT_TARGET_CHECK":
            from .impact import analyze_impact
            diff = record_by_id(root, "records/diffs", "diff_id", plan["semantic_diff_id"])
            impact = record_by_id(root, "records/impacts", "impact_id", plan["impact_analysis_id"])
            verify(impact, contract="impact-analysis-report")
            computed = analyze_impact(root, semantic_diff=diff)
            actual = computed["content_digest"] == impact["content_digest"] and computed["status"] == "COMPLETE" and not computed["unknown_impacts"]
        elif category == "RELEASE_METADATA_CHECK":
            manifest = regression_checks.document(package_root, "ontology-package.json")
            base = package_record(root, base_package_id)
            from .diff.versioning import _v
            actual = (manifest["package_status"] == "VALIDATED_UNPUBLISHED" and manifest["package_name"] == base["package_name"]
                and manifest["ontology_identity"]["ontology_iri"] == base["ontology_iri"]
                and _v(manifest["package_version"]) > _v(base["package_version"]))
        elif category == "CONSUMER_CONTRACT":
            consumer = record_by_id(root, "records/consumers", "consumer_id", test.get("consumer_ref"))
            verify(consumer, contract="consumer-manifest")
            manifest = json.loads((package_root / "ontology-package.json").read_bytes())
            mappings = json.loads((package_root / "mappings/mapping-plan.json").read_bytes())
            cq = json.loads((package_root / "validation/competency-question-test-plan.json").read_bytes())
            constraints = consumer["package_constraints"]
            from .diff.versioning import _v
            version = _v(manifest["package_version"])
            # package_ids identify the subscribed base; a successor is checked
            # by the explicit version/semantic/query contracts, not ID equality.
            actual = (consumer["status"] == "ACTIVE"
                and consumer["ontology_iri"] == manifest["ontology_identity"]["ontology_iri"]
                and (not constraints["package_names"] or manifest["package_name"] in constraints["package_names"])
                and (not constraints["minimum_version"] or version >= _v(constraints["minimum_version"]))
                and (not constraints["maximum_version_exclusive"] or version < _v(constraints["maximum_version_exclusive"]))
                and (not consumer["required_term_iris"] or _term_contract(package_root, consumer["required_term_iris"]))
                and set(consumer["required_graph_roles"]).issubset(g["role"] for g in manifest["graphs"])
                and set(consumer["required_cq_ids"]).issubset(q["question_id"] for q in cq["tests"])
                and all(identifier in _all_strings(mappings) for identifier in consumer["required_mapping_ids"]))
        elif category == "VERSION_COMPATIBILITY":
            version = record_by_id(root, "records/version-compatibility", "report_id", test.get("source_artifact_ref"))
            verify(version, contract="version-compatibility-report")
            actual = version["compatible"] is True
        elif category in {"CANDIDATE_CQ", "BASE_REQUIRED_CQ", "CONSUMER_QUERY"}:
            if category=="CONSUMER_QUERY":
                cq = execute_consumer_query(root, package_root, test)
            else:
                plan_root=package_root
                if category=="BASE_REQUIRED_CQ":
                    if not base_package_id:
                        return "UNVERIFIED",["base-package-required"],evidence
                    plan_root=package_files(root,package_record(root,base_package_id))[2]
                cq=execute_packaged_cq(plan_root,package_root)
            evidence={**evidence,"cq_report":cq}
            actual=cq["required_passed"] is True and cq["status"]=="PASSED"
        elif category == "TERM_CONTRACT":
            actual = _term_contract(package_root, test.get("affected_iris", []))
        elif category == "MAPPING_CONTRACT":
            actual = regression_checks.mappings(package_root, test.get("source_artifact_ref"))
        elif category == "PROVENANCE":
            actual = regression_checks.provenance(package_root)
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
    verify(plan, contract="regression-test-plan")
    tests = plan.get("tests")
    if not isinstance(tests, list) or not tests:
        raise LifecycleError("REGRESSION_FAILED", "test plan has no executable tests")
    results = []
    for test in tests:
        status, issues, evidence = _execute_test(root, test, package_verifier, base_package_id=plan["base_package_id"], plan=plan)
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
    report = canonicalize(report)
    bind_identity(report, "report_id", "regression-test-report")
    save(root, f"records/regressions/{report['report_id'].rsplit(':', 1)[1]}.json", report)
    return report
