"""Finite, fail-closed Candidate-to-RDF mapping for confirmed ABox decisions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re
from typing import Any, Mapping

from rdflib import OWL, RDF, RDFS, SH, XSD, Graph, Literal, URIRef

from ..modeling.package_validation import load_term_type_index
from ..modeling.review_actions import validate_instance_iri
from .candidate_resolution import (
    CandidateResolutionError,
    resolve_candidate_iri,
    resolve_effective_candidates,
    resolve_effective_entity_iris,
)

FORBIDDEN_PREDICATES = {
    RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range,
    OWL.equivalentClass, OWL.equivalentProperty, OWL.disjointWith,
}
FORBIDDEN_TYPE_OBJECTS = {
    OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
    SH.NodeShape, SH.PropertyShape,
}


class ABoxCompilationError(ValueError):
    pass


_XSD_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
_XSD_DATETIME_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?Z"
)


def _validate_strict_calendar_lexical(raw: str, datatype: str) -> None:
    if datatype == str(XSD.date):
        match = _XSD_DATE_RE.fullmatch(raw)
        if match is None:
            raise ABoxCompilationError(
                f"invalid xsd:date lexical value: {raw!r}; expected YYYY-MM-DD"
            )
        try:
            datetime.strptime(match.group("date"), "%Y-%m-%d")
        except ValueError as exc:
            raise ABoxCompilationError(
                f"invalid xsd:date calendar value: {raw!r}"
            ) from exc
        return

    match = _XSD_DATETIME_RE.fullmatch(raw)
    if match is None:
        raise ABoxCompilationError(
            "invalid xsd:dateTime lexical value: "
            f"{raw!r}; expected YYYY-MM-DDTHH:MM:SS[.fraction]Z"
        )
    try:
        datetime.strptime(
            f"{match.group('date')}T{match.group('time')}",
            "%Y-%m-%dT%H:%M:%S",
        )
    except ValueError as exc:
        raise ABoxCompilationError(
            f"invalid xsd:dateTime calendar value: {raw!r}"
        ) from exc


@dataclass(frozen=True)
class CompiledAssertion:
    confirmed_item_id: str
    source_candidate_id: str
    effective_candidate_id: str
    decision_id: str
    candidate_kind: str
    triple: tuple[URIRef, URIRef, Any]
    semantic_content: Mapping[str, Any]


def _iri(value: Any, field: str) -> URIRef:
    if not isinstance(value, str) or not value.startswith(("http://", "https://", "urn:")):
        raise ABoxCompilationError(f"{field} must be an absolute IRI")
    return URIRef(value)


def _instance_iri(value: Any, field: str) -> URIRef:
    if not isinstance(value, str):
        raise ABoxCompilationError(f"{field} must be an instance IRI")
    errors = validate_instance_iri(value)
    if errors:
        raise ABoxCompilationError("; ".join(errors))
    return _iri(value, field)


def _literal(value: Any) -> Literal:
    if not isinstance(value, Mapping):
        raise ABoxCompilationError("data property object must be a typed literal object")
    raw = value.get("value")
    if raw is None:
        raise ABoxCompilationError("null literal cannot be compiled")
    language = value.get("language")
    datatype = value.get("datatype_iri")
    if language is not None and datatype is not None:
        raise ABoxCompilationError("literal cannot have both language and datatype_iri")
    if language is not None:
        if not isinstance(raw, str) or not isinstance(language, str) or not language:
            raise ABoxCompilationError("language-tagged literal requires string value and language")
        return Literal(raw, lang=language)
    if not isinstance(datatype, str):
        raise ABoxCompilationError("typed literal requires datatype_iri")
    supported = {
        str(XSD.string), str(XSD.boolean), str(XSD.integer), str(XSD.decimal),
        str(XSD.date), str(XSD.dateTime),
    }
    if datatype not in supported:
        raise ABoxCompilationError(f"unsupported datatype: {datatype}")
    if datatype == str(XSD.string):
        if not isinstance(raw, str):
            raise ABoxCompilationError("xsd:string value must be a string")
        return Literal(raw, datatype=XSD.string)
    if datatype == str(XSD.boolean):
        if isinstance(raw, bool):
            lexical = "true" if raw else "false"
        elif isinstance(raw, str) and raw in {"true", "false", "1", "0"}:
            lexical = "true" if raw in {"true", "1"} else "false"
        else:
            raise ABoxCompilationError("invalid xsd:boolean value")
        return Literal(lexical, datatype=XSD.boolean, normalize=False)
    if datatype == str(XSD.integer):
        if isinstance(raw, bool):
            raise ABoxCompilationError("invalid xsd:integer value")
        try:
            lexical = str(int(raw))
        except (TypeError, ValueError) as exc:
            raise ABoxCompilationError("invalid xsd:integer value") from exc
        if isinstance(raw, (float, str)) and str(raw).strip() not in {lexical, "+" + lexical}:
            raise ABoxCompilationError("invalid xsd:integer lexical form")
        return Literal(lexical, datatype=XSD.integer, normalize=False)
    if datatype == str(XSD.decimal):
        try:
            decimal = Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise ABoxCompilationError("invalid xsd:decimal value") from exc
        if not decimal.is_finite():
            raise ABoxCompilationError("invalid xsd:decimal value")
        lexical = format(decimal, "f")
        if "." not in lexical:
            lexical += ".0"
        return Literal(lexical, datatype=XSD.decimal, normalize=False)
    if not isinstance(raw, str):
        raise ABoxCompilationError("date/dateTime values must use canonical strings")
    _validate_strict_calendar_lexical(raw, datatype)
    return Literal(raw, datatype=URIRef(datatype), normalize=False)


def _validate_term_type(iri: str, expected: set[str], term_types: Mapping[str, str], field: str) -> None:
    actual = term_types.get(iri)
    if actual not in expected:
        raise ABoxCompilationError(f"{field} has invalid ontology term type {actual!r}: {iri}")


def candidate_to_rdf_triple(
    candidate: Mapping[str, Any],
    entity_iris: Mapping[str, str],
    term_types: Mapping[str, str],
) -> tuple[URIRef, URIRef, Any]:
    """Project one finite ABox Candidate with the authoritative Stage 06 rules."""

    kind = str(candidate.get("candidate_kind", "ENTITY"))
    if candidate.get("publication_scope") != "ABOX":
        raise ABoxCompilationError("candidate must remain in ABOX publication scope")
    if kind == "MAPPING_ASSERTION":
        raise ABoxCompilationError(
            "MAPPING_ASSERTION is forbidden until a typed object contract exists"
        )
    if kind == "ENTITY":
        candidate_id = str(candidate.get("candidate_id", ""))
        iri_value = entity_iris.get(candidate_id) or candidate.get("proposed_iri")
        subject = _instance_iri(iri_value, "proposed_iri")
        class_iri = str(candidate.get("class_iri"))
        _validate_term_type(class_iri, {"Class"}, term_types, "class_iri")
        triple = (subject, RDF.type, _iri(class_iri, "class_iri"))
    elif kind == "CLASS_ASSERTION":
        subject = _iri(
            resolve_candidate_iri(str(candidate.get("subject_ref")), entity_iris),
            "subject_ref",
        )
        class_iri = str(candidate.get("class_iri"))
        _validate_term_type(class_iri, {"Class"}, term_types, "class_iri")
        triple = (subject, RDF.type, _iri(class_iri, "class_iri"))
    elif kind == "OBJECT_PROPERTY_ASSERTION":
        subject = _iri(
            resolve_candidate_iri(str(candidate.get("subject_ref")), entity_iris),
            "subject_ref",
        )
        predicate = str(candidate.get("predicate_iri"))
        _validate_term_type(
            predicate, {"ObjectProperty"}, term_types, "predicate_iri"
        )
        obj = _iri(
            resolve_candidate_iri(str(candidate.get("object")), entity_iris),
            "object",
        )
        triple = (subject, _iri(predicate, "predicate_iri"), obj)
    elif kind == "DATA_PROPERTY_ASSERTION":
        subject = _iri(
            resolve_candidate_iri(str(candidate.get("subject_ref")), entity_iris),
            "subject_ref",
        )
        predicate = str(candidate.get("predicate_iri"))
        _validate_term_type(
            predicate, {"DatatypeProperty"}, term_types, "predicate_iri"
        )
        triple = (
            subject,
            _iri(predicate, "predicate_iri"),
            _literal(candidate.get("object")),
        )
    else:
        raise ABoxCompilationError(f"unsupported candidate kind: {kind}")
    if triple[1] in FORBIDDEN_PREDICATES or (
        triple[1] == RDF.type and triple[2] in FORBIDDEN_TYPE_OBJECTS
    ):
        raise ABoxCompilationError("TBox declaration leakage is forbidden")
    return triple


def compile_abox(
    package: Mapping[str, Any],
    proposal: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    *,
    compilation_hash: str | None = None,
    term_types: Mapping[str, str] | None = None,
) -> tuple[Graph, list[CompiledAssertion]]:
    if package.get("confirmed_schema_delta"):
        raise ABoxCompilationError("confirmed_schema_delta must be empty")
    types = dict(term_types) if term_types is not None else load_term_type_index()
    effective = resolve_effective_candidates(package, proposal)
    entity_iris = resolve_effective_entity_iris(package, proposal)
    graph = Graph()
    abox_hash = compilation_hash or str(package.get("package_semantic_hash"))
    ontology_iri = URIRef(f"urn:kg-mnp:compiled-abox:{abox_hash}")
    root_version_iri = _iri(ontology_baseline.get("root_version_iri"), "root_version_iri")
    graph.add((ontology_iri, RDF.type, OWL.Ontology))
    graph.add((ontology_iri, OWL.imports, root_version_iri))
    assertions: list[CompiledAssertion] = []

    for item in package.get("confirmed_abox_decisions", []):
        envelope = item["confirmed_candidate"]
        source_id = str(envelope["source_candidate_id"])
        effective_id = str(envelope["effective_candidate_id"])
        candidate = effective.get(source_id) or effective.get(effective_id)
        if candidate is None:
            raise CandidateResolutionError(f"effective candidate not found: {effective_id}")
        if item.get("publication_scope") != "ABOX" or candidate.get("publication_scope") != "ABOX":
            raise ABoxCompilationError("confirmed candidates must remain in ABOX publication scope")
        candidate_with_id = dict(candidate)
        candidate_with_id.setdefault("candidate_id", effective_id)
        triple = candidate_to_rdf_triple(candidate_with_id, entity_iris, types)
        kind = str(candidate.get("candidate_kind", "ENTITY"))
        graph.add(triple)
        assertions.append(CompiledAssertion(
            confirmed_item_id=str(envelope["confirmed_item_id"]),
            source_candidate_id=source_id,
            effective_candidate_id=effective_id,
            decision_id=str(item["decision_id"]),
            candidate_kind=kind,
            triple=triple,
            semantic_content=dict(candidate),
        ))
    return graph, assertions
