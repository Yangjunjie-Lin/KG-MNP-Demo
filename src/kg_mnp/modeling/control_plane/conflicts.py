"""Deterministic candidate conflict detection."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from kg_mnp.contracts.canonical import stable_urn


def issue(code: str, message: str, candidate_refs: list[str] | tuple[str, ...], *, severity: str = "BLOCKING", evidence_refs: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    semantic = {"code": code, "message": message, "candidate_refs": sorted(set(candidate_refs)), "evidence_refs": sorted(set(evidence_refs))}
    return {"issue_id": stable_urn("modeling-issue", semantic), **semantic, "severity": severity}


def _cycles(candidates: list[dict[str, Any]]) -> list[list[str]]:
    graph = {item["candidate_id"]: set(item["dependency_candidate_refs"]) for item in candidates}
    cycles: set[tuple[str, ...]] = set()
    visited: set[str] = set()
    active: list[str] = []

    def visit(node: str) -> None:
        if node in active:
            start = active.index(node)
            cycles.add(tuple(sorted(active[start:])))
            return
        if node in visited:
            return
        active.append(node)
        for target in sorted(graph.get(node, set())):
            if target in graph:
                visit(target)
        active.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return [list(value) for value in sorted(cycles)]


def detect_conflicts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    iri_declarations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mapping_sources: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    literal_assertions: dict[tuple[str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
    domain_axioms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    range_axioms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cardinalities: dict[tuple[str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
    subclass_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        body = candidate["body"]
        declared = body.get("subject_iri") or body.get("target_iri")
        if declared and candidate["candidate_action"] == "CREATE_NEW":
            iri_declarations[declared].append(candidate)
        if body.get("label"):
            labels[body["label"].casefold()].append(candidate)
        if candidate["candidate_kind"] == "MAPPING" and body.get("source_field"):
            mapping_sources[(candidate["kg_ir_item_refs"][0] if candidate["kg_ir_item_refs"] else "", body["source_field"])].append(candidate)
        if body["candidate_type"] == "DATA_PROPERTY_ASSERTION":
            literal_assertions[(body.get("subject_iri"), body.get("predicate_iri"))].append(candidate)
        if body["candidate_type"] == "DOMAIN_AXIOM":
            domain_axioms[body.get("subject_iri") or body.get("predicate_iri") or ""].append(candidate)
        if body["candidate_type"] == "RANGE_AXIOM":
            range_axioms[body.get("subject_iri") or body.get("predicate_iri") or ""].append(candidate)
        if body["candidate_type"] in {"MIN_COUNT", "MAX_COUNT"}:
            cardinalities[(body.get("subject_iri") or body.get("target_iri"), body.get("predicate_iri"))].append(candidate)
        if body["candidate_type"] == "SUBCLASS_AXIOM" and body.get("subject_iri") and body.get("object_iri"):
            subclass_edges[body["subject_iri"]].append(candidate)
    for iri_value, rows in sorted(iri_declarations.items()):
        types = {item["body"]["candidate_type"] for item in rows}
        if len(rows) > 1 and len(types) > 1:
            conflicts.append(issue("IRI_COLLISION", f"IRI {iri_value} has conflicting element types", [item["candidate_id"] for item in rows]))
            conflicts.append(issue("ELEMENT_TYPE_CONFLICT", f"IRI {iri_value} is declared with incompatible element types", [item["candidate_id"] for item in rows]))
    for label, rows in sorted(labels.items()):
        iris = {item["body"].get("subject_iri") or item["body"].get("target_iri") for item in rows}
        if len(iris - {None}) > 1:
            conflicts.append(issue("DUPLICATE_LABEL", f"label {label!r} maps to multiple candidate IRIs", [item["candidate_id"] for item in rows], severity="WARNING"))
    for source, rows in sorted(mapping_sources.items()):
        targets = {item["body"].get("target_iri") for item in rows}
        if len(targets) > 1:
            conflicts.append(issue("MAPPING_TARGET_CONFLICT", f"source field {source} has multiple mapping targets", [item["candidate_id"] for item in rows]))
    for key, rows in sorted(literal_assertions.items(), key=lambda item: str(item[0])):
        literals = {str(item["body"].get("literal")) for item in rows}
        if len(literals) > 1:
            conflicts.append(issue("LITERAL_CONFLICT", f"assertion {key} has contradictory literal values", [item["candidate_id"] for item in rows]))
            conflicts.append(issue("EVIDENCE_CONTRADICTION", f"assertion {key} carries contradictory evidence-bound values", [item["candidate_id"] for item in rows]))
        datatypes = {
            (item["body"].get("literal") or {}).get("datatype_iri")
            for item in rows
        }
        if len(datatypes - {None}) > 1:
            conflicts.append(issue("DATATYPE_CONFLICT", f"assertion {key} uses incompatible datatypes", [item["candidate_id"] for item in rows]))
    for code, groups in (("DOMAIN_CONFLICT", domain_axioms), ("RANGE_CONFLICT", range_axioms)):
        for property_iri, rows in sorted(groups.items()):
            targets = {item["body"].get("object_iri") or item["body"].get("target_iri") for item in rows}
            if len(targets - {None}) > 1:
                conflicts.append(issue(code, f"property {property_iri} has incompatible axiom targets", [item["candidate_id"] for item in rows]))
    for key, rows in sorted(cardinalities.items(), key=lambda item: str(item[0])):
        minimums = [item["body"]["integer_value"] for item in rows if item["body"]["candidate_type"] == "MIN_COUNT" and isinstance(item["body"]["integer_value"], int)]
        maximums = [item["body"]["integer_value"] for item in rows if item["body"]["candidate_type"] == "MAX_COUNT" and isinstance(item["body"]["integer_value"], int)]
        if minimums and maximums and max(minimums) > min(maximums):
            conflicts.append(issue("CARDINALITY_CONFLICT", f"shape path {key} has minimum greater than maximum", [item["candidate_id"] for item in rows]))
    semantic_graph = {
        child: {
            item["body"]["object_iri"]
            for item in rows
        }
        for child, rows in subclass_edges.items()
    }
    for start in sorted(semantic_graph):
        frontier = [(start, (start,))]
        while frontier:
            node, trail = frontier.pop()
            for parent in sorted(semantic_graph.get(node, set())):
                if parent == start:
                    involved = [
                        item["candidate_id"]
                        for child in trail
                        for item in subclass_edges.get(child, [])
                    ]
                    conflicts.append(issue("SUBCLASS_CYCLE", "subclass candidate graph contains a cycle", involved))
                    frontier = []
                    break
                if parent not in trail:
                    frontier.append((parent, (*trail, parent)))
    for cycle in _cycles(candidates):
        conflicts.append(issue("SUBCLASS_CYCLE", "candidate dependency cycle detected", cycle))
    return sorted(
        {item["issue_id"]: item for item in conflicts}.values(),
        key=lambda item: item["issue_id"],
    )
