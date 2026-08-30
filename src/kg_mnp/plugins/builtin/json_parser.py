"""Duplicate-safe, Decimal-preserving JSON leaf parser."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PluginError(f"DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


class JSONParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        try:
            value = json.loads(
                request.content.decode("utf-8-sig"),
                object_pairs_hook=_pairs,
                parse_float=Decimal,
                parse_int=int,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    PluginError(f"non-finite JSON number: {token}")
                ),
            )
        except PluginError:
            raise
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PluginError(f"invalid JSON: {exc}") from exc
        units: list[ParsedUnit] = []
        nodes = 0

        def visit(item: Any, pointer: str, depth: int) -> None:
            nonlocal nodes
            nodes += 1
            if depth > request.limits.max_json_depth:
                raise PluginError("JSON_DEPTH_LIMIT_EXCEEDED")
            if nodes > request.limits.max_json_items:
                raise PluginError("JSON_ITEM_LIMIT_EXCEEDED")
            if isinstance(item, dict):
                for key in sorted(item):
                    visit(item[key], f"{pointer}/{_escape(key)}", depth + 1)
            elif isinstance(item, list):
                for index, nested in enumerate(item):
                    visit(nested, f"{pointer}/{index}", depth + 1)
            else:
                stored: Any = {"decimal": str(item)} if isinstance(item, Decimal) else item
                units.append(ParsedUnit("scalar-field", stored, {"locator_kind": "json-pointer", "pointer": pointer}, "application/json", len(units), (("field_name", pointer.rsplit("/", 1)[-1] if pointer else "$"),)))

        visit(value, "", 0)
        return tuple(units)
