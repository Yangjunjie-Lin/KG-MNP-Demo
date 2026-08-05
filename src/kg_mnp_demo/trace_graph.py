"""Build real RDF dependency subgraphs for eligibility assessments.

Edge selection is defined solely by ``queries/assessment_subgraph.rq``.
Python converts SPARQL rows into stable nodes/edges and validates integrity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from kg_mnp_demo.loader import query_path
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.rule_engine import resolve_case_uri

PREFERRED_TYPES = [
    "EligibilityAssessment",
    "BlockingReason",
    "BlockingDecision",
    "EligibleDecision",
    "ManualReviewDecision",
    "ConditionalDecision",
    "EligibilityDecision",
    "EvidenceRecord",
    "SystemObservation",
    "EligibilityRule",
    "RuleVersion",
    "RegulatoryClause",
    "RegulatoryDocument",
    "RemediationAction",
    "MNPCase",
    "ReassessmentMarker",
]

SUBGRAPH_QUERY_FILE = "assessment_subgraph.rq"


class TraceSubgraphIntegrityError(RuntimeError):
    """Raised when the SPARQL subgraph contains edges absent from the RDF graph."""


def _local(iri: str | None) -> str:
    if not iri:
        return ""
    text = str(iri)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rsplit("/", 1)[-1]


def _pick_type(types: set[str]) -> str | None:
    locals_ = {_local(t) for t in types}
    for preferred in PREFERRED_TYPES:
        if preferred in locals_:
            return preferred
    return sorted(locals_)[0] if locals_ else None


def _node_label(graph: Graph, node: URIRef, node_type: str | None) -> str:
    if node_type == "RuleVersion":
        rid = graph.value(node, MNP.ruleIdentifier)
        ver = graph.value(node, MNP.ruleVersion)
        if rid and ver:
            return f"{rid} v{ver}"
        if ver:
            return str(ver)
    for pred in (
        MNP.assessmentIdentifier,
        MNP.reasonCode,
        MNP.decisionCode,
        MNP.ruleIdentifier,
        MNP.clauseIdentifier,
        MNP.actionCode,
        MNP.caseIdentifier,
        MNP.systemIdentifier,
        MNP.ruleVersion,
    ):
        val = graph.value(node, pred)
        if val is not None:
            return str(val)
    local = _local(str(node))
    return local


def _types_of(graph: Graph, node: URIRef) -> set[str]:
    return {str(t) for t in graph.objects(node, RDF.type)}


def _load_subgraph_query() -> str:
    path = Path(query_path(SUBGRAPH_QUERY_FILE))
    if not path.exists():
        raise FileNotFoundError(f"Missing subgraph query file: {path}")
    return path.read_text(encoding="utf-8")


def _run_subgraph_query(graph: Graph, case_id: str) -> list[tuple[URIRef, URIRef, URIRef]]:
    query = _load_subgraph_query()
    rows = graph.query(
        query,
        initBindings={"requestedCaseId": Literal(case_id, datatype=XSD.string)},
    )
    triples: list[tuple[URIRef, URIRef, URIRef]] = []
    for row in rows:
        subject, predicate, obj = row.subject, row.predicate, row.object
        if not isinstance(subject, URIRef):
            raise TraceSubgraphIntegrityError(
                f"Subgraph subject is not a URIRef: {subject!r}"
            )
        if not isinstance(predicate, URIRef):
            raise TraceSubgraphIntegrityError(
                f"Subgraph predicate is not a URIRef: {predicate!r}"
            )
        if not isinstance(obj, URIRef):
            raise TraceSubgraphIntegrityError(
                f"Subgraph object is not a URIRef: {obj!r}"
            )
        triples.append((subject, predicate, obj))
    return triples


def edges_exist_in_graph(graph: Graph, subgraph: dict[str, Any]) -> list[dict[str, str]]:
    """Return edges from subgraph that are missing from the RDF graph."""
    missing: list[dict[str, str]] = []
    for edge in subgraph.get("edges", []):
        s = URIRef(edge["source"])
        p = URIRef(edge.get("predicate_iri") or str(MNP[edge["predicate"]]))
        o = URIRef(edge["target"])
        if (s, p, o) not in graph:
            missing.append(edge)
    return missing


def build_assessment_subgraph(graph: Graph, case_id: str) -> dict[str, Any]:
    """Execute assessment_subgraph.rq and convert rows to nodes/edges."""
    case_uri = resolve_case_uri(graph, case_id)
    triples = _run_subgraph_query(graph, case_id)

    edge_keys: set[tuple[str, str, str]] = set()
    edges: list[dict[str, str]] = []
    node_iris: set[str] = set()

    if case_uri is not None:
        node_iris.add(str(case_uri))

    for subject, predicate, obj in triples:
        s, p_iri, o = str(subject), str(predicate), str(obj)
        pred_local = _local(p_iri)
        key = (s, p_iri, o)
        if key in edge_keys:
            continue
        edge_keys.add(key)
        node_iris.add(s)
        node_iris.add(o)
        edges.append(
            {
                "source": s,
                "predicate": pred_local,
                "predicate_iri": p_iri,
                "target": o,
                "source_local": _local(s),
                "target_local": _local(o),
            }
        )

    nodes: list[dict[str, Any]] = []
    for iri in sorted(node_iris, key=_local):
        uri = URIRef(iri)
        ntype = _pick_type(_types_of(graph, uri))
        nodes.append(
            {
                "id": iri,
                "local_id": _local(iri),
                "type": ntype,
                "label": _node_label(graph, uri, ntype),
            }
        )

    edges.sort(key=lambda e: (e["source_local"], e["predicate"], e["target_local"]))
    subgraph = {
        "case_id": case_id,
        "root": str(case_uri) if case_uri is not None else case_id,
        "root_local": _local(str(case_uri)) if case_uri is not None else case_id,
        "nodes": nodes,
        "edges": edges,
        "query_file": SUBGRAPH_QUERY_FILE,
    }

    missing = edges_exist_in_graph(graph, subgraph)
    if missing:
        sample = missing[0]
        raise TraceSubgraphIntegrityError(
            f"Subgraph edge missing from RDF graph: "
            f"{sample['source_local']} -{sample['predicate']}-> {sample['target_local']} "
            f"({len(missing)} missing)"
        )

    # Every edge endpoint must appear in nodes
    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise TraceSubgraphIntegrityError(
                "Subgraph nodes incomplete relative to edges"
            )

    return subgraph


def format_subgraph_tree(subgraph: dict[str, Any]) -> str:
    """Render a terminal tree from real edges (no fabricated predicates)."""
    case_id = subgraph["case_id"]
    nodes_by_id = {n["id"]: n for n in subgraph["nodes"]}
    edges = subgraph["edges"]

    def children(source: str) -> list[dict[str, str]]:
        return [e for e in edges if e["source"] == source]

    def describe(node_id: str) -> str:
        node = nodes_by_id.get(node_id)
        if not node:
            return _local(node_id)
        ntype = node.get("type") or "Resource"
        label = node.get("label") or node.get("local_id") or _local(node_id)
        return f"{ntype}: {label}"

    root = subgraph.get("root")
    if not root or root not in nodes_by_id:
        for n in subgraph["nodes"]:
            if n.get("type") == "MNPCase":
                root = n["id"]
                break
        else:
            root = subgraph.get("root") or case_id

    lines: list[str] = [f"MNPCase: {case_id}"]
    assess_edges = [
        e for e in children(root) if e["predicate"] == "hasEligibilityAssessment"
    ]

    for a_edge in assess_edges:
        assessment = a_edge["target"]
        lines.append("└── hasEligibilityAssessment")
        lines.append(f"    {describe(assessment)}")

        preferred_order = [
            "usesEvidence",
            "evaluatedByRule",
            "usesRuleVersion",
            "producesDecision",
            "aboutCase",
            "markedForReassessment",
        ]
        a_children = children(assessment)
        by_pred: dict[str, list[str]] = {}
        for e in a_children:
            by_pred.setdefault(e["predicate"], []).append(e["target"])

        ordered_preds = [p for p in preferred_order if p in by_pred]
        ordered_preds += sorted(p for p in by_pred if p not in preferred_order)

        for p_idx, pred in enumerate(ordered_preds):
            is_last_pred = p_idx == len(ordered_preds) - 1
            pred_branch = "└──" if is_last_pred else "├──"
            targets = sorted(set(by_pred[pred]), key=_local)
            indent = "    "
            child_indent = indent + ("    " if is_last_pred else "│   ")

            if pred == "aboutCase":
                continue

            if pred == "evaluatedByRule":
                lines.append(f"{indent}{pred_branch} {pred}")
                for target in targets:
                    lines.append(f"{child_indent}{describe(target)}")
                    clause_edges = [
                        e
                        for e in children(target)
                        if e["predicate"] == "operationalizesClause"
                    ]
                    for c_edge in clause_edges:
                        lines.append(f"{child_indent}└── operationalizesClause")
                        clause = c_edge["target"]
                        lines.append(f"{child_indent}    {describe(clause)}")
                        for d_edge in children(clause):
                            if d_edge["predicate"] != "partOfDocument":
                                continue
                            lines.append(f"{child_indent}    └── partOfDocument")
                            lines.append(
                                f"{child_indent}        {describe(d_edge['target'])}"
                            )
                continue

            if pred == "producesDecision":
                lines.append(f"{indent}{pred_branch} {pred}")
                reason_preds = [
                    "hasBlockingReason",
                    "supportedByEvidence",
                    "triggeredByRule",
                    "triggeredByRuleVersion",
                    "citesClause",
                    "recommendsAction",
                ]
                for t_idx, target in enumerate(targets):
                    lines.append(f"{child_indent}{describe(target)}")
                    # Blocking reasons hang off the decision
                    br_edges = [
                        e
                        for e in children(target)
                        if e["predicate"] == "hasBlockingReason"
                    ]
                    for br in br_edges:
                        reason = br["target"]
                        lines.append(f"{child_indent}└── hasBlockingReason")
                        lines.append(f"{child_indent}    {describe(reason)}")
                        r_children = children(reason)
                        r_by: dict[str, list[str]] = {}
                        for e in r_children:
                            r_by.setdefault(e["predicate"], []).append(e["target"])
                        r_ordered = [p for p in reason_preds if p in r_by and p != "hasBlockingReason"]
                        r_ordered += sorted(
                            p for p in r_by if p not in reason_preds and p != "hasBlockingReason"
                        )
                        for rp_idx, rpred in enumerate(r_ordered):
                            r_last = rp_idx == len(r_ordered) - 1
                            marker = "└──" if r_last else "├──"
                            for tgt in sorted(set(r_by[rpred]), key=_local):
                                tgt_label = nodes_by_id.get(tgt, {}).get("label") or _local(tgt)
                                lines.append(
                                    f"{child_indent}    {marker} {rpred} → {tgt_label}"
                                )
                    if t_idx < len(targets) - 1:
                        lines.append(f"{child_indent}")
                continue

            lines.append(f"{indent}{pred_branch} {pred}")
            for target in targets:
                short = nodes_by_id.get(target, {}).get("label") or _local(target)
                ntype = (nodes_by_id.get(target) or {}).get("type") or "Resource"
                lines.append(f"{child_indent}{ntype}: {short}")

    return "\n".join(lines)


def render_subgraph_html(subgraph: dict[str, Any]) -> str:
    """Offline HTML fragment: nested lists with real predicates."""
    import html as html_mod

    def esc(v: Any) -> str:
        return html_mod.escape("" if v is None else str(v))

    nodes_by_id = {n["id"]: n for n in subgraph["nodes"]}
    edges = subgraph["edges"]

    def children(source: str) -> list[dict[str, str]]:
        return [e for e in edges if e["source"] == source]

    def node_title(node_id: str) -> str:
        node = nodes_by_id.get(node_id, {})
        ntype = node.get("type") or "Resource"
        label = node.get("label") or node.get("local_id") or _local(node_id)
        return f"{ntype}: {label}"

    root = subgraph.get("root")
    assess_edges = (
        [e for e in children(root) if e["predicate"] == "hasEligibilityAssessment"]
        if root
        else []
    )

    parts: list[str] = [
        f'<div class="subgraph"><div class="node root"><span class="ntype">MNPCase</span> '
        f'<span class="nlabel">{esc(subgraph["case_id"])}</span></div>'
    ]
    parts.append("<ul class='tree'>")
    for a_edge in assess_edges:
        assessment = a_edge["target"]
        parts.append(
            f"<li><span class='pred'>hasEligibilityAssessment</span>"
            f"<div class='node'><span class='ntype'>{esc(nodes_by_id.get(assessment, {}).get('type') or 'EligibilityAssessment')}</span> "
            f"<span class='nlabel'>{esc(nodes_by_id.get(assessment, {}).get('label') or _local(assessment))}</span></div>"
        )
        parts.append("<ul>")
        preferred = [
            "usesEvidence",
            "evaluatedByRule",
            "usesRuleVersion",
            "producesDecision",
        ]
        a_children = children(assessment)
        by_pred: dict[str, list[str]] = {}
        for e in a_children:
            by_pred.setdefault(e["predicate"], []).append(e["target"])
        for pred in preferred:
            if pred not in by_pred:
                continue
            parts.append(f"<li><span class='pred'>{esc(pred)}</span><ul>")
            for target in sorted(set(by_pred[pred]), key=_local):
                parts.append(f"<li><div class='node'>{esc(node_title(target))}</div>")
                if pred == "evaluatedByRule":
                    for ce in children(target):
                        if ce["predicate"] != "operationalizesClause":
                            continue
                        parts.append(
                            f"<ul><li><span class='pred'>operationalizesClause</span>"
                            f"<div class='node'>{esc(node_title(ce['target']))}</div></li></ul>"
                        )
                if pred == "producesDecision":
                    parts.append("<ul>")
                    for re in children(target):
                        if re["predicate"] != "hasBlockingReason":
                            continue
                        reason = re["target"]
                        parts.append(
                            f"<li><span class='pred'>hasBlockingReason</span>"
                            f"<div class='node'>{esc(node_title(reason))}</div><ul>"
                        )
                        for child in children(reason):
                            if child["predicate"] in {
                                "supportedByEvidence",
                                "triggeredByRule",
                                "triggeredByRuleVersion",
                                "citesClause",
                                "recommendsAction",
                            }:
                                parts.append(
                                    f"<li><span class='pred'>{esc(child['predicate'])}</span>"
                                    f"<div class='node'>{esc(node_title(child['target']))}</div></li>"
                                )
                        parts.append("</ul></li>")
                    parts.append("</ul>")
                parts.append("</li>")
            parts.append("</ul></li>")
        parts.append("</ul></li>")
    parts.append("</ul></div>")
    return "".join(parts)
