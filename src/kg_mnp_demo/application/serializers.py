"""JSON-safe serializers for assessment outputs (no RDFLib / Path leakage)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


def to_iso_utc(value: datetime | date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return f"{value.isoformat()}T00:00:00Z"
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def json_safe(value: Any) -> Any:
    """Recursively convert values to JSON-serializable forms.

    - datetime → ISO 8601 UTC
    - Decimal → string
    - Path → basename only (never absolute paths)
    - RDFLib nodes / Graphs → string or omitted
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return to_iso_utc(value)
    if isinstance(value, date):
        return to_iso_utc(value)
    if isinstance(value, Path):
        return value.name
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(json_safe(v) for v in value)
    # RDFLib Graph / Node / Literal etc.
    type_name = type(value).__name__
    module = type(value).__module__ or ""
    if "rdflib" in module or type_name in {"Graph", "URIRef", "BNode", "Literal"}:
        return str(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return json_safe(value.to_dict())
    return str(value)


def deep_merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``changes`` into a copy of ``base`` (dicts only)."""
    result = dict(base)
    for key, value in changes.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def stable_sort_key(item: Any) -> Any:
    if isinstance(item, dict):
        for key in (
            "reason_code",
            "rule_id",
            "evidence_id",
            "action_code",
            "id",
            "code",
        ):
            if key in item and item[key] is not None:
                return (key, str(item[key]))
        return ("json", str(sorted(item.items())))
    return ("val", str(item))


def sort_stable(items: list[Any]) -> list[Any]:
    return sorted(items, key=stable_sort_key)
