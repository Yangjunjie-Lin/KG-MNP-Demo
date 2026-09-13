import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from zhigou_toolchain.modeling.five_stage.agents import (
    AgentRun,
    AgentToolDenied,
    FiveStageCoordinator,
)
from zhigou_toolchain.ontology_io.adapters import (
    adapt_llms4ol,
    freeze_prediction,
    project_prediction,
)
from zhigou_toolchain.ontology_io.contracts import REPORT_SCHEMA
from zhigou_toolchain.ontology_io.native_metrics import LLMS4OL_COMMIT, llms4ol_exact
from zhigou_toolchain.ontology_io.reports import inspect_report
from zhigou_toolchain.ontology_io.statistics import paired_comparison

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/ontology_io"


def scorer(tmp_path):
    target = tmp_path / "2026/metrics/graph_similarity.py"
    target.parent.mkdir(parents=True)
    raw = (FIXTURES / "graph_similarity.py.txt").read_bytes()
    target.write_bytes(raw)
    (tmp_path / "asset-lock.json").write_text(json.dumps({"commit": LLMS4OL_COMMIT, "files": [{"path": "2026/metrics/graph_similarity.py", "sha256": hashlib.sha256(raw).hexdigest()}]}))
    return tmp_path


def test_native_exact_keeps_upstream_empty_and_no_taxonomy_behaviour(tmp_path):
    source = scorer(tmp_path)
    assert llms4ol_exact(source, [], []) == {"edge_f1": 1., "neighborhood_similarity": 0., "taxonomy_similarity": 0., "graph_similarity": 1 / 3}
    ordinary = [["Tree", "located at", "Site"]]
    assert llms4ol_exact(source, ordinary, ordinary)["graph_similarity"] == 2 / 3
    taxonomy = [["Oak", "is-a", "Tree"]]
    assert llms4ol_exact(source, taxonomy, taxonomy)["graph_similarity"] == 1.
    assert llms4ol_exact(source, taxonomy, [["Tree", "is-a", "Oak"]])["edge_f1"] == 0.
    assert llms4ol_exact(source, taxonomy, [["Oak", "instance-of", "Tree"]])["edge_f1"] == 0.


def test_changed_scorer_rejected_even_if_local_asset_lock_rewritten(tmp_path):
    source = scorer(tmp_path)
    file = source / "2026/metrics/graph_similarity.py"
    file.write_bytes(file.read_bytes() + b"\n# tampered")
    with pytest.raises(ValueError, match="SCORER_SOURCE_CHANGED"):
        llms4ol_exact(source, [], [])


def test_gold_not_used_to_supply_scope_or_identity():
    raw = {"id": "s1", "context": "Oak is a tree.", "primitive-ontology-triples": [["PRIVATE_GOLD_SENTINEL", "is-a", "Secret"]]}
    value = adapt_llms4ol(raw, task="flagship")
    assert "PRIVATE_GOLD_SENTINEL" not in value.model_dump_json()
    assert value.initial_triples == [] and value.identity_policy == "PER_SAMPLE_CANDIDATE_LABEL_V1"


def test_reuse_projection_keeps_wrong_predictions_but_excludes_supplied_edges(tmp_path):
    initial = [["Oak", "is-a", "Tree"]]
    sample = adapt_llms4ol({"id": "s1", "context": "Oak is a tree.", "initial-primitive-ontology-triples": initial,
        "extended-primitive-ontology-triples": [["SECRET_GOLD", "is-a", "Hidden"]]}, task="reuse")
    assert "SECRET_GOLD" not in sample.model_dump_json()
    wrong = ["Tree", "is-a", "Oak"]
    freeze_prediction(tmp_path / "prediction", sample, [*initial, wrong])
    result = project_prediction(tmp_path / "prediction", sample)
    assert result["triples"] == [wrong] and result["audit"]["removed_input_triples"] == 1
    assert not result["audit"]["model_called"]


def test_native_relation_normalization_preserves_rdf_class_and_instance_roles():
    from rdflib import RDF, RDFS

    from zhigou_toolchain.ontology_io.adapters import iri, triples_graph

    graph = triples_graph([["Oak", " IS-A ", "Tree"], ["tree-1", "Instance-Of", "Oak"]])
    assert (iri("Oak"), RDFS.subClassOf, iri("Tree")) in graph
    assert (iri("tree-1"), RDF.type, iri("Oak")) in graph
    assert len(graph) == 2


def test_coordinator_rejects_skips_and_changed_handoffs_before_call():
    flow = FiveStageCoordinator(AgentRun("s", "r", None, [], mode="BENCHMARK_DRAFT"))
    with pytest.raises(AgentToolDenied):
        flow.execute(5, "compile.build", dict, inputs={})
    value = flow.execute(1, "input.profile", lambda: {"source": 1}, inputs={})
    assert value == {"source": 1}
    touched = []
    with pytest.raises(AgentToolDenied):
        flow.execute(2, "structure.design", lambda: touched.append(1), inputs={}, parent_digest="wrong")
    assert not touched


def test_paired_statistics_group_replicates_and_preserve_zero():
    a = {"doc1": [0, 0, 0], "doc2": [.5, .5, .5]}
    b = {"doc1": [.1, .1, .1], "doc2": [.4, .4, .4]}
    result = paired_comparison(a, b, bootstrap_samples=100, seed=13)
    assert result["independent_groups"] == 2
    assert abs(result["difference"]) < 1e-12
    assert paired_comparison({"one": [0, 0, 0]}, {"one": [1, 1, 1]})["confidence_interval_95"] is None
    with pytest.raises(ValueError, match="PAIRED_REPLICATES_DIFFER"):
        paired_comparison({"a": [0]}, {"a": [0, 0]})


def empty_report():
    report = {key: "not-run" for key in REPORT_SCHEMA["required"]}
    report.update(schema_version="1.0.0", status="NOT_RUN", metrics=[{"name": "F1", "source": "native", "matching": "exact",
        "value": None, "unit": "fraction", "numerator": None, "denominator": None, "status": "NOT_RUN"}],
        observed_model_ids=[], resources=[], limitations=[], comparison=None, sample_count=0, failure_count=0)
    report.update(evaluation_scope="ENGINEERING_CHECK", source_commit=None, scorer_commit=None,
        source_fingerprint_sha256=None, input_manifest_sha256=None, prediction_manifest_sha256=None, scorer_config_sha256=None)
    return report


def test_not_run_null_and_measured_zero_are_distinct_and_private_fields_rejected():
    report = empty_report()
    assert inspect_report(report)["production_allowed"] is False
    report["metrics"][0]["value"] = 0
    with pytest.raises(ValidationError):
        Draft202012Validator(REPORT_SCHEMA).validate(report)
    report["metrics"][0]["status"] = "MEASURED"
    report.update(status="MEASURED", sample_count=1, source_commit="0" * 40, scorer_commit="0" * 40,
        source_fingerprint_sha256="0" * 64, input_manifest_sha256="0" * 64, prediction_manifest_sha256="0" * 64, scorer_config_sha256="0" * 64)
    Draft202012Validator(REPORT_SCHEMA).validate(report)
    report["extra"] = {"private_gold": ["NO"]}
    with pytest.raises(ValueError, match="PRIVATE_SCORING"):
        inspect_report(report)
