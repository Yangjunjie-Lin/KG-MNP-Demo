from __future__ import annotations

from rdflib import OWL, Graph, URIRef

import run_reasoner as reasoner


def _iri(local: str) -> URIRef:
    return URIRef(reasoner.TERM_NAMESPACE + local)


def test_asserted_self_and_nothing_equivalences_are_not_unexpected():
    asserted = Graph()
    reasoned = Graph()
    alpha, beta = _iri("Alpha"), _iri("Beta")
    asserted.add((alpha, OWL.equivalentClass, beta))
    for triple in asserted:
        reasoned.add(triple)
    reasoned.add((alpha, OWL.equivalentClass, alpha))
    reasoned.add((beta, OWL.equivalentClass, OWL.Nothing))
    assert reasoner.detect_inferred_equivalent_classes(asserted, reasoned) == (
        [],
        [],
        [],
    )


def test_new_named_equivalence_is_unexpected_without_allowlist():
    asserted = Graph()
    reasoned = Graph()
    alpha, beta = _iri("Alpha"), _iri("Beta")
    reasoned.add((alpha, OWL.equivalentClass, beta))
    inferred, approved, unexpected = reasoner.detect_inferred_equivalent_classes(
        asserted,
        reasoned,
    )
    pair = [str(alpha), str(beta)]
    assert inferred == [pair]
    assert approved == []
    assert unexpected == [pair]


def test_allowlist_approves_unordered_pair():
    asserted = Graph()
    reasoned = Graph()
    alpha, beta = _iri("Alpha"), _iri("Beta")
    reasoned.add((beta, OWL.equivalentClass, alpha))
    pair = tuple(sorted((str(alpha), str(beta))))
    inferred, approved, unexpected = reasoner.detect_inferred_equivalent_classes(
        asserted,
        reasoned,
        {pair},
    )
    assert inferred == [list(pair)]
    assert approved == [list(pair)]
    assert unexpected == []


def test_equivalence_components_are_compared_by_transitive_closure():
    asserted = Graph()
    reasoned = Graph()
    alpha, beta, gamma = _iri("Alpha"), _iri("Beta"), _iri("Gamma")
    asserted.add((alpha, OWL.equivalentClass, beta))
    reasoned.add((beta, OWL.equivalentClass, alpha))
    reasoned.add((beta, OWL.equivalentClass, gamma))
    inferred, _, unexpected = reasoner.detect_inferred_equivalent_classes(
        asserted,
        reasoned,
    )
    assert inferred == [
        [str(alpha), str(gamma)],
        [str(beta), str(gamma)],
    ]
    assert unexpected == inferred
