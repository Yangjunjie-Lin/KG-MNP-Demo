"""Actual shared-kernel execution with recorded model boundaries, not research scores."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import validate
from rdflib import OWL, RDF, Graph
from rdflib.compare import isomorphic

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage import assistance
from zhigou_toolchain.modeling.five_stage.agents import (
    AgentRun,
    AgentToolDenied,
    FiveStageCoordinator,
)
from zhigou_toolchain.modeling.five_stage.semantic_check import check_research_graphs
from zhigou_toolchain.ontology_io.adapters import (
    adapt_llms4ol,
    project_task_prediction,
    triples_graph,
)
from zhigou_toolchain.ontology_io.compilation import compile_task_graphs
from zhigou_toolchain.ontology_io.contracts import ModelingInput, Protocol
from zhigou_toolchain.ontology_io.cq4oe import adapt_cq4oe
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.kernel import components

SYSTEMS = ["TwoAgentKernelV1", "NoRetrieval", "NoConstrainedExtraction", "NoValidationFeedback", "DirectRetrievalContext"]
REUSE = {"decisions": [], "unresolved": []}
VOCAB = {"classes": ["Oak", "Tree"], "entities": [], "relations": [], "unresolved": []}
TRIPLES = [["Oak", "is-a", "Tree"]]
TBOX = """@prefix : <urn:test:> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
:Animal a owl:Class; rdfs:subClassOf [a owl:Restriction; owl:onProperty :eats; owl:someValuesFrom :Plant] .
:Plant a owl:Class . :eats a owl:ObjectProperty .
"""


class Boundary:
    lock = SimpleNamespace(model_id="fixture", revision="fixture-v1")
    last_public_response = None

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.requests = []

    def propose(self, instruction, content, schema, **options):
        from zhigou_toolchain.modeling.five_stage.tools import validate_references
        self.requests.append({"instruction": instruction, "content": deepcopy(content), "schema": schema})
        value = next(self.outputs)
        if isinstance(value, Exception):
            raise value
        validate(value, schema)
        validate_references(value, set(options.get("allowed_iris", ())), set())
        return {"proposal": deepcopy(value), "execution_source": "RECORDED", "usage": {"total_tokens": None}}


def protocol(**profile):
    return Protocol(protocol_id="kernel-offline", model_id="fixture", declared_revision="fixture-v1", systems=SYSTEMS,
        replicates=1, kernel_profile=profile, budget={"max_calls": 6, "max_total_tokens": 120000, "max_output_tokens": 2048})


def sample(reuse=False):
    return adapt_llms4ol({"id": "oak", "context": "Oak is a tree.", "terms": [], "types": ["Oak", "Tree"],
        "initial-primitive-ontology-triples": TRIPLES}, task="reuse" if reuse else "flagship")


def extracted(quote="Oak is a tree.", triples=None):
    return {"prediction": {"triples": TRIPLES if triples is None else triples},
        "evidence": [{"triple_index": 0, "quote": quote, "start": 0}]}


def test_kernel_calls_real_retrieval_compilers_and_rebinds_evidence(tmp_path, monkeypatch):
    touched = []
    original = assistance.retrieve_cards

    def retrieval(*args, **kwargs):
        touched.append("retrieval")
        return original(*args, **kwargs)

    monkeypatch.setattr(assistance, "retrieve_cards", retrieval)
    boundary = Boundary([REUSE, VOCAB, extracted()])
    result = generate_sample(sample(True), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=boundary)
    assert result["status"] == "GENERATED", result
    assert touched == ["retrieval"]
    assert result["kernel"]["validation"]["compilation"]["report"]["compilers"] == [
        "semantic_kernel.tbox.compile_tbox", "semantic_kernel.abox.compile_abox"]
    assert result["kernel"]["evidence"]["bindings"][0]["quote"] == "Oak is a tree."
    assert result["kernel"]["validation"]["semantic"]["owl_consistency"]["status"] == "REASONER_UNAVAILABLE"
    assert result["kernel"]["validation"]["semantic"]["shacl"]["status"] == "NOT_APPLICABLE_NO_LEGAL_SHAPES"
    assert len(boundary.requests) == 3
    rows = result["agent_execution"]["records"]
    assert {r["agent_id"] for r in rows if r["stage_id"] in {1, 2, 4}} == {"RuleAgent"}
    assert {r["agent_id"] for r in rows if r["stage_id"] in {3, 5}} == {"TaskExecutionAgent"}
    assert rows[-1]["tool_id"] == "archive.verify"
    assert project_task_prediction(tmp_path / "run/artifacts", sample(True))["triples"] == []  # supplied edge, not newly earned


def test_fact_feedback_routes_s4_to_s3_and_retains_bad_history(tmp_path):
    client = Boundary([VOCAB, extracted("invented quote"), extracted()])
    result = generate_sample(sample(), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED", result
    assert result["resources"]["semantic_repairs"] == 1
    assert result["kernel"]["history"][0]["validation"]["issues"][0]["code"] == "EVIDENCE_QUOTE_UNBOUND"
    assert result["kernel"]["history"][1]["validation"]["issues"] == []
    rows = result["agent_execution"]["records"]
    route = next(i for i, row in enumerate(rows) if row["tool_id"] == "repair.route")
    assert rows[route + 1]["stage_id"] == 3
    assert client.requests[-1]["content"]["feedback"]["source"] == "DETERMINISTIC_PUBLIC_INPUT_CHECKS_ONLY"


def test_cqs_structure_repair_returns_to_s2_and_never_fakes_abox(tmp_path):
    s = adapt_cq4oe([{"id": "CQ1", "value": "Which animals eat plants?"}], sample_id="animals", task="cq2onto")
    client = Boundary([{"turtle": "not turtle"}, {"turtle": TBOX}])
    result = generate_sample(s, protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED", result
    rows = result["agent_execution"]["records"]
    route = next(i for i, row in enumerate(rows) if row["tool_id"] == "repair.route")
    assert rows[route + 1]["stage_id"] == 2
    assert all(r["tool_id"] == "facts.normalize" for r in rows if r["stage_id"] == 3)
    graph = Graph().parse(tmp_path / "run/artifacts/ontology.ttl", format="turtle")
    assert isomorphic(graph, Graph().parse(data=TBOX, format="turtle"))
    assert list(graph.subjects(RDF.type, OWL.Restriction))
    assert not list(graph.subjects(RDF.type, OWL.NamedIndividual))


def test_ablation_changes_actual_requests_and_feedback_behaviour(tmp_path):
    parent = generate_sample(sample(True), protocol(), "TwoAgentKernelV1", tmp_path / "parent", client=Boundary([REUSE, VOCAB, extracted("bad"), extracted()]))
    no_validation = generate_sample(sample(True), protocol(), "NoValidationFeedback", tmp_path / "no-feedback", client=Boundary([REUSE, VOCAB, extracted("bad")]))
    assert parent["resources"]["model_calls"] == 4 and no_validation["resources"]["model_calls"] == 3
    assert no_validation["kernel"]["validation"]["issues"]
    assert no_validation["status"] == "GENERATED"  # score wrong/unsupported outputs, do not silently drop them
    without = Boundary([REUSE, VOCAB, extracted()])
    no_retrieval = generate_sample(sample(True), protocol(), "NoRetrieval", tmp_path / "no-retrieval", client=without)
    assert no_retrieval["kernel"]["retrieval"] == []
    assert without.requests[0]["content"]["retrieval"] == []
    assert parent["kernel"]["retrieval"] != []
    assert parent["capabilities"]["configuration_sha256"] != no_retrieval["capabilities"]["configuration_sha256"]


def test_unconstrained_extraction_only_removes_vocabulary_constraint_not_quote_integrity(tmp_path):
    s = sample().model_copy(update={"text": "Elm is a tree."})
    value = extracted("Elm is a tree.", [["Elm", "is-a", "Tree"]])
    parent = generate_sample(s, protocol(max_repair_cycles=0), "TwoAgentKernelV1", tmp_path / "parent", client=Boundary([VOCAB, value]))
    client = Boundary([VOCAB, value])
    ablated = generate_sample(s, protocol(max_repair_cycles=0), "NoConstrainedExtraction", tmp_path / "no", client=client)
    assert any(r["code"] == "FROZEN_VOCABULARY_VIOLATION" for r in parent["kernel"]["validation"]["issues"])
    assert not ablated["kernel"]["validation"]["issues"]
    assert client.requests[-1]["content"]["candidate_vocabulary"] is None
    assert ablated["kernel"]["evidence"]["bindings"]  # still required


@pytest.mark.parametrize("system,source,settings", [("NoRetrieval", sample(), {}),
    ("NoValidationFeedback", sample(), {"max_repair_cycles": 0}),
    ("NoConstrainedExtraction", adapt_cq4oe([{"id": "Q", "value": "Which trees?"}], sample_id="trees", task="cq2onto"), {})])
def test_inapplicable_ablation_rejected_before_model(system, source, settings, tmp_path):
    client = Boundary([])
    result = generate_sample(source, protocol(**settings), system, tmp_path / "run", client=client)
    assert result["failure_code"] == "ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE"
    assert client.requests == []


def test_same_retrieval_context_control_is_one_call(tmp_path):
    client = Boundary([{"triples": TRIPLES}])
    result = generate_sample(sample(True), protocol(), "DirectRetrievalContext", tmp_path / "direct", client=client)
    assert result["status"] == "GENERATED" and result["resources"]["model_calls"] == 1
    assert client.requests[0]["content"]["retrieval_context"] == result["kernel"]["retrieval"]


def test_repair_budget_and_wipe_to_empty_cannot_fake_validation_success(tmp_path):
    client = Boundary([VOCAB, extracted("bad"), {"prediction": {"triples": []}, "evidence": []}])
    result = generate_sample(sample(), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "FAILED" and result["failure_code"] == "REPAIR_EMPTY_OUTPUT_REJECTED"
    assert len(result["kernel"]["history"]) == 1
    assert result["resources"]["model_calls"] == 3
    client = Boundary([VOCAB, extracted("bad"), extracted("still bad")])
    result = generate_sample(sample(), protocol(), "TwoAgentKernelV1", tmp_path / "bounded", client=client)
    assert result["status"] == "GENERATED" and result["kernel"]["status"] == "GENERATED_WITH_VALIDATION_ISSUES"
    assert result["resources"]["model_calls"] == 3


def test_original_coordinator_cannot_gain_unbounded_or_production_repair():
    flow = FiveStageCoordinator(AgentRun("s", "t", None, [], mode="PRODUCTION"), max_repairs=10)
    for stage in range(1, 5):
        tool = {1: "input.profile", 2: "structure.design", 3: "facts.normalize", 4: "semantic.check"}[stage]
        flow.execute(stage, tool, dict, inputs={}, parent_digest=flow.parent_digest)
    with pytest.raises(AgentToolDenied):
        flow.repair(2, feedback={}, parent_digest=semantic_hash({}))


def test_typed_compiler_preserves_facts_and_type_bindings():
    s = ModelingInput(sample_id="city", benchmark_id="fixture", dataset_version="fixture", task_id="schema_guided_abox", split="fixture",
        evaluation_scope="ENGINEERING_CHECK", group_id="city", mode="SCHEMA_ABOX", text="A is in B.", allowed_schema={
            "entity_types": [{"id": "City"}, {"id": "Country"}], "relations": [{"id": "country", "domain": "City", "range": "Country"}], "hierarchy": []})
    compiled = compile_task_graphs(s, {"triples": [["A", "country", "B"]], "schemas": [{"sub": "City", "rel": "country", "obj": "Country"}]})
    assert compiled["report"]["task_projection_isomorphic"]
    assert compiled["report"]["abox_statements"] == 5  # fact + two types + two metadata declarations


def test_primitive_compiler_keeps_reverse_and_duplicate_raw_prediction_semantics():
    raw = [["Tree", "is-a", "Oak"], ["x", "instance-of", "Tree"], ["x", "p", "y"]] * 2
    compiled = compile_task_graphs(sample(), {"triples": raw})
    assert compiled["report"]["task_projection_isomorphic"]
    assert len(triples_graph(raw)) == 3


def test_generated_imports_do_not_trigger_reasoner_or_remote_access(monkeypatch):
    graph = Graph().parse(data='@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:x> owl:imports <https://example.invalid/gold> .', format="turtle")
    monkeypatch.setattr("zhigou_toolchain.semantic_kernel.reasoner.run_hermit", lambda *a, **k: pytest.fail("imports cannot reach reasoner"))
    with pytest.raises(ValueError, match="REMOTE_IMPORT"):
        check_research_graphs(tbox=graph, abox=Graph())


def test_shared_real_shacl_positive_and_negative_no_fake_shapes():
    tbox = Graph().parse(data='@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:C> a owl:Class .', format="turtle")
    shapes = Graph().parse(data='@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:S> a sh:NodeShape; sh:targetClass <urn:C>; sh:property [sh:path <urn:p>; sh:minCount 1] .', format="turtle")
    abox = Graph().parse(data='<urn:x> a <urn:C> .', format="turtle")
    negative = check_research_graphs(tbox=tbox, abox=abox, shapes=shapes)
    assert negative["shacl"]["status"] == "VIOLATION"
    abox.parse(data='<urn:x> <urn:p> "value" .', format="turtle")
    positive = check_research_graphs(tbox=tbox, abox=abox, shapes=shapes)
    assert positive["shacl"]["status"] == "CONFORMS"
    assert positive["target_coverage"]["status"] == "PASS"


def test_shared_real_hermit_consistency_and_inconsistency():
    jar = Path(__file__).resolve().parents[2] / "third_party/downloads/robot-1.9.7.jar"
    if not jar.exists():
        pytest.skip("Pinned reasoner bundle not installed; not a passing reasoner claim")
    tbox = Graph().parse(data='@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:A> a owl:Class; owl:disjointWith <urn:B> . <urn:B> a owl:Class .', format="turtle")
    abox = Graph().parse(data='<urn:x> a <urn:A> .', format="turtle")
    assert check_research_graphs(tbox=tbox, abox=abox, reasoner_jar=jar)["owl_consistency"]["status"] == "CONSISTENT"
    abox.parse(data='<urn:x> a <urn:B> .', format="turtle")
    assert check_research_graphs(tbox=tbox, abox=abox, reasoner_jar=jar)["owl_consistency"]["status"] == "INCONSISTENT"


def test_profile_components_do_not_claim_vector_weights_or_production_approval():
    cap = components(sample(True), protocol(), "TwoAgentKernelV1")
    assert cap["retrieval_scope"] == "ONLY_SUPPLIED_INPUT_EXACT_LOOKUP_NO_EXTRA_CORPUS"
    assert cap["formal_v3_export"] is False


def test_replay_entry_is_credential_free_bound_to_input_and_not_a_live_bypass(tmp_path, monkeypatch):
    import json

    import yaml

    from zhigou_toolchain.ontology_io.replay import replay_sample

    root = Path(__file__).resolve().parents[2]
    fixture = root / "tests/fixtures/ontology_io/kernel"
    config = yaml.safe_load((root / "config/ontology_io/protocols/kernel-engineering.yaml").read_text(encoding="utf-8"))
    config["kernel_profile"]["reasoner_jar"] = None
    protocol_file = tmp_path / "protocol.yaml"
    protocol_file.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("zhigou_toolchain.ontology_io.engine.configured_client", lambda: pytest.fail("replay must never configure LIVE provider"))
    result = replay_sample(fixture / "primitive-input.json", protocol_file, fixture / "primitive-recording.json", tmp_path / "run", system="TwoAgentKernelV1")
    assert result["status"] == "GENERATED" and result["live_inference_calls"] == 0 and result["source_unchanged"]
    raw = json.loads((fixture / "primitive-input.json").read_bytes())
    raw["text"] = "changed text"
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="REPLAY_FROZEN_INPUT_CHANGED"):
        replay_sample(input_file, protocol_file, fixture / "primitive-recording.json", tmp_path / "changed", system="TwoAgentKernelV1")
    raw["evaluation_scope"] = "LOCAL_HOLDOUT"
    input_file.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="REPLAY_ONLY_ACCEPTS_ENGINEERING_INPUTS"):
        replay_sample(input_file, protocol_file, fixture / "primitive-recording.json", tmp_path / "real", system="TwoAgentKernelV1")


def test_validation_unavailable_is_incomplete_not_a_pass_or_a_repair_request(tmp_path):
    client = Boundary([VOCAB, extracted()])
    result = generate_sample(sample(), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED"
    assert result["kernel"]["validation"]["status"] == "INCOMPLETE_VALIDATION"
    assert result["kernel"]["validation"]["validation_blockers"] == ["OWL_CHECK_REASONER_UNAVAILABLE"]
    assert result["resources"]["semantic_repairs"] == 0


def test_reuse_reference_choices_reach_existing_transport_reference_guard(tmp_path):
    from zhigou_toolchain.ontology_io.adapters import iri

    decision = {"decisions": [{"term": "Oak", "decision": "REUSE", "existing_iri": str(iri("Oak")), "reason": "supplied class"}], "unresolved": []}
    result = generate_sample(sample(True), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=Boundary([decision, VOCAB, extracted()]))
    assert result["status"] == "GENERATED", result


def test_cqs_only_without_baseline_uses_no_dummy_reuse_model_call(tmp_path):
    s = adapt_cq4oe([{"id": "CQ1", "value": "Which animals?"}], sample_id="animals", task="cq2onto")
    client = Boundary([{"turtle": TBOX}])
    result = generate_sample(s, protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED", result
    assert result["resources"]["model_calls"] == 1
    assert result["kernel"]["reuse"]["status"] == "NOT_APPLICABLE_NO_SUPPLIED_ONTOLOGY"
