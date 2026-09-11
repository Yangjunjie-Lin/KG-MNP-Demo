"""Frozen Plugin SDK request, response, registry and conformance models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PluginStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    VALID = "VALID"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"
    INCOMPATIBLE = "INCOMPATIBLE"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    INVALID = "INVALID"
    TAMPERED = "TAMPERED"


@dataclass(frozen=True)
class ResourceLimits:
    max_source_bytes: int = 32 * 1024 * 1024
    max_sources_per_batch: int = 256
    max_archive_entries: int = 2048
    max_archive_uncompressed_bytes: int = 128 * 1024 * 1024
    max_compression_ratio: int = 100
    max_json_depth: int = 64
    max_json_items: int = 100_000
    max_text_line_length: int = 1_000_000
    max_table_rows: int = 100_000
    max_table_columns: int = 4096
    max_cell_characters: int = 1_000_000
    max_pdf_pages: int = 2000
    max_document_blocks: int = 100_000
    max_image_pixels: int = 100_000_000
    max_audio_duration_ms: int = 86_400_000
    max_extracted_characters: int = 16_000_000

    def to_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class SourceReadRequest:
    source_path: Path
    limits: ResourceLimits


@dataclass(frozen=True)
class SourceReadResult:
    content: bytes
    display_name: str


@dataclass(frozen=True)
class MediaDetectionRequest:
    content: bytes
    original_name: str
    declared_media_type: str | None = None
    limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class MediaDetection:
    detected_media_type: str
    declared_media_type: str | None
    extension_hint: str | None
    confidence_basis: tuple[str, ...]
    conflicts: tuple[str, ...]
    selected_parser_capability: str | None


@dataclass(frozen=True)
class ParseRequest:
    content: bytes
    media_type: str
    limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class ParsedUnit:
    unit_kind: str
    value: Any
    locator: dict[str, Any]
    media_type: str
    ordinal: int
    metadata: tuple[tuple[str, Any], ...] = ()
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizeRequest:
    parsed_unit: ParsedUnit


@dataclass(frozen=True)
class NormalizedUnit:
    unit_kind: str
    original_value: Any
    normalized_value: Any
    locator: dict[str, Any]
    media_type: str
    ordinal: int
    transformations: tuple[str, ...]
    quality_flags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class QualityEvaluationRequest:
    units: tuple[NormalizedUnit, ...]
    unresolved_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityEvaluationResult:
    gate_status: str
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class PluginDescriptor:
    plugin_id: str
    manifest: dict[str, Any]
    manifest_bytes: bytes
    distribution_name: str
    distribution_version: str
    distribution_root: Path
    builtin: bool
    status: PluginStatus
    status_reason: str = ""
    entry_point: Any = None

    @property
    def enabled(self) -> bool:
        return self.status == PluginStatus.ENABLED


@dataclass(frozen=True)
class ProviderSelection:
    descriptor: PluginDescriptor
    reason: str


@dataclass(frozen=True)
class ConformanceResult:
    plugin_id: str
    status: str
    checks: tuple[tuple[str, str], ...]
    errors: tuple[str, ...] = ()
