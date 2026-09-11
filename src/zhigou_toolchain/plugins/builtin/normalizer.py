"""NFC/newline-only generic normalization; no domain inference."""

from __future__ import annotations

import unicodedata

from zhigou_toolchain.plugins.models import NormalizedUnit, NormalizeRequest


class GenericNormalizer:
    def normalize(self, request: NormalizeRequest) -> NormalizedUnit:
        unit = request.parsed_unit
        value = unit.value
        transformations: list[str] = []
        if isinstance(value, str):
            newline = value.replace("\r\n", "\n").replace("\r", "\n")
            if newline != value:
                transformations.append("newline-lf")
            normalized = unicodedata.normalize("NFC", newline)
            if normalized != newline:
                transformations.append("unicode-nfc")
            if not transformations:
                transformations.append("safe-string-preservation")
        elif isinstance(value, dict) and set(value) == {"decimal"}:
            normalized = value
            transformations.append("decimal-string-preservation")
        else:
            normalized = value
            transformations.append("safe-string-preservation")
        return NormalizedUnit(unit.unit_kind, value, normalized, unit.locator, unit.media_type, unit.ordinal, tuple(transformations), unit.quality_flags, unit.metadata)
