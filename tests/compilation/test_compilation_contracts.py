import copy
import json
from pathlib import Path

import pytest

from kg_mnp_demo.compilation.contracts import (
    COMPILATION_CONTRACT_SPECS,
    CompilationContractError,
    load_compilation_schema,
    validate_compilation_contract,
)


ROOT = Path(__file__).resolve().parents[2]


def test_compilation_contracts_have_unique_stable_ids():
    ids = [spec.schema_id for spec in COMPILATION_CONTRACT_SPECS]
    assert len(ids) == len(set(ids))
    assert all(load_compilation_schema(spec.name)["$id"] == spec.schema_id for spec in COMPILATION_CONTRACT_SPECS)


def test_compilation_common_definitions_are_closed_and_reusable():
    schema = load_compilation_schema("common")
    assert schema["additionalProperties"] is False
    for name in ("SHA256", "StableURN", "AbsoluteIRI", "RDFTerm", "ArtifactRecord", "GraphIRIManifest", "SHACLResult"):
        assert name in schema["$defs"]
        assert schema["$defs"][name].get("additionalProperties", False) is False


def test_compilation_manifest_schema_closed():
    manifest = json.loads(
        (ROOT / "examples/compilation/expected/full-confirmation/compilation-manifest.json")
        .read_text(encoding="utf-8")
    )
    schema = load_compilation_schema("compilation-manifest")
    assert schema["additionalProperties"] is False
    required = {
        "contract_version", "compilation_id", "compilation_semantic_hash",
        "compiler_policy_id", "compiler_policy_version", "compiler_policy_hash",
        "compiler_version", "source_package_id", "source_package_semantic_hash",
        "source_proposal_id", "source_proposal_hash", "source_review_decision_log_id",
        "source_review_decision_log_hash", "ontology_baseline_id", "ontology_version",
        "ontology_release_source_hash", "graph_iris", "artifact_manifest",
        "asserted_fact_count", "inferred_fact_count", "inference_materialized",
        "provenance_record_count", "review_record_count", "shacl_status",
        "shacl_violation_count", "shacl_warning_count", "shacl_info_count",
        "owl_consistency_status", "release_status",
    }
    assert required <= set(schema["required"])
    validate_compilation_contract("compilation-manifest", manifest)

    forged = copy.deepcopy(manifest)
    forged["unexpected"] = True
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("compilation-manifest", forged)
    forged = copy.deepcopy(manifest)
    forged["graph_iris"]["unexpected"] = "urn:kg-mnp:graph:unexpected"
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("compilation-manifest", forged)
    forged = copy.deepcopy(manifest)
    forged["artifact_manifest"][0]["unexpected"] = True
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("compilation-manifest", forged)
    forged = copy.deepcopy(manifest)
    forged.pop("source_proposal_hash")
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("compilation-manifest", forged)


def test_artifact_record_rejects_absolute_and_parent_paths_semantically():
    manifest = json.loads(
        (ROOT / "examples/compilation/expected/full-confirmation/compilation-manifest.json")
        .read_text(encoding="utf-8")
    )
    for unsafe in ("C:/outside.json", "/outside.json", "nested/../outside.json"):
        forged = copy.deepcopy(manifest)
        forged["artifact_manifest"][0]["relative_path"] = unsafe
        with pytest.raises(CompilationContractError, match="relative_path"):
            validate_compilation_contract("compilation-manifest", forged)


def test_artifact_manifest_unique_identity_and_rdf_count_semantics():
    manifest = json.loads(
        (ROOT / "examples/compilation/expected/full-confirmation/compilation-manifest.json")
        .read_text(encoding="utf-8")
    )
    for field in ("relative_path", "artifact_id"):
        forged = copy.deepcopy(manifest)
        forged["artifact_manifest"][1][field] = forged["artifact_manifest"][0][field]
        with pytest.raises(CompilationContractError, match=f"duplicate.*{field}"):
            validate_compilation_contract("compilation-manifest", forged)
    forged = copy.deepcopy(manifest)
    forged["artifact_manifest"][0]["quad_count"] = 0
    with pytest.raises(CompilationContractError, match="triple_count and quad_count"):
        validate_compilation_contract("compilation-manifest", forged)


def test_shacl_result_schema_closed():
    schema = load_compilation_schema("shacl-validation-report")
    assert schema["additionalProperties"] is False
    assert "$ref" in str(schema)
    result = {
        "result_id": "urn:kg-mnp:shacl-result:" + "b" * 64,
        "focus_node": {"term_type": "IRI", "value": "urn:kg-mnp:test:focus"},
        "result_path": None,
        "value": {
            "term_type": "LITERAL",
            "lexical_form": "INVALID",
            "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
            "language": None,
        },
        "source_shape": None,
        "source_constraint_component": None,
        "severity": {"term_type": "IRI", "value": "http://www.w3.org/ns/shacl#Warning"},
        "message": "warning",
    }
    report = {
        "report_id": "urn:kg-mnp:shacl-report:" + "a" * 64,
        "conforms": True,
        "status": "CONFORMS",
        "results": [result],
        "violation_count": 0,
        "warning_count": 1,
        "info_count": 0,
        "profile_bundle_hash": "c" * 64,
    }
    validate_compilation_contract("shacl-validation-report", report)
    forged = copy.deepcopy(report)
    forged["results"][0]["unknown"] = "rejected"
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("shacl-validation-report", forged)
    forged = copy.deepcopy(report)
    forged["warning_count"] = 0
    with pytest.raises(CompilationContractError, match="warning_count"):
        validate_compilation_contract("shacl-validation-report", forged)


def test_owl_consistency_contract_has_conditional_status_semantics():
    schema = load_compilation_schema("owl-consistency-report")
    assert "hermit_dependency_version" in schema["required"]
    base = {
        "status": "CONSISTENT", "consistent": True, "reasoner": "HermiT",
        "robot_version": "1.9.7", "robot_jar_sha256": "a" * 64,
        "ontology_release_source_hash": "b" * 64, "abox_semantic_hash": "c" * 64,
        "combined_input_semantic_hash": "d" * 64, "source_package_hash": "e" * 64,
        "hermit_dependency_version": "1.4.5.456", "exit_code": 0,
    }
    validate_compilation_contract("owl-consistency-report", base)
    forged = copy.deepcopy(base)
    forged["consistent"] = False
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("owl-consistency-report", forged)
