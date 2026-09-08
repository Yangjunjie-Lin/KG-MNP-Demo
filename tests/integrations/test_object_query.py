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


def test_object_query_uses_the_exact_verified_bytes_if_live_package_changes(prompt05_case, monkeypatch):
    import json

    from rdflib import RDF, Dataset, URIRef

    from kg_mnp.integrations import object_query
    from kg_mnp.semantic_kernel.packaging import archive
    from kg_mnp.semantic_kernel.packaging.verifier import verify_package

    package = prompt05_case["result"].package_directory
    path = package / "dataset/dataset.nq"
    original = path.read_bytes()
    manifest = json.loads((package / "dataset/rdf-dataset-manifest.json").read_bytes())
    graph_iri = next(item["graph_iri"] for item in manifest["graphs"] if item["role"] == "abox")
    dataset = Dataset()
    dataset.parse(data=original.decode(), format="nquads")
    subject = str(next(dataset.graph(URIRef(graph_iri)).subjects(RDF.type, None)))
    tamper = f'<{subject}> <urn:unverified:predicate> "UNVERIFIED" <{graph_iri}> .\n'.encode()
    calls = []

    def verify_then_change_live_files(snapshot):
        result = verify_package(snapshot)
        calls.append(snapshot)
        path.write_bytes(original + tamper)
        return result

    # Cover the old imported verifier and the shared snapshot path, without
    # simulating successful validation: both delegate to the real verifier.
    monkeypatch.setattr(object_query, "verify_package", verify_then_change_live_files, raising=False)
    monkeypatch.setattr(archive, "verify_package", verify_then_change_live_files)
    try:
        result = query_objects(package, instance_iri=subject)
        assert len(calls) == 1
        assert not any(row["predicate"] == "urn:unverified:predicate" for row in result["rows"])
    finally:
        path.write_bytes(original)
