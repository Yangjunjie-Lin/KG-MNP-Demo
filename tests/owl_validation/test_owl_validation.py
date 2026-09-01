from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.reasoner import run_hermit, verify_reasoner_bundle
from kg_mnp.semantic_kernel.snapshot import ROBOT_SHA256
from kg_mnp.semantic_kernel.validators.owl_consistency import check_owl_consistency
from kg_mnp.semantic_kernel.validators.owl_profile import validate_owl_profile

ROOT = Path(__file__).resolve().parents[2]
JAR = ROOT / "third_party" / "downloads" / "robot-1.9.7.jar"


def test_reasoner_bundle_is_pinned_and_unavailable_is_honest(tmp_path: Path) -> None:
    assert hashlib.sha256(JAR.read_bytes()).hexdigest() == ROBOT_SHA256
    assert verify_reasoner_bundle(JAR) == JAR.resolve()
    changed = tmp_path / "robot.jar"
    changed.write_bytes(JAR.read_bytes() + b"tamper")
    try:
        verify_reasoner_bundle(changed)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:  # pragma: no cover - explicit security assertion
        raise AssertionError("tampered reasoner bundle accepted")
    result = run_hermit(b"", reasoner_jar=None, timeout_seconds=1, max_output_bytes=1024)
    assert result["status"] == "REASONER_UNAVAILABLE"


def test_pinned_robot_profile_and_hermit_consistency() -> None:
    tbox = Graph()
    tbox.add((URIRef("urn:test:Class"), RDF.type, OWL.Class))
    profile = validate_owl_profile(tbox, baseline_digest="0" * 64, delta_digest="1" * 64, reasoner_jar=JAR, timeout_seconds=60)
    consistency = check_owl_consistency(baseline_graph=Graph(), tbox_graph=tbox, abox_graph=Graph(), reasoner_jar=JAR, timeout_seconds=60)
    assert profile["status"] == "PASSED"
    assert consistency["status"] == "CONSISTENT"
    assert consistency["robot_jar_sha256"] == ROBOT_SHA256


def test_disjoint_class_inconsistency_is_not_reported_as_consistent() -> None:
    left = URIRef("urn:test:Left")
    right = URIRef("urn:test:Right")
    entity = URIRef("urn:test:entity")
    tbox = Graph()
    for value in (left, right):
        tbox.add((value, RDF.type, OWL.Class))
    tbox.add((left, OWL.disjointWith, right))
    abox = Graph()
    abox.add((entity, RDF.type, left))
    abox.add((entity, RDF.type, right))
    report = check_owl_consistency(baseline_graph=Graph(), tbox_graph=tbox, abox_graph=abox, reasoner_jar=JAR, timeout_seconds=60)
    assert report["status"] == "INCONSISTENT"
    assert report["consistent"] is False


@pytest.mark.parametrize("conflict", ["functional", "irreflexive", "datatype"])
def test_additional_real_owl_inconsistencies_fail_closed(conflict: str) -> None:
    entity = URIRef("urn:test:entity")
    predicate = URIRef(f"urn:test:{conflict}")
    tbox = Graph()
    abox = Graph()
    if conflict == "functional":
        tbox.add((predicate, RDF.type, OWL.DatatypeProperty))
        tbox.add((predicate, RDF.type, OWL.FunctionalProperty))
        abox.add((entity, predicate, Literal("left")))
        abox.add((entity, predicate, Literal("right")))
    elif conflict == "irreflexive":
        tbox.add((predicate, RDF.type, OWL.ObjectProperty))
        tbox.add((predicate, RDF.type, OWL.IrreflexiveProperty))
        abox.add((entity, predicate, entity))
    else:
        tbox.add((predicate, RDF.type, OWL.DatatypeProperty))
        tbox.add((predicate, RDFS.range, XSD.integer))
        abox.add((entity, predicate, Literal("text", datatype=XSD.string)))
    report = check_owl_consistency(
        baseline_graph=Graph(),
        tbox_graph=tbox,
        abox_graph=abox,
        reasoner_jar=JAR,
        timeout_seconds=60,
    )
    assert report["status"] == "INCONSISTENT"
    assert report["consistent"] is False


def test_unsupported_owl_profile_is_rejected_before_execution() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        validate_owl_profile(
            Graph(),
            baseline_digest="0" * 64,
            delta_digest="1" * 64,
            requested_profile="OWL_FULL",
            reasoner_jar=JAR,
        )
