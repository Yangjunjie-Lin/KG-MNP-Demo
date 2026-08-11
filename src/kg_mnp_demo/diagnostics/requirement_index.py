"""Reconstruct locally scoped requirements from verified formal constraints."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import OWL, SH

from kg_mnp_demo.modeling.canonical_json import semantic_hash


@dataclass(frozen=True, order=True)
class Requirement:
    focus_node: str
    path: str
    requirement_type: str
    authority_iri: str
    module: str
    publication_id: str
    shape_iri: str | None = None
    constraint_iri: str | None = None
    min_count: int = 0
    max_count: int | None = None
    evidence_required: bool = False
    source_required: bool = False
    evidence_min_count: int = 1
    source_min_count: int = 1
    report_optional_absence: bool = False

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.focus_node,
                self.path,
                self.requirement_type,
                self.authority_iri,
                self.module,
                self.publication_id,
            )
        ):
            raise ValueError("requirement identity fields must be non-empty")
        if self.min_count < 0 or (
            self.max_count is not None and self.max_count < 0
        ):
            raise ValueError("requirement counts must be non-negative")
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("max_count cannot be less than min_count")
        if self.evidence_min_count < 1 or self.source_min_count < 1:
            raise ValueError("lineage requirement counts must be positive")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Requirement:
        focus_node = value.get("focus_node", value.get("focusNode"))
        path = value.get("path", value.get("resultPath"))
        authority_iri = (
            value.get("authority_iri")
            or value.get("constraint_iri")
            or value.get("shape_iri")
        )
        if not all(
            isinstance(item, str) and item
            for item in (
                focus_node,
                path,
                authority_iri,
                value.get("publication_id"),
            )
        ):
            raise ValueError("requirement is missing its formal identity")
        return cls(
            focus_node=focus_node,
            path=path,
            requirement_type=str(value.get("requirement_type", "SHACL_PROPERTY_CONSTRAINT")),
            authority_iri=authority_iri,
            module=str(value.get("module", "verified-shacl")),
            publication_id=str(value["publication_id"]),
            shape_iri=(str(value["shape_iri"]) if value.get("shape_iri") else None),
            constraint_iri=(
                str(value["constraint_iri"])
                if value.get("constraint_iri")
                else None
            ),
            min_count=int(value.get("min_count", value.get("minCount", 0))),
            max_count=(
                int(value.get("max_count", value.get("maxCount")))
                if value.get("max_count", value.get("maxCount")) is not None
                else None
            ),
            evidence_required=value.get("evidence_required") is True,
            source_required=value.get("source_required") is True,
            evidence_min_count=int(value.get("evidence_min_count", 1)),
            source_min_count=int(value.get("source_min_count", 1)),
            report_optional_absence=value.get("report_optional_absence") is True,
        )

    def authority_basis(self) -> dict[str, Any]:
        return {
            "requirement_type": self.requirement_type,
            "authority_iri": self.authority_iri,
            "shape_iri": self.shape_iri,
            "constraint_iri": self.constraint_iri,
            "module": self.module,
            "publication_id": self.publication_id,
        }


class RequirementIndex:
    def __init__(self, requirements: Iterable[Requirement | Mapping[str, Any]]) -> None:
        normalized = [
            value if isinstance(value, Requirement) else Requirement.from_dict(value)
            for value in requirements
        ]
        self._requirements = tuple(sorted(set(normalized)))
        grouped: dict[tuple[str, str], list[Requirement]] = defaultdict(list)
        for requirement in self._requirements:
            grouped[(requirement.focus_node, requirement.path)].append(requirement)
        self._grouped = {
            key: tuple(sorted(values)) for key, values in grouped.items()
        }

    def __iter__(self):
        return iter(self._requirements)

    def __len__(self) -> int:
        return len(self._requirements)

    def for_focus_path(self, focus_node: str, path: str) -> tuple[Requirement, ...]:
        return self._grouped.get((focus_node, path), ())

    @property
    def focus_nodes(self) -> tuple[str, ...]:
        return tuple(sorted({value.focus_node for value in self._requirements}))


def build_requirement_index(
    requirements: Iterable[Requirement | Mapping[str, Any]],
) -> RequirementIndex:
    return RequirementIndex(requirements)


def _term_iri(graph: Graph, term: Any) -> str:
    if isinstance(term, URIRef):
        return str(term)
    description = sorted(
        (str(predicate), value.n3())
        for predicate, value in graph.predicate_objects(term)
    )
    return f"urn:kg-mnp:shacl-constraint:{semantic_hash(description)}"


def reconstruct_requirements_from_shacl(
    shapes_graph: Graph,
    data_graph: Graph,
    *,
    publication_id: str,
    module: str = "verified-shacl",
) -> RequirementIndex:
    """Project min/max-count constraints onto their formally targeted nodes."""

    requirements: list[Requirement] = []
    for node_shape in sorted(
        set(shapes_graph.subjects(RDF.type, SH.NodeShape)), key=str
    ):
        targets = {str(value) for value in shapes_graph.objects(node_shape, SH.targetNode)}
        for target_class in shapes_graph.objects(node_shape, SH.targetClass):
            targets.update(str(subject) for subject in data_graph.subjects(RDF.type, target_class))
        for property_shape in sorted(
            set(shapes_graph.objects(node_shape, SH.property)), key=str
        ):
            path = shapes_graph.value(property_shape, SH.path)
            if not isinstance(path, URIRef):
                continue
            min_value = shapes_graph.value(property_shape, SH.minCount)
            max_value = shapes_graph.value(property_shape, SH.maxCount)
            if min_value is None and max_value is None:
                continue
            shape_iri = _term_iri(shapes_graph, node_shape)
            constraint_iri = _term_iri(shapes_graph, property_shape)
            kinds = []
            if min_value is not None:
                kinds.append("SHACL_MIN_COUNT")
            if max_value is not None:
                kinds.append("SHACL_MAX_COUNT")
            for focus in targets:
                requirements.append(
                    Requirement(
                        focus_node=focus,
                        path=str(path),
                        requirement_type="+".join(kinds),
                        authority_iri=constraint_iri,
                        shape_iri=shape_iri,
                        constraint_iri=constraint_iri,
                        module=module,
                        publication_id=publication_id,
                        min_count=int(min_value) if isinstance(min_value, Literal) else 0,
                        max_count=(
                            int(max_value) if isinstance(max_value, Literal) else None
                        ),
                    )
                )
    for functional in sorted(
        set(shapes_graph.subjects(RDF.type, OWL.FunctionalProperty)), key=str
    ):
        for focus in sorted({str(subject) for subject in data_graph.subjects(functional, None)}):
            constraint = str(functional)
            requirements.append(
                Requirement(
                    focus_node=focus,
                    path=str(functional),
                    requirement_type="OWL_FUNCTIONAL_PROPERTY",
                    authority_iri=constraint,
                    constraint_iri=constraint,
                    module=module,
                    publication_id=publication_id,
                    max_count=1,
                )
            )
    return RequirementIndex(requirements)


def normalized_facts(
    facts: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Index only asserted/confirmed facts; review candidates never satisfy it."""

    result: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        status = str(fact.get("status", "CONFIRMED")).upper()
        if status not in {"CONFIRMED", "ASSERTED"}:
            continue
        focus = fact.get("focus_node", fact.get("subject", fact.get("s")))
        path = fact.get("path", fact.get("predicate", fact.get("p")))
        if focus is None or path is None or not any(
            key in fact for key in ("value", "object", "o")
        ):
            raise ValueError("fact is missing subject, predicate, or object")
        value = fact.get("value", fact.get("object", fact.get("o")))
        if value is None:
            raise ValueError("asserted fact object cannot be null")
        record = {
            "focus_node": str(focus),
            "path": str(path),
            "value": value,
            "assertion_ref": str(
                fact.get("assertion_ref")
                or fact.get("assertion_id")
                or f"urn:kg-mnp:assertion:{semantic_hash([str(focus), str(path), value])}"
            ),
            "evidence_refs": sorted({str(item) for item in fact.get("evidence_refs", [])}),
            "source_refs": sorted({str(item) for item in fact.get("source_refs", [])}),
            "value_state": str(fact.get("value_state", "KNOWN")).upper(),
        }
        result[(record["focus_node"], record["path"])].append(record)
    for records in result.values():
        records.sort(
            key=lambda record: (
                semantic_hash(record["value"]),
                record["assertion_ref"],
            ),
        )
    return dict(result)
