"""Manifest-driven local Domain Pack baseline closure."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from rdflib import OWL, RDF, Graph

from kg_mnp.domain_packs.registry import DomainPackRegistry

from .rdf.canonical import graph_semantic_digest
from .rdf.skolem import skolemize_graph

_STANDARD_ANNOTATION_NAMESPACES = (
    "http://purl.org/dc/terms/",
    "http://www.w3.org/2004/02/skos/core#",
)


@dataclass(frozen=True)
class BaselineClosure:
    tbox: Graph
    shapes: Graph
    assets: tuple[dict, ...]
    payload_files: dict[str, bytes]
    ontology_iris: tuple[str, ...]
    query_assets: dict[str, bytes]
    statement_sources: dict[tuple, tuple[dict, ...]]


def _format(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".ttl", ".turtle"}:
        return "turtle"
    if suffix in {".nt"}:
        return "nt"
    if suffix in {".rdf", ".owl", ".xml"}:
        return "xml"
    raise ValueError(f"unsupported baseline RDF format: {suffix}")


def load_baseline_closure(
    project_lock: dict,
    *,
    domain_packs_root: Path | str,
) -> BaselineClosure:
    registry = DomainPackRegistry(domain_packs_root)
    tbox_raw = Graph()
    shapes_raw = Graph()
    assets = []
    payload_files = {}
    query_assets = {}
    ontology_iris = set()
    statement_sources: dict[tuple, list[dict]] = {}
    for locked in sorted(project_lock["resolved_domain_packs"], key=lambda item: (item["pack_id"], item["pack_version"])):
        pack = registry.resolve(locked["pack_id"], locked["pack_version"])
        if pack.lock.lock_id != locked["pack_lock_id"] or pack.lock.content_digest != locked["pack_content_digest"]:
            raise ValueError("Domain Pack Lock mismatch")
        manifest_assets = {item["asset_id"]: item for item in pack.manifest.document["assets"]}
        lock_assets = {item["asset_id"]: item for item in pack.lock.document["assets"]}
        lock_bytes = (pack.root / "pack.lock.json").read_bytes()
        payload_files[f"baseline/domain-pack-locks/{pack.manifest.pack_id}-{pack.manifest.pack_version}.lock.json"] = lock_bytes
        for asset_id, asset in sorted(manifest_assets.items()):
            lock_asset = lock_assets[asset_id]
            source = (pack.root / asset["path"]).resolve(strict=True)
            if pack.root.resolve(strict=True) not in source.parents or source.is_symlink():
                raise ValueError("Domain Pack asset escapes its locked root")
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != lock_asset["sha256"] or len(data) != lock_asset["size_bytes"]:
                raise ValueError("Domain Pack asset does not match its lock")
            package_path = f"baseline/assets/{pack.manifest.pack_id}/{asset['path']}"
            payload_files[package_path] = data
            semantic_digest = hashlib.sha256(data).hexdigest()
            if asset["kind"] in {"ontology-root", "ontology-module", "ontology-alignment"}:
                file_graph = Graph()
                file_graph.parse(data=data.decode(), format=_format(asset["path"]))
                stable_file_graph = skolemize_graph(file_graph)
                for triple in stable_file_graph:
                    tbox_raw.add(triple)
                    statement_sources.setdefault(triple, []).append(
                        {
                            "pack_lock_id": pack.lock.lock_id,
                            "asset_path": package_path,
                            "lock_path": f"baseline/domain-pack-locks/{pack.manifest.pack_id}-{pack.manifest.pack_version}.lock.json",
                            "graph_role": "effective-tbox",
                        }
                    )
                for ontology in file_graph.subjects(RDF.type, OWL.Ontology):
                    ontology_iris.add(str(ontology))
                semantic_digest = graph_semantic_digest(skolemize_graph(file_graph))
            elif asset["kind"] == "shacl-shapes":
                file_graph = Graph()
                file_graph.parse(data=data.decode(), format=_format(asset["path"]))
                stable_file_graph = skolemize_graph(file_graph)
                for triple in stable_file_graph:
                    shapes_raw.add(triple)
                    statement_sources.setdefault(triple, []).append(
                        {
                            "pack_lock_id": pack.lock.lock_id,
                            "asset_path": package_path,
                            "lock_path": f"baseline/domain-pack-locks/{pack.manifest.pack_id}-{pack.manifest.pack_version}.lock.json",
                            "graph_role": "effective-shapes",
                        }
                    )
                semantic_digest = graph_semantic_digest(skolemize_graph(file_graph))
            elif asset["kind"] in {"query", "competency-questions"} and source.suffix.lower() == ".rq":
                query_assets[asset_id] = data
                query_assets[asset["path"]] = data
            assets.append({"pack_lock_id": pack.lock.lock_id, "asset_path": package_path, "byte_sha256": hashlib.sha256(data).hexdigest(), "semantic_sha256": semantic_digest, "role": asset["kind"].upper().replace("-", "_")})
    for triple in list(tbox_raw.triples((None, OWL.imports, None))):
        tbox_raw.remove(triple)
    used_standard_annotations = {
        predicate
        for _, predicate, _ in tbox_raw
        if str(predicate).startswith(_STANDARD_ANNOTATION_NAMESPACES)
    }
    for predicate in sorted(used_standard_annotations, key=str):
        declaration = (predicate, RDF.type, OWL.AnnotationProperty)
        if declaration in tbox_raw:
            continue
        predicate_sources = {
            (item["pack_lock_id"], item["asset_path"], item["lock_path"]): item
            for triple, values in statement_sources.items()
            if triple[1] == predicate
            for item in values
        }
        tbox_raw.add(declaration)
        statement_sources[declaration] = [
            {
                **predicate_sources[key],
                "graph_role": "effective-tbox",
                "profile_bridge": "STANDARD_ANNOTATION_DECLARATION",
            }
            for key in sorted(predicate_sources)
        ]
    frozen_sources = {
        triple: tuple(sorted(values, key=lambda item: (item["pack_lock_id"], item["asset_path"])))
        for triple, values in statement_sources.items()
    }
    return BaselineClosure(tbox=skolemize_graph(tbox_raw), shapes=skolemize_graph(shapes_raw), assets=tuple(sorted(assets, key=lambda item: (item["pack_lock_id"], item["asset_path"]))), payload_files=payload_files, ontology_iris=tuple(sorted(ontology_iris)), query_assets=query_assets, statement_sources=frozen_sources)
