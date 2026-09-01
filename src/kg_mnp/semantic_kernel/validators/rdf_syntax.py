"""RDF parse, canonical round-trip, and paired-view equivalence."""

from __future__ import annotations

import hashlib
from typing import Any

from rdflib import BNode, Dataset, Graph
from rdflib.exceptions import ParserError

from ..contracts import finalize_artifact
from ..rdf.canonical import canonical_nquads, canonical_ntriples

_FORMATS = {".nt": "nt", ".ttl": "turtle", ".nq": "nquads", ".trig": "trig"}
_MEDIA = {".nt": "application/n-triples", ".ttl": "text/turtle", ".nq": "application/n-quads", ".trig": "application/trig"}


def _canonical(data: bytes, suffix: str) -> tuple[bytes, int, int]:
    if suffix in {".nq", ".trig"}:
        dataset = Dataset()
        dataset.parse(data=data.decode(), format=_FORMATS[suffix])
        quads = []
        blank_count = 0
        for s, p, o, context in dataset.quads((None, None, None, None)):
            graph = context.identifier if hasattr(context, "identifier") else context
            quads.append((s, p, o, graph))
            blank_count += sum(isinstance(term, BNode) for term in (s, p, o, graph))
        return canonical_nquads(quads), len(set(quads)), blank_count
    graph = Graph()
    graph.parse(data=data.decode(), format=_FORMATS[suffix])
    blank_count = sum(isinstance(term, BNode) for triple in graph for term in triple)
    return canonical_ntriples(graph), len(graph), blank_count


def validate_rdf_artifacts(
    artifacts: dict[str, bytes],
    *,
    dataset_id: str,
    equivalents: dict[str, str],
) -> dict[str, Any]:
    rows = []
    canonical: dict[str, bytes] = {}
    issues = []
    for path in sorted(equivalents):
        data = artifacts[path]
        suffix = "." + path.rsplit(".", 1)[-1].lower()
        try:
            value, count, blanks = _canonical(data, suffix)
            parse_status = "PASSED"
        except (ParserError, SyntaxError, UnicodeError, ValueError) as exc:
            value, count, blanks = b"", 0, 0
            parse_status = "FAILED"
            issues.append(str(exc))
        canonical[path] = value
        equivalent = equivalents[path]
        rows.append({"path": path, "media_type": _MEDIA[suffix], "byte_sha256": hashlib.sha256(data).hexdigest(), "parsed_statement_count": count, "canonical_semantic_digest": hashlib.sha256(value).hexdigest(), "blank_node_count": blanks, "parse_status": parse_status, "round_trip_status": "PASSED" if parse_status == "PASSED" else "FAILED", "equivalent_canonical_artifact": equivalent})
    for row in rows:
        path = row["path"]
        if canonical[path] != canonical.get(equivalents[path], b"__missing__") or row["blank_node_count"]:
            row["round_trip_status"] = "FAILED"
    status = "PASSED" if all(row["parse_status"] == row["round_trip_status"] == "PASSED" for row in rows) else "FAILED"
    issue_rows = []
    for index, message in enumerate(issues):
        from kg_mnp.contracts.canonical import stable_urn

        issue_rows.append({"issue_id": stable_urn("rdf-validation-issue", {"index": index, "message": message}), "code": "RDF_PARSE_FAILED", "severity": "BLOCKING", "message": message[:4096] or "RDF parse failed", "artifact_refs": []})
    core = {"manifest_kind": "KG_MNP_RDF_SYNTAX_VALIDATION_REPORT", "schema_version": "1.0.0", "dataset_id": dataset_id, "files": rows, "status": status, "issues": issue_rows}
    return finalize_artifact(core, id_field="report_id", urn_kind="rdf-syntax-validation-report", contract="rdf-syntax-validation-report")
