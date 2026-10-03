"""Explicit quote-coupled research profile, using strict source-only locators."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from zhigou_toolchain.modeling.five_stage import assistance
from zhigou_toolchain.modeling.five_stage.tools import bind_quote

LEGACY = "MODEL_ABSOLUTE_OFFSET"
PROGRAM = "PROGRAM_UNIQUE_QUOTE_V1"


def locator_mode(protocol):
    mode = (protocol.total_run_authorization or {}).get("evidence_locator_mode", LEGACY)
    if mode not in {LEGACY, PROGRAM}:
        raise ValueError("UNKNOWN_EVIDENCE_LOCATOR_PROFILE")
    return mode


def coupled_schema(output_schema):
    fields = {"triple": deepcopy(output_schema["properties"]["triples"]["items"]),
        "quote": {"type": "string", "minLength": 1, "maxLength": 8192}}
    if "schemas" in output_schema["properties"]:
        fields["schema"] = deepcopy(output_schema["properties"]["schemas"]["items"])
    return assistance.obj({"facts": assistance.array(assistance.obj(fields), 300)})


def decode_coupled_facts(response, *, typed) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Only repackage actual returned values; never add/drop/fix a fact."""
    if set(response) != {"facts"} or not isinstance(response["facts"], list):
        raise ValueError("COUPLED_FACT_ENVELOPE_INVALID")
    required = {"triple", "quote", "schema"} if typed else {"triple", "quote"}
    if any(set(row) != required for row in response["facts"]):
        raise ValueError("COUPLED_FACT_FIELDS_INVALID")
    prediction = {"triples": [deepcopy(row["triple"]) for row in response["facts"]]}
    if typed:
        prediction["schemas"] = [deepcopy(row["schema"]) for row in response["facts"]]
    evidence = [{"triple_index": index, "quote": row["quote"]} for index, row in enumerate(response["facts"])]
    return prediction, evidence


def bind_unique_source_quote(text, chunks, quote):
    if not isinstance(quote, str) or not quote or len(quote) > 8192:
        raise ValueError("QUOTE_WINDOW_OR_TYPE_INVALID")
    matches = list(re.finditer(re.escape(quote), text))
    if not matches:
        raise ValueError("QUOTE_NOT_FOUND")
    if len(matches) != 1:
        raise ValueError("QUOTE_AMBIGUOUS")
    start = matches[0].start()
    for chunk in chunks:
        if chunk["start"] <= start and start + len(quote) <= chunk["end"]:
            binding = bind_quote(text, chunk, quote, expected_start=start)
            return {**binding, "locator_origin": "PROGRAM_EXACT_UNIQUE_SOURCE_MATCH", "model_supplied_offset": False}
    raise ValueError("QUOTE_OUTSIDE_FROZEN_WINDOWS")
