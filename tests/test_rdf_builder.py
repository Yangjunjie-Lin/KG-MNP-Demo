"""Tests for RDF builder from normalized JSON input."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.input_adapter import normalize_case_input
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.rdf_builder import build_case_graph, case_iri

ROOT = Path(__file__).resolve().parents[1]


def _normalized_case03():
    data = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    return normalize_case_input(data)


def test_repeatable_rdf_conversion():
    n = _normalized_case03()
    g1 = build_case_graph(n)
    g2 = build_case_graph(n)
    assert set(g1) == set(g2)


def test_has_case_evidence_present():
    g = build_case_graph(_normalized_case03())
    case = case_iri("CASE-03")
    evidence = list(g.objects(case, MNP.hasCaseEvidence))
    assert len(evidence) == 5


def test_no_ev03_iri_dependency():
    g = build_case_graph(_normalized_case03())
    iris = " ".join(str(s) for s in g.subjects())
    assert "Ev-03-" not in iris
    assert "Evidence-CASE-03-CONTRACT" in iris
