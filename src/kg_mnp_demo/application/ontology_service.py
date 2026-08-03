"""Ontology catalog service for module/class/property browsing and graph export."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import XSD

from kg_mnp_demo.application.serializers import json_safe
from kg_mnp_demo.loader import (
    load_ontology_graph,
    ontology_modules_config_path,
    ontology_paths,
)
from kg_mnp_demo.namespaces import MNP


def _local(iri: Any) -> str:
    text = str(iri)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rsplit("/", 1)[-1]


@lru_cache(maxsize=1)
def _modules_config() -> dict[str, Any]:
    path = ontology_modules_config_path()
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _label(graph: Graph, node: URIRef, lang: str | None = None) -> str | None:
    labels = list(graph.objects(node, RDFS.label))
    if lang:
        for lab in labels:
            if isinstance(lab, Literal) and lab.language == lang:
                return str(lab)
    for lab in labels:
        if isinstance(lab, Literal) and lab.language == "en":
            return str(lab)
    for lab in labels:
        if isinstance(lab, Literal) and lab.language == "zh":
            return str(lab)
    if labels:
        return str(labels[0])
    return None


def _display_name(graph: Graph, node: URIRef) -> str:
    return (
        _label(graph, node, "zh")
        or _label(graph, node, "en")
        or _local(node)
    )


def _module_for(graph: Graph, node: URIRef, core_map: dict[str, str]) -> str | None:
    codes = list(graph.objects(node, MNP.moduleCode))
    if codes:
        return str(codes[0])
    return core_map.get(_local(node))


def _is_mnp_term(node: URIRef) -> bool:
    return str(node).startswith(str(MNP))


class OntologyService:
    """Read-only ontology catalog built from local TTL modules + YAML catalog."""

    def __init__(self, *, include_alignments: bool = False) -> None:
        self.include_alignments = include_alignments
        self._graph = load_ontology_graph(include_alignments=include_alignments)
        self._config = _modules_config()
        self._core_map = dict(self._config.get("core_term_modules") or {})

    def get_summary(self) -> dict[str, Any]:
        modules = self.list_modules()
        return {
            "module_count": len([m for m in modules if m.get("runtime")]),
            "module_count_all": len(modules),
            "class_count": len(self.list_classes()),
            "object_property_count": len(self.list_object_properties()),
            "data_property_count": len(self.list_data_properties()),
            "runtime_files": [p.name for p in ontology_paths()],
        }

    def list_modules(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for mod in self._config.get("modules") or []:
            code = mod["code"]
            classes = [c for c in self.list_classes() if c.get("module") == code]
            ops = [p for p in self.list_object_properties() if p.get("module") == code]
            dps = [p for p in self.list_data_properties() if p.get("module") == code]
            result.append(
                {
                    "module": code,
                    "label_zh": mod.get("label_zh"),
                    "label_en": mod.get("label_en"),
                    "description": mod.get("description"),
                    "file": mod.get("file"),
                    "runtime": bool(mod.get("runtime", True)),
                    "classes": [c["local_name"] for c in classes],
                    "object_properties": [p["local_name"] for p in ops],
                    "data_properties": [p["local_name"] for p in dps],
                }
            )
        return result

    def list_classes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cls in sorted(self._graph.subjects(RDF.type, OWL.Class), key=str):
            if not isinstance(cls, URIRef) or not _is_mnp_term(cls):
                continue
            rows.append(
                {
                    "iri": str(cls),
                    "id": str(cls),
                    "local_name": _local(cls),
                    "label": _display_name(self._graph, cls),
                    "label_en": _label(self._graph, cls, "en"),
                    "label_zh": _label(self._graph, cls, "zh"),
                    "type": "Class",
                    "module": _module_for(self._graph, cls, self._core_map),
                }
            )
        return sorted(rows, key=lambda r: r["local_name"])

    def list_object_properties(self) -> list[dict[str, Any]]:
        return self._list_properties(OWL.ObjectProperty, "ObjectProperty")

    def list_data_properties(self) -> list[dict[str, Any]]:
        return self._list_properties(OWL.DatatypeProperty, "DatatypeProperty")

    def _list_properties(self, rdf_type: URIRef, type_name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for prop in sorted(self._graph.subjects(RDF.type, rdf_type), key=str):
            if not isinstance(prop, URIRef) or not _is_mnp_term(prop):
                continue
            domains = sorted(
                _local(d) for d in self._graph.objects(prop, RDFS.domain) if isinstance(d, URIRef)
            )
            ranges = sorted(
                _local(r) for r in self._graph.objects(prop, RDFS.range) if isinstance(r, URIRef)
            )
            rows.append(
                {
                    "iri": str(prop),
                    "id": str(prop),
                    "local_name": _local(prop),
                    "label": _display_name(self._graph, prop),
                    "label_en": _label(self._graph, prop, "en"),
                    "label_zh": _label(self._graph, prop, "zh"),
                    "type": type_name,
                    "module": _module_for(self._graph, prop, self._core_map),
                    "domain": domains,
                    "range": ranges,
                }
            )
        return sorted(rows, key=lambda r: r["local_name"])

    def get_class_detail(self, iri_or_local_name: str) -> dict[str, Any] | None:
        node = self._resolve(iri_or_local_name)
        if node is None or (node, RDF.type, OWL.Class) not in self._graph:
            return None
        parents = sorted(
            _local(p)
            for p in self._graph.objects(node, RDFS.subClassOf)
            if isinstance(p, URIRef) and _is_mnp_term(p)
        )
        base = next(
            (c for c in self.list_classes() if c["iri"] == str(node)),
            None,
        )
        if not base:
            return None
        return {
            **base,
            "comment": str(next(self._graph.objects(node, RDFS.comment), "") or ""),
            "subClassOf": parents,
        }

    def get_property_detail(self, iri_or_local_name: str) -> dict[str, Any] | None:
        node = self._resolve(iri_or_local_name)
        if node is None:
            return None
        for collector in (self.list_object_properties, self.list_data_properties):
            for row in collector():
                if row["iri"] == str(node) or row["local_name"] == iri_or_local_name:
                    return {
                        **row,
                        "comment": str(
                            next(self._graph.objects(node, RDFS.comment), "") or ""
                        ),
                    }
        return None

    def build_ontology_graph(self, module: str | None = None) -> dict[str, Any]:
        classes = self.list_classes()
        props = self.list_object_properties()
        if module:
            module = module.upper()
            classes = [c for c in classes if c.get("module") == module]
            props = [p for p in props if p.get("module") == module]

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        class_ids = {c["iri"] for c in classes}

        for c in classes:
            nodes.append(
                {
                    "id": c["iri"],
                    "label": c["label"],
                    "local_name": c["local_name"],
                    "type": "Class",
                    "module": c.get("module"),
                }
            )

        for c in classes:
            node = URIRef(c["iri"])
            for parent in self._graph.objects(node, RDFS.subClassOf):
                if not isinstance(parent, URIRef) or not _is_mnp_term(parent):
                    continue
                if str(parent) not in class_ids and module:
                    continue
                if (node, RDFS.subClassOf, parent) not in self._graph:
                    continue
                edges.append(
                    {
                        "source": str(node),
                        "predicate": "subClassOf",
                        "target": str(parent),
                    }
                )

        for p in props:
            prop = URIRef(p["iri"])
            for d in self._graph.objects(prop, RDFS.domain):
                for r in self._graph.objects(prop, RDFS.range):
                    if not isinstance(d, URIRef) or not isinstance(r, URIRef):
                        continue
                    if module and (str(d) not in class_ids or str(r) not in class_ids):
                        continue
                    if (prop, RDFS.domain, d) not in self._graph:
                        continue
                    if (prop, RDFS.range, r) not in self._graph:
                        continue
                    edges.append(
                        {
                            "source": str(d),
                            "predicate": p["local_name"],
                            "target": str(r),
                            "property_iri": str(prop),
                        }
                    )

        edges = sorted(
            edges,
            key=lambda e: (e["source"], e["predicate"], e["target"]),
        )
        nodes = sorted(nodes, key=lambda n: n["local_name"])
        return json_safe({"nodes": nodes, "edges": edges})

    def _resolve(self, iri_or_local_name: str) -> URIRef | None:
        text = iri_or_local_name.strip()
        if text.startswith("http://") or text.startswith("https://"):
            return URIRef(text)
        candidate = MNP[text]
        if any(self._graph.triples((candidate, None, None))):
            return candidate
        return None


def edge_exists_in_ontology(graph_payload: dict[str, Any], rdf: Graph | None = None) -> list[str]:
    """Return missing edges (source,predicate,target) not present in ontology RDF."""
    g = rdf or load_ontology_graph()
    missing: list[str] = []
    for edge in graph_payload.get("edges") or []:
        src = URIRef(edge["source"])
        tgt = URIRef(edge["target"])
        pred = edge["predicate"]
        if pred == "subClassOf":
            if (src, RDFS.subClassOf, tgt) not in g:
                missing.append(f"{edge['source']}|subClassOf|{edge['target']}")
            continue
        prop_iri = edge.get("property_iri") or str(MNP[pred])
        prop = URIRef(prop_iri)
        if (prop, RDFS.domain, src) not in g or (prop, RDFS.range, tgt) not in g:
            missing.append(f"{edge['source']}|{pred}|{edge['target']}")
    return missing
