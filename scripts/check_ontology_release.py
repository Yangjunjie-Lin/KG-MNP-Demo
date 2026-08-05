#!/usr/bin/env python3
"""Ontology release checks: IRIs, uniqueness, annotations, no example.org in runtime."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, URIRef
from rdflib.namespace import XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kg_mnp_demo.loader import load_ontology_graph, ontology_paths  # noqa: E402
from stage03_constants import TERM_NS  # noqa: E402

RUNTIME_GLOBS = [
    "ontology/*.ttl",
    "shapes/*.ttl",
    "examples/eligibility-use-case/shapes/*.ttl",
    "data/*.ttl",
    "queries/*.rq",
    "mappings/*.yaml",
    "src/kg_mnp_demo/*.py",
]


def main() -> int:
    errors: list[str] = []
    g = load_ontology_graph(include_alignments=False)

    # No example.org in formal runtime assets
    for pattern in RUNTIME_GLOBS:
        for path in ROOT.glob(pattern):
            text = path.read_text(encoding="utf-8")
            if "example.org" in text:
                # allow comments in scripts that document migration? src should be clean
                if path.name in {"migrate_ontology_iris.py", "stage03_constants.py"}:
                    continue
                errors.append(f"example.org found in runtime asset: {path.relative_to(ROOT)}")

    # Term uniqueness: each class/property defined in exactly one module file
    defining: dict[str, list[str]] = defaultdict(list)
    for path in ontology_paths(include_alignments=False):
        local = Graph()
        local.parse(path, format="turtle")
        for s in local.subjects(RDF.type, OWL.Class):
            if str(s).startswith(TERM_NS):
                defining[str(s)].append(path.name)
        for s in local.subjects(RDF.type, OWL.ObjectProperty):
            if str(s).startswith(TERM_NS):
                defining[str(s)].append(path.name)
        for s in local.subjects(RDF.type, OWL.DatatypeProperty):
            if str(s).startswith(TERM_NS):
                defining[str(s)].append(path.name)

    for iri, files in sorted(defining.items()):
        if len(files) != 1:
            errors.append(f"Term defined in multiple modules: {iri} -> {files}")

    # Labels/definitions for non-deprecated classes and properties
    for term_type in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        for s in g.subjects(RDF.type, term_type):
            if not str(s).startswith(TERM_NS):
                continue
            if (s, OWL.deprecated, Literal(True)) in g or (
                s,
                OWL.deprecated,
                Literal("true", datatype=XSD.boolean),
            ) in g:
                # still require labels
                pass
            labels = list(g.objects(s, RDFS.label))
            defs = list(g.objects(s, SKOS.definition))
            has_en = any(isinstance(l, Literal) and l.language == "en" for l in labels)
            has_zh = any(isinstance(l, Literal) and l.language in {"zh-CN", "zh"} for l in labels)
            def_en = any(isinstance(l, Literal) and l.language == "en" for l in defs)
            def_zh = any(isinstance(l, Literal) and l.language in {"zh-CN", "zh"} for l in defs)
            if not (has_en and has_zh and def_en and def_zh):
                errors.append(f"Missing bilingual label/definition: {s}")

    # Inventory exists and is sorted
    inv = ROOT / "docs" / "ontology" / "term-inventory.csv"
    if not inv.is_file():
        errors.append("missing term-inventory.csv")
    else:
        rows = list(csv.DictReader(inv.open(encoding="utf-8")))
        keys = [(r["term_type"], r["defining_module"], r["local_name"]) for r in rows]
        if keys != sorted(keys):
            errors.append("term-inventory.csv is not stably sorted")

    # OWL-RL smoke
    try:
        import owlrl

        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"OWL-RL failed: {exc}")

    if errors:
        print("ONTOLOGY RELEASE CHECK FAILED")
        for e in errors:
            print(" -", e)
        return 1
    print("Ontology release check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
