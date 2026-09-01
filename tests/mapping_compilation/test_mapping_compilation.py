from __future__ import annotations

import pytest
from prompt05_support import candidate
from rdflib import OWL, RDF, Graph, URIRef

from kg_mnp.semantic_kernel.mapping import compile_mapping_plan


def _tbox() -> Graph:
    graph = Graph()
    graph.add((URIRef("urn:test:Class"), RDF.type, OWL.Class))
    graph.add((URIRef("urn:test:name"), RDF.type, OWL.DatatypeProperty))
    graph.add((URIRef("urn:test:knows"), RDF.type, OWL.ObjectProperty))
    return graph


def test_mapping_plan_is_declarative_complete_and_deterministic() -> None:
    values = [
        candidate("RECORD_TO_CLASS", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", target_iri="urn:test:Class"),
        candidate("FIELD_TO_DATA_PROPERTY", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", ordinal=1, target_iri="urn:test:name", conversion_policy="TRIM", null_policy="OMIT"),
        candidate("REFERENCE_TO_OBJECT_PROPERTY", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", ordinal=2, target_iri="urn:test:knows"),
        candidate("VALUE_MAPPING", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", ordinal=3, values=["A=alpha", "B=beta"]),
        candidate("IRI_TEMPLATE", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", ordinal=4, values=["urn:test:entity:{id}"]),
        candidate("NULL_HANDLING_POLICY", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", ordinal=5, null_policy="REJECT"),
    ]
    kwargs = {"source_plan_id": "urn:kg-mnp:semantic-compilation-plan:" + "3" * 64, "review_decision_id": "urn:kg-mnp:ontology-review-decision-log:" + "4" * 64, "effective_tbox": _tbox()}
    first = compile_mapping_plan(values, **kwargs)
    second = compile_mapping_plan(list(reversed(values)), **kwargs)
    assert first == second
    assert first["execution_policy"] == "DECLARATIVE_NOT_EXECUTED"
    assert first["mapping_count"] == 6


@pytest.mark.parametrize("template", ["urn:test:{obj.attr}", "urn:test:{fn()}", "$(whoami)", "python:exec"])
def test_mapping_template_rejects_code_and_expression_surfaces(template: str) -> None:
    value = candidate("IRI_TEMPLATE", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", values=[template])
    with pytest.raises(ValueError, match="unsafe"):
        compile_mapping_plan([value], source_plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64, review_decision_id="urn:kg-mnp:ontology-review-decision-log:" + "4" * 64, effective_tbox=_tbox())


def test_mapping_rejects_wrong_target_type_and_duplicate_value_keys() -> None:
    wrong = candidate("FIELD_TO_DATA_PROPERTY", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", target_iri="urn:test:Class")
    with pytest.raises(ValueError, match="wrong semantic type"):
        compile_mapping_plan([wrong], source_plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64, review_decision_id="urn:kg-mnp:ontology-review-decision-log:" + "4" * 64, effective_tbox=_tbox())
    duplicate = candidate("VALUE_MAPPING", candidate_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING", values=["A=one", "A=two"])
    with pytest.raises(ValueError, match="duplicate"):
        compile_mapping_plan([duplicate], source_plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64, review_decision_id="urn:kg-mnp:ontology-review-decision-log:" + "4" * 64, effective_tbox=_tbox())
