from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.workbench.view_model import (
    assert_view_model_fidelity,
    build_view_model,
)

from ._helpers import ENTITY, iri, literal, query_result, row


def exact_result():
    parameters = {
        "subject": ENTITY,
        "predicate": "urn:kg-mnp:predicate:test",
        "object": {
            "term_type": "LITERAL",
            "value": "active",
            "datatype_iri": "urn:datatype:test",
            "language": "en",
        },
        "limit": 100,
        "offset": 0,
    }
    result = query_result(
        "provenance.fact",
        parameters,
        ["businessGraph", "subject", "predicate", "object"],
        [
            row(
                businessGraph=iri("urn:kg-mnp:graph:test"),
                subject=iri(ENTITY),
                predicate=iri("urn:kg-mnp:predicate:test"),
                object=literal("active", "urn:datatype:test", "en"),
            )
        ],
    )
    return result


def test_view_model_is_deterministic_and_excludes_runtime_metadata() -> None:
    first_result = exact_result()
    second_result = copy.deepcopy(first_result)
    second_result["runtime_metadata"] = {
        "duration_ms": 999.0,
        "served_at": "2026-08-10T12:00:00Z",
    }
    first = build_view_model(first_result, view_type="FACT_TRACE")
    second = build_view_model(second_result, view_type="FACT_TRACE")
    assert first == second
    assert "runtime_metadata" not in first
    assert_view_model_fidelity(first_result, first)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda model: model["rows"].clear(),
        lambda model: model["rows"][0]["bindings"][-1]["term"].pop("datatype_iri"),
        lambda model: model["rows"][0]["bindings"][-1]["term"].pop("language"),
        lambda model: model.update(source_result_hash="0" * 64),
        lambda model: model.update(publication_id="urn:attacker"),
    ],
)
def test_semantic_presentation_attacks_are_detected(mutation) -> None:
    result = exact_result()
    model = build_view_model(result, view_type="FACT_TRACE")
    mutation(model)
    with pytest.raises(ValueError, match="fidelity"):
        assert_view_model_fidelity(result, model)
