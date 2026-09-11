"""Canonical SPARQL JSON projection with full RDF term fidelity."""

from __future__ import annotations

import json
from typing import Any

from .errors import ApplicationError, ErrorCode


def normalize_binding(binding: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(binding, dict) or not isinstance(binding.get("value"), str):
        raise ApplicationError(ErrorCode.INTERNAL_ERROR)
    kind = binding.get("type")
    if kind == "uri":
        if set(binding) - {"type", "value"}:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        return {"term_type": "IRI", "iri": binding["value"]}
    if kind in {"literal", "typed-literal"}:
        allowed = {"type", "value", "datatype", "xml:lang", "lang"}
        if set(binding) - allowed:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        language = binding.get("xml:lang", binding.get("lang"))
        datatype = binding.get("datatype")
        if datatype is not None and not isinstance(datatype, str):
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        if language is not None and not isinstance(language, str):
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        return {
            "term_type": "LITERAL",
            "lexical_form": binding["value"],
            "datatype_iri": datatype,
            "language": language,
        }
    raise ApplicationError(ErrorCode.INTERNAL_ERROR)


def normalize_select(payload: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        variables = [str(value) for value in payload["head"]["vars"]]
        raw_rows = payload["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise ApplicationError(ErrorCode.INTERNAL_ERROR) from exc
    if len(variables) != len(set(variables)) or not isinstance(raw_rows, list):
        raise ApplicationError(ErrorCode.INTERNAL_ERROR)
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict) or set(raw) - set(variables):
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        bindings = [
            {"variable": variable, "term": normalize_binding(raw[variable])}
            for variable in variables
            if variable in raw
        ]
        rows.append({"bindings": bindings})
    rows.sort(key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return variables, rows
