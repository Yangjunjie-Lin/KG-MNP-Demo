from __future__ import annotations

import pytest

from kg_mnp.modeling.control_plane.conflicts import detect_conflicts
from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.providers.models import candidate_body
from kg_mnp.modeling.control_plane.security import validate_iri


@pytest.mark.parametrize("iri", ["file:///tmp/x", "javascript:alert(1)", "data:text/plain,x", "ftp://x"])
def test_invalid_iri_schemes_are_rejected(iri: str) -> None:
    with pytest.raises(ModelingControlError, match="scheme|filesystem"):
        validate_iri(iri, creating=True)


def test_reserved_namespace_cannot_be_redefined_but_standard_reference_is_read_only() -> None:
    standard = "http://www.w3.org/2001/XMLSchema#string"
    validate_iri(standard, creating=False)
    with pytest.raises(ModelingControlError, match="read-only"):
        validate_iri(standard, creating=True, allowed_schemes={"http", "https", "urn"})


def test_dependency_cycle_is_classified(prompt04_case: dict) -> None:
    first = dict(prompt04_case["proposal"]["abox_candidates"][0])
    second = dict(prompt04_case["proposal"]["abox_candidates"][1])
    first["dependency_candidate_refs"] = [second["candidate_id"]]
    second["dependency_candidate_refs"] = [first["candidate_id"]]
    assert any(item["code"] == "SUBCLASS_CYCLE" for item in detect_conflicts([first, second]))


def test_semantic_conflict_families_are_classified(prompt04_case: dict) -> None:
    template = prompt04_case["proposal"]["tbox_candidates"][0]

    def candidate(index: int, body: dict, kind: str = "TBOX") -> dict:
        value = dict(template)
        value["candidate_id"] = f"urn:kg-mnp:ontology-candidate:{index:064x}"
        value["candidate_kind"] = kind
        value["publication_scope"] = kind
        value["body"] = body
        return value

    property_iri = "urn:kg-mnp:project:test:property"
    subject_iri = "urn:kg-mnp:project:test:subject"
    predicate_iri = "urn:kg-mnp:project:test:predicate"
    rows = [
        candidate(1, candidate_body(candidate_type="DOMAIN_AXIOM", subject_iri=property_iri, object_iri="urn:kg-mnp:project:test:ClassA")),
        candidate(2, candidate_body(candidate_type="DOMAIN_AXIOM", subject_iri=property_iri, object_iri="urn:kg-mnp:project:test:ClassB")),
        candidate(3, candidate_body(candidate_type="RANGE_AXIOM", subject_iri=property_iri, object_iri="http://www.w3.org/2001/XMLSchema#string")),
        candidate(4, candidate_body(candidate_type="RANGE_AXIOM", subject_iri=property_iri, object_iri="http://www.w3.org/2001/XMLSchema#integer")),
        candidate(5, candidate_body(candidate_type="MIN_COUNT", target_iri=subject_iri, predicate_iri=predicate_iri, integer_value=2), "SHACL"),
        candidate(6, candidate_body(candidate_type="MAX_COUNT", target_iri=subject_iri, predicate_iri=predicate_iri, integer_value=1), "SHACL"),
        candidate(7, candidate_body(candidate_type="DATA_PROPERTY_ASSERTION", subject_iri=subject_iri, predicate_iri=predicate_iri, literal={"lexical_value": "1", "datatype_iri": "http://www.w3.org/2001/XMLSchema#integer", "language": None}), "ABOX"),
        candidate(8, candidate_body(candidate_type="DATA_PROPERTY_ASSERTION", subject_iri=subject_iri, predicate_iri=predicate_iri, literal={"lexical_value": "one", "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None}), "ABOX"),
    ]
    codes = {item["code"] for item in detect_conflicts(rows)}
    assert {
        "DOMAIN_CONFLICT",
        "RANGE_CONFLICT",
        "CARDINALITY_CONFLICT",
        "DATATYPE_CONFLICT",
        "LITERAL_CONFLICT",
        "EVIDENCE_CONTRADICTION",
    } <= codes
