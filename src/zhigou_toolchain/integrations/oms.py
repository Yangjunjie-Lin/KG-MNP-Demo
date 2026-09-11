from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

from zhigou_toolchain.semantic_kernel.packaging.archive import (
    read_verified_package_files,
)


class OMSMetadataService:
    def __init__(self, package_root: Path | str):
        self.root = Path(package_root)
        files, verification = read_verified_package_files(self.root)
        if verification.get("status") != "VALID":
            raise ValueError("verified package required")
        self.manifest = json.loads(files["ontology-package.json"])
        self.graph = Graph()
        if "ontology/effective-tbox.nt" in files:
            self.graph.parse(data=files["ontology/effective-tbox.nt"].decode("utf-8"), format="nt")

    def metadata(self, *, limit: int = 100, offset: int = 0) -> dict:
        classes = sorted({str(item) for class_iri in (RDFS.Class, OWL.Class) for item in self.graph.subjects(RDF.type, class_iri) if isinstance(item, URIRef)})
        properties = sorted({str(item) for property_iri in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty) for item in self.graph.subjects(RDF.type, property_iri) if isinstance(item, URIRef)})
        rows = []
        for iri in classes:
            term = URIRef(iri)
            rows.append({"iri": iri, "kind": "CLASS", "labels": [{"value": str(label), "language": label.language if isinstance(label, Literal) else None} for label in self.graph.objects(term, RDFS.label)], "definitions": [{"value": str(definition), "language": definition.language if isinstance(definition, Literal) else None} for definition in self.graph.objects(term, RDFS.comment)], "domain": [], "range": []})
        for iri in properties:
            term = URIRef(iri)
            rows.append({"iri": iri, "kind": "PROPERTY", "labels": [{"value": str(label), "language": label.language if isinstance(label, Literal) else None} for label in self.graph.objects(term, RDFS.label)], "definitions": [{"value": str(definition), "language": definition.language if isinstance(definition, Literal) else None} for definition in self.graph.objects(term, RDFS.comment)], "domain": sorted(str(item) for item in self.graph.objects(term, RDFS.domain)), "range": sorted(str(item) for item in self.graph.objects(term, RDFS.range))})
        return {"project_id": self.manifest.get("project_id"), "package_id": self.manifest.get("package_id"), "release_id": None, "semantic_digest": self.manifest.get("semantic_summary", {}).get("semantic_dataset_digest"), "view": "RELEASED_PACKAGE", "current_environment_selection": False, "rows": rows[offset:offset + limit], "page": {"offset": offset, "limit": limit, "total": len(rows)}}
