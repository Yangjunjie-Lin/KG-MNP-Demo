from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from rdflib import BNode, Dataset

from ..compilation.rdf_canonical import canonical_nquads
from ..modeling.dependencies import ROOT

EXPECTED_GRAPH_KEYS = ("business_abox", "modeling_provenance", "review_audit")


class DatasetAssemblyError(ValueError):
    pass


def assemble_stage06_dataset(compilation_directory: Path, *, root: Path = ROOT) -> dict[str, Any]:
    compilation_directory = Path(compilation_directory).resolve()
    manifest_path = compilation_directory / "compilation-manifest.json"
    dataset_path = compilation_directory / "rdf" / "dataset.nq"
    if not manifest_path.is_file() or not dataset_path.is_file():
        raise DatasetAssemblyError("Stage 06 compilation manifest or dataset.nq is missing")
    import json
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DatasetAssemblyError(f"invalid Stage 06 compilation manifest: {exc}") from exc
    if manifest.get("release_status") != "FORMALLY_VALIDATED" or manifest.get("shacl_status") != "CONFORMS" or manifest.get("owl_consistency_status") != "CONSISTENT":
        raise DatasetAssemblyError("Stage 06 compilation is not FORMALLY_VALIDATED")
    if manifest.get("inferred_fact_count") != 0 or manifest.get("inference_materialized") is not False:
        raise DatasetAssemblyError("Stage 06 inferred facts are not frozen to zero")
    graph_iris = manifest.get("graph_iris")
    if not isinstance(graph_iris, Mapping) or tuple(graph_iris) != EXPECTED_GRAPH_KEYS:
        raise DatasetAssemblyError("Stage 06 graph_iris must contain exactly the three authoritative graphs")
    if len(set(graph_iris.values())) != 3:
        raise DatasetAssemblyError("Stage 06 graph IRIs must be unique")
    dataset = Dataset()
    try:
        dataset.parse(dataset_path.as_posix(), format="nquads")
    except Exception as exc:
        raise DatasetAssemblyError(f"cannot parse Stage 06 dataset.nq: {exc}") from exc
    quads = [(s, p, o, g) for s, p, o, g in dataset.quads((None, None, None, None))]
    if any(quad[3] is None for quad in quads) or any(
        isinstance(term, BNode) for quad in quads for term in quad
    ):
        raise DatasetAssemblyError("Stage 06 dataset contains blank/default graph terms")
    actual_graphs = {str(g) for _, _, _, g in quads}
    expected_graphs = set(str(value) for value in graph_iris.values())
    if actual_graphs != expected_graphs:
        raise DatasetAssemblyError("Stage 06 dataset named graph set does not match manifest")
    data = canonical_nquads(quads)
    return {"manifest": manifest, "quads": quads, "data": data, "quad_count": len(quads), "graph_counts": {iri: sum(1 for _, _, _, g in quads if str(g) == iri) for iri in sorted(expected_graphs)}, "named_graphs": sorted(expected_graphs)}


assemble_dataset = assemble_stage06_dataset
