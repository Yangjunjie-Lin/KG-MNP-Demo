"""Input allowlists and loss-audited primitive graph projections."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.compare import isomorphic

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.semantic_kernel.rdf.serializers import deterministic_turtle

from .contracts import EvaluationScope, ModelingInput


def adapt_llms4ol(record, *, task, split: EvaluationScope = "LOCAL_HOLDOUT"):
    # Only official input fields are consulted here. No gold/extended graph is
    # read to derive identities, classes, scopes, dictionaries, or resources.
    if task not in {"flagship", "reuse"}:
        raise ValueError("UNKNOWN_LLMS4OL_TASK")
    text = record["context"]
    initial = record["initial-primitive-ontology-triples"] if task == "reuse" else []
    return ModelingInput(sample_id=record["id"], benchmark_id="llms4ol_2026", task_id=task,
        dataset_version="315a9a5d883eada26e00fef1356a05802936c584", split=split, evaluation_scope=split,
        group_id=hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest(),
        mode="TEXT_EXTEND" if task == "reuse" else "TEXT_NEW", text=text, initial_triples=initial,
        supplied_terms=record.get("terms", []) if task == "reuse" else [],
        supplied_types=record.get("types", []) if task == "reuse" else [],
        requirements=["Construct primitive ontology triples; distinguish is-a from instance-of.", "Return additions only for reuse."])


def iri(label):
    return URIRef("urn:ontology-io:label:" + hashlib.sha256(label.encode()).hexdigest())


def native_exact_key(triple):
    """Projection policy frozen against pinned upstream normalize_triples.

    Only input-edge subtraction uses this key. Original prediction spelling,
    wrong edges and the actual serialized graph remain unchanged.
    """
    return tuple(" ".join(str(value).lower().strip().split()) for value in triple)


def additions_only(triples, initial):
    supplied = {native_exact_key(row) for row in initial}
    return [row for row in triples if native_exact_key(row) not in supplied]


def triples_graph(triples):
    graph = Graph()
    for row in triples:
        if not isinstance(row, (tuple, list)) or len(row) != 3 or any(not isinstance(value, str) or not value.strip() for value in row):
            raise ValueError("INVALID_PRIMITIVE_TRIPLE")
        s, p, o = row
        # Native exact matching normalizes relation spelling. Preserve the raw
        # label in the projection, but never serialize "IS-A" as an ordinary
        # relation while scoring it as a class hierarchy edge.
        relation = native_exact_key(row)[1]
        predicate = RDFS.subClassOf if relation == "is-a" else RDF.type if relation == "instance-of" else iri(p)
        graph.add((iri(s), predicate, iri(o)))
    return graph


def freeze_prediction(directory, sample, triples):
    """Serialize the actual final graph, then re-read and bind its projection."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    graph = triples_graph(triples)
    graph_file = directory / "ontology.ttl"
    graph_file.write_bytes(deterministic_turtle(graph))
    reread = Graph().parse(graph_file, format="turtle")
    if not isomorphic(graph, reread):
        raise ValueError("DISK_GRAPH_MISMATCH")
    data = {"sample_id": sample.sample_id, "triples": triples, "graph_sha256": hashlib.sha256(graph_file.read_bytes()).hexdigest(),
        "identity_policy": sample.identity_policy, "approval": "UNREVIEWED_EVAL_DRAFT", "release_status": "NOT_RELEASED",
        "semantic_encoding": "PRIMITIVE_RDF_RELATION_ROLES_V2",
        "representation": "PRIMITIVE_GRAPH_NOT_ARBITRARY_OWL_OR_TYPED_ABOX", "metadata_in_prediction": False}
    (directory / "projection.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def project_prediction(directory, sample):
    directory = Path(directory)
    projected = json.loads((directory / "projection.json").read_bytes())
    if projected.get("semantic_encoding") != "PRIMITIVE_RDF_RELATION_ROLES_V2":
        raise ValueError("PROJECTION_ENCODING_VERSION_UNSUPPORTED")
    if projected["sample_id"] != sample.sample_id or projected["graph_sha256"] != hashlib.sha256((directory / "ontology.ttl").read_bytes()).hexdigest():
        raise ValueError("PREDICTION_ARTIFACT_CHANGED")
    if not isomorphic(triples_graph(projected["triples"]), Graph().parse(directory / "ontology.ttl", format="turtle")):
        raise ValueError("PROJECTION_NOT_ACTUAL_GRAPH")
    predicted = projected["triples"]
    additions = additions_only(predicted, sample.initial_triples) if sample.task_id == "reuse" else predicted
    return {"id": sample.sample_id, "triples": additions, "audit": {"projection_version": "primitive-v3-native-exact-relations",
        "input_sha256": semantic_hash(sample.model_dump(mode="json")), "raw_count": len(predicted), "projected_count": len(additions),
        "removed_input_triples": len(predicted) - len(additions), "gold_access": False, "model_called": False,
        "unmatched_predictions_discarded": False}}


def task_output_schema(sample):
    from .engine import OUTPUT_SCHEMA
    if sample.task_id == "cq2onto":
        return {"type": "object", "additionalProperties": False, "required": ["turtle"],
            "properties": {"turtle": {"type": "string", "maxLength": 200000}}}
    if sample.task_id == "cq2term":
        occurrence_ids = [r["id"] for r in sample.cq_occurrences]
        terms = {"type": "array", "maxItems": 300, "items": {"type": "string", "minLength": 1, "maxLength": 500}}
        entry = {"type": "object", "additionalProperties": False, "required": ["id", "classes", "properties"],
            "properties": {"id": {"enum": occurrence_ids}, "classes": terms, "properties": terms}}
        return {"type": "object", "additionalProperties": False, "required": ["cq_terms"], "properties": {
            "cq_terms": {"type": "array", "maxItems": 1000, "items": entry}}}
    if sample.mode == "SCHEMA_ABOX":
        return {**OUTPUT_SCHEMA, "required": ["triples", "schemas"], "properties": {**OUTPUT_SCHEMA["properties"],
            "schemas": {"type": "array", "maxItems": 300, "items": {"type": "object", "additionalProperties": False,
                "required": ["sub", "rel", "obj"], "properties": {k: {"type": "string", "minLength": 1, "maxLength": 500} for k in ("sub", "rel", "obj")}}}}}
    return OUTPUT_SCHEMA


def typed_graphs(prediction):
    """Keep native schema predictions and bind types to the corresponding facts.

    No gold-driven filtering or business-fact/declaration mixing. Duplicate
    schemas are deliberately retained in JSON because native SS counts them.
    """
    if len(prediction["triples"]) != len(prediction["schemas"]):
        raise ValueError("TYPED_FACT_SCHEMA_BINDING_COUNT_MISMATCH")
    facts, schema = Graph(), Graph()
    for (s, p, o), types in zip(prediction["triples"], prediction["schemas"], strict=True):
        if p != types["rel"]:
            raise ValueError("TYPED_FACT_SCHEMA_RELATION_MISMATCH")
        facts.add((iri(s), iri(p), iri(o)))
        facts.add((iri(s), RDF.type, iri(types["sub"])))
        facts.add((iri(o), RDF.type, iri(types["obj"])))
        schema.add((iri(p), RDFS.domain, iri(types["sub"])))
        schema.add((iri(p), RDFS.range, iri(types["obj"])))
    return {"instances.ttl": facts, "schema.ttl": schema}


def draft_turtle(graph):
    # Production RDF forbids BNodes; arbitrary OWL restrictions require them.
    # Research-only canonical serialization, without changing the v3 compiler.
    from zhigou_toolchain.semantic_kernel.rdf.serializers import research_ntriples
    return research_ntriples(graph)


def freeze_task_prediction(directory, sample, prediction):
    from jsonschema import validate
    validate(prediction, task_output_schema(sample))
    if sample.mode in {"TEXT_NEW", "TEXT_EXTEND"}:
        return freeze_prediction(directory, sample, prediction["triples"])
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    graphs = {}
    if sample.task_id == "cq2onto":
        # Parse supplied bytes, never a URL/JSON-LD context or owl:imports fetch.
        graphs["ontology.ttl"] = Graph().parse(data=prediction["turtle"], format="turtle", publicID="urn:ontology-io:draft:")
    elif sample.mode == "SCHEMA_ABOX":
        graphs = typed_graphs(prediction)
    elif sample.task_id == "cq2term":
        ids = [r["id"] for r in prediction["cq_terms"]]
        if len(set(ids)) != len(ids) or set(ids) != {r["id"] for r in sample.cq_occurrences}:
            raise ValueError("CQ_TERM_OCCURRENCE_INVENTORY_MISMATCH")
    else:
        raise ValueError("UNSUPPORTED_TASK_ARTIFACT")
    files = {}
    for name, graph in graphs.items():
        data = draft_turtle(graph)
        (directory / name).write_bytes(data)
        if not isomorphic(graph, Graph().parse(data=data, format="turtle")):
            raise ValueError("DISK_GRAPH_MISMATCH")
        files[name] = hashlib.sha256(data).hexdigest()
    data = {"sample_id": sample.sample_id, "payload": prediction, "files": files,
        "representation": sample.task_id, "approval": "UNREVIEWED_EVAL_DRAFT", "release_status": "NOT_RELEASED",
        "serialization": "RDFLIB_CANONICAL_BNODE_TURTLE_RESEARCH_ONLY_V1", "imports": "RETAINED_NOT_FETCHED"}
    (directory / "projection.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def project_task_prediction(directory, sample):
    if sample.mode in {"TEXT_NEW", "TEXT_EXTEND"}:
        return project_prediction(directory, sample)
    directory = Path(directory)
    data = json.loads((directory / "projection.json").read_bytes())
    if data["sample_id"] != sample.sample_id or data["representation"] != sample.task_id:
        raise ValueError("PREDICTION_CONTEXT_CHANGED")
    payload = data["payload"]
    if sample.task_id == "cq2onto":
        expected = {"ontology.ttl": Graph().parse(data=payload["turtle"], format="turtle", publicID="urn:ontology-io:draft:")}
    elif sample.mode == "SCHEMA_ABOX":
        expected = typed_graphs(payload)
    else:
        expected = {}
    if set(data["files"]) != set(expected):
        raise ValueError("ARTIFACT_FILE_INVENTORY_CHANGED")
    for name, graph in expected.items():
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != data["files"][name] or not isomorphic(graph, Graph().parse(data=raw, format="turtle")):
            raise ValueError("PREDICTION_ARTIFACT_CHANGED")
    return {"id": sample.sample_id, **payload}
