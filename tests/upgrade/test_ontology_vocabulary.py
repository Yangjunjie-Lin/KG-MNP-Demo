"""Baseline closure uses only supplied labels; unknown labels still need S2."""
from copy import deepcopy

import pytest

from tests.upgrade.test_ontology_io_kernel import (
    REUSE,
    VOCAB,
    Boundary,
    protocol,
    sample,
)
from tests.upgrade.test_ontology_source_quotes import facts, program_protocol
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.kernel import check_prediction
from zhigou_toolchain.ontology_io.vocabulary import close_vocabulary


def test_supplied_labels_and_proposal_retained_without_new_prediction_or_gold():
    proposal = {"classes": ["New"], "entities": [], "relations": ["r"], "unresolved": ["keep"]}
    cards = [{"iri": "urn:Known", "label": "Known", "element_kind": "CLASS"},
        {"iri": "urn:E", "label": "Entity", "element_kind": "ENTITY"},
        {"iri": "urn:P", "label": "relation", "element_kind": "OBJECT_PROPERTY"}]
    original = deepcopy((proposal, cards))
    effective, provenance = close_vocabulary(proposal, cards)
    assert effective == {"classes": ["New", "Known"], "entities": ["Entity"], "relations": ["r", "relation"], "unresolved": ["keep"]}
    assert (proposal, cards) == original
    assert provenance["proposal_sha256"] == semantic_hash(proposal)
    assert provenance["facts_or_scoring_answers_used"] is False and provenance["approval"] == "NOT_GRANTED"


def test_no_silent_case_or_punctuation_aliasing():
    proposal = {"classes": ["known"], "entities": [], "relations": [], "unresolved": []}
    effective, _ = close_vocabulary(proposal, [{"iri": "urn:Known", "label": "Known", "element_kind": "CLASS"}])
    assert effective["classes"] == ["known", "Known"]
    with pytest.raises(ValueError, match="KIND"):
        close_vocabulary(proposal, [{"iri": "urn:X", "label": "X", "element_kind": "UNREVIEWED_KIND"}])


def test_reused_input_terms_are_allowed_without_pretending_model_generated_them(tmp_path):
    empty_proposal = {"classes": [], "entities": [], "relations": [], "unresolved": []}
    client = Boundary([REUSE, empty_proposal, facts()])
    result = generate_sample(sample(True), program_protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED" and len(client.requests) == 3
    assert result["calls"][1]["proposal"] == empty_proposal
    record = result["kernel"]["vocabulary_history"][0]
    assert record["model_proposal"] == empty_proposal and set(record["effective_vocabulary"]["classes"]) == {"Oak", "Tree"}
    assert not result["kernel"]["validation"]["issues"]


def test_unknown_generated_term_stays_rejected_and_is_routed_to_s2():
    s = sample().model_copy(update={"text": "Elm is a tree."})
    result = check_prediction(s, {"triples": [["Elm", "is-a", "Tree"]]}, VOCAB, [], [], constrained=True)
    issue = next(row for row in result["issues"] if row["code"] == "FROZEN_VOCABULARY_VIOLATION")
    assert issue["target_stage"] == 2
    assert result["vocabulary_gap_candidates"]["subjects"] == ["Elm"]
    assert result["vocabulary_gap_candidates"]["origin"] == "ACTUAL_MODEL_LABELS_NOT_APPROVED_OR_GOLD"


def test_vocabulary_repair_replans_before_reextracting_within_existing_call_cap(tmp_path):
    s = sample(True).model_copy(update={"text": "Elm is a tree."})
    old = deepcopy(VOCAB)
    fixed = {"classes": ["Elm", "Tree"], "entities": [], "relations": [], "unresolved": []}
    observed = {"facts": [{"triple": ["Elm", "is-a", "Tree"], "quote": "Elm is a tree."}]}
    client = Boundary([REUSE, old, observed, fixed, observed])
    p = program_protocol().model_copy(update={"budget": protocol().budget.model_copy(update={"max_calls": 5})})
    result = generate_sample(s, p, "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "GENERATED" and result["resources"]["model_calls"] == 5
    assert result["resources"]["semantic_repairs"] == 1
    assert result["kernel"]["history"][0]["validation"]["issues"][0]["code"] == "FROZEN_VOCABULARY_VIOLATION"
    assert not result["kernel"]["validation"]["issues"]
    assert client.requests[3]["content"]["feedback"]["vocabulary_gap_candidates"]["subjects"] == ["Elm"]
    stages = result["agent_execution"]["records"]
    repair = next(i for i, row in enumerate(stages) if row["tool_id"] == "repair.route")
    assert stages[repair + 1]["stage_id"] == 2


def test_no_validation_feedback_does_not_acquire_an_extra_replanning_call(tmp_path):
    s = sample().model_copy(update={"text": "Elm is a tree."})
    value = {"facts": [{"triple": ["Elm", "is-a", "Tree"], "quote": "Elm is a tree."}]}
    client = Boundary([VOCAB, value])
    result = generate_sample(s, program_protocol(), "NoValidationFeedback", tmp_path / "run", client=client)
    assert len(client.requests) == 2 and result["resources"]["semantic_repairs"] == 0
    assert any(r["code"] == "FROZEN_VOCABULARY_VIOLATION" for r in result["kernel"]["validation"]["issues"])
