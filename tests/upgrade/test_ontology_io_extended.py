"""Offline checks, never measurements of benchmark improvement."""
from __future__ import annotations

import ast
import hashlib
from copy import deepcopy
from pathlib import Path

import networkx as nx
import pytest
from rdflib import OWL, RDF, Graph
from rdflib.compare import isomorphic

from tests.upgrade.test_ontology_io import scorer
from tests.upgrade.test_ontology_io_integrity import RecordedClient, protocol, sample
from zhigou_toolchain.ontology_io.adapters import (
    adapt_llms4ol,
    freeze_task_prediction,
    project_task_prediction,
)
from zhigou_toolchain.ontology_io.cq4oe import (
    CQ4OE_COMMIT,
    adapt_cq4oe,
    native_term_hard,
)
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.isolation import probe_isolation, require_isolation
from zhigou_toolchain.ontology_io.matrix import budget_upper_bound, validate_resume
from zhigou_toolchain.ontology_io.native_metrics import llms4ol_fuzzy
from zhigou_toolchain.ontology_io.splits import group_public_documents, phase_for_group
from zhigou_toolchain.ontology_io.statistics import paired_cluster_aggregate


def test_reuse_public_terms_types_and_gold_metamorphic_fixed_request(tmp_path):
    raw = {"id": "a", "context": "Oak is a tree.", "terms": ["tree-1"], "types": ["Oak", "Tree"],
        "initial-primitive-ontology-triples": [], "extended-primitive-ontology-triples": [["SECRET", "p", "X"]]}
    requests = []
    for index in range(2):
        s = adapt_llms4ol(raw, task="reuse")
        assert s.supplied_types == raw["types"] and s.supplied_terms == raw["terms"]
        client = RecordedClient([{"triples": []}])
        assert generate_sample(s, protocol(), "DirectGeneralLLM", tmp_path / str(index), client=client)["status"] == "GENERATED"
        requests.append(deepcopy(client.inputs))
        raw["extended-primitive-ontology-triples"] = [["DIFFERENT_GOLD", "q", "Y"]]
    assert requests[0] == requests[1] and "SECRET" not in str(requests)


@pytest.mark.parametrize("gold,pred", [([], []), ([["a", "p", "b"]], []), ([], [["a", "p", "b"]]),
    ([["Oak", "is-a", "Tree"]], [[" OAK ", " IS-A ", "TREE"]]),
    ([["Oak", "is-a", "Tree"]], [["Tree", "is-a", "Oak"]]),
    ([["Oak", "is-a", "Tree"]], [["Oak", "instance-of", "Tree"]]),
    ([["blue oak", "is-a", "tree"]], [["blue oaks", "is-a", "tree"]] * 2),
    ([["a", "is-a", "b"], ["b", "is-a", "c"]], [["a", "is-a", "c"], ["extra", "p", "wrong"]])])
def test_fuzzy_equivalence_to_unmodified_native_function_definitions(tmp_path, gold, pred):
    from collections import defaultdict

    import numpy as np
    from rapidfuzz import fuzz
    from scipy.optimize import linear_sum_assignment

    upstream = scorer(tmp_path)
    raw = (upstream / "2026/metrics/graph_similarity.py").read_bytes()
    # Independent load of ALL native function definitions, with no upstream
    # top-level imports or embedding constructor. Semantic is never invoked.
    namespace = {"nx": nx, "np": np, "fuzz": fuzz, "defaultdict": defaultdict,
        "linear_sum_assignment": linear_sum_assignment, "TAXONOMY_RELATIONS": {"is-a"}}
    tree = ast.Module(body=[n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)], type_ignores=[])
    exec(compile(tree, "native_functions_parity_oracle", "exec"), namespace)  # noqa: S102
    assert llms4ol_fuzzy(upstream, gold, pred) == namespace["fuzzy_match"](gold, pred)
    assert "model" not in namespace  # no hidden embedding call


TBOX = """@prefix : <urn:test:> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
:Animal a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :eats ; owl:someValuesFrom :Plant ] .
:Plant a owl:Class . :eats a owl:ObjectProperty .
"""


def test_arbitrary_owl_restrictions_roundtrip_without_fake_v3_approval(tmp_path):
    s = adapt_cq4oe([{"id": "Q", "value": "Which animals eat plants?"}], sample_id="animal", task="cq2onto")
    result = freeze_task_prediction(tmp_path / "draft", s, {"turtle": TBOX})
    assert result["approval"] == "UNREVIEWED_EVAL_DRAFT"
    projection = project_task_prediction(tmp_path / "draft", s)
    disk = Graph().parse(tmp_path / "draft/ontology.ttl", format="turtle")
    assert isomorphic(disk, Graph().parse(data=TBOX, format="turtle"))
    assert list(disk.subjects(RDF.type, OWL.Restriction)) and projection["turtle"] == TBOX


def test_tbox_baselines_really_use_task_schema_and_do_not_invent_s3(tmp_path):
    s = adapt_cq4oe([{"id": "Q", "value": "Which animals eat plants?"}], sample_id="animal", task="cq2onto")
    for system in ("DirectGeneralLLM", "DirectBudgetControl"):
        client = RecordedClient([{"turtle": TBOX}] * 4)
        result = generate_sample(s, protocol(), system, tmp_path / system, client=client)
        assert result["status"] == "GENERATED"
        assert len(client.inputs) == (1 if system == "DirectGeneralLLM" else 4)
        assert result["agent_execution"]["records"] == []


def test_typed_schema_binding_roundtrip_and_declarations_not_projected_as_facts(tmp_path):
    s = sample().model_copy(update={"mode": "SCHEMA_ABOX", "task_id": "schema_guided_abox"})
    payload = {"triples": [["A", "country", "B"]], "schemas": [{"sub": "City", "rel": "country", "obj": "Country"}]}
    freeze_task_prediction(tmp_path / "typed", s, payload)
    projected = project_task_prediction(tmp_path / "typed", s)
    assert projected["triples"] == payload["triples"] and projected["schemas"] == payload["schemas"]
    assert len(Graph().parse(tmp_path / "typed/instances.ttl")) == 3
    bad = {**payload, "schemas": []}
    with pytest.raises(ValueError, match="BINDING_COUNT"):
        freeze_task_prediction(tmp_path / "bad", s, bad)


def test_cq_occurrences_do_not_overwrite_repeated_ids(tmp_path):
    s = adapt_cq4oe([{"id": "CQ13", "value": "Which plants?"}] * 2, sample_id="plants", task="cq2term")
    ids = [r["id"] for r in s.cq_occurrences]
    assert len(set(ids)) == 2
    payload = {"cq_terms": [{"id": i, "classes": ["Plant"], "properties": []} for i in ids]}
    freeze_task_prediction(tmp_path / "terms", s, payload)
    assert project_task_prediction(tmp_path / "terms", s)["cq_terms"] == payload["cq_terms"]
    with pytest.raises(ValueError, match="INVENTORY"):
        freeze_task_prediction(tmp_path / "missing", s, {"cq_terms": payload["cq_terms"][:1]})


def test_cross_task_source_and_near_duplicate_split_keeps_every_record():
    text = " ".join("token" + str(i) for i in range(100))
    rows = [{"key": "flagship:a", "text": text, "source": "a"}, {"key": "reuse:a", "text": text + " extra", "source": "a"},
        {"key": "flagship:b", "text": text + " other", "source": "b"}, {"key": "flagship:c", "text": "unrelated content", "source": "c"}]
    result = group_public_documents(rows)
    assert len(result["groups"]) == 4 and result["independent_groups"] == 2
    assert len({phase_for_group(result["groups"][r["key"]]) for r in rows[:3]}) == 1
    assert group_public_documents(list(reversed(rows)))["groups"] == result["groups"]


def test_native_nonadditive_aggregate_recomputed_on_every_resample():
    calls = []

    def aggregate(rows):
        calls.append(rows)
        gold = set().union(*(r[0] for r in rows))
        pred = set().union(*(r[1] for r in rows))
        return 2 * len(gold & pred) / (len(gold) + len(pred)) if gold or pred else 0

    left = {"a": {0: [({"x"}, {"x"})]}, "b": {0: [({"x"}, set())]}}
    right = {"a": {0: [({"x"}, {"x"})]}, "b": {0: [({"x"}, {"x"})]}}
    result = paired_cluster_aggregate(left, right, aggregate=aggregate, bootstrap_samples=100)
    assert result["difference"] == 0  # Not mean(sample F1) delta = .5.
    assert result["native_aggregate_recomputed"] and len(calls) > 200
    assert result["test"] == "EXACT_PAIRED_CLUSTER_EXCHANGE"


def test_budget_counts_failures_reserves_and_resume_drift_rejected():
    p = protocol(replicates=3)
    budget = budget_upper_bound([2, 4], ["DirectGeneralLLM", "DirectBudgetControl", "OursFull"], p)
    assert budget["model_call_upper_bound"] == 18 * 9
    assert budget["cost_upper_bound"] is None and budget["unplanned_retry_allowance"] == 0
    frozen = {k: k for k in ("protocol_sha256", "source_fingerprint_sha256", "resource_locks", "input_locks", "phase")}
    validate_resume(frozen, frozen)
    for key in frozen:
        with pytest.raises(ValueError, match="RESUME_FROZEN_CONTEXT_CHANGED"):
            validate_resume(frozen, {**frozen, key: "changed"})


def test_false_isolation_flags_never_grant_live_execution(monkeypatch):
    monkeypatch.setattr("zhigou_toolchain.ontology_io.isolation.shutil.which", lambda _: None)
    result = probe_isolation()
    assert result["status"] == "BLOCKED_OS_ISOLATION" and result["os_canary_access_denied"] is False
    with pytest.raises(ValueError, match="BLOCKED_OS_ISOLATION"):
        require_isolation({"raw_gold_access": False, "status": "PASS"})


@pytest.mark.parametrize("pred,gold,expected", [(["Tree"], ["tree"], 1), ([], [], 0), (["Tree", "Wrong"], ["Tree"], 2 / 3),
    (["Tree", "Tree"], ["Tree"], 2 / 3), (["TreeNode"], ["tree_node"], 1)])
def test_cq4oe_native_hard_term_boundary_with_locked_resource(pred, gold, expected):
    root = Path(__file__).resolve().parents[2] / "runtime/ontology-io/upstream/cq4oe_0_0_1" / CQ4OE_COMMIT
    if not (root / "asset-lock.json").exists():
        pytest.skip("Prepare pinned CQ4OE scorer assets for native integration test")
    assert native_term_hard(root, pred, gold)["f1"] == expected


def test_tbox_modified_bytes_rejected(tmp_path):
    s = adapt_cq4oe([{"id": "Q", "value": "Which animals?"}], sample_id="animal", task="cq2onto")
    result = freeze_task_prediction(tmp_path / "draft", s, {"turtle": TBOX})
    file = tmp_path / "draft/ontology.ttl"
    assert hashlib.sha256(file.read_bytes()).hexdigest() == result["files"]["ontology.ttl"]
    file.write_bytes(file.read_bytes() + b"\n# changed")
    with pytest.raises(ValueError, match="PREDICTION_ARTIFACT_CHANGED"):
        project_task_prediction(tmp_path / "draft", s)


@pytest.mark.parametrize("failed", [False, True])
def test_cq_native_scoring_cli_reads_frozen_artifact_without_credentials(tmp_path, monkeypatch, failed):
    from zhigou_toolchain.contracts.canonical import semantic_hash
    from zhigou_toolchain.ontology_io.cli import load, save, score

    upstream = Path(__file__).resolve().parents[2] / "runtime/ontology-io/upstream/cq4oe_0_0_1" / CQ4OE_COMMIT
    if not (upstream / "asset-lock.json").exists():
        pytest.skip("Prepare fixed upstream scorer assets")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("zhigou_toolchain.ontology_io.engine.configured_client", lambda: pytest.fail("scoring must not configure a model"))
    s = adapt_cq4oe([{"id": "Q", "value": "Which plants?"}], sample_id="plants", task="cq2term")
    p = protocol(replicates=1, primary_metrics=["classes_f1"])
    payload = {"cq_terms": [{"id": s.cq_occurrences[0]["id"], "classes": ["Plant"], "properties": []}]}
    output = tmp_path / "run"
    generated = generate_sample(s, p, "DirectGeneralLLM", output / "plants-0", client=RecordedClient([TimeoutError() if failed else payload]))
    samples = [s.model_dump(mode="json")]
    gold = {"plants": [{"id": "Q", "classes": ["Plant"], "properties": []}]}
    prepared = tmp_path / "prepared"
    save(prepared / "scoring/gold.json", gold)
    save(prepared / "prepared-lock.json", {"benchmark_id": "cq4oe_0_0_1", "dataset_version": CQ4OE_COMMIT, "task_id": "cq2term",
        "evaluation_scope": "ENGINEERING_CHECK", "sample_count": 1, "input_sha256": semantic_hash(samples), "gold_sha256": semantic_hash(gold)})
    save(output / "generation-inputs.json", samples)
    save(output / "run.json", {"run_id": "fixture", "status": "FROZEN_PREDICTIONS", "protocol": p.model_dump(mode="json"),
        "protocol_sha256": semantic_hash(p.model_dump(mode="json")), "input_sha256": semantic_hash(samples), "system_id": "DirectGeneralLLM",
        "source_commit": "0" * 40, "source_fingerprint_sha256": "0" * 64, "generation_runtime": {},
        "samples": [{"sample_id": "plants", "group_id": s.group_id, "replicate_id": 0, "path": "plants-0",
            "status": generated["status"], "result_sha256": semantic_hash(generated)}]})
    result = score(output, prepared, upstream, tmp_path / "score.json")
    report = load(tmp_path / "score.json")
    assert result["status"] == ("UNSCORABLE" if failed else "MEASURED")
    assert result["samples"] == 1 and result["failed"] == int(failed)
    assert report["metrics"][0]["value"] == (None if failed else 1)


def test_cq_hard_equivalence_to_all_native_function_defs():
    import contextlib
    import io
    import re

    root = Path(__file__).resolve().parents[2] / "runtime/ontology-io/upstream/cq4oe_0_0_1" / CQ4OE_COMMIT
    if not (root / "asset-lock.json").exists():
        pytest.skip("Prepare pinned CQ4OE scorer")
    raw = (root / "CQ2Term/scripts/concept_label_matching.py").read_bytes()
    namespace = {"re": re, "HARD_THRESHOLD": 1., "SEMANTIC_THRESHOLD": .6, "LEXICAL_THRESHOLD": .8}
    definitions = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), "independent_native_cq_functions", "exec"), namespace)  # noqa: S102
    with contextlib.redirect_stdout(io.StringIO()):
        expected = namespace["cal_metrics"](["PlantPart", "extra"], ["plant_part"], "hard_match")[:4]
    assert tuple(native_term_hard(root, ["PlantPart", "extra"], ["plant_part"]).values()) == expected
