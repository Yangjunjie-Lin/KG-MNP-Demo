"""Audited deterministic built-in Plugin providers."""

from __future__ import annotations

import zipfile
from io import BytesIO

from zhigou_toolchain.plugins.errors import PluginError
from zhigou_toolchain.plugins.models import ResourceLimits


def validate_zip_container(content: bytes, limits: ResourceLimits) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(BytesIO(content))
        entries = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise PluginError(f"invalid ZIP container: {exc}") from exc
    if len(entries) > limits.max_archive_entries:
        archive.close()
        raise PluginError("ZIP entry limit exceeded")
    total = 0
    for entry in entries:
        name = entry.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/") or "\x00" in name:
            archive.close()
            raise PluginError("ZIP_SLIP: unsafe archive member")
        total += entry.file_size
        if total > limits.max_archive_uncompressed_bytes:
            archive.close()
            raise PluginError("ZIP_BOMB: uncompressed byte limit exceeded")
        compressed = max(entry.compress_size, 1)
        if entry.file_size / compressed > limits.max_compression_ratio:
            archive.close()
            raise PluginError("ZIP_BOMB: compression ratio limit exceeded")
    return archive


def reject_office_active_content(archive: zipfile.ZipFile) -> None:
    names = {
        item.filename.casefold().replace("\\", "/"): item.filename
        for item in archive.infolist()
    }
    if any(name.endswith("vbaproject.bin") for name in names):
        raise PluginError("OFFICE_MACRO_REJECTED")
    for name, actual_name in names.items():
        if name.endswith((".xml", ".rels")):
            data = archive.read(actual_name)
            lowered = data.lower()
            if b"<!doctype" in lowered or b"<!entity" in lowered:
                raise PluginError("XML_EXTERNAL_ENTITY_REJECTED")
            try:
                from defusedxml import ElementTree

                ElementTree.fromstring(data)
            except ImportError as exc:
                raise PluginError("MISSING_DEPENDENCY: defusedxml") from exc
            except Exception as exc:
                raise PluginError(f"UNSAFE_OR_INVALID_XML: {name}") from exc
        if name.endswith(".rels"):
            data = archive.read(actual_name)
            lowered = data.lower()
            if b'targetmode="external"' in lowered or b"targetmode='external'" in lowered:
                raise PluginError("OFFICE_EXTERNAL_RELATIONSHIP_REJECTED")
