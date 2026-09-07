"""Isolated, read-only SPARQL competency-question execution with explicit oracles."""

from __future__ import annotations

import hashlib
import multiprocessing
from collections.abc import Callable, Iterable
from queue import Empty
from typing import Any

from rdflib import Dataset, Graph, URIRef

from kg_mnp.contracts.canonical import semantic_hash, stable_urn

from ..contracts import finalize_artifact, verify_artifact
from ..rdf.canonical import canonical_nquads, canonical_ntriples
from ..security import assert_read_only_query


def build_cq_test_plan(
    tests: Iterable[dict[str, Any]],
    *,
    query_loader: Callable[[str], bytes],
    important_policy: str = "MUST_PASS",
) -> dict[str, Any]:
    rows = []
    required = []
    for source in tests:
        row = dict(source)
        query_ref = row["query_artifact_ref"]
        query_bytes = query_loader(query_ref)
        query = query_bytes.decode("utf-8")
        limits = {item["name"]: int(item["value"]) for item in row.get("resource_limits", [])}
        query_type = assert_read_only_query(
            query,
            max_characters=limits.get("max_query_characters", 100_000),
            max_path_depth=limits.get("max_query_path_depth", 8),
        )
        if row.get("query_type") != query_type:
            raise ValueError("declared CQ query type does not match parsed operation")
        row["query_sha256"] = hashlib.sha256(query_bytes).hexdigest()
        row.pop("test_id", None)
        row.pop("content_digest", None)
        digest = semantic_hash(row)
        row["content_digest"] = digest
        row["test_id"] = stable_urn("competency-question-test", {"content_digest": digest})
        if row["requirement"] == "REQUIRED":
            required.append(row["question_id"])
        rows.append(row)
    core = {"manifest_kind": "KG_MNP_COMPETENCY_QUESTION_TEST_PLAN", "schema_version": "1.0.0", "tests": sorted(rows, key=lambda item: item["test_id"]), "required_question_ids": sorted(set(required)), "important_policy": important_policy, "optional_policy": "MAY_BE_UNVERIFIED"}
    return finalize_artifact(core, id_field="test_plan_id", urn_kind="competency-question-test-plan", contract="competency-question-test-plan")


def _query_worker(
    nquads: bytes,
    query: str,
    operation: str,
    max_results: int,
    output: multiprocessing.Queue,
) -> None:
    try:
        dataset = Dataset()
        dataset.parse(data=nquads.decode(), format="nquads")
        dataset.default_union = True
        answer = dataset.query(query)
        if operation == "ASK":
            value: Any = {"boolean": bool(answer.askAnswer)}
        elif operation == "SELECT":
            variables = [str(item) for item in answer.vars]
            rows = []
            for result in answer:
                rows.append({name: (result[index].n3() if result[index] is not None else None) for index, name in enumerate(variables)})
                if len(rows) > max_results:
                    output.put(("RESULT_LIMIT", None))
                    return
            value = {"variables": variables, "rows": sorted(rows, key=semantic_hash)}
        else:
            graph = answer.graph if hasattr(answer, "graph") else Graph()
            if len(graph) > max_results:
                output.put(("RESULT_LIMIT", None))
                return
            value = {"canonical_nt": canonical_ntriples(graph).decode()}
        output.put(("OK", value))
    except Exception as exc:  # noqa: BLE001 - isolated worker must return engine failures
        output.put(("ERROR", type(exc).__name__))


def _execute(
    nquads: bytes,
    query: str,
    operation: str,
    timeout: int,
    max_results: int,
) -> tuple[str, Any]:
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(
        target=_query_worker,
        args=(nquads, query, operation, max_results, output),
    )
    process.start()
    try:
        # Drain before joining: the child's Queue feeder cannot finish when a
        # bounded but large result fills the pipe and the parent only joins.
        status, value = output.get(timeout=timeout)
        process.join(5)
        return ("OK", value) if status == "OK" else ("ENGINE_FAILED", value)
    except Empty:
        return ("TIMEOUT" if process.is_alive() else "ENGINE_FAILED"), None
    finally:
        if process.is_alive():
            process.terminate()
        process.join(5)
        output.close()
        output.join_thread()


def _selected_nquads(
    nquads: bytes,
    *,
    roles: list[str],
    graph_iris: dict[str, str] | None,
) -> bytes:
    if graph_iris is None:
        return nquads
    unknown = sorted(set(roles) - set(graph_iris))
    if unknown:
        raise ValueError("CQ targets unknown graph roles: " + ", ".join(unknown))
    allowed = {URIRef(graph_iris[role]) for role in roles}
    dataset = Dataset()
    dataset.parse(data=nquads.decode(), format="nquads")
    quads = []
    for subject, predicate, obj, context in dataset.quads((None, None, None, None)):
        graph = context.identifier if hasattr(context, "identifier") else context
        if graph in allowed:
            quads.append((subject, predicate, obj, graph))
    return canonical_nquads(quads)


def _assertions(operation: str, result: dict[str, Any], assertions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, str]:
    if operation == "ASK":
        count = int(result["boolean"])
    elif operation == "SELECT":
        count = len(result["rows"])
    else:
        count = len([line for line in result["canonical_nt"].splitlines() if line])
    digest = semantic_hash(result)
    outputs = []
    for assertion in assertions:
        kind = assertion["assertion_type"]
        passed = False
        if kind == "BOOLEAN_EQUALS" and operation == "ASK":
            passed = result["boolean"] is assertion["boolean_value"]
        elif kind == "MIN_ROW_COUNT":
            passed = count >= assertion["integer_value"]
        elif kind == "MAX_ROW_COUNT":
            passed = count <= assertion["integer_value"]
        elif kind == "REQUIRED_BINDINGS" and operation == "SELECT":
            passed = set(assertion["string_values"]).issubset(result["variables"])
        elif kind == "REQUIRED_IRIS":
            text = str(result)
            passed = all(URIRef(value).n3() in text for value in assertion["string_values"])
        elif kind == "RESULT_SEMANTIC_HASH":
            passed = digest == assertion["semantic_hash"]
        elif kind == "GRAPH_PATTERN_PRESENT" and operation == "CONSTRUCT":
            passed = all(value in result["canonical_nt"] for value in assertion["string_values"])
        outputs.append({"assertion_type": kind, "passed": passed})
    return outputs, count, digest


def execute_cq_test_plan(
    plan: dict[str, Any],
    *,
    dataset_nquads: bytes,
    query_loader: Callable[[str], bytes],
    graph_iris: dict[str, str] | None = None,
) -> dict[str, Any]:
    verify_artifact(plan, id_field="test_plan_id", urn_kind="competency-question-test-plan", contract="competency-question-test-plan")
    results = []
    for test in plan["tests"]:
        query_bytes = query_loader(test["query_artifact_ref"])
        if hashlib.sha256(query_bytes).hexdigest() != test["query_sha256"]:
            execution, value = "QUERY_REJECTED", None
        else:
            query = query_bytes.decode("utf-8")
            limits = {item["name"]: int(item["value"]) for item in test["resource_limits"]}
            try:
                operation = assert_read_only_query(
                    query,
                    max_characters=limits.get("max_query_characters", 100_000),
                    max_path_depth=limits.get("max_query_path_depth", 8),
                )
                selected = _selected_nquads(
                    dataset_nquads,
                    roles=test["target_graph_roles"],
                    graph_iris=graph_iris,
                )
            except ValueError:
                execution, value = "QUERY_REJECTED", None
            else:
                execution, value = _execute(
                    selected,
                    query,
                    operation,
                    limits.get("max_query_seconds", 30),
                    limits.get("max_query_results", 100_000),
                )
        if execution == "OK":
            assertion_results, count, digest = _assertions(test["query_type"], value, test["assertions"])
            if not test["assertions"]:
                test_status, question_status = "EXECUTED_NO_ORACLE", "UNVERIFIED"
            elif all(item["passed"] for item in assertion_results):
                test_status, question_status = "ASSERTION_PASSED", "PASSED"
            else:
                test_status, question_status = "ASSERTION_FAILED", "FAILED"
        else:
            assertion_results, count, digest = [], 0, semantic_hash({"status": execution})
            test_status = execution
            question_status = "FAILED" if test["requirement"] == "REQUIRED" else "UNVERIFIED"
        results.append({"test_id": test["test_id"], "question_id": test["question_id"], "test_status": test_status, "question_status": question_status, "result_count": count, "result_semantic_hash": digest, "assertion_results": assertion_results})
    required_ids = set(plan["required_question_ids"])
    required_passed = all(any(row["question_id"] == question and row["question_status"] == "PASSED" for row in results) for question in required_ids)
    important_failed = plan["important_policy"] == "MUST_PASS" and any(test["requirement"] == "IMPORTANT" and result["question_status"] != "PASSED" for test, result in zip(plan["tests"], results, strict=True))
    if not required_passed or important_failed:
        status = "FAILED"
    elif any(row["question_status"] == "UNVERIFIED" for row in results):
        status = "UNVERIFIED"
    else:
        status = "PASSED"
    core = {"manifest_kind": "KG_MNP_COMPETENCY_QUESTION_TEST_REPORT", "schema_version": "1.0.0", "test_plan_id": plan["test_plan_id"], "results": results, "required_passed": required_passed, "status": status, "issues": []}
    return finalize_artifact(core, id_field="report_id", urn_kind="competency-question-test-report", contract="competency-question-test-report")
