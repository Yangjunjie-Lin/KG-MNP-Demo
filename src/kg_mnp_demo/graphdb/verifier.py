from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..compilation.rdf_canonical import parse_ntriples
from ..modeling.canonical_json import canonical_json_bytes
from ._io import read_json, json_bytes
from .client import GraphDBClient
from .contracts import validate_graphdb_contract
from .query_suite import query_suite_hash
from .rdf_semantics import GraphDBRDFSemanticError, graphdb_semantic_hash_nquads


class GraphDBVerificationError(RuntimeError):
    pass


_XSD_DATETIME = "http://www.w3.org/2001/XMLSchema#dateTime"


def _normalized_datetime_lexical(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GraphDBVerificationError("invalid xsd:dateTime lexical in SPARQL result") from exc
    if parsed.tzinfo is None:
        return value
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _integer_term(value: Mapping[str, Any]) -> int:
    lexical = value.get("value")
    datatype = value.get("datatype")
    if value.get("type") != "literal" or not isinstance(lexical, str) or not re.fullmatch(r"-?[0-9]+", lexical):
        raise GraphDBVerificationError(f"SPARQL count is not an integer RDF term: {value}")
    if datatype is not None and not str(datatype).startswith("http://www.w3.org/2001/XMLSchema#"):
        raise GraphDBVerificationError(f"SPARQL count has an unexpected datatype: {datatype}")
    return int(lexical)


def _term_value(value: Mapping[str, Any]) -> dict[str, str]:
    kind = value.get("type")
    if kind == "uri":
        return {"type": "uri", "value": str(value["value"])}
    if kind == "literal":
        term = {"type": "literal", "value": str(value.get("value", ""))}
        if value.get("xml:lang"):
            term["language"] = str(value["xml:lang"])
        if value.get("datatype"):
            term["datatype"] = str(value["datatype"])
            if term["datatype"] == _XSD_DATETIME:
                term["value"] = _normalized_datetime_lexical(term["value"])
        return term
    if kind == "bnode":
        raise GraphDBVerificationError("blank node in SPARQL result")
    raise GraphDBVerificationError(f"unsupported RDF term type: {kind}")


def normalize_select_result(result: Mapping[str, Any]) -> dict[str, Any]:
    head = result.get("head", {})
    variables = list(head.get("vars", [])) if isinstance(head, Mapping) else []
    rows = []
    bindings = result.get("results", {}).get("bindings", [])
    for binding in bindings:
        rows.append({variable: _term_value(binding[variable]) if variable in binding else None for variable in variables})
    rows.sort(
        key=lambda row: tuple(
            () if row[key] is None else tuple(sorted(row[key].items()))
            for key in variables
        )
    )
    return {"head": {"vars": variables}, "results": {"bindings": rows}}


def normalize_ask_result(value: bool) -> dict[str, bool]:
    return {"boolean": bool(value)}


def semantic_hash_nquads(data: bytes) -> str:
    try:
        return graphdb_semantic_hash_nquads(data)
    except GraphDBRDFSemanticError as exc:
        raise GraphDBVerificationError(f"export is not valid N-Quads: {exc}") from exc


def _normalized_row_sort(
    row: Mapping[str, Any], variables: tuple[str, ...]
) -> tuple[Any, ...]:
    return tuple(
        () if row[key] is None else tuple(sorted(row[key].items()))
        for key in variables
    )


def expected_review_audit_rows(expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "log": {"type": "uri", "value": expected["decision_log_id"]},
            "session": {"type": "uri", "value": expected["review_session_id"]},
            "reviewer": {"type": "uri", "value": expected["reviewer_id"]},
            "decision": {"type": "uri", "value": decision["decision_id"]},
            "outcome": {"type": "literal", "value": decision["outcome"]},
            "decidedAt": {
                "type": "literal",
                "value": _normalized_datetime_lexical(decision["decided_at"]),
                "datatype": _XSD_DATETIME,
            },
            "subject": {"type": "uri", "value": decision["subject"]},
        }
        for decision in expected["decisions"]
    ]
    variables = ("log", "session", "reviewer", "decision", "outcome", "decidedAt", "subject")
    rows.sort(key=lambda row: _normalized_row_sort(row, variables))
    return rows


def assert_review_audit_semantics(
    actual_rows: list[dict[str, Any]], expected: Mapping[str, Any]
) -> None:
    if not expected or actual_rows != expected_review_audit_rows(expected):
        raise GraphDBVerificationError("review audit semantic coverage mismatch")


def expected_tbox_version_rows(
    expected: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "g": {"type": "uri", "value": item["graph_iri"]},
            "ontology": {"type": "uri", "value": item["ontology_iri"]},
            "version": {"type": "uri", "value": item["version_iri"]},
        }
        for item in expected
    ]
    variables = ("g", "ontology", "version")
    rows.sort(key=lambda row: _normalized_row_sort(row, variables))
    return rows


def assert_tbox_version_semantics(
    actual_rows: list[dict[str, Any]], expected: list[Mapping[str, Any]]
) -> None:
    for item in expected:
        graph_iri = str(item["graph_iri"])
        parts = graph_iri.split(":")
        if len(parts) < 6 or parts[4] != str(item["module_code"]):
            raise GraphDBVerificationError("TBox module code/graph binding mismatch")
    if actual_rows != expected_tbox_version_rows(expected):
        raise GraphDBVerificationError("TBox graph/ontology/version set mismatch")


def verify_imported_repository(client: GraphDBClient, package_directory: Path, *, report_directory: Path | None = None) -> dict[str, Any]:
    package_directory = Path(package_directory)
    manifest = read_json(package_directory / "graphdb-import-manifest.json")
    repository_id = manifest["repository_id"]
    expected_counts = read_json(package_directory / "verification" / "expected" / "named-graph-counts.json")
    suite = read_json(package_directory / "verification" / "query-suite-manifest.json")
    validate_graphdb_contract("query-suite-manifest", suite)
    if query_suite_hash(suite) != suite["query_suite_hash"] or suite["query_suite_hash"] != manifest["query_suite_hash"]:
        raise GraphDBVerificationError("query suite hash mismatch")
    import_hash = semantic_hash_nquads(
        (package_directory / "import" / "knowledge-graph.nq").read_bytes()
    )
    if import_hash != manifest["assembled_dataset_semantic_hash"]:
        raise GraphDBVerificationError("package import dataset semantic hash mismatch")
    actual_count = client.count_repository_statements(repository_id)
    graph_counts: dict[str, int] = {}
    query_dir = package_directory / "verification" / "queries"
    query_results: dict[str, dict[str, Any]] = {}
    invariant_results: dict[str, dict[str, bool]] = {}
    expected_query_paths = {f"{query_id}.rq" for query_id in suite["queries"]}
    actual_query_paths = {path.name for path in query_dir.glob("*.rq")}
    if actual_query_paths != expected_query_paths:
        raise GraphDBVerificationError("verification query closed set mismatch")
    default_graph_check: dict[str, Any] | None = None
    for check_id, check in sorted(suite["verifications"].items()):
        verification_type = check["verification_type"]
        if verification_type == "GRAPH_STORE_DEFAULT_GRAPH":
            snapshot = client.assert_default_graph_empty(repository_id)
            if snapshot.statement_count != int(check["expected_statement_count"]):
                raise GraphDBVerificationError(
                    "physical default graph statement count mismatch"
                )
            default_graph_check = {
                "verification_type": verification_type,
                "method": "GET /repositories/<repository-id>/rdf-graphs/service?default",
                "http_status": snapshot.http_status,
                "statement_count": snapshot.statement_count,
                "semantic_hash": snapshot.semantic_hash,
                "content_type": snapshot.content_type,
            }
            invariant_results[check_id] = {
                "expected": True,
                "actual": snapshot.statement_count == 0,
            }
            continue
        query_id = check["query_id"]
        query = suite["queries"][query_id]
        if (query_dir / f"{query_id}.rq").read_text(encoding="utf-8") != query:
            raise GraphDBVerificationError(f"verification query bytes mismatch: {query_id}")
        if verification_type == "SPARQL_SELECT":
            normalized = normalize_select_result(client.sparql_select(repository_id, query))
            validate_graphdb_contract("query-result", normalized)
            query_results[query_id] = normalized
            if query_id == "02-named-graph-counts":
                for row in normalized["results"]["bindings"]:
                    if row.get("g") and row.get("count") is not None:
                        if row["g"].get("type") != "uri":
                            raise GraphDBVerificationError("named graph result is not an IRI")
                        graph_counts[row["g"]["value"]] = _integer_term(row["count"])
        elif verification_type == "SPARQL_ASK":
            result = normalize_ask_result(client.sparql_ask(repository_id, query))
            validate_graphdb_contract("query-result", result)
            query_results[query_id] = result
            invariant_results[query_id] = {"expected": True, "actual": result["boolean"]}
            if not result["boolean"]:
                raise GraphDBVerificationError(f"invariant failed: {query_id}")
        else:
            raise GraphDBVerificationError(f"unsupported verification type: {verification_type}")
    if default_graph_check is None:
        raise GraphDBVerificationError("physical default graph check was not executed")
    summary_rows = query_results["01-repository-summary"]["results"]["bindings"]
    if len(summary_rows) != 1:
        raise GraphDBVerificationError("repository summary did not return exactly one row")
    summary = summary_rows[0]
    if _integer_term(summary["namedGraphCount"]) != len(expected_counts):
        raise GraphDBVerificationError("repository summary named graph count mismatch")
    if _integer_term(summary["quadCount"]) != int(manifest["assembled_quad_count"]):
        raise GraphDBVerificationError("repository summary quad count mismatch")
    for query_id in ("03-business-assertions", "04-provenance-coverage"):
        if query_results[query_id]["results"]["bindings"]:
            raise GraphDBVerificationError(f"semantic invariant returned violations: {query_id}")
    review_rows = query_results["05-review-audit-coverage"]["results"]["bindings"]
    expected_review = suite["expected"]["review_audit"]
    assert_review_audit_semantics(review_rows, expected_review)
    tbox_rows = query_results["06-tbox-version"]["results"]["bindings"]
    assert_tbox_version_semantics(tbox_rows, suite["expected"]["tbox_versions"])
    forbidden_json = read_json(
        package_directory / "verification" / "expected" / "forbidden-business-assertions.json"
    )
    validate_graphdb_contract("forbidden-business-assertions", forbidden_json)
    forbidden_nt = (
        package_directory / "verification" / "expected" / "forbidden-business-assertions.nt"
    ).read_bytes()
    if forbidden_json.get("forbidden_assertion_count") != int(manifest["forbidden_assertion_count"]):
        raise GraphDBVerificationError("forbidden assertion projection count mismatch")
    if forbidden_json.get("forbidden_assertion_count") != suite["expected"]["forbidden_assertion_count"]:
        raise GraphDBVerificationError("query suite forbidden assertion count mismatch")
    forbidden_graph = parse_ntriples(forbidden_nt)
    if len(forbidden_graph) != int(manifest["forbidden_assertion_count"]):
        raise GraphDBVerificationError("forbidden assertion N-Triples count mismatch")
    if forbidden_json["canonical_ntriples_sha256"] != hashlib.sha256(forbidden_nt).hexdigest():
        raise GraphDBVerificationError("forbidden assertion N-Triples hash mismatch")
    expected_projection_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "records": forbidden_json["records"],
                "canonical_ntriples_sha256": hashlib.sha256(forbidden_nt).hexdigest(),
            }
        )
    ).hexdigest()
    if forbidden_json.get("semantic_hash") != expected_projection_hash or manifest["forbidden_assertion_set_hash"] != expected_projection_hash:
        raise GraphDBVerificationError("forbidden assertion projection semantic hash mismatch")
    forbidden_rows = query_results["09-no-rejected-business-facts"]["results"]["bindings"]
    if forbidden_rows:
        raise GraphDBVerificationError("forbidden rejected/deferred assertion leaked into business graph")
    exported = client.export_nquads(repository_id, include_inferred=False)
    if report_directory:
        diagnostic_export_directory = Path(report_directory) / "export"
        diagnostic_export_directory.mkdir(parents=True, exist_ok=True)
        (diagnostic_export_directory / "explicit-repository.nq").write_bytes(exported)
    export_hash = semantic_hash_nquads(exported)
    complete_export_hash = semantic_hash_nquads(
        client.export_nquads(repository_id, include_inferred=True)
    )
    expected_hash = manifest["assembled_dataset_semantic_hash"]
    if export_hash != expected_hash:
        raise GraphDBVerificationError("GraphDB explicit export semantic hash mismatch")
    if complete_export_hash != export_hash:
        raise GraphDBVerificationError("GraphDB full export contains inferred statements")
    expected_graph_counts = {str(k): int(v) for k, v in expected_counts.items()}
    if actual_count != int(manifest["assembled_quad_count"]):
        raise GraphDBVerificationError("repository explicit statement count mismatch")
    if graph_counts != expected_graph_counts:
        raise GraphDBVerificationError("named graph count mismatch")
    result = {"status": "IMPORT_VERIFIED", "repository_id": repository_id, "actual_quad_count": actual_count, "expected_quad_count": manifest["assembled_quad_count"], "expected_graph_counts": expected_counts, "actual_graph_counts": graph_counts, "default_graph_statement_count": default_graph_check["statement_count"], "default_graph_check": default_graph_check, "forbidden_assertion_count": int(manifest["forbidden_assertion_count"]), "violating_forbidden_assertion_count": len(forbidden_rows), "inferred_statement_count": 0, "import_semantic_hash": expected_hash, "export_semantic_hash": export_hash, "complete_export_semantic_hash": complete_export_hash, "query_results": query_results, "invariant_results": invariant_results}
    if report_directory:
        destination = Path(report_directory)
        (destination / "verification").mkdir(parents=True, exist_ok=True)
        (destination / "verification" / "query-results").mkdir(parents=True, exist_ok=True)
        (destination / "export").mkdir(parents=True, exist_ok=True)
        (destination / "verification" / "graph-counts.json").write_bytes(json_bytes({"expected": expected_counts, "actual": graph_counts}))
        (destination / "verification" / "invariant-results.json").write_bytes(json_bytes(invariant_results))
        (destination / "verification" / "default-graph-check.json").write_bytes(json_bytes(default_graph_check))
        for query_id, query_result in query_results.items():
            (destination / "verification" / "query-results" / f"{query_id}.json").write_bytes(json_bytes(query_result))
    return result
