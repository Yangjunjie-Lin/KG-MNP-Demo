"""Public source-registration helpers."""

from pathlib import Path

from .limits import DEFAULT_LIMITS, ResourceLimits
from .source_store import SourceStore


def register_source(
    workspace: Path | str,
    source: Path | str,
    *,
    declared_media_type: str | None = None,
    limits: ResourceLimits = DEFAULT_LIMITS,
) -> dict:
    return SourceStore(workspace, limits=limits).add_file(
        source, declared_media_type=declared_media_type
    ).source
