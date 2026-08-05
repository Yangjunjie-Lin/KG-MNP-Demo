"""SHACL validation with pySHACL and shape profiles."""

from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate
from rdflib import Graph

from kg_mnp_demo.loader import shape_paths


@dataclass(frozen=True)
class ValidationResult:
    conforms: bool
    text: str
    report_graph: Graph | None = None

    def to_dict(self) -> dict:
        return {"conforms": self.conforms, "text": self.text}


def _run_validate(data_graph: Graph, shapes: Graph, *, abort_on_first: bool = False) -> ValidationResult:
    conforms, report_graph, text = validate(
        data_graph,
        shacl_graph=shapes,
        inference="none",
        abort_on_first=abort_on_first,
        meta_shacl=False,
        advanced=True,
        js=False,
        debug=False,
    )
    return ValidationResult(conforms=bool(conforms), text=str(text), report_graph=report_graph)


def validate_graph(
    data_graph: Graph,
    *,
    profile: str = "eligibility",
    abort_on_first: bool = False,
) -> ValidationResult:
    """Validate an ABox graph against a SHACL profile (foundation|eligibility)."""
    shapes = Graph()
    for path in shape_paths(profile):
        shapes.parse(path, format="turtle")
    return _run_validate(data_graph, shapes, abort_on_first=abort_on_first)


def validate_ontology_schema(ontology_graph: Graph, *, abort_on_first: bool = False) -> ValidationResult:
    """Validate TBox annotation quality using ontology_schema profile."""
    shapes = Graph()
    for path in shape_paths("ontology_schema"):
        shapes.parse(path, format="turtle")
    return _run_validate(ontology_graph, shapes, abort_on_first=abort_on_first)
