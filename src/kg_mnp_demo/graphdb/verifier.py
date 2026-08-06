from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from rdflib import BNode, Dataset

from ..compilation.rdf_canonical import canonical_nquads
from ._io import read_json, json_bytes
from .client import GraphDBClient
from .contracts import validate_graphdb_contract
from .query_suite import query_suite_hash


class GraphDBVerificationError(RuntimeError):
    pass


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
    dataset = Dataset()
    try:
        dataset.parse(data=data.decode("utf-8"), format="nquads")
    except Exception as exc:
        raise GraphDBVerificationError(f"export is not valid N-Quads: {exc}") from exc
    quads = [(s, p, o, g) for s, p, o, g in dataset.quads((None, None, None, None))]
    if any(isinstance(term, BNode) for quad in quads for term in quad):
        raise GraphDBVerificationError("export contains blank nodes")
    return hashlib.sha256(canonical_nquads(quads)).hexdigest()


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
    for query_id, query in sorted(suite["queries"].items()):
        if (query_dir / f"{query_id}.rq").read_text(encoding="utf-8") != query:
            raise GraphDBVerificationError(f"verification query bytes mismatch: {query_id}")
        if query_id in {"01-repository-summary", "02-named-graph-counts", "03-business-assertions", "04-provenance-coverage", "05-review-audit-coverage", "06-tbox-version"}:
            normalized = normalize_select_result(client.sparql_select(repository_id, query))
            validate_graphdb_contract("query-result", normalized)
            query_results[query_id] = normalized
            if query_id == "02-named-graph-counts":
                for row in normalized["results"]["bindings"]:
                    if row.get("g") and row.get("count") is not None:
                        if row["g"].get("type") != "uri":
                            raise GraphDBVerificationError("named graph result is not an IRI")
                        graph_counts[row["g"]["value"]] = _integer_term(row["count"])
        else:
            result = normalize_ask_result(client.sparql_ask(repository_id, query))
            validate_graphdb_contract("query-result", result)
            query_results[query_id] = result
            invariant_results[query_id] = {"expected": True, "actual": result["boolean"]}
            if not result["boolean"]:
                raise GraphDBVerificationError(f"invariant failed: {query_id}")
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
    source_manifest = read_json(package_directory / "source" / "compilation-manifest.json")
    review_graph = source_manifest["graph_iris"]["review_audit"]
    review_rows = query_results["05-review-audit-coverage"]["results"]["bindings"]
    if len(review_rows) != 1 or _integer_term(review_rows[0]["count"]) != int(expected_counts[review_graph]):
        raise GraphDBVerificationError("review audit coverage count mismatch")
    tbox_rows = query_results["06-tbox-version"]["results"]["bindings"]
    if len(tbox_rows) != int(suite["expected"]["tbox_module_count"]):
        raise GraphDBVerificationError("TBox version/module count mismatch")
    exported = client.export_nquads(repository_id, include_inferred=False)
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
    result = {"status": "IMPORT_VERIFIED", "repository_id": repository_id, "actual_quad_count": actual_count, "expected_quad_count": manifest["assembled_quad_count"], "expected_graph_counts": expected_counts, "actual_graph_counts": graph_counts, "inferred_statement_count": 0, "import_semantic_hash": expected_hash, "export_semantic_hash": export_hash, "complete_export_semantic_hash": complete_export_hash, "query_results": query_results, "invariant_results": invariant_results}
    if report_directory:
        destination = Path(report_directory)
        (destination / "verification").mkdir(parents=True, exist_ok=True)
        (destination / "verification" / "query-results").mkdir(parents=True, exist_ok=True)
        (destination / "export").mkdir(parents=True, exist_ok=True)
        (destination / "verification" / "graph-counts.json").write_bytes(json_bytes({"expected": expected_counts, "actual": graph_counts}))
        (destination / "verification" / "invariant-results.json").write_bytes(json_bytes(invariant_results))
        for query_id, query_result in query_results.items():
            (destination / "verification" / "query-results" / f"{query_id}.json").write_bytes(json_bytes(query_result))
        (destination / "export" / "explicit-repository.nq").write_bytes(exported)
    return result
