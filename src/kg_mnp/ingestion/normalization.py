"""Core validation around the generic normalizer response."""

from kg_mnp.plugins.models import NormalizedUnit, NormalizeRequest, ParsedUnit

from .errors import IngestionError


def normalize_units(provider: object, units: tuple[ParsedUnit, ...]) -> tuple[NormalizedUnit, ...]:
    method = getattr(provider, "normalize", None)
    if method is None:
        raise IngestionError("selected normalizer does not implement NormalizerPlugin")
    result = []
    for unit in units:
        normalized = method(NormalizeRequest(unit))
        if not isinstance(normalized, NormalizedUnit):
            raise IngestionError("NormalizerPlugin returned an invalid response type")
        if (
            normalized.locator != unit.locator
            or normalized.ordinal != unit.ordinal
            or normalized.unit_kind != unit.unit_kind
            or normalized.media_type != unit.media_type
            or normalized.original_value != unit.value
            or normalized.metadata != unit.metadata
        ):
            raise IngestionError("NormalizerPlugin changed source authority coordinates")
        result.append(normalized)
    return tuple(result)
