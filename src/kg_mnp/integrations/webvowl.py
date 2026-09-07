from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from kg_mnp.semantic_kernel.packaging.verifier import verify_package


class WebVOWLConverter:
    converter_version = "local-webvowl-json-1.0"

    def convert(self, package_root: Path | str, output: Path | str | None = None) -> dict:
        root = Path(package_root)
        if verify_package(root).get("status") != "VALID":
            return {"status": "UNAVAILABLE", "reason": "verified package required", "converter_version": self.converter_version}
        graph = Graph()
        graph.parse(root / "ontology" / "effective-tbox.nt", format="nt")
        node_ids = sorted({str(subject) for class_iri in (RDFS.Class, OWL.Class) for subject in graph.subjects(RDF.type, class_iri) if isinstance(subject, URIRef)})
        predicate_ids = sorted({str(predicate) for _subject, predicate, _obj in graph if isinstance(predicate, URIRef)})
        nodes = [{"id": identifier, "type": "class"} for identifier in node_ids]
        properties = [{"id": identifier, "type": "property"} for identifier in predicate_ids]
        supported = {RDF.type, RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range, RDFS.label, RDFS.comment, OWL.equivalentClass, OWL.equivalentProperty}
        unsupported = sorted({str(predicate) for _subject, predicate, _obj in graph if isinstance(predicate, URIRef) and predicate not in supported})
        document = {"status": "CONVERTED", "converter_version": self.converter_version, "package_id": json.loads((root / "ontology-package.json").read_bytes()).get("package_id"), "nodes": nodes, "properties": properties, "unsupported_constructs": unsupported}
        if output:
            Path(output).write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            document["output_path"] = str(output)
        return document
