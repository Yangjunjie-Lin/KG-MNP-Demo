"""Core parser dispatch after deterministic provider selection."""

from __future__ import annotations

from zhigou_toolchain.plugins.models import ParsedUnit, ParseRequest, ResourceLimits

from .errors import IngestionPlanError


def parse_with_provider(
    provider: object,
    *,
    content: bytes,
    media_type: str,
    limits: ResourceLimits,
) -> tuple[ParsedUnit, ...]:
    method = getattr(provider, "parse", None)
    if method is None:
        raise IngestionPlanError("selected parser does not implement ParserPlugin")
    result = method(ParseRequest(content=content, media_type=media_type, limits=limits))
    if not isinstance(result, tuple) or not all(isinstance(item, ParsedUnit) for item in result):
        raise IngestionPlanError("ParserPlugin returned an invalid response type")
    if len(result) > limits.max_json_items:
        raise IngestionPlanError("ParserPlugin returned too many ParsedUnit values")
    ordinals = [item.ordinal for item in result]
    if ordinals != list(range(len(result))):
        raise IngestionPlanError("ParserPlugin returned non-contiguous or reordered ordinals")
    return result
