import pytest

from kg_mnp.integrations.object_query import query_objects


def test_actual_package_object_query_is_bounded_and_typed(prompt05_case):
    package = prompt05_case["result"].package_directory
    iri = "https://yangjunjie-lin.github.io/KG-MNP-Demo/domain-packs/minimal/terms#Entity"
    first = query_objects(package, class_iri=iri, limit=1)
    assert first["rows"] and first["execution"]["isolated"] is True
    instance = query_objects(package, instance_iri=first["rows"][0]["iri"])
    assert any(row["object"]["term_type"] == "LITERAL" for row in instance["rows"])
    assert all("datatype" in row["object"] and "language" in row["object"] for row in instance["rows"] if row["object"]["term_type"] == "LITERAL")
    paged = [query_objects(package, instance_iri=first["rows"][0]["iri"], offset=index, limit=1)["rows"][0] for index in range(len(instance["rows"]))]
    assert paged == instance["rows"]
    assert query_objects(package, class_iri=iri, offset=1000)["rows"] == []


@pytest.mark.parametrize("value", ['urn:test> } SERVICE <https://example.invalid> { ?s ?p ?o', 'relative', 'urn:test\n'])
def test_query_selector_cannot_inject_sparql(tmp_path, value):
    with pytest.raises(ValueError, match="invalid absolute object IRI"):
        query_objects(tmp_path, class_iri=value)


def test_query_timeout_is_not_empty_success(prompt05_case, monkeypatch):
    monkeypatch.setattr("kg_mnp.integrations.object_query._execute", lambda *args: ("TIMEOUT", None))
    with pytest.raises(TimeoutError):
        query_objects(prompt05_case["result"].package_directory, instance_iri="urn:synthetic:instance")
