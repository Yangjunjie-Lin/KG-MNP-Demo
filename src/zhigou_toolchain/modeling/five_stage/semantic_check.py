"""Temporary proposal checks using the production compiler's graph functions."""
from __future__ import annotations

from rdflib import RDF, SH, Graph

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.semantic_kernel.abox import compile_abox
from zhigou_toolchain.semantic_kernel.rdf.canonical import graph_semantic_digest
from zhigou_toolchain.semantic_kernel.shacl import compile_shacl
from zhigou_toolchain.semantic_kernel.tbox import compile_tbox
from zhigou_toolchain.semantic_kernel.validators.owl_consistency import (
    check_owl_consistency,
)
from zhigou_toolchain.semantic_kernel.validators.owl_profile import validate_owl_profile
from zhigou_toolchain.semantic_kernel.validators.shacl import validate_shacl


def target_coverage(data: Graph, shapes: Graph) -> dict:
    rows = []
    for shape, target in shapes.subject_objects(SH.targetClass):
        hits = sorted(str(s) for s in data.subjects(RDF.type, target))
        rows.append({"shape": str(shape), "target_class": str(target), "explicit_focus_nodes": hits,
                     "count": len(hits), "status": "PASS" if hits else "FAIL"})
    return {"schema_version": "1.0.0", "status": "PASS" if rows and all(r["count"] for r in rows) else "FAIL",
            "target_count": sum(r["count"] for r in rows), "targets": rows,
            "scope": "Explicit targetClass/type coverage; not inferred focus count. Empty/unsupported target selection cannot pass."}


def integrity(candidates: list[dict], evidence_ids: set[str]) -> dict:
    import networkx as nx

    ids = {c["candidate_id"] for c in candidates}
    missing, graph = [], nx.DiGraph()
    graph.add_nodes_from(ids)
    for candidate in candidates:
        for dep in candidate["dependency_candidate_refs"]:
            if dep not in ids:
                missing.append({"candidate_id": candidate["candidate_id"], "missing_dependency": dep})
            else:
                graph.add_edge(dep, candidate["candidate_id"])
        for ev in candidate["evidence_refs"]:
            if ev not in evidence_ids:
                missing.append({"candidate_id": candidate["candidate_id"], "missing_evidence": ev})
    acyclic = nx.is_directed_acyclic_graph(graph)
    return {"status": "PASS" if not missing and acyclic and len(ids) == len(candidates) and ids else "FAIL",
            "missing": missing, "task_dependencies_acyclic": acyclic,
            "build_order": list(nx.lexicographical_topological_sort(graph)) if acyclic else [],
            "candidate_hashes": {c["candidate_id"]: semantic_hash(c) for c in candidates},
            "meaning": "Only explicit construction dependencies are edges; business relation cycles are not task cycles."}


def check_graphs(candidates: list[dict], *, baseline, namespace: str, reasoner_jar) -> dict:
    identifier = stable_urn("semantic-compilation-plan", {"candidates": candidates, "baseline": graph_semantic_digest(baseline.tbox)})
    identity = {"default_namespace": namespace, "ontology_iri": namespace + "validation", "version_iri": namespace + "validation-v1",
                "ontology_version": "0.0.0", "baseline_ontology_iris": list(baseline.ontology_iris)}
    tbox = compile_tbox([c for c in candidates if c["candidate_kind"] == "TBOX"], baseline_graph=baseline.tbox,
                        ontology_identity=identity, compiler_snapshot_id=identifier, package_id=identifier, plan_id=identifier)
    abox = compile_abox([c for c in candidates if c["candidate_kind"] == "ABOX"], effective_tbox=tbox.effective, plan_id=identifier)
    shapes = compile_shacl([c for c in candidates if c["candidate_kind"] == "SHACL"], baseline_shapes=baseline.shapes, plan_id=identifier)
    coverage = target_coverage(abox.graph, shapes.effective)
    shacl, _ = validate_shacl(data_graph=abox.graph, shapes_graph=shapes.effective, ontology_graph=tbox.effective)
    # No provenance/review/SHACL graph or generated ontology header in OWL input.
    owl = check_owl_consistency(baseline_graph=Graph(), tbox_graph=tbox.effective, abox_graph=abox.graph, reasoner_jar=reasoner_jar)
    profile = validate_owl_profile(tbox.effective + abox.graph, baseline_digest=graph_semantic_digest(baseline.tbox),
                                  delta_digest=graph_semantic_digest(tbox.delta), reasoner_jar=reasoner_jar)
    return {"schema_version": "1.0.0", "status": "PASS" if coverage["status"] == "PASS" and shacl["conforms"]
            and owl["status"] == "CONSISTENT" and profile["status"] == "PASSED" else "FAIL",
            "checks": {"explicit_target_coverage": coverage, "shacl": shacl, "owl_profile": profile, "hermit": owl},
            "graphs": {"ontology": tbox.effective.serialize(format="turtle"), "instances": abox.graph.serialize(format="turtle"),
                       "shapes": shapes.effective.serialize(format="turtle")},
            "approval": "NOT_GRANTED", "formal_delivery": "NOT_CREATED",
            "graph_compilers": ["semantic_kernel.tbox.compile_tbox", "semantic_kernel.abox.compile_abox", "semantic_kernel.shacl.compile_shacl"]}
