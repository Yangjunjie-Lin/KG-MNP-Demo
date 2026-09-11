"""Signature, structure, UTF-8 and extension-based deterministic media detection."""

from __future__ import annotations

import csv
import json
import zipfile
from io import StringIO
from pathlib import PurePath

from zhigou_toolchain.plugins.models import MediaDetection, MediaDetectionRequest

_EXTENSIONS = {
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".tif": "image/tiff",
    ".tiff": "image/tiff", ".wav": "audio/wav", ".json": "application/json", ".csv": "text/csv",
    ".tsv": "text/tab-separated-values", ".md": "text/markdown", ".markdown": "text/markdown",
    ".txt": "text/plain", ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".zip": "application/zip",
}

_CAPABILITIES = {
    "application/pdf": "parse-pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "parse-docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "parse-xlsx", "image/png": "parse-image-metadata",
    "image/jpeg": "parse-image-metadata", "image/gif": "parse-image-metadata", "image/tiff": "parse-image-metadata",
    "audio/wav": "parse-wav-metadata", "application/json": "parse-json", "text/csv": "parse-delimited",
    "text/tab-separated-values": "parse-delimited", "text/markdown": "parse-markdown", "text/plain": "parse-text",
}


def _office_type(content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(content)) as archive:
            names = {item.filename.replace("\\", "/") for item in archive.infolist()}
    except zipfile.BadZipFile:
        return None
    if "word/document.xml" in names and "[Content_Types].xml" in names:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if "xl/workbook.xml" in names and "[Content_Types].xml" in names:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/zip"


def _textual_type(content: bytes, extension: str) -> tuple[str, list[str]] | None:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    basis = ["valid UTF-8 or UTF-8 BOM"]
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            json.loads(text)
            return "application/json", [*basis, "valid JSON structure"]
        except json.JSONDecodeError:
            pass
    if extension in {".md", ".markdown"}:
        return "text/markdown", [*basis, "Markdown extension hint"]
    sample = text[:65536]
    if "\t" in sample and sample.count("\t") >= sample.count(","):
        try:
            list(csv.reader(StringIO(sample), delimiter="\t"))
            return "text/tab-separated-values", [*basis, "bounded tabular delimiter structure"]
        except csv.Error:
            pass
    if "," in sample and "\n" in sample:
        try:
            list(csv.reader(StringIO(sample), delimiter=","))
            return "text/csv", [*basis, "bounded comma delimiter structure"]
        except csv.Error:
            pass
    return "text/plain", basis


class SignatureMediaDetector:
    def detect(self, request: MediaDetectionRequest) -> MediaDetection:
        content = request.content
        extension = PurePath(request.original_name).suffix.casefold()
        extension_hint = _EXTENSIONS.get(extension)
        detected = "application/octet-stream"
        basis: list[str] = []
        if content.startswith(b"%PDF-"):
            detected, basis = "application/pdf", ["PDF magic signature"]
        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            detected, basis = "image/png", ["PNG magic signature"]
        elif content.startswith(b"\xff\xd8\xff"):
            detected, basis = "image/jpeg", ["JPEG magic signature"]
        elif content.startswith((b"GIF87a", b"GIF89a")):
            detected, basis = "image/gif", ["GIF magic signature"]
        elif content.startswith((b"II*\x00", b"MM\x00*")):
            detected, basis = "image/tiff", ["TIFF magic signature"]
        elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
            detected, basis = "audio/wav", ["RIFF/WAVE signature"]
        elif len(content) >= 20 and content[4:8] == b"ftyp" and content[8:12] in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1"} and 16 <= int.from_bytes(content[:4], "big") <= len(content):
            detected, basis = "video/mp4", ["ISO BMFF MP4 brand signature"]
        elif content.startswith(b"PK\x03\x04"):
            detected = _office_type(content) or "application/zip"
            basis = ["ZIP signature", "bounded Office ZIP structure inspection"]
        else:
            textual = _textual_type(content, extension)
            if textual:
                detected, basis = textual
            elif extension_hint in {"video/mp4", "audio/mpeg"}:
                detected, basis = extension_hint, ["unsupported-format extension hint only"]
        conflicts: list[str] = []
        if extension_hint and extension_hint != detected:
            conflicts.append(f"extension suggests {extension_hint}, structure indicates {detected}")
        if request.declared_media_type and request.declared_media_type != detected:
            conflicts.append(
                f"declared media type {request.declared_media_type} conflicts with {detected}"
            )
        return MediaDetection(
            detected_media_type=detected,
            declared_media_type=request.declared_media_type,
            extension_hint=extension_hint,
            confidence_basis=tuple(basis or ["no recognized safe signature"]),
            conflicts=tuple(sorted(conflicts)),
            selected_parser_capability=_CAPABILITIES.get(detected),
        )
