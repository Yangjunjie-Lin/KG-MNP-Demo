"""Task representations -> existing semantic compilers, never production approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rdflib import OWL, RDF, Graph
from rdflib.compare import isomorphic

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.semantic_kernel.abox import compile_abox
from zhigou_toolchain.semantic_kernel.rdf.serializers import research_ntriples
from zhigou_toolchain.semantic_kernel.tbox import compile_tbox

from .adapters import iri, native_exact_key, triples_graph, typed_graphs


def parse_draft(text):
    graph = Graph().parse(data=text, format="turtle", publicID="urn:ontology-io:draft:")
    if len(graph) > 10000:
        raise ValueError("RESEARCH_GRAPH_LIMIT")
    return graph


def compile_task_graphs(sample, prediction):
    if sample.task_id == "cq2term":
        return {"tbox": "", "abox": "", "report": {"status": "NOT_APPLICABLE_TERMS_ONLY", "authority": "DIAGNOSTIC_ONLY"}}
    if sample.task_id == "cq2onto":
        graph = parse_draft(prediction["turtle"])
        return {"tbox": research_ntriples(graph).decode(), "abox": "", "report": {
            "status": "SERIALIZED_NATIVE_OWL", "compiler": "semantic_kernel.rdf.serializers.research_ntriples",
            "restriction_nodes": len(list(graph.subjects(RDF.type, OWL.Restriction))),
            "authority": "DIAGNOSTIC_ONLY", "production_candidate_compiler": "NOT_APPLICABLE_ARBITRARY_OWL"}}

    structural, assertions = {}, {}

    def candidate(table, kind, subject, obj=None, predicate=None):
        body = {"candidate_type": kind, "subject_iri": str(iri(subject))}
        if obj is not None:
            body["object_iri"] = str(iri(obj))
        if predicate is not None:
            body["predicate_iri"] = str(iri(predicate))
        key = stable_urn("research-draft-candidate", body)
        # Set de-duplication is only the compiler's RDF representation; native
        # payloads retain duplicates (important for OSKGC SS).
        table[key] = {"candidate_id": key, "body": body, "candidate_action": "CREATE_NEW" if table is structural else "ASSERT"}

    def cls(label):
        candidate(structural, "CLASS", label)

    def prop(label):
        candidate(structural, "OBJECT_PROPERTY", label)

    def fact(s, p, o):
        candidate(assertions, "INDIVIDUAL", s)
        candidate(assertions, "INDIVIDUAL", o)
        prop(p)
        candidate(assertions, "OBJECT_PROPERTY_ASSERTION", s, o, p)

    typed = sample.mode == "SCHEMA_ABOX"
    if typed:
        expected = typed_graphs(prediction)["instances.ttl"]
        for (s, p, o), types in zip(prediction["triples"], prediction["schemas"], strict=True):
            fact(s, p, o)
            for entity, label in ((s, types["sub"]), (o, types["obj"])):
                cls(label)
                candidate(assertions, "CLASS_ASSERTION", entity, label)
        # Legal category schema, not per-entry gold schema or predicted schema.
        for row in sample.allowed_schema.get("entity_types", []):
            cls(row["id"])
        for row in sample.allowed_schema.get("relations", []):
            prop(row["id"])
            cls(row["domain"])
            cls(row["range"])
            candidate(structural, "DOMAIN_AXIOM", row["id"], row["domain"])
            candidate(structural, "RANGE_AXIOM", row["id"], row["range"])
        for row in sample.allowed_schema.get("hierarchy", []):
            cls(row["domain"])
            cls(row["range"])
            candidate(structural, "SUBCLASS_AXIOM", row["domain"], row["range"])
    else:
        triples = [*sample.initial_triples, *prediction["triples"]]
        expected = triples_graph(triples)
        for s, p, o in triples:
            relation = native_exact_key((s, p, o))[1]
            if relation == "is-a":
                cls(s)
                cls(o)
                candidate(structural, "SUBCLASS_AXIOM", s, o)
            elif relation == "instance-of":
                candidate(assertions, "INDIVIDUAL", s)
                cls(o)
                candidate(assertions, "CLASS_ASSERTION", s, o)
            else:
                fact(s, p, o)
    plan = stable_urn("research-compilation-plan", {"input": sample.model_dump(mode="json"), "prediction": prediction})
    identity = {"default_namespace": "urn:ontology-io:label:", "ontology_iri": "urn:ontology-io:diagnostic",
        "version_iri": "urn:ontology-io:diagnostic:v1", "ontology_version": "0.0.0", "baseline_ontology_iris": []}
    tbox = compile_tbox(list(structural.values()), baseline_graph=Graph(), ontology_identity=identity,
        compiler_snapshot_id=plan, package_id=plan, plan_id=plan)
    abox = compile_abox(list(assertions.values()), effective_tbox=tbox.effective, plan_id=plan)
    actual = Graph()
    for table, compiled in ((structural, tbox), (assertions, abox)):
        for key, row in table.items():
            kind = row["body"]["candidate_type"]
            if kind in {"CLASS", "OBJECT_PROPERTY", "INDIVIDUAL"} or typed and table is structural:
                continue
            for triple in compiled.item_triples[key]:
                actual.add(triple)
    if not isomorphic(expected, actual):
        raise ValueError("SHARED_COMPILER_TASK_PROJECTION_MISMATCH")
    return {"tbox": research_ntriples(tbox.effective).decode(), "abox": research_ntriples(abox.graph).decode(),
        "report": {"status": "COMPILED", "compilers": ["semantic_kernel.tbox.compile_tbox", "semantic_kernel.abox.compile_abox"],
            "authority": "DIAGNOSTIC_ONLY", "approval": "UNREVIEWED_EVAL_DRAFT", "formal_delivery": False,
            "native_reports_are_computation_not_confirmed_review": True,
            "tbox_computation_sha256": semantic_hash(tbox.report), "abox_computation_sha256": semantic_hash(abox.report),
            "tbox_statements": len(tbox.effective), "abox_statements": len(abox.graph), "task_projection_isomorphic": True}}


def freeze_compilation(directory, compilation):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for role in ("tbox", "abox"):
        raw = compilation[role].encode()
        graph = Graph().parse(data=raw, format="nt")
        path = directory / (role + ".nt")
        path.write_bytes(raw)
        if not isomorphic(graph, Graph().parse(path, format="nt")):
            raise ValueError("SHARED_COMPILED_GRAPH_ROUNDTRIP_CHANGED")
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"files": hashes, "compilation": compilation["report"], "authority": "DIAGNOSTIC_ONLY"}
    (directory / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
