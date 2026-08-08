from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from rdflib import Graph, URIRef

from ..compilation.rdf_canonical import canonical_nquads, assert_no_blank_nodes
from ..modeling.dependencies import ROOT, build_ontology_baseline_manifest, verify_ontology_baseline_manifest
from .identifiers import root_tbox_graph_iri, tbox_graph_iri


class TBoxAssemblyError(ValueError):
    pass


def _safe_module_path(root: Path, relative: str) -> Path:
    path_text = str(relative)
    parsed = PurePosixPath(path_text)
    if (
        not parsed.parts
        or parsed.is_absolute()
        or ".." in parsed.parts
        or "\\" in path_text
        or ":" in parsed.parts[0]
    ):
        raise TBoxAssemblyError(f"unsafe ontology module path: {relative}")
    current = root
    for part in parsed.parts:
        current /= part
        is_junction = bool(getattr(current, "is_junction", lambda: False)())
        if current.is_symlink() or is_junction:
            raise TBoxAssemblyError(
                f"ontology module uses a symlink or junction: {relative}"
            )
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise TBoxAssemblyError(
            f"ontology module is unavailable: {relative}"
        ) from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise TBoxAssemblyError(f"ontology module escapes authority root: {relative}")
    return resolved


def _parse(path: Path) -> Graph:
    graph = Graph()
    try:
        graph.parse(path.as_posix(), format="turtle")
    except Exception as exc:
        raise TBoxAssemblyError(f"cannot parse ontology module {path}: {exc}") from exc
    return graph


def assemble_runtime_tbox(*, root: Path = ROOT, baseline: Mapping[str, Any] | None = None) -> dict[str, Any]:
    requested_root = Path(root)
    root_is_junction = bool(
        getattr(requested_root, "is_junction", lambda: False)()
    )
    if requested_root.is_symlink() or root_is_junction:
        raise TBoxAssemblyError("ontology authority root is a symlink or junction")
    root = requested_root.resolve()
    expected_baseline = build_ontology_baseline_manifest(root)
    if baseline is None:
        baseline = expected_baseline
    if dict(baseline) != expected_baseline:
        raise TBoxAssemblyError("Stage 03 ontology baseline is stale")
    errors = verify_ontology_baseline_manifest(baseline, root=root)
    if errors:
        raise TBoxAssemblyError("Stage 03 ontology baseline verification failed: " + "; ".join(errors))
    modules: list[dict[str, Any]] = []
    root_config = _safe_module_path(root, "ontology/kg-mnp.ttl")
    root_graph = _parse(root_config)
    root_iri = root_tbox_graph_iri(str(baseline["release_source_hash"]))
    modules.append({"code": "root", "path": "ontology/kg-mnp.ttl", "source_hash": baseline["release_source_hash"], "graph_iri": root_iri, "graph": root_graph, "ontology_iri": baseline["root_ontology_iri"], "version_iri": baseline["root_version_iri"]})
    for entry in baseline.get("runtime_modules", []):
        path = _safe_module_path(root, str(entry["file"]))
        graph = _parse(path)
        graph_iri = tbox_graph_iri(str(entry["code"]), str(entry["source_hash"]))
        modules.append({"code": entry["code"], "path": entry["file"], "source_hash": entry["source_hash"], "graph_iri": graph_iri, "graph": graph, "ontology_iri": entry["ontology_iri"], "version_iri": entry["version_iri"]})
    quads = [(s, p, o, URIRef(item["graph_iri"])) for item in modules for s, p, o in item["graph"]]
    assert_no_blank_nodes(quads)
    data = canonical_nquads(quads)
    for item in modules:
        item.pop("graph")
    return {"modules": modules, "quads": quads, "data": data, "triple_count": len(quads), "module_count": len(modules), "named_graphs": [item["graph_iri"] for item in modules]}


assemble_tbox = assemble_runtime_tbox
