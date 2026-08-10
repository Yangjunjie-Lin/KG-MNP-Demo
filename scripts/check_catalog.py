#!/usr/bin/env python3
"""Validate ontology catalog, imports, and module metadata (offline)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

ROOT = Path(__file__).resolve().parents[1]
NS = {"c": "urn:oasis:names:tc:entity:xmlns:xml:catalog"}


def load_catalog() -> dict[str, str]:
    path = ROOT / "ontology" / "catalog-v001.xml"
    tree = ET.parse(path)
    mapping = {}
    for uri in tree.getroot().findall("c:uri", NS):
        mapping[uri.attrib["name"]] = uri.attrib["uri"]
    return mapping


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "ontology_modules.yaml").read_text(encoding="utf-8"))
    catalog = load_catalog()
    errors: list[str] = []

    modules = cfg["modules"] + [
        {
            "file": cfg["root"]["file"],
            "ontology_iri": cfg["root"]["ontology_iri"],
            "version_iri": cfg["root"]["version_iri"],
            "code": "ROOT",
        }
    ]

    for entry in modules:
        file_name = entry["file"]
        path = ROOT / "ontology" / file_name
        if not path.is_file():
            errors.append(f"Missing module file: {file_name}")
            continue
        g = Graph()
        g.parse(path, format="turtle")
        ont_iri = URIRef(entry["ontology_iri"])
        ver_iri = URIRef(entry["version_iri"])
        if (ont_iri, RDF.type, OWL.Ontology) not in g:
            errors.append(f"{file_name}: missing owl:Ontology {ont_iri}")
        if (ont_iri, OWL.versionIRI, ver_iri) not in g:
            errors.append(f"{file_name}: versionIRI mismatch")
        if catalog.get(str(ont_iri)) != file_name:
            errors.append(f"catalog missing ontology IRI mapping for {ont_iri}")
        if catalog.get(str(ver_iri)) != file_name:
            errors.append(f"catalog missing version IRI mapping for {ver_iri}")
        for o in g.objects(ont_iri, OWL.imports):
            if str(o) not in catalog:
                errors.append(f"{file_name}: import {o} not in catalog")
            else:
                local = ROOT / "ontology" / catalog[str(o)]
                if not local.is_file():
                    errors.append(f"{file_name}: import resolves to missing file {local}")

    # cycle check on imports declared in config runtime modules
    graph: dict[str, list[str]] = {}
    for entry in cfg["modules"]:
        if not entry.get("runtime"):
            continue
        stem = entry["file"].replace(".ttl", "")
        graph[stem] = list(entry.get("imports") or [])

    def dfs(node: str, stack: list[str]) -> None:
        if node in stack:
            errors.append(f"Cycle in imports: {' -> '.join(stack + [node])}")
            return
        for nxt in graph.get(node, []):
            dfs(nxt, stack + [node])

    for n in graph:
        dfs(n, [])

    # every catalog entry points to existing file
    for name, filename in catalog.items():
        if not (ROOT / "ontology" / filename).is_file():
            errors.append(f"catalog URI {name} -> missing {filename}")

    if errors:
        print("CATALOG CHECK FAILED")
        for e in errors:
            print(" -", e)
        return 1
    print("Catalog and imports check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
