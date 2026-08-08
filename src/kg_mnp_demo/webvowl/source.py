from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from rdflib import Graph

from ..compilation.rdf_canonical import assert_no_blank_nodes, canonical_nquads
from ..graphdb.tbox_assembler import assemble_runtime_tbox
from ..modeling.dependencies import (
    ROOT,
    build_ontology_baseline_manifest,
    verify_ontology_baseline_manifest,
)


class VisualizationSourceError(ValueError):
    pass


def _safe_local(root: Path, rel: str) -> Path:
    pp = PurePosixPath(rel)
    if (
        pp.is_absolute()
        or ".." in pp.parts
        or "\\" in rel
        or ":" in rel.split("/", 1)[0]
    ):
        raise VisualizationSourceError(f"unsafe ontology source path: {rel}")
    current = root
    for part in pp.parts:
        current /= part
        is_junction = bool(getattr(current, "is_junction", lambda: False)())
        if current.is_symlink() or is_junction:
            raise VisualizationSourceError(
                f"ontology source uses a symlink or junction: {rel}"
            )
    path = current.resolve()
    if root not in path.parents or not path.is_file():
        raise VisualizationSourceError(f"ontology source escapes authority root: {rel}")
    return path


def _parse(path: Path) -> Graph:
    g = Graph()
    try:
        g.parse(path.as_posix(), format="turtle")
    except Exception as exc:
        raise VisualizationSourceError(
            f"cannot parse ontology file {path}: {exc}"
        ) from exc
    return g


def build_visualization_source(
    *, root: Path = ROOT, baseline: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    requested_root = Path(root)
    root_is_junction = bool(getattr(requested_root, "is_junction", lambda: False)())
    if requested_root.is_symlink() or root_is_junction:
        raise VisualizationSourceError(
            "ontology authority root is a symlink or junction"
        )
    root = requested_root.resolve()
    expected = build_ontology_baseline_manifest(root)
    if baseline is None:
        baseline = expected
    if dict(baseline) != expected:
        raise VisualizationSourceError("Stage 03 baseline is stale")
    errors = verify_ontology_baseline_manifest(baseline, root=root)
    if errors:
        raise VisualizationSourceError(
            "Stage 03 baseline verification failed: " + "; ".join(errors)
        )
    records = [
        {
            "role": "ROOT_ONTOLOGY",
            "path": "ontology/kg-mnp.ttl",
            "sha256": hashlib.sha256(
                _safe_local(root, "ontology/kg-mnp.ttl").read_bytes()
            ).hexdigest(),
        }
    ]
    for item in baseline.get("runtime_modules", []):
        rel = str(item["file"])
        path = _safe_local(root, rel)
        records.append(
            {
                "role": "RUNTIME_DEPENDENCY",
                "module_code": str(item["code"]),
                "path": rel,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    tbox = assemble_runtime_tbox(root=root, baseline=baseline)
    assert_no_blank_nodes(tbox["quads"])
    data = canonical_nquads(tbox["quads"])
    return {
        "root": root,
        "baseline": dict(baseline),
        "files": records,
        "graphs": tbox["quads"],
        "tbox_data": data,
        "tbox_triple_count": len(tbox["quads"]),
        "tbox_semantic_hash": hashlib.sha256(data).hexdigest(),
        "module_count": len(records),
    }
