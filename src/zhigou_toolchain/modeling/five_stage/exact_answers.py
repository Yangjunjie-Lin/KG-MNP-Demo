"""Typed exact-answer V1 -> frozen CQ MULTISET/ASK assertion adapter."""
from __future__ import annotations

from typing import Literal as Kind

from pydantic import Field, model_validator
from rdflib import Literal, URIRef

from zhigou_toolchain.contracts.canonical import semantic_hash

from .contracts import DTO


class RDFTerm(DTO):
    kind: Kind["IRI", "LITERAL"]
    value: str = Field(max_length=10000)
    datatype: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def valid_term(self):
        import re
        iri = re.compile(r"^(?:https?://|urn:)[^\s<>\"{}|^`\\]+$")
        if self.kind == "IRI" and (not iri.fullmatch(self.value) or self.datatype or self.language):
            raise ValueError("invalid IRI term")
        if self.kind == "LITERAL" and (bool(self.datatype) == bool(self.language)):
            raise ValueError("literal requires exactly one explicit datatype or language")
        if self.datatype and not iri.fullmatch(self.datatype):
            raise ValueError("invalid datatype IRI")
        if self.language and not re.fullmatch(r"[a-zA-Z]+(?:-[a-zA-Z0-9]+)*", self.language):
            raise ValueError("invalid language")
        return self

    def n3(self):
        return URIRef(self.value).n3() if self.kind == "IRI" else Literal(self.value, datatype=URIRef(self.datatype) if self.datatype else None, lang=self.language, normalize=False).n3()


class ExactAnswer(DTO):
    schema_version: Kind["1.0.0"] = "1.0.0"
    query_type: Kind["ASK", "SELECT"]
    comparison: Kind["BOOLEAN", "MULTISET", "SET", "ORDERED"]
    variables: list[str] = Field(default_factory=list, max_length=100)
    rows: list[dict[str, RDFTerm | None]] = Field(default_factory=list, max_length=10000)
    boolean: bool | None = None

    @model_validator(mode="after")
    def shape(self):
        import re
        if self.query_type == "ASK":
            if self.comparison != "BOOLEAN" or self.boolean is None or self.rows or self.variables:
                raise ValueError("ASK requires only an explicit boolean")
        elif (self.comparison not in {"MULTISET", "SET", "ORDERED"} or self.boolean is not None or not self.variables
              or len(self.variables) != len(set(self.variables))
              or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) for v in self.variables)
              or any(set(row) != set(self.variables) for row in self.rows)):
            raise ValueError("SELECT requires exact typed rows and unique variables")
        return self

    def normalized(self):
        if self.query_type == "ASK":
            return {"boolean": self.boolean}
        rows = [{name: value.n3() if value else None for name, value in row.items()} for row in self.rows]
        if self.comparison == "SET":
            rows = list({semantic_hash(row): row for row in rows}.values())
        return {"variables": self.variables, "rows": rows if self.comparison == "ORDERED" else sorted(rows, key=semantic_hash)}


def assertions(answer: ExactAnswer) -> list[dict]:
    empty = {"integer_value": None, "boolean_value": None, "string_values": [], "semantic_hash": None}
    if answer.query_type == "ASK":
        return [{**empty, "assertion_type": "BOOLEAN_EQUALS", "boolean_value": answer.boolean}]
    if answer.comparison in {"SET", "ORDERED"}:
        # Old empty string_values continue to mean typed multiset V1.
        return [{**empty, "assertion_type": "RESULT_SEMANTIC_HASH", "string_values": [answer.comparison + "_V1"],
                 "semantic_hash": semantic_hash(answer.normalized())}]
    return [{**empty, "assertion_type": "RESULT_SEMANTIC_HASH", "semantic_hash": semantic_hash(answer.normalized())},
            {**empty, "assertion_type": "MIN_ROW_COUNT", "integer_value": len(answer.rows)},
            {**empty, "assertion_type": "MAX_ROW_COUNT", "integer_value": len(answer.rows)}]
