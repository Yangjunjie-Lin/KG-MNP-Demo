"""Build real RDF dependency subgraphs for eligibility assessments."""

from __future__ import annotations

from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

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
    "AssessmentDependency",
    "MNPCase",
    "ReassessmentMarker",
]

ASSESSMENT_PREDICATES = [
    MNP.aboutCase,
    MNP.usesEvidence,
    MNP.evaluatedByRule,
    MNP.usesRuleVersion,
    MNP.producesDecision,
    MNP.producesBlockingReason,
    MNP.dependsOn,
]

REASON_PREDICATES = [
    MNP.supportedByEvidence,
    MNP.triggeredByRule,
    MNP.triggeredByRuleVersion,
    MNP.citesClause,
    MNP.recommendsAction,
]

DEPENDENCY_PREDICATES = [
    MNP.dependsOnEvidence,
    MNP.dependsOnRuleVersion,
]


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
    if node_type == "AssessmentDependency":
        return "AssessmentDependency"
    return local


def _types_of(graph: Graph, node: URIRef) -> set[str]:
    return {str(t) for t in graph.objects(node, RDF.type)}


def _add_edge(
    edges: list[dict[str, str]],
    edge_keys: set[tuple[str, str, str]],
    node_types: dict[str, set[str]],
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    obj: URIRef,
) -> None:
    if not isinstance(obj, URIRef):
        return
    s, p, o = str(subject), _local(str(predicate)), str(obj)
    key = (s, p, o)
    if key in edge_keys:
        return
    edge_keys.add(key)
    node_types.setdefault(s, set()).update(_types_of(graph, subject))
    node_types.setdefault(o, set()).update(_types_of(graph, obj))
    edges.append(
        {
            "source": s,
            "predicate": p,
            "target": o,
            "source_local": _local(s),
            "target_local": _local(o),
        }
    )


def build_assessment_subgraph(graph: Graph, case_id: str) -> dict[str, Any]:
    """Walk real RDF edges from the case assessment(s). No fabricated predicates."""
    case_uri = resolve_case_uri(graph, case_id)
    edges: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    node_types: dict[str, set[str]] = {}

    if case_uri is None:
        return {
            "case_id": case_id,
            "root": case_id,
            "root_local": case_id,
            "nodes": [],
            "edges": [],
        }

    node_types[str(case_uri)] = _types_of(graph, case_uri)

    assessments = sorted(
        (a for a in graph.objects(case_uri, MNP.hasEligibilityAssessment) if isinstance(a, URIRef)),
        key=str,
    )
    for assessment in assessments:
        _add_edge(
            edges,
            edge_keys,
            node_types,
            graph,
            case_uri,
            MNP.hasEligibilityAssessment,
            assessment,
        )
        for pred in ASSESSMENT_PREDICATES:
            for obj in sorted(graph.objects(assessment, pred), key=str):
                if isinstance(obj, URIRef):
                    _add_edge(edges, edge_keys, node_types, graph, assessment, pred, obj)

        for rule in sorted(graph.objects(assessment, MNP.evaluatedByRule), key=str):
            if not isinstance(rule, URIRef):
                continue
            for clause in sorted(graph.objects(rule, MNP.operationalizesClause), key=str):
                if isinstance(clause, URIRef):
                    _add_edge(
                        edges,
                        edge_keys,
                        node_types,
                        graph,
                        rule,
                        MNP.operationalizesClause,
                        clause,
                    )
                    for doc in sorted(graph.objects(clause, MNP.partOfDocument), key=str):
                        if isinstance(doc, URIRef):
                            _add_edge(
                                edges,
                                edge_keys,
                                node_types,
                                graph,
                                clause,
                                MNP.partOfDocument,
                                doc,
                            )

        for reason in sorted(graph.objects(assessment, MNP.producesBlockingReason), key=str):
            if not isinstance(reason, URIRef):
                continue
            for pred in REASON_PREDICATES:
                for obj in sorted(graph.objects(reason, pred), key=str):
                    if isinstance(obj, URIRef):
                        _add_edge(edges, edge_keys, node_types, graph, reason, pred, obj)

        for dep in sorted(graph.objects(assessment, MNP.dependsOn), key=str):
            if not isinstance(dep, URIRef):
                continue
            for pred in DEPENDENCY_PREDICATES:
                for obj in sorted(graph.objects(dep, pred), key=str):
                    if isinstance(obj, URIRef):
                        _add_edge(edges, edge_keys, node_types, graph, dep, pred, obj)

    nodes: list[dict[str, Any]] = []
    for iri, types in sorted(node_types.items(), key=lambda x: _local(x[0])):
        ntype = _pick_type(types)
        nodes.append(
            {
                "id": iri,
                "local_id": _local(iri),
                "type": ntype,
                "label": _node_label(graph, URIRef(iri), ntype),
            }
        )

    edges.sort(key=lambda e: (e["source_local"], e["predicate"], e["target_local"]))
    return {
        "case_id": case_id,
        "root": str(case_uri),
        "root_local": _local(str(case_uri)),
        "nodes": nodes,
        "edges": edges,
    }


def edges_exist_in_graph(graph: Graph, subgraph: dict[str, Any]) -> list[dict[str, str]]:
    """Return edges from subgraph that are missing from the RDF graph."""
    missing: list[dict[str, str]] = []
    for edge in subgraph.get("edges", []):
        s = URIRef(edge["source"])
        p = MNP[edge["predicate"]]
        o = URIRef(edge["target"])
        if (s, p, o) not in graph:
            missing.append(edge)
    return missing


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
            "producesBlockingReason",
            "dependsOn",
            "aboutCase",
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

            if pred == "producesBlockingReason":
                lines.append(f"{indent}{pred_branch} {pred}")
                reason_preds = [
                    "supportedByEvidence",
                    "triggeredByRule",
                    "triggeredByRuleVersion",
                    "citesClause",
                    "recommendsAction",
                ]
                for t_idx, target in enumerate(targets):
                    lines.append(f"{child_indent}{describe(target)}")
                    r_children = children(target)
                    r_by: dict[str, list[str]] = {}
                    for e in r_children:
                        r_by.setdefault(e["predicate"], []).append(e["target"])
                    r_ordered = [p for p in reason_preds if p in r_by]
                    r_ordered += sorted(p for p in r_by if p not in reason_preds)
                    for rp_idx, rpred in enumerate(r_ordered):
                        r_last = rp_idx == len(r_ordered) - 1
                        marker = "└──" if r_last else "├──"
                        for tgt in sorted(set(r_by[rpred]), key=_local):
                            tgt_label = nodes_by_id.get(tgt, {}).get("label") or _local(tgt)
                            lines.append(
                                f"{child_indent}{marker} {rpred} → {tgt_label}"
                            )
                    if t_idx < len(targets) - 1:
                        lines.append(f"{child_indent}")
                continue

            if pred == "dependsOn":
                lines.append(f"{indent}{pred_branch} {pred}")
                for target in targets:
                    lines.append(f"{child_indent}{describe(target)}")
                    d_children = children(target)
                    d_by: dict[str, list[str]] = {}
                    for e in d_children:
                        d_by.setdefault(e["predicate"], []).append(e["target"])
                    d_order = ["dependsOnEvidence", "dependsOnRuleVersion"]
                    d_ordered = [p for p in d_order if p in d_by]
                    d_ordered += sorted(p for p in d_by if p not in d_order)
                    for dp_idx, dpred in enumerate(d_ordered):
                        d_last = dp_idx == len(d_ordered) - 1
                        marker = "└──" if d_last else "├──"
                        for tgt in sorted(set(d_by[dpred]), key=_local):
                            tgt_label = nodes_by_id.get(tgt, {}).get("label") or _local(tgt)
                            lines.append(
                                f"{child_indent}{marker} {dpred} → {tgt_label}"
                            )
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
            "producesBlockingReason",
            "dependsOn",
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
                if pred == "producesBlockingReason":
                    parts.append("<ul>")
                    for re in children(target):
                        tgt_label = nodes_by_id.get(re["target"], {}).get("label") or _local(
                            re["target"]
                        )
                        parts.append(
                            f"<li><span class='pred'>{esc(re['predicate'])}</span> → "
                            f"<span class='leaf'>{esc(tgt_label)}</span></li>"
                        )
                    parts.append("</ul>")
                if pred == "dependsOn":
                    parts.append("<ul>")
                    for de in children(target):
                        tgt_label = nodes_by_id.get(de["target"], {}).get("label") or _local(
                            de["target"]
                        )
                        parts.append(
                            f"<li><span class='pred'>{esc(de['predicate'])}</span> → "
                            f"<span class='leaf'>{esc(tgt_label)}</span></li>"
                        )
                    parts.append("</ul>")
                parts.append("</li>")
            parts.append("</ul></li>")
        parts.append("</ul></li>")
    parts.append("</ul></div>")
    return "".join(parts)
