"""Closed transformation registry for Stage 04 mapping rules."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .canonical_json import semantic_hash

TRANSFORMATION_IDS = frozenset(
    {
        "IDENTITY",
        "STRING_TRIM",
        "STRING_NORMALIZE",
        "BOOLEAN_STRICT",
        "INTEGER_STRICT",
        "DECIMAL_STRICT",
        "DATETIME_TO_UTC",
        "CODE_NORMALIZE",
        "IRI_FROM_STABLE_ID",
    }
)

DATA_INSTANCE_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/"


class TransformationError(ValueError):
    """A finite transform could not safely consume the supplied value."""


def _string(value: Any, transform: str) -> str:
    if not isinstance(value, str):
        raise TransformationError(f"{transform} requires a string")
    return value


def _decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise TransformationError("DECIMAL_STRICT requires a finite decimal value")
    if isinstance(value, float) and not math.isfinite(value):
        raise TransformationError("DECIMAL_STRICT rejects NaN and Infinity")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise TransformationError("DECIMAL_STRICT received an invalid decimal") from exc
    if not parsed.is_finite():
        raise TransformationError("DECIMAL_STRICT rejects NaN and Infinity")
    normalized = format(parsed.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", ""} else normalized


def transform_value(
    transformation_id: str,
    value: Any,
    *,
    context: Mapping[str, Any] | None = None,
) -> Any:
    if transformation_id not in TRANSFORMATION_IDS:
        raise TransformationError(f"unknown transformation_id: {transformation_id}")
    context = context or {}
    if transformation_id == "IDENTITY":
        return value
    if transformation_id == "STRING_TRIM":
        return _string(value, transformation_id).strip()
    if transformation_id == "STRING_NORMALIZE":
        text = unicodedata.normalize("NFKC", _string(value, transformation_id))
        return " ".join(text.strip().split())
    if transformation_id == "BOOLEAN_STRICT":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise TransformationError("BOOLEAN_STRICT accepts only booleans or true/false")
    if transformation_id == "INTEGER_STRICT":
        if isinstance(value, bool):
            raise TransformationError("INTEGER_STRICT rejects booleans")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value.strip()):
            return int(value.strip())
        raise TransformationError("INTEGER_STRICT received an invalid integer")
    if transformation_id == "DECIMAL_STRICT":
        return _decimal(value)
    if transformation_id == "DATETIME_TO_UTC":
        text = _string(value, transformation_id).strip()
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        except ValueError as exc:
            raise TransformationError("DATETIME_TO_UTC received an invalid date-time") from exc
        if parsed.tzinfo is None:
            raise TransformationError("DATETIME_TO_UTC requires an explicit timezone")
        utc = parsed.astimezone(timezone.utc)
        rendered = utc.isoformat(timespec="auto").replace("+00:00", "Z")
        return rendered
    if transformation_id == "CODE_NORMALIZE":
        text = unicodedata.normalize("NFKC", _string(value, transformation_id))
        return re.sub(r"[\s-]+", "_", text.strip()).upper()
    if transformation_id == "IRI_FROM_STABLE_ID":
        if not isinstance(value, (str, int)) or isinstance(value, bool) or str(value) == "":
            raise TransformationError("IRI_FROM_STABLE_ID requires a non-empty string or integer")
        digest = semantic_hash(
            {
                "class_iri": context.get("target_term_iri"),
                "stable_id": str(value),
            }
        )
        return DATA_INSTANCE_BASE + digest
    raise AssertionError("closed transformation registry was not exhaustive")
