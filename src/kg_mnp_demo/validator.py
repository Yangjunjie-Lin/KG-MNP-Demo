"""SHACL validation with pySHACL."""

from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate
from rdflib import Graph

from kg_mnp_demo.loader import shapes_path


@dataclass(frozen=True)
class ValidationResult:
    conforms: bool
    text: str
    report_graph: Graph | None = None

    def to_dict(self) -> dict:
        return {"conforms": self.conforms, "text": self.text}


def validate_graph(data_graph: Graph, *, abort_on_first: bool = False) -> ValidationResult:
    shapes = Graph()
    shapes.parse(shapes_path(), format="turtle")
    # inference=none: avoid RDFS domain expansion typing RuleVersion as EligibilityRule
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
