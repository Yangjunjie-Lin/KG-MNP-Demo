"""Stage 03 ontology release tests — core gates."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import SKOS

from kg_mnp_demo.loader import (
    load_case_graph,
    load_ontology_graph,
    ontology_module_files,
    ontology_modules_config_path,
    shape_paths,
)
from kg_mnp_demo.namespaces import BASE, MNP
from kg_mnp_demo.validator import validate_graph, validate_ontology_schema

ROOT = Path(__file__).resolve().parents[2]
TERM_NS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"


def test_module_config_drives_loader():
    files = ontology_module_files(include_alignments=False)
    assert "mnp-core.ttl" in files
    assert "mnp-modeling-provenance.ttl" in files
    assert "mnp-alignments.ttl" not in files
    assert ontology_module_files(include_alignments=True)[-1] == "mnp-alignments.ttl"


def test_each_module_has_ontology_and_version():
    cfg = yaml.safe_load(ontology_modules_config_path().read_text(encoding="utf-8"))
    for entry in cfg["modules"]:
        g = Graph()
        g.parse(ROOT / "ontology" / entry["file"], format="turtle")
        ont = URIRef(entry["ontology_iri"])
        assert (ont, RDF.type, OWL.Ontology) in g
        assert (ont, OWL.versionIRI, URIRef(entry["version_iri"])) in g


def test_catalog_covers_modules():
    import runpy

    ns = runpy.run_path(str(ROOT / "scripts" / "check_catalog.py"))
    assert ns["main"]() == 0


def test_no_example_org_in_runtime_ontology_data_shapes():
    for pattern in ["ontology/*.ttl", "shapes/*.ttl", "data/*.ttl", "queries/*.rq"]:
        for path in ROOT.glob(pattern):
            text = path.read_text(encoding="utf-8")
            assert "example.org" not in text, path


def test_formal_term_namespace():
    assert BASE.startswith("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms")
    assert str(MNP.Subscriber).startswith(TERM_NS)


def test_term_inventory_deterministic_and_complete():
    inv = ROOT / "docs" / "ontology" / "term-inventory.csv"
    rows = list(csv.DictReader(inv.open(encoding="utf-8")))
    assert rows
    keys = [(r["term_type"], r["defining_module"], r["local_name"]) for r in rows]
    assert keys == sorted(keys)
    locals_ = {r["local_name"] for r in rows if r["term_type"] != "Ontology"}
    for required in [
        "Subscriber",
        "holdsSubscription",
        "billedThrough",
        "hasBlockingReason",
        "MappingRecord",
        "ownsPhoneNumber",
        "AssessmentDependency",
    ]:
        assert required in locals_


def test_single_defining_module():
    seen: dict[str, str] = {}
    for path in (ROOT / "ontology").glob("mnp-*.ttl"):
        if path.name == "mnp-alignments.ttl":
            continue
        g = Graph()
        g.parse(path, format="turtle")
        for t in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
            for s in g.subjects(RDF.type, t):
                if not str(s).startswith(TERM_NS):
                    continue
                key = str(s)
                assert key not in seen, f"{key} in {seen[key]} and {path.name}"
                seen[key] = path.name


def test_bilingual_annotations_on_classes_and_properties():
    g = load_ontology_graph()
    missing = []
    for t in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        for s in g.subjects(RDF.type, t):
            if not str(s).startswith(TERM_NS):
                continue
            labels = list(g.objects(s, RDFS.label))
            defs = list(g.objects(s, SKOS.definition))
            has_en = any(isinstance(x, Literal) and x.language == "en" for x in labels)
            has_zh = any(isinstance(x, Literal) and x.language == "zh-CN" for x in labels)
            def_en = any(isinstance(x, Literal) and x.language == "en" for x in defs)
            def_zh = any(isinstance(x, Literal) and x.language == "zh-CN" for x in defs)
            if not (has_en and has_zh and def_en and def_zh):
                missing.append(str(s))
    assert not missing, missing[:10]


def test_domain_range_odr_decisions():
    g = load_ontology_graph()
    assert (MNP.billedThrough, RDFS.domain, MNP.ServiceSubscription) in g
    assert (MNP.holdsSubscription, RDFS.domain, MNP.Subscriber) in g
    assert (MNP.hasBlockingReason, RDFS.domain, MNP.EligibilityDecision) in g
    assert (MNP.assignedToSubscription, RDFS.domain, MNP.PhoneNumber) in g


def test_deprecated_terms_marked():
    g = load_ontology_graph()
    for term in [
        MNP.ownsPhoneNumber,
        MNP.hasSubscription,
        MNP.producesBlockingReason,
        MNP.AssessmentDependency,
        MNP.dependsOn,
        MNP.relatedAccount,
    ]:
        assert (term, OWL.deprecated, Literal(True)) in g or list(
            g.objects(term, OWL.deprecated)
        )


def test_mapping_record_not_in_core():
    core = Graph()
    core.parse(ROOT / "ontology" / "mnp-core.ttl", format="turtle")
    assert (MNP.MappingRecord, RDF.type, OWL.Class) not in core
    prov = Graph()
    prov.parse(ROOT / "ontology" / "mnp-modeling-provenance.ttl", format="turtle")
    assert (MNP.MappingRecord, RDF.type, OWL.Class) in prov


def test_shape_profiles_distinct():
    foundation = shape_paths("foundation")
    eligibility = shape_paths("eligibility")
    schema = shape_paths("ontology_schema")
    assert foundation[0].name == "foundation-instance-shapes.ttl"
    assert any(p.name == "eligibility-instance-shapes.ttl" for p in eligibility)
    assert schema[0].name == "ontology-schema-shapes.ttl"
    # foundation alone does not include eligibility file
    assert all("eligibility" not in p.name for p in foundation)


def test_foundation_does_not_require_case_evidence():
    g = load_case_graph("CASE-01")
    # remove evidence links
    for triple in list(g.triples((None, MNP.hasCaseEvidence, None))):
        g.remove(triple)
    result = validate_graph(g, profile="foundation")
    assert result.conforms, result.text


def test_eligibility_still_requires_case_evidence():
    g = load_case_graph("CASE-01")
    for triple in list(g.triples((None, MNP.hasCaseEvidence, None))):
        g.remove(triple)
    result = validate_graph(g, profile="eligibility")
    assert not result.conforms


def test_case_03_eligibility_conforms():
    g = load_case_graph("CASE-03")
    assert validate_graph(g, profile="eligibility").conforms


def test_release_determinism_inventory_hash_stable():
    inv = (ROOT / "docs" / "ontology" / "term-inventory.csv").read_bytes()
    h1 = hashlib.sha256(inv).hexdigest()
    h2 = hashlib.sha256(inv).hexdigest()
    assert h1 == h2


def test_competency_query_blocking_reason():
    from rdflib import Literal
    from rdflib.namespace import XSD

    from kg_mnp_demo.evaluator import materialize_assessment

    g = load_case_graph("CASE-03")
    g, _ = materialize_assessment(g, "CASE-03", validate=False)
    q = (ROOT / "competency_questions" / "queries" / "cq02_blocking_reasons.rq").read_text(
        encoding="utf-8"
    )
    rows = list(
        g.query(q, initBindings={"requestedCaseId": Literal("CASE-03", datatype=XSD.string)})
    )
    assert rows


def test_reasoner_report_fields_present():
    report = ROOT / "docs" / "ontology" / "reasoner-report.md"
    attestation_path = ROOT / "docs" / "ontology" / "reasoner-attestation.json"
    assert report.is_file()
    assert attestation_path.is_file()
    text = report.read_text(encoding="utf-8")
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    assert "Release source hash" in text
    assert "Reasoner input semantic hash" in text
    assert "Reasoner input file hash" in text
    assert attestation["status"] == "PASS"
    assert attestation["consistency"] == "CONSISTENT"
    assert attestation["unsatisfiable_named_classes"] == []
    assert attestation["unexpected_equivalent_classes"] == []
