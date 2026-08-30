"""Strict parameter and RDF-term validation without raw SPARQL interpolation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from rdflib import Literal, URIRef

from .errors import ApplicationError, ErrorCode
from .policy import (
    ALLOWED_IRI_SCHEMES,
    EXTERNAL_ONTOLOGY_PREFIXES,
    MAX_IRI_LENGTH,
    MAX_STRING_PARAMETER_LENGTH,
    PROJECT_HTTPS_PREFIX,
    PROJECT_URN_PREFIX,
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_LANGUAGE = re.compile(r"^[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*$")


def validate_iri(value: Any, *, allow_external: bool = True) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_IRI_LENGTH:
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if _CONTROL.search(value) or any(char.isspace() for char in value):
        raise ApplicationError(ErrorCode.INVALID_IRI)
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ApplicationError(ErrorCode.INVALID_IRI) from exc
    known_external = value.startswith(EXTERNAL_ONTOLOGY_PREFIXES)
    if (
        parsed.scheme not in ALLOWED_IRI_SCHEMES
        and not (parsed.scheme == "http" and allow_external and known_external)
    ) or parsed.username or parsed.password:
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if parsed.scheme == "https" and not parsed.hostname:
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if parsed.scheme == "urn" and not value.startswith(PROJECT_URN_PREFIX):
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if not allow_external and not value.startswith((PROJECT_HTTPS_PREFIX, PROJECT_URN_PREFIX)):
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if allow_external and not value.startswith(
        (PROJECT_HTTPS_PREFIX, PROJECT_URN_PREFIX, *EXTERNAL_ONTOLOGY_PREFIXES)
    ):
        raise ApplicationError(ErrorCode.INVALID_IRI)
    decoded = value
    for _ in range(2):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    try:
        decoded_path = urlsplit(decoded).path
    except ValueError as exc:
        raise ApplicationError(ErrorCode.INVALID_IRI) from exc
    if _CONTROL.search(decoded) or any(part in {".", ".."} for part in decoded_path.split("/")):
        raise ApplicationError(ErrorCode.INVALID_IRI)
    if "%25" in value.lower():
        raise ApplicationError(ErrorCode.INVALID_IRI)
    return value


def validate_stable_identifier(value: Any) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return value


def validate_bounded_string(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_STRING_PARAMETER_LENGTH
        or _CONTROL.search(value)
    ):
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return value


def validate_enum(value: Any, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return value


@dataclass(frozen=True)
class RDFTermInput:
    term_type: str
    value: str
    datatype_iri: str | None = None
    language: str | None = None

    def as_rdflib(self) -> URIRef | Literal:
        if self.term_type == "IRI":
            return URIRef(validate_iri(self.value))
        lexical = validate_bounded_string(self.value)
        if self.datatype_iri and self.language:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        datatype = URIRef(validate_iri(self.datatype_iri)) if self.datatype_iri else None
        if self.language and not _LANGUAGE.fullmatch(self.language):
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        return Literal(lexical, datatype=datatype, lang=self.language)


def parse_rdf_term(value: Mapping[str, Any] | RDFTermInput) -> RDFTermInput:
    if isinstance(value, RDFTermInput):
        value.as_rdflib()
        return value
    if not isinstance(value, Mapping) or set(value) - {
        "term_type",
        "value",
        "datatype_iri",
        "language",
    }:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    term_type = validate_enum(value.get("term_type"), ("IRI", "LITERAL"))
    term = RDFTermInput(
        term_type=term_type,
        value=value.get("value"),
        datatype_iri=value.get("datatype_iri"),
        language=value.get("language"),
    )
    term.as_rdflib()
    return term


def serialize_rdf_term(value: URIRef | Literal) -> str:
    """Serialize a validated RDF term for use inside a fixed VALUES clause."""
    if not isinstance(value, (URIRef, Literal)):
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return value.n3()
