"""Deterministic sample normalizer used only by Plugin SDK tests."""

from kg_mnp.plugins.models import NormalizedUnit, NormalizeRequest


class UppercaseNormalizer:
    def normalize(self, request: NormalizeRequest) -> NormalizedUnit:
        unit = request.parsed_unit
        value = unit.value.upper() if isinstance(unit.value, str) else unit.value
        return NormalizedUnit(
            unit_kind=unit.unit_kind,
            original_value=unit.value,
            normalized_value=value,
            locator=unit.locator,
            media_type=unit.media_type,
            ordinal=unit.ordinal,
            transformations=("safe-string-preservation",),
            quality_flags=unit.quality_flags,
            metadata=unit.metadata,
        )
