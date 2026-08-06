"""Frozen-profile SHACL execution with deterministic result rebuilding."""

from __future__ import annotations

import hashlib
import importlib.metadata
from typing import Any, Mapping, Sequence

from pyshacl import validate
from rdflib import RDF, SH, BNode, Graph, Literal, URIRef
from rdflib.compare import to_canonical_graph

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT
from .identifiers import shacl_result_id
from .policy import profile_files


class SHACLValidationError(ValueError):
    pass


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _shape_semantic_hash(graph: Graph) -> str:
    canonical = to_canonical_graph(graph)
    data = canonical.serialize(format="nt")
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    lines = sorted(line.strip() for line in text.splitlines() if line.strip())
    return hashlib.sha256((("\n".join(lines) + "\n") if lines else "").encode("utf-8")).hexdigest()


def load_shapes(profile_ids: Sequence[str] = ("foundation-instance",)) -> tuple[Graph, dict[str, Any], dict[str, bytes]]:
    shapes = Graph()
    records: list[dict[str, Any]] = []
    frozen_files: dict[str, bytes] = {}
    for profile_id in sorted(set(profile_ids)):
        for path in profile_files(profile_id):
            relative = path.relative_to(ROOT).as_posix()
            data = _lf(path.read_bytes())
            frozen_files[relative] = data
            file_graph = Graph()
            file_graph.parse(data=data.decode("utf-8"), format="turtle")
            for triple in file_graph:
                shapes.add(triple)
            records.append({
                "profile_id": profile_id,
                "source_path": relative,
                "byte_sha256": hashlib.sha256(data).hexdigest(),
                "shacl_graph_semantic_hash": _shape_semantic_hash(file_graph),
            })
    manifest = {
        "contract_version": "1.0",
        "profiles": records,
        "pyshacl_version": importlib.metadata.version("pyshacl"),
        "inference": "RDFS",
        "advanced": False,
        "js": False,
        "network": False,
    }
    manifest["profile_bundle_hash"] = semantic_hash(manifest)
    return shapes, manifest, frozen_files


def _stable_blank_node(graph: Graph, value: BNode, active: set[BNode] | None = None) -> str:
    """Project a SHACL blank-node shape/path by structure, never its raw label."""
    import hashlib
    active = set() if active is None else set(active)
    if value in active:
        return "_:cycle"
    active.add(value)
    lines = []
    for subject, predicate, obj in sorted(graph.triples((value, None, None)), key=lambda item: (item[1].n3(), item[2].n3())):
        if isinstance(obj, BNode):
            encoded = _stable_blank_node(graph, obj, active)
        else:
            encoded = obj.n3()
        lines.append(f"{predicate.n3()}={encoded}")
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return "urn:kg-mnp:shacl-node:" + digest


def _node(graph: Graph, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, BNode):
        return _stable_blank_node(graph, value)
    return str(value)


def _first(graph: Graph, subject: Any, predicate: Any) -> Any:
    values = sorted(graph.objects(subject, predicate), key=lambda item: item.n3())
    return values[0] if values else None


def _result_content(graph: Graph, result: Any) -> dict[str, Any]:
    messages = sorted(str(value) for value in graph.objects(result, SH.resultMessage))
    return {
        "focus_node": _node(graph, _first(graph, result, SH.focusNode)),
        "result_path": _node(graph, _first(graph, result, SH.resultPath)),
        "value": _node(graph, _first(graph, result, SH.value)),
        "source_shape": _node(graph, _first(graph, result, SH.sourceShape)),
        "source_constraint_component": _node(graph, _first(graph, result, SH.sourceConstraintComponent)),
        "severity": _node(graph, _first(graph, result, SH.resultSeverity)),
        "message": messages[0] if messages else "",
    }


def _deterministic_report_graph(report: Mapping[str, Any]) -> Graph:
    graph = Graph()
    report_iri = URIRef(str(report["report_id"]))
    graph.add((report_iri, RDF.type, SH.ValidationReport))
    graph.add((report_iri, SH.conforms, Literal(bool(report["conforms"]))))
    for result in report["results"]:
        result_iri = URIRef(str(result["result_id"]))
        graph.add((report_iri, SH.result, result_iri))
        graph.add((result_iri, RDF.type, SH.ValidationResult))
        fields = (
            ("focus_node", SH.focusNode), ("result_path", SH.resultPath),
            ("value", SH.value), ("source_shape", SH.sourceShape),
            ("source_constraint_component", SH.sourceConstraintComponent),
            ("severity", SH.resultSeverity),
        )
        for field, predicate in fields:
            value = result.get(field)
            if value is not None:
                graph.add((result_iri, predicate, URIRef(str(value))))
        if result.get("message"):
            graph.add((result_iri, SH.resultMessage, Literal(str(result["message"]))))
    return graph


def validate_abox(
    data_graph: Graph,
    ontology_graph: Graph,
    *,
    profile_ids: Sequence[str] = ("foundation-instance",),
) -> tuple[dict[str, Any], Graph, dict[str, Any], dict[str, bytes]]:
    shapes, profile_manifest, frozen_files = load_shapes(profile_ids)
    try:
        conforms, raw_results, _ = validate(
            data_graph=data_graph,
            shacl_graph=shapes,
            ont_graph=ontology_graph,
            inference="rdfs",
            advanced=False,
            js=False,
            allow_infos=True,
            allow_warnings=True,
            do_owl_imports=False,
            meta_shacl=False,
            serialize_report_graph=False,
        )
    except Exception as exc:
        raise SHACLValidationError(f"SHACL execution failed: {exc}") from exc
    if not isinstance(raw_results, Graph):
        raise SHACLValidationError("pySHACL did not return a result graph")
    results = []
    for raw_result in raw_results.subjects(RDF.type, SH.ValidationResult):
        content = _result_content(raw_results, raw_result)
        content["result_id"] = shacl_result_id(content)
        results.append(content)
    results.sort(key=lambda item: item["result_id"])
    severities = [item.get("severity") for item in results]
    violation_count = sum(value == str(SH.Violation) for value in severities)
    warning_count = sum(value == str(SH.Warning) for value in severities)
    info_count = sum(value == str(SH.Info) for value in severities)
    report_content = {
        "conforms": bool(conforms) and violation_count == 0,
        "status": "CONFORMS" if bool(conforms) and violation_count == 0 else "VIOLATION",
        "results": results,
        "violation_count": violation_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "profile_bundle_hash": profile_manifest["profile_bundle_hash"],
    }
    report_content["report_id"] = "urn:kg-mnp:shacl-report:" + semantic_hash(report_content)
    report_graph = _deterministic_report_graph(report_content)
    return report_content, report_graph, profile_manifest, frozen_files
