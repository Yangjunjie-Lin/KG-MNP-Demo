"""TM Forum mapping and source manifest tests."""

from kg_mnp_demo.mappings import (
    load_mappings,
    load_source_manifest,
    validate_mapping_structure,
)


REQUIRED_SOURCES = [
    "Point-Topic/cto-ontology",
    "tmforum-apis/TMF629_CustomerManagement",
    "tmforum-apis/TMF637_ProductInventory",
    "tmforum-apis/TMF620_ProductCatalog",
    "RDFLib/rdflib",
    "RDFLib/pySHACL",
    "RDFLib/OWL-RL",
    "protegeproject/protege",
    "dgarijo/WIDOCO",
]


def test_mapping_structure_valid():
    mappings = load_mappings()
    assert len(mappings) >= 6
    for m in mappings:
        errors = validate_mapping_structure(m)
        assert not errors, (m.get("id"), errors)


def test_core_concepts_have_tmf_basis():
    mappings = load_mappings()
    targets = {m["target_term"] for m in mappings if m.get("in_mvp")}
    assert "mnp:Subscriber" in targets
    assert "mnp:ServiceSubscription" in targets
    assert "mnp:TelecomService" in targets


def test_no_exact_mapping_for_tmf_json_objects():
    for m in load_mappings():
        assert m["mapping_type"] in {"related", "broader", "narrower", "exact"}
        # JSON schema objects should not be claimed exact for core entities
        if m["target_term"] in {
            "mnp:Subscriber",
            "mnp:ServiceSubscription",
            "mnp:TelecomService",
        }:
            assert m["mapping_type"] != "exact"


def test_source_manifest_contains_required():
    sources = load_source_manifest()
    names = {s["name"] for s in sources}
    for required in REQUIRED_SOURCES:
        assert required in names, required


def test_runtime_dependencies_have_licenses():
    sources = load_source_manifest()
    runtime = [s for s in sources if s.get("runtime_dependency") is True]
    assert runtime
    for s in runtime:
        assert s.get("license"), s["name"]


def test_cto_is_conceptual_reference_only():
    sources = {s["name"]: s for s in load_source_manifest()}
    cto = sources["Point-Topic/cto-ontology"]
    assert cto["runtime_dependency"] is False
    assert cto["reuse_mode"] == "conceptual_reference"
    assert cto["local_path"] in (None, "null", "") or cto["local_path"] is None
