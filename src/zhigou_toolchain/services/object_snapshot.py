"""Request-scoped OMS/ODS read session over one freshly verified package.

No cross-request cache, no database bypass, no optional verification. The
business executor consumes this ontology-service boundary inside its fenced
workspace; source evidence is independently reverified before returning.
"""
from __future__ import annotations

import json

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ingestion.evidence import verify_evidence_closure
from zhigou_toolchain.ingestion.limits import DEFAULT_LIMITS
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.integrations.local_rdf import LocalRDFQueryAdapter
from zhigou_toolchain.integrations.object_query import _iri
from zhigou_toolchain.semantic_kernel.artifact_resolver import WorkspaceArtifactResolver
from zhigou_toolchain.semantic_kernel.packaging.archive import (
    read_verified_package_files,
)

from .compilation import package_location
from .errors import ServiceBoundaryError
from .projects import require_access


def read(app, project, principal, package_id, class_iri):
    principal = app._current(principal)
    require_access(principal, project)
    if not principal.can("package:read") or not principal.can("source:read"):
        raise ServiceBoundaryError("FORBIDDEN", "package:read and source:read required", status_code=403)
    _iri(class_iri)
    files, verified = read_verified_package_files(package_location(project, package_id), expected_package_id=package_id)
    if verified["status"] != "VALID":
        raise ServiceBoundaryError("PACKAGE_INVALID", "Verified package snapshot required", status_code=409)
    manifest = json.loads(files["ontology-package.json"])
    tbox = Graph().parse(data=files["ontology/effective-tbox.nt"], format="nt")
    data = Graph().parse(data=files["data/abox.nt"], format="nt")
    vocabulary = sorted({str(s) for kind in (OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property) for s in tbox.subjects(RDF.type, kind) if isinstance(s, URIRef)})
    subjects = sorted(set(data.subjects(RDF.type, URIRef(class_iri))), key=str)
    if len(subjects) > 1000:
        raise ServiceBoundaryError("OBJECT_LIMIT_EXCEEDED", "Object snapshot exceeds 1000 objects", status_code=422)
    provenance = json.loads(files["provenance/statement-provenance-manifest.json"])
    statements = {s: [r for r in provenance["statements"] if r["subject"] == s.n3()] for s in subjects}
    evidence_ids = sorted({identifier for records in statements.values() for row in records for identifier in row["evidence_record_refs"]})
    resolver, store = WorkspaceArtifactResolver(project.root), SourceStore(project.root)
    evidence = {identifier: resolver.resolve(identifier).document for identifier in evidence_ids}
    sources = {}
    for source_id in sorted({e["source_id"] for e in evidence.values()}):
        source = store.verify_source(source_id)
        sources[source_id] = source, store.blob_for(source).read_bytes()
    snapshots = tuple(resolver.resolve(identifier).document for identifier in sorted({e["plugin_snapshot_id"] for e in evidence.values()}))
    transformations = tuple(resolver.resolve(identifier).document for identifier in sorted({ref for e in evidence.values() for ref in e["transformation_ids"]}))
    if evidence:
        verify_evidence_closure(records=tuple(evidence.values()), transformations=transformations, snapshots=snapshots, sources=sources, limits=DEFAULT_LIMITS)
    objects = []
    for subject in subjects:
        properties = [{"predicate": str(predicate), "object": LocalRDFQueryAdapter._term(value)} for predicate, value in data.predicate_objects(subject)]
        properties.sort(key=lambda p: (p["predicate"], json.dumps(p["object"], sort_keys=True)))
        if len(properties) > 1000:
            raise ServiceBoundaryError("OBJECT_LIMIT_EXCEEDED", "Object property limit exceeded", status_code=422)
        refs = sorted({identifier for row in statements[subject] for identifier in row["evidence_record_refs"]})
        objects.append({"iri": str(subject), "properties": properties, "evidence": [evidence[identifier] for identifier in refs],
                        "object_version": semantic_hash(properties)})
    return {"package_id": package_id, "semantic_digest": manifest["semantic_summary"]["semantic_dataset_digest"],
            "vocabulary": vocabulary, "objects": objects, "mode": "DETERMINISTIC", "verification": "FRESH_PACKAGE_AND_SOURCE_CLOSURE"}
