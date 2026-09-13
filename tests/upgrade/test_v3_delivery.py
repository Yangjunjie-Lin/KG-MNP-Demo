import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from zhigou_toolchain.modeling.delivery.v3 import (
    DeliveryError,
    V3Delivery,
    package_bytes,
    read_zip,
)

REFERENCE = Path(__file__).resolve().parents[2] / "docs/reference/ontology-v3/ontology_delivery"


def reference_files():
    return {p.relative_to(REFERENCE).as_posix(): p.read_bytes() for p in REFERENCE.rglob("*") if p.is_file()}


def update_file(files, name, value):
    update_bytes(files, name, json.dumps(value, ensure_ascii=False).encode())


def update_bytes(files, name, raw):
    files[name] = raw
    manifest = json.loads(files["manifest.json"])
    for row in manifest["files"]:
        if row["path"] == name:
            row.update(bytes=len(files[name]), sha256=hashlib.sha256(files[name]).hexdigest())
    files["manifest.json"] = json.dumps(manifest).encode()


def test_real_v3_reference_reopens_schema_graph_provenance_query_and_shacl():
    files = reference_files()
    result = V3Delivery(files).inspect(run_shacl=True)
    assert result["status"] == "PASS" and result["shacl"]["status"] == "PASS"
    assert result["counts"]["assertions"] == 21 and result["counts"]["facts"] == 18
    assert result["owl"]["status"] == "NOT_RUN" and result["real_approval"]["status"] == "NOT_RUN"
    assert result["production_allowed"] is False
    assert read_zip(package_bytes(files)) == files


def test_digest_failure_does_not_become_semantic_pass():
    files = reference_files()
    files["model/instances.ttl"] += b"# changed"
    with pytest.raises(DeliveryError, match="FILE_DIGEST_MISMATCH"):
        V3Delivery(files).inspect()


def test_shapes_cannot_be_added_to_default_business_query_even_with_fresh_hashes():
    files = reference_files()
    contract = json.loads(files["integration/load_contract.json"])
    contract["query_dataset"]["include_roles"].append("shapes")
    update_file(files, "integration/load_contract.json", contract)
    with pytest.raises(DeliveryError, match="UNSUPPORTED_QUERY_DATASET"):
        V3Delivery(files).inspect()


@pytest.mark.parametrize("name", ["../manifest.json", "/manifest.json", "C:/manifest.json", "folder/../manifest.json"])
def test_zip_paths_rejected_without_writing_files(name):
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(name, b"{}")
    with pytest.raises(DeliveryError):
        read_zip(data.getvalue())


def test_incoming_schema_cannot_relax_pinned_contract():
    files = reference_files()
    update_file(files, "contracts/delivery.schema.json", {"type": "object"})
    with pytest.raises(DeliveryError, match="INCOMING_SCHEMA_NOT_PINNED"):
        V3Delivery(files).inspect()


def test_manifest_cannot_disable_validation_for_required_documents():
    files = reference_files()
    manifest = json.loads(files["manifest.json"])
    next(row for row in manifest["files"] if row["path"] == "data/facts.jsonl")["schema_ref"] = None
    files["manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(DeliveryError, match="REQUIRED_SCHEMA_BINDING_MISSING"):
        V3Delivery(files).inspect()


@pytest.mark.parametrize("change,code", [
    ({"mapping_rule_id": "missing"}, "ASSERTION_MAPPING_RULE_MISSING"),
    ({"transform_id": "unlocked@1"}, "ASSERTION_TRANSFORM_NOT_LOCKED"),
    ({"polarity": "NEGATIVE"}, "NON_POSITIVE_ASSERTION"),
    ({"conditional": True}, "NON_POSITIVE_ASSERTION"),
    ({"source_field": "department_id"}, "MAPPING_ATTRIBUTE_PREDICATE_MISMATCH"),
])
def test_assertion_semantic_closure_even_when_file_hashes_are_refreshed(change, code):
    files = reference_files()
    name = "provenance/assertions.jsonl"
    rows = [json.loads(line) for line in files[name].splitlines()]
    rows[1].update(change)
    update_bytes(files, name, b"\n".join(json.dumps(row).encode() for row in rows))
    with pytest.raises(DeliveryError, match=code):
        V3Delivery(files).inspect()


def test_orphan_assertion_does_not_disappear_from_accounting():
    files = reference_files()
    name = "provenance/assertions.jsonl"
    row = json.loads(files[name].splitlines()[0])
    row["assertion_id"] = "ORPHAN"
    update_bytes(files, name, files[name] + json.dumps(row).encode() + b"\n")
    with pytest.raises(DeliveryError, match="ORPHAN_ASSERTION"):
        V3Delivery(files).inspect()


@pytest.mark.parametrize("pointer", ["/-1", "/00", "/~2", "/999"])
def test_json_pointer_does_not_accept_python_negative_or_non_rfc_indices(pointer):
    from zhigou_toolchain.modeling.delivery.closure import resolve_pointer
    with pytest.raises(DeliveryError):
        resolve_pointer(["one"], pointer)


@pytest.mark.parametrize("query", [
    'SELECT ?s FROM <file:///private.ttl> WHERE { ?s ?p ?o }',
    'SELECT ?s WHERE { SERVICE <https://example.invalid/> { ?s ?p ?o } }',
    'PREFIX local: <file:///> SELECT ?s FROM local:private WHERE { ?s ?p ?o }',
])
def test_queries_cannot_read_external_files_or_network(query):
    from zhigou_toolchain.semantic_kernel.errors import SemanticKernelError
    files = reference_files()
    baseline = json.loads(files["acceptance/baseline.json"])
    update_bytes(files, baseline["query_ref"], query.encode())
    with pytest.raises(SemanticKernelError, match="unsafe"):
        V3Delivery(files).inspect()


def test_query_timeout_is_not_reported_as_answer_pass(monkeypatch):
    monkeypatch.setattr("zhigou_toolchain.modeling.delivery.v3._execute", lambda *args: ("TIMEOUT", None))
    with pytest.raises(DeliveryError, match="QUERY_TIMEOUT"):
        V3Delivery(reference_files()).inspect()


def test_shacl_timeout_is_not_promoted_to_pass(monkeypatch):
    monkeypatch.setattr("zhigou_toolchain.modeling.delivery.v3.shacl_check", lambda _: {"status": "TIMEOUT"})
    result = V3Delivery(reference_files()).inspect(run_shacl=True)
    assert result["status"] == "TIMEOUT" and result["shacl"]["status"] == "TIMEOUT"


def test_catalog_and_axioms_must_refer_to_actual_rdf():
    files = reference_files()
    name = "model/axioms.json"
    axioms = json.loads(files[name])
    axioms["items"][0]["subject"] = "urn:not-in-actual-ontology"
    update_file(files, name, axioms)
    with pytest.raises(DeliveryError, match="AXIOM_NOT_IN_RDF"):
        V3Delivery(files).inspect()
