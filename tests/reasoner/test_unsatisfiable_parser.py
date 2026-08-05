from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import OWL, RDFS, Graph, URIRef

import run_reasoner as reasoner


def test_missing_unsatisfiable_report_is_an_error(tmp_path: Path):
    with pytest.raises(reasoner.UnsatisfiableReportError, match="missing"):
        reasoner.parse_unsatisfiable_file(tmp_path / "missing.txt")


def test_empty_report_has_no_unsatisfiable_named_classes(tmp_path: Path):
    report = tmp_path / "unsatisfiable.txt"
    report.write_text("", encoding="utf-8")
    assert reasoner.parse_unsatisfiable_file(report) == []


def test_only_owl_nothing_comments_and_headers_are_ignored(tmp_path: Path):
    report = tmp_path / "unsatisfiable.txt"
    report.write_text(
        "# generated report\nUnsatisfiable named classes:\nowl:Nothing\n",
        encoding="utf-8",
    )
    assert reasoner.parse_unsatisfiable_file(report) == []


def test_uri_and_curie_project_classes_are_parsed(tmp_path: Path):
    report = tmp_path / "unsatisfiable.txt"
    report.write_text(
        "mnp:ImpossibleOne\n"
        "<https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#ImpossibleTwo>\n",
        encoding="utf-8",
    )
    assert reasoner.parse_unsatisfiable_file(report) == [
        reasoner.TERM_NAMESPACE + "ImpossibleOne",
        reasoner.TERM_NAMESPACE + "ImpossibleTwo",
    ]


def test_multiple_unsatisfiable_classes_are_sorted_and_deduplicated(tmp_path: Path):
    report = tmp_path / "unsatisfiable.txt"
    report.write_text("mnp:Zed\nmnp:Alpha\nmnp:Zed\n", encoding="utf-8")
    assert reasoner.parse_unsatisfiable_file(report) == [
        reasoner.TERM_NAMESPACE + "Alpha",
        reasoner.TERM_NAMESPACE + "Zed",
    ]


def test_invalid_encoding_fails_closed(tmp_path: Path):
    report = tmp_path / "unsatisfiable.txt"
    report.write_bytes(b"\xff\xfe\x80")
    with pytest.raises(reasoner.UnsatisfiableReportError, match="UTF-8"):
        reasoner.parse_unsatisfiable_file(report)


def test_reasoned_graph_detects_named_classes_but_not_owl_nothing():
    graph = Graph()
    impossible = URIRef(reasoner.TERM_NAMESPACE + "Impossible")
    other = URIRef(reasoner.TERM_NAMESPACE + "OtherImpossible")
    graph.add((impossible, OWL.equivalentClass, OWL.Nothing))
    graph.add((other, RDFS.subClassOf, OWL.Nothing))
    graph.add((OWL.Nothing, OWL.equivalentClass, OWL.Nothing))
    assert reasoner.find_unsatisfiable_named_classes(graph) == sorted(
        (str(impossible), str(other))
    )
