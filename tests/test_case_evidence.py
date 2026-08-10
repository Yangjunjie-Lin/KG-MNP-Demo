"""Tests for relation-based case evidence selection."""

from __future__ import annotations

from rdflib import Literal
from rdflib.namespace import RDF

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import CASE_FILES, DATA, MNP
from kg_mnp_demo.rule_engine import collect_evidence
from kg_mnp_demo.validator import validate_graph


def test_all_cases_have_has_case_evidence():
    for case_id in CASE_FILES:
        g = load_case_graph(case_id)
        q = """
        PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
        SELECT (COUNT(?ev) AS ?n) WHERE {
          ?case mnp:caseIdentifier %s ;
                mnp:hasCaseEvidence ?ev .
        }
        """ % f'"{case_id}"'
        n = int(next(iter(g.query(q))).n)
        assert n >= 1, case_id


def test_evidence_belongs_to_correct_case_only():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    # Ev-03-* should not appear for CASE-02 when only CASE-03 graph is loaded,
    # but more importantly collect_evidence scopes by relation.
    ev = collect_evidence(g, "CASE-03")
    iris = {e.iri for views in ev.values() for e in views}
    assert any("Ev-03" in i or "CTR" in i for i in iris)
    # Ensure no leakage from unrelated naming alone: invent fake Ev-02 node without relation
    fake = DATA["Ev-02-BILL-FAKE"]
    g.add((fake, RDF.type, MNP.SystemObservation))
    g.add((fake, MNP.evidenceType, Literal("BILLING_BALANCE")))
    g.add((fake, MNP.evidenceStatus, Literal("VALID")))
    g.add((fake, MNP.evidenceGeneratedAt, Literal("2026-06-20T10:10:00Z")))
    g.add((fake, MNP.hasSourceSystem, DATA["SYS-BILLING"]))
    ev2 = collect_evidence(g, "CASE-03")
    iris2 = {e.iri for views in ev2.values() for e in views}
    assert str(fake) not in iris2


def test_collect_evidence_not_name_dependent():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    # Rename Ev-03-CTR to an arbitrary IRI while keeping hasCaseEvidence
    old = DATA["Ev-03-CTR"]
    new = DATA["ArbitraryContractEvidenceXYZ"]
    for p, o in list(g.predicate_objects(old)):
        g.remove((old, p, o))
        g.add((new, p, o))
    for s, p in list(g.subject_predicates(old)):
        g.remove((s, p, old))
        g.add((s, p, new))
    # Ensure case still links the renamed evidence
    g.add((DATA["CASE-03"], MNP.hasCaseEvidence, new))
    g.remove((DATA["CASE-03"], MNP.hasCaseEvidence, old))

    result = evaluate_case(g, "CASE-03", validate=False)
    assert result["decision"] == "BLOCKED"
    assert result["blocking_reasons"][0]["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert "ArbitraryContractEvidenceXYZ" in (
        result["blocking_reasons"][0]["evidence"]["evidence_iri"] or ""
    )


def test_missing_has_case_evidence_fails_shacl():
    g = load_case_graph("CASE-03")
    for triple in list(g.triples((DATA["CASE-03"], MNP.hasCaseEvidence, None))):
        g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
    assert "hasCaseEvidence" in result.text or "案件证据" in result.text


def test_assessment_using_foreign_evidence_fails_shacl():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    evaluate_case(g, "CASE-03", validate=False)
    # Attach foreign evidence node and make assessment use it
    foreign = DATA["ForeignEvidence"]
    g.add((foreign, RDF.type, MNP.EvidenceRecord))
    g.add((foreign, MNP.evidenceType, Literal("CONTRACT_STATUS")))
    g.add((foreign, MNP.evidenceStatus, Literal("VALID")))
    g.add((foreign, MNP.evidenceGeneratedAt, Literal("2026-06-20T10:15:00Z")))
    g.add((foreign, MNP.hasSourceSystem, DATA["SYS-CONTRACT"]))
    assessment = DATA["Assessment-CASE-03"]
    g.add((assessment, MNP.usesEvidence, foreign))
    result = validate_graph(g)
    assert not result.conforms
    assert "不属于其对应案件的证据集合" in result.text


def test_no_prefix_selection_in_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    banned_patterns = [
        'startswith(prefix)',
        'startswith(f"Ev-',
        'startswith("Ev-',
        "CONTAINS(STR(?ev",
        "CONTAINS(STR(?evNum",
        "CONTAINS(STR(?evId",
        "CONTAINS(STR(?evBill",
        "CONTAINS(STR(?evCtr",
        "CONTAINS(STR(?evPort",
    ]
    hits = []
    for base in ("src", "scripts", "queries"):
        for path in (root / base).rglob("*"):
            if path.suffix not in {".py", ".rq"}:
                continue
            text = path.read_text(encoding="utf-8")
            for pat in banned_patterns:
                if pat in text:
                    hits.append(f"{path.relative_to(root)}: {pat}")
    assert hits == [], hits
