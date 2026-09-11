"""Strict RDF literal construction without silent repair."""

from __future__ import annotations

from rdflib import Literal, URIRef

from .security import validate_iri, validate_language


def compile_literal(value: dict[str, object]) -> Literal:
    lexical = value.get("lexical_value")
    datatype = value.get("datatype_iri")
    language = value.get("language")
    if not isinstance(lexical, str):
        raise TypeError("literal lexical_value must be a string")
    if datatype is not None and language is not None:
        raise ValueError("an RDF literal cannot combine datatype and language")
    validate_language(language if isinstance(language, str) else None)
    if datatype is not None:
        if not isinstance(datatype, str):
            raise ValueError("literal datatype IRI must be a string")
        validate_iri(datatype, label="datatype IRI")
        literal = Literal(lexical, datatype=URIRef(datatype), normalize=False)
        if literal.ill_typed is True:
            raise ValueError("literal lexical form is invalid for its datatype")
        return literal
    if language is not None:
        return Literal(lexical, lang=str(language), normalize=False)
    return Literal(lexical, normalize=False)
