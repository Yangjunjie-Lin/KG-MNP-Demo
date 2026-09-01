"""Deterministic final pySHACL gate."""

from __future__ import annotations

import importlib.metadata
import multiprocessing
from typing import Any

from pyshacl import validate
from rdflib import RDF, SH, BNode, Graph, URIRef

from ..contracts import finalize_artifact
from ..identifiers import semantic_id
from ..rdf.canonical import graph_semantic_digest
from ..shacl import assert_safe_shacl_graph


def _shacl_worker(
    data_bytes: bytes,
    shapes_bytes: bytes,
    ontology_bytes: bytes,
    output: multiprocessing.Queue,
) -> None:
    try:
        data_graph = Graph().parse(data=data_bytes.decode(), format="nt")
        shapes_graph = Graph().parse(data=shapes_bytes.decode(), format="nt")
        ontology_graph = Graph().parse(data=ontology_bytes.decode(), format="nt")
        conforms, raw, _ = validate(
            data_graph=data_graph,
            shacl_graph=shapes_graph,
            ont_graph=ontology_graph,
            inference="rdfs",
            advanced=False,
            js=False,
            allow_infos=True,
            allow_warnings=True,
            do_owl_imports=False,
            meta_shacl=True,
            serialize_report_graph=False,
        )
        if not isinstance(raw, Graph):
            output.put(("ENGINE_ERROR", False, []))
            return
        rows = []
        for result in raw.subjects(RDF.type, SH.ValidationResult):
            severity_value = next(iter(raw.objects(result, SH.resultSeverity)), SH.Violation)
            severity = {SH.Violation: "VIOLATION", SH.Warning: "WARNING", SH.Info: "INFO"}.get(severity_value, "VIOLATION")
            focus = next(iter(raw.objects(result, SH.focusNode)), None)
            shape = next(iter(raw.objects(result, SH.sourceShape)), None)
            message = str(next(iter(raw.objects(result, SH.resultMessage)), ""))[:4096]
            rows.append(
                {
                    "severity": severity,
                    "severity_iri": str(severity_value),
                    "focus_node": None if focus is None or isinstance(focus, BNode) else str(focus),
                    "source_shape": None if shape is None or isinstance(shape, BNode) else str(shape),
                    "message": message,
                }
            )
        output.put(("OK", bool(conforms), rows))
    except Exception as exc:  # noqa: BLE001 - isolated validator reports engine failure
        output.put(("ENGINE_ERROR", False, [type(exc).__name__]))


def validate_shacl(
    *,
    data_graph: Graph,
    shapes_graph: Graph,
    ontology_graph: Graph,
    max_results: int = 100_000,
    max_seconds: int = 120,
) -> tuple[dict[str, Any], Graph]:
    assert_safe_shacl_graph(shapes_graph)
    from ..rdf.canonical import canonical_ntriples

    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(
        target=_shacl_worker,
        args=(
            canonical_ntriples(data_graph),
            canonical_ntriples(shapes_graph),
            canonical_ntriples(ontology_graph),
            output,
        ),
    )
    process.start()
    process.join(max_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        execution, conforms, raw_rows = "TIMEOUT", False, []
    elif output.empty():
        execution, conforms, raw_rows = "ENGINE_ERROR", False, []
    else:
        execution, conforms, raw_rows = output.get()
    results = []
    stable_graph = Graph()
    for row in raw_rows if execution == "OK" else []:
        severity_value = URIRef(row.pop("severity_iri"))
        content = dict(row)
        identifier = semantic_id("semantic-shacl-result", content)
        results.append({"result_id": identifier, **content})
        ref = URIRef(identifier)
        stable_graph.add((ref, RDF.type, SH.ValidationResult))
        stable_graph.add((ref, SH.resultSeverity, severity_value))
        if content["focus_node"] is not None:
            stable_graph.add((ref, SH.focusNode, URIRef(content["focus_node"])))
        if content["source_shape"] is not None:
            stable_graph.add((ref, SH.sourceShape, URIRef(content["source_shape"])))
    results.sort(key=lambda item: item["result_id"])
    if len(results) > max_results:
        raise ValueError("SHACL result limit exceeded")
    counts = {name: sum(item["severity"] == name for item in results) for name in ("VIOLATION", "WARNING", "INFO")}
    passes = execution == "OK" and bool(conforms) and counts["VIOLATION"] == 0
    status = "CONFORMS" if passes else ("VIOLATION" if execution == "OK" else execution)
    core = {"manifest_kind": "KG_MNP_SEMANTIC_SHACL_VALIDATION_REPORT", "schema_version": "1.0.0", "conforms": passes, "status": status, "results": results, "violation_count": counts["VIOLATION"], "warning_count": counts["WARNING"], "info_count": counts["INFO"], "shape_graph_digest": graph_semantic_digest(shapes_graph), "data_graph_digest": graph_semantic_digest(data_graph), "ontology_graph_digest": graph_semantic_digest(ontology_graph), "pyshacl_version": importlib.metadata.version("pyshacl"), "inference_profile": "RDFS", "meta_shacl_status": "PASSED" if execution == "OK" else "NOT_RUN_UNSUPPORTED", "execution_limits": [{"name": "max_shacl_results", "value": max_results}, {"name": "max_shacl_seconds", "value": max_seconds}]}
    report = finalize_artifact(core, id_field="report_id", urn_kind="semantic-shacl-validation-report", contract="semantic-shacl-validation-report")
    return report, stable_graph
