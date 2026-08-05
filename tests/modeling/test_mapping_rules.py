"""Formal MappingRules are finite, versioned, and review-only inputs."""

from __future__ import annotations

import copy
import json

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.dependencies import (
    DependencyError,
    ROOT,
    load_mapping_rules,
    load_modeling_dependencies,
    validate_modeling_evidence_references,
)
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal
from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.selectors import validate_json_pointer
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_mapping_rules_semantics,
)
from kg_mnp_demo.modeling.transformations import TRANSFORMATION_IDS


TERM_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"


def _dependencies() -> dict:
    return load_modeling_dependencies()


def _validate(rules: dict, dependencies: dict) -> None:
    validate_mapping_rules_semantics(
        rules,
        dependencies["ontology_baseline"],
        dependencies["terminology_profile"],
        term_iris=dependencies["term_iris"],
    )


def test_formal_mapping_rules_validate_offline_and_are_versioned():
    dependencies = _dependencies()
    rules = dependencies["mapping_rules"]
    validate_contract("mapping-rules", rules)
    _validate(rules, dependencies)
    assert rules["contract_version"] == "1.0"
    assert rules["mapping_set_version"] == "1.0.0"
    assert all(rule["rule_version"] == "1.0.0" for rule in rules["rules"])


def test_rules_use_only_exact_json_pointers_and_finite_transforms():
    rules = _dependencies()["mapping_rules"]
    for rule in rules["rules"]:
        validate_json_pointer(rule["source_selector"])
        assert rule["source_selector"].startswith("/")
        assert rule["transformation_id"] in TRANSFORMATION_IDS
    serialized = json.dumps(rules, sort_keys=True).casefold()
    assert "eval" not in serialized
    assert "jsonpath" not in serialized
    assert "python" not in serialized


def test_rules_cover_the_frozen_stage04_terms_and_wire_entity_references():
    rules = _dependencies()["mapping_rules"]["rules"]
    targets = {rule["target_term_iri"].removeprefix(TERM_NS) for rule in rules}
    assert targets == {
        "Subscriber",
        "TelecomAccount",
        "ServiceSubscription",
        "billedThrough",
        "subscriptionStatusCode",
    }
    by_id = {rule["rule_id"]: rule for rule in rules}
    for rule in rules:
        if rule["candidate_kind"] in {
            "CLASS_ASSERTION",
            "OBJECT_PROPERTY_ASSERTION",
            "DATA_PROPERTY_ASSERTION",
        }:
            assert by_id[rule["subject_entity_rule_id"]]["candidate_kind"] == "ENTITY"
        if rule["candidate_kind"] == "OBJECT_PROPERTY_ASSERTION":
            assert by_id[rule["object_entity_rule_id"]]["candidate_kind"] == "ENTITY"


def test_tmf_alignment_remains_reference_only_modeling_evidence():
    dependencies = _dependencies()
    references = {
        reference
        for rule in dependencies["mapping_rules"]["rules"]
        for reference in rule["modeling_evidence_refs"]
    }
    assert any(value.startswith("mappings/tmf_to_mnp.yaml#") for value in references)
    tmf_reference = (ROOT / "mappings" / "tmf_to_mnp.yaml").read_text(
        encoding="utf-8"
    )
    assert "source_path: components.schemas." in tmf_reference
    assert "transformation_id:" not in tmf_reference
    assert "source_selector:" not in tmf_reference


def test_all_modeling_evidence_references_resolve_offline():
    rules = _dependencies()["mapping_rules"]
    validate_modeling_evidence_references(rules)
    invalid = copy.deepcopy(rules)
    invalid["rules"][0]["modeling_evidence_refs"] = [
        "mappings/tmf_to_mnp.yaml#DOES-NOT-EXIST"
    ]
    with pytest.raises(DependencyError, match="unknown modeling evidence fragment"):
        validate_modeling_evidence_references(invalid)


def test_deprecated_rule_is_not_executed():
    dependencies = _dependencies()
    rules = copy.deepcopy(dependencies["mapping_rules"])
    deprecated = copy.deepcopy(rules["rules"][0])
    deprecated["rule_id"] = "deprecated-subscriber-copy"
    deprecated["status"] = "DEPRECATED"
    rules["rules"].append(deprecated)
    _validate(rules, dependencies)

    cleaned = json.loads(
        (ROOT / "examples" / "modeling" / "inputs" / "partial-basic.json").read_text(
            encoding="utf-8"
        )
    )
    proposal = generate_modeling_proposal(
        cleaned,
        dependencies["ontology_baseline"],
        rules,
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        term_iris=set(dependencies["term_iris"]),
    )
    used_rule_ids = {
        rule_id
        for candidate in [
            *proposal["candidate_entities"],
            *proposal["candidate_assertions"],
        ]
        for rule_id in candidate["mapping_rule_ids"]
    }
    assert "deprecated-subscriber-copy" not in used_rule_ids


def test_unknown_transform_fails_closed():
    dependencies = _dependencies()
    rules = copy.deepcopy(dependencies["mapping_rules"])
    rules["rules"][0]["transformation_id"] = "EXECUTE_TEXT"
    with pytest.raises((ValidationError, SemanticValidationError)):
        _validate(rules, dependencies)


def test_unknown_target_term_fails_closed():
    dependencies = _dependencies()
    rules = copy.deepcopy(dependencies["mapping_rules"])
    rules["rules"][0]["target_term_iri"] = "https://invalid.example/ontology#Unknown"
    with pytest.raises(SemanticValidationError, match="absent from ontology baseline"):
        _validate(rules, dependencies)


def test_duplicate_rule_id_fails_closed():
    dependencies = _dependencies()
    rules = copy.deepcopy(dependencies["mapping_rules"])
    duplicate = copy.deepcopy(rules["rules"][0])
    rules["rules"].append(duplicate)
    with pytest.raises(SemanticValidationError, match="duplicate rule_id"):
        _validate(rules, dependencies)


def test_missing_rule_version_fails_contract_validation():
    rules = copy.deepcopy(_dependencies()["mapping_rules"])
    del rules["rules"][0]["rule_version"]
    with pytest.raises(ValidationError):
        validate_contract("mapping-rules", rules)


def test_rule_contract_can_explicitly_choose_null_handling():
    rules = copy.deepcopy(_dependencies()["mapping_rules"])
    rules["rules"][-1]["allow_null"] = True
    validate_contract("mapping-rules", rules)


def test_yaml_dependency_loader_rejects_duplicate_keys(tmp_path):
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        'contract_version: "1.0"\ncontract_version: "2.0"\n',
        encoding="utf-8",
    )
    with pytest.raises(DependencyError, match="duplicate key"):
        load_mapping_rules(duplicate)
