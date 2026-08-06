import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError
from rdflib import Graph, URIRef, XSD

from kg_mnp_demo.compilation.abox_compiler import _literal
from kg_mnp_demo.compilation.compiler import CompilationError, build_artifact_set
from kg_mnp_demo.compilation.identifiers import artifact_id, compilation_id
from kg_mnp_demo.compilation.manifest import (
    compilation_manifest_hash,
    json_bytes,
    json_semantic_hash,
    rdf_semantic_hash,
)
from kg_mnp_demo.compilation.rdf_canonical import canonical_ntriples
from kg_mnp_demo.compilation.validator import CompilationValidationError, validate_compilation_package_against_authorities
from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.review_identifiers import (
    confirmed_item_id,
    confirmed_package_id,
    package_semantic_hash,
)
from ._helpers import authorities, build


def _rehash_manifest(manifest: dict) -> None:
    digest = compilation_manifest_hash(manifest)
    manifest["compilation_semantic_hash"] = digest
    manifest["compilation_id"] = compilation_id(digest)
    assert manifest["compilation_semantic_hash"] == compilation_manifest_hash(manifest)


def _rehash_artifact_and_manifest(directory: Path, relative: str, data: bytes) -> None:
    artifact_path = directory / relative
    artifact_path.write_bytes(data)
    manifest_path = directory / "compilation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(
        item for item in manifest["artifact_manifest"]
        if item["relative_path"] == relative
    )
    record["byte_sha256"] = hashlib.sha256(data).hexdigest()
    record["size_bytes"] = len(data)
    suffix = artifact_path.suffix
    record["semantic_sha256"] = (
        json_semantic_hash(data)
        if suffix == ".json"
        else rdf_semantic_hash(data, suffix)
    )
    record_without_id = {key: value for key, value in record.items() if key != "artifact_id"}
    record["artifact_id"] = artifact_id(record_without_id)
    assert record["byte_sha256"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    _rehash_manifest(manifest)
    manifest_path.write_bytes(json_bytes(manifest))


def _tamper_shacl_report(payload: dict) -> None:
    payload.update({"conforms": False, "status": "VIOLATION", "violation_count": 1})
    content = {key: value for key, value in payload.items() if key != "report_id"}
    payload["report_id"] = "urn:kg-mnp:shacl-report:" + semantic_hash(content)


def _tamper_consistency_report(payload: dict) -> None:
    payload.update({"consistent": False, "status": "INCONSISTENT", "exit_code": 1})


def _tamper_source_package(payload: dict) -> None:
    payload["publication_manifest"]["compile_allowed"] = False
    digest = package_semantic_hash(payload)
    payload["package_semantic_hash"] = digest
    payload["package_id"] = confirmed_package_id(digest)
    assert payload["package_semantic_hash"] == package_semantic_hash(payload)


def _rehash_package_payload(payload: dict) -> None:
    digest = package_semantic_hash(payload)
    payload["package_semantic_hash"] = digest
    payload["package_id"] = confirmed_package_id(digest)
    assert payload["package_semantic_hash"] == package_semantic_hash(payload)


def _tampered_json(directory: Path, relative: str, mutate) -> bytes:
    payload = json.loads((directory / relative).read_text(encoding="utf-8"))
    mutate(payload)
    return json_bytes(payload)


def test_blocked_package_fails_closed():
    values = list(authorities("deferred-review"))
    with pytest.raises((CompilationError, ValueError)):
        build_artifact_set(*values)


def test_dataset_artifact_rehash_forgery_is_rejected(tmp_path):
    directory, _, _ = build(tmp_path)
    dataset = directory / "rdf" / "dataset.nq"
    _rehash_artifact_and_manifest(directory, "rdf/dataset.nq", dataset.read_bytes() + b"\n")
    with pytest.raises(CompilationValidationError):
        validate_compilation_package_against_authorities(directory, *authorities())


@pytest.mark.parametrize(
    ("relative", "mutate"),
    [
        ("shacl/report.json", _tamper_shacl_report),
        ("reasoner/owl-consistency-report.json", _tamper_consistency_report),
        ("source/confirmed-modeling-package.json", _tamper_source_package),
    ],
    ids=["shacl-report", "owl-consistency-report", "source-package"],
)
def test_rehashed_authoritative_artifact_forgery_is_rejected(tmp_path, relative, mutate):
    directory, _, _ = build(tmp_path)
    data = _tampered_json(directory, relative, mutate)
    _rehash_artifact_and_manifest(directory, relative, data)
    with pytest.raises(CompilationValidationError):
        validate_compilation_package_against_authorities(directory, *authorities())


def test_manifest_rehash_forgery_is_rejected(tmp_path):
    directory, _, _ = build(tmp_path)
    manifest_path = directory / "compilation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["release_status"] = "UNVALIDATED"
    _rehash_manifest(manifest)
    manifest_path.write_bytes(json_bytes(manifest))
    with pytest.raises(CompilationValidationError):
        validate_compilation_package_against_authorities(directory, *authorities())


def test_missing_artifact_is_rejected(tmp_path):
    directory, _, _ = build(tmp_path)
    (directory / "rdf" / "abox.nt").unlink()
    with pytest.raises(CompilationValidationError, match="missing artifact"):
        validate_compilation_package_against_authorities(directory, *authorities())


def test_unexpected_artifact_is_rejected(tmp_path):
    directory, _, _ = build(tmp_path)
    (directory / "unexpected.txt").write_text("forged\n", encoding="utf-8")
    with pytest.raises(CompilationValidationError, match="unexpected artifact"):
        validate_compilation_package_against_authorities(directory, *authorities())


def test_direct_proposal_compilation_has_no_valid_entry_point():
    with pytest.raises((TypeError, ValueError, ValidationError)):
        build_artifact_set(authorities()[0], authorities()[1], authorities()[2], None, *authorities()[4:])


def test_cleaned_json_cannot_bypass_proposal_and_package_authorities():
    values = authorities()
    with pytest.raises((TypeError, ValueError, ValidationError)):
        build_artifact_set(values[0], None, None, None, *values[4:])


def test_review_log_cannot_bypass_confirmed_package_authority():
    values = authorities()
    with pytest.raises((TypeError, ValueError, ValidationError)):
        build_artifact_set(values[0], values[1], values[2], None, *values[4:])


def test_rehashed_blocked_package_cannot_forge_ready_authority():
    values = list(authorities("deferred-review"))
    package = copy.deepcopy(values[3])
    package["publication_manifest"]["package_status"] = "READY_FOR_COMPILATION"
    package["publication_manifest"]["compile_allowed"] = True
    digest = package_semantic_hash(package)
    package["package_semantic_hash"] = digest
    package["package_id"] = confirmed_package_id(digest)
    values[3] = package
    with pytest.raises((CompilationError, ValueError, ValidationError)):
        build_artifact_set(*values)


def test_rehashed_tbox_scope_injection_is_rejected():
    values = list(authorities())
    package = copy.deepcopy(values[3])
    package["confirmed_abox_decisions"][0]["publication_scope"] = "TBOX"
    _rehash_package_payload(package)
    values[3] = package
    with pytest.raises((CompilationError, ValueError, ValidationError)):
        build_artifact_set(*values)


def test_rehashed_mapping_assertion_injection_is_rejected():
    values = list(authorities())
    package = copy.deepcopy(values[3])
    item = package["confirmed_abox_decisions"][0]
    envelope = item["confirmed_candidate"]
    content = envelope["semantic_content"]
    content["candidate_kind"] = "MAPPING_ASSERTION"
    envelope["semantic_hash"] = semantic_hash(content)
    envelope["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=envelope["source_candidate_id"],
        effective_candidate_id=envelope["effective_candidate_id"],
        confirmation_mode=envelope["confirmation_mode"],
        semantic_content=content,
    )
    _rehash_package_payload(package)
    values[3] = package
    with pytest.raises((CompilationError, ValueError, ValidationError)):
        build_artifact_set(*values)


def test_rdf_injection_text_remains_one_literal_triple():
    value = '" . <urn:injected:s> <urn:injected:p> <urn:injected:o> .\nnext'
    literal = _literal({"value": value, "datatype_iri": str(XSD.string)})
    data = canonical_ntriples([(URIRef("urn:s"), URIRef("urn:p"), literal)])
    graph = Graph()
    graph.parse(data=data.decode("utf-8"), format="nt")
    assert len(graph) == 1
    assert next(graph.objects(URIRef("urn:s"), URIRef("urn:p"))).toPython() == value
