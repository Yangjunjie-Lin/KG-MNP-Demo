"""Lossless public-context encoding; unchanged budgets and no gold inputs."""
import json
from copy import deepcopy

import pytest

from zhigou_toolchain.modeling.five_stage import assistance
from zhigou_toolchain.ontology_io.prompt_views import (
    GUIDE,
    compact_cards,
    compact_retrieval,
    context_view,
    expand_cards,
    expand_retrieval,
)


def fixture(count=39):
    cards = [{"iri": "urn:synthetic:" + str(i).zfill(64), "label": "Synthetic concept " + str(i), "element_kind": "CLASS",
        "aliases": [], "definition": "Synthetic supplied input, not a scoring target."} for i in range(count)]
    return cards, assistance.retrieve_cards([c["label"] for c in cards], cards, mode="LLM_SUBSTITUTE")


def test_every_original_card_rank_and_metadata_roundtrips_without_mutation():
    cards, rows = fixture()
    before = deepcopy((cards, rows))
    packed = compact_retrieval(cards, rows)
    assert expand_retrieval(cards, packed) == rows
    assert (cards, rows) == before
    assert len(packed["rows"]) == len(rows)
    assert len(json.dumps(packed)) < len(json.dumps(rows)) / 2


def test_varying_scores_and_methods_are_not_collapsed_or_discarded():
    cards, rows = fixture(2)
    rows[1]["method"] = "SYNTHETIC_OTHER"
    rows[1]["exact"][0].update(vector_score=.123, sources=["VECTOR"])
    rows[0]["extra_metadata"] = {"keep": True}
    assert expand_retrieval(cards, compact_retrieval(cards, rows)) == rows


def test_unknown_card_and_invalid_index_fail_closed():
    cards, rows = fixture(1)
    bad = deepcopy(rows)
    bad[0]["exact"][0]["card"]["label"] = "changed"
    with pytest.raises(ValueError, match="FROZEN_CATALOG"):
        compact_retrieval(cards, bad)
    packed = compact_retrieval(cards, rows)
    for index in (-1, 1, True, "0"):
        packed["rows"][0]["exact"][0]["card_index"] = index
        with pytest.raises(ValueError, match="INVALID"):
            expand_retrieval(cards, packed)


def test_context_is_self_contained_and_keeps_all_reuse_reasons_and_native_ids():
    cards, rows = fixture(2)
    original = {"input": {"allowed": True}, "retrieval": rows, "reuse": {"decisions": [
        {"term": cards[0]["label"], "existing_iri": cards[0]["iri"], "decision": "REUSE", "reason": "Exact input match"},
        {"term": "new", "existing_iri": None, "decision": "GAP", "reason": "Unresolved"}], "unresolved": ["keep"]}}
    view, changed = context_view(cards, original)
    assert changed and expand_cards(view["cards"]) == cards and view["input"] == original["input"]
    assert expand_retrieval(view["cards"], view["retrieval"]) == rows
    decision = view["reuse"]["decisions"][0]
    assert expand_cards(view["cards"])[decision["existing_card_index"]]["iri"] == original["reuse"]["decisions"][0]["existing_iri"]
    assert decision["reason"] == "Exact input match" and original["reuse"]["decisions"][0]["existing_iri"] == cards[0]["iri"]
    assert view["reuse"]["decisions"][1] == original["reuse"]["decisions"][1]


def test_no_retrieval_ablation_gains_no_catalog_or_hidden_context():
    cards, _ = fixture()
    original = {"input": {}, "retrieval": [], "reuse": {"decisions": [], "unresolved": []}}
    view, changed = context_view(cards, original)
    assert not changed and view == original and "cards" not in view


def test_changed_catalog_is_not_silently_replaced_and_guide_is_source_catalogued():
    from zhigou_toolchain.modeling.five_stage.prompts import source_catalogue
    cards, rows = fixture(2)
    with pytest.raises(ValueError, match="CATALOG_CHANGED"):
        context_view(cards, {"cards": [], "retrieval": rows})
    catalogue = source_catalogue()
    assert "ontology_io/prompt_views.py" in catalogue["source_files"]
    assert any(row["target"] == "GUIDE" and row["source"] == "ontology_io/prompt_views.py" for row in catalogue["dynamic_builders"])


def test_large_synthetic_reuse_request_fits_unchanged_32768_budget_without_truncation():
    cards, rows = fixture()
    captured = {}

    def capture(task, content, schema):
        view, changed = context_view(cards, content)
        captured.update(original=content, view=view, changed=changed, schema=schema)
        return len(json.dumps(view, ensure_ascii=False).encode()) + len((task + GUIDE).encode()) + len(json.dumps(schema).encode()) + 2048 + 8192

    reserve = assistance.select_reuse(capture, terms=[c["label"] for c in cards], cards=cards, retrieval=rows, business_rules=[])
    assert reserve <= 32768 and len(expand_cards(captured["view"]["cards"])) == 39
    assert expand_retrieval(captured["view"]["cards"], captured["view"]["retrieval"]) == rows
    assert captured["schema"]["properties"]["decisions"]["items"]["properties"]["existing_iri"]["enum"] == [None, *sorted(c["iri"] for c in cards)]


def test_columnar_catalog_preserves_metadata_and_optional_field_presence():
    cards, _ = fixture(3)
    assert expand_cards(compact_cards(cards)) == cards
    cards[0]["optional"] = None
    packed = compact_cards(cards)
    assert isinstance(packed, list) and expand_cards(packed) == cards
    assert "optional" not in expand_cards(packed)[1]
