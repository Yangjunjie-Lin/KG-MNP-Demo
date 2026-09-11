"""Generic pinned ROBOT/HermiT consistency execution."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from rdflib import Graph

from ..contracts import finalize_artifact
from ..rdf.canonical import canonical_ntriples, graph_semantic_digest
from ..reasoner import run_hermit
from ..snapshot import HERMIT_VERSION, ROBOT_SHA256, ROBOT_VERSION


def check_owl_consistency(
    *,
    baseline_graph: Graph,
    tbox_graph: Graph,
    abox_graph: Graph,
    reasoner_jar: Path | str | None,
    timeout_seconds: int = 180,
    max_output_bytes: int = 16_777_216,
    ontology_profile: str = "OWL_2_DL_STRICT",
) -> dict[str, Any]:
    combined = Graph()
    for graph in (baseline_graph, tbox_graph, abox_graph):
        for triple in graph:
            combined.add(triple)
    input_digest = graph_semantic_digest(combined)
    execution = run_hermit(canonical_ntriples(combined), reasoner_jar=reasoner_jar, timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)
    status = execution["status"]
    exit_code = execution["exit_code"]
    timeout = execution["timeout"]
    java_major = execution["java_major"]
    diagnostics = execution["diagnostics"]
    core = {"manifest_kind": "KG_MNP_SEMANTIC_OWL_CONSISTENCY_REPORT", "schema_version": "1.0.0", "status": status, "consistent": status == "CONSISTENT", "reasoning_scope": "LOCAL_BASELINE_TBOX_ABOX_CLOSURE", "reasoner": "HermiT", "reasoner_version": HERMIT_VERSION, "robot_version": ROBOT_VERSION, "robot_jar_sha256": ROBOT_SHA256, "java_runtime_major_version": java_major, "ontology_profile": ontology_profile, "input_semantic_digest": input_digest, "baseline_semantic_digest": graph_semantic_digest(baseline_graph), "tbox_semantic_digest": graph_semantic_digest(tbox_graph), "abox_semantic_digest": graph_semantic_digest(abox_graph), "exit_code": exit_code, "timeout": timeout, "sanitized_diagnostics_hash": hashlib.sha256(diagnostics).hexdigest()}
    return finalize_artifact(core, id_field="report_id", urn_kind="semantic-owl-consistency-report", contract="semantic-owl-consistency-report")
