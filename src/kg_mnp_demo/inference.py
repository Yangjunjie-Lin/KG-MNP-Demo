"""OWL 2 RL inference via owlrl."""

from __future__ import annotations

import owlrl
from rdflib import Graph


def apply_owlrl(graph: Graph) -> Graph:
    """Expand graph in-place with OWL-RL entailments and return it."""
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(graph)
    return graph


def inferred_copy(graph: Graph) -> Graph:
    g = Graph()
    for triple in graph:
        g.add(triple)
    return apply_owlrl(g)
