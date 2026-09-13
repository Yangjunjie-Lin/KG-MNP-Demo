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
