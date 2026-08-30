"""SourceLocator semantic validation and locator re-extraction."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from jsonschema import ValidationError

from kg_mnp.contracts.canonical import bytes_sha256
from kg_mnp.contracts.registry import validate_contract
from kg_mnp.plugins.builtin.docx_parser import DocxParser
from kg_mnp.plugins.builtin.image_metadata_parser import ImageMetadataParser
from kg_mnp.plugins.builtin.json_parser import JSONParser
from kg_mnp.plugins.builtin.pdf_parser import PdfParser
from kg_mnp.plugins.builtin.wav_metadata_parser import WavMetadataParser
from kg_mnp.plugins.builtin.xlsx_parser import XlsxParser
from kg_mnp.plugins.models import ParseRequest, ResourceLimits

from .errors import SourceError


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise SourceError(f"JSON Pointer is out of bounds: {pointer}") from exc
    return current


def _check_order(locator: dict[str, Any]) -> None:
    kind = locator["locator_kind"]
    pairs = {
        "byte-range": (("start", "end"),),
        "text-line-range": (("start_line", "end_line"),),
        "delimited-range": (("start_row", "end_row"), ("start_column", "end_column")),
        "spreadsheet-range": (("start_row", "end_row"), ("start_column", "end_column")),
        "time-range": (("start_ms", "end_ms"),),
    }
    for start, end in pairs.get(kind, ()):
        if locator[end] < locator[start]:
            raise SourceError(f"invalid {kind}: {end} is before {start}")
        if kind in {"byte-range", "time-range"} and locator[end] == locator[start]:
            raise SourceError(f"invalid empty end-exclusive {kind}")


def validate_locator(locator: dict[str, Any]) -> None:
    try:
        validate_contract("source-locator", locator)
    except ValidationError as exc:
        raise SourceError(f"invalid SourceLocator: {exc.message}") from exc
    _check_order(locator)


def extract_locator_value(
    *,
    content: bytes,
    media_type: str,
    locator: dict[str, Any],
    limits: ResourceLimits,
) -> Any:
    validate_locator(locator)
    kind = locator["locator_kind"]
    if kind == "whole-source":
        return bytes_sha256(content)
    if kind == "byte-range":
        if locator["end"] > len(content):
            raise SourceError("byte range is out of bounds")
        return content[locator["start"]:locator["end"]]
    if kind == "text-line-range":
        try:
            lines = content.decode("utf-8-sig").splitlines(keepends=True) or [""]
        except UnicodeDecodeError as exc:
            raise SourceError("line locator source is not UTF-8") from exc
        if locator["end_line"] > len(lines):
            raise SourceError("text line range is out of bounds")
        selected = [line.rstrip("\r\n") for line in lines[locator["start_line"] - 1:locator["end_line"]]]
        return "\n".join(selected)
    if kind == "json-pointer":
        units = JSONParser().parse(ParseRequest(content, media_type, limits))
        for unit in units:
            if unit.locator == locator:
                return unit.value
        raise SourceError("JSON Pointer is out of bounds")
    if kind in {"delimited-cell", "delimited-range"}:
        delimiter = "\t" if media_type == "text/tab-separated-values" else ","
        rows = list(csv.reader(StringIO(content.decode("utf-8-sig")), delimiter=delimiter))
        if kind == "delimited-cell":
            row, column = locator["row"], locator["column"]
            if row > len(rows) or column > len(rows[row - 1]):
                raise SourceError("delimited cell is out of bounds")
            return rows[row - 1][column - 1]
        start_row, end_row = locator["start_row"], locator["end_row"]
        start_column, end_column = locator["start_column"], locator["end_column"]
        if end_row > len(rows):
            raise SourceError("delimited range is out of bounds")
        selected = []
        for row in rows[start_row - 1:end_row]:
            if end_column > len(row):
                raise SourceError("delimited range is out of bounds")
            selected.append(row[start_column - 1:end_column])
        return selected
    if kind == "spreadsheet-range":
        units = XlsxParser().parse(ParseRequest(content, media_type, limits))
        cells = {
            (unit.locator["sheet"], unit.locator["row"], unit.locator["column"]): unit.value
            for unit in units
        }
        result = []
        for row in range(locator["start_row"], locator["end_row"] + 1):
            result.append(
                [
                    cells.get((locator["sheet"], row, column))
                    for column in range(locator["start_column"], locator["end_column"] + 1)
                ]
            )
        if not any(key[0] == locator["sheet"] for key in cells):
            raise SourceError("spreadsheet range sheet is out of bounds")
        return result
    providers = {
        "spreadsheet-cell": XlsxParser,
        "document-paragraph": DocxParser,
        "document-table-cell": DocxParser,
        "pdf-page": PdfParser,
        "pdf-page-region": PdfParser,
        "image-region": ImageMetadataParser,
        "time-range": WavMetadataParser,
    }
    provider_type = providers.get(kind)
    if provider_type is not None:
        units = provider_type().parse(ParseRequest(content, media_type, limits))
        for unit in units:
            if unit.locator == locator:
                return unit.value
        if kind == "image-region":
            from io import BytesIO

            from PIL import Image

            with Image.open(BytesIO(content)) as image:
                if locator["x"] + locator["width"] > image.width or locator["y"] + locator["height"] > image.height:
                    raise SourceError("image region is out of bounds")
                return None
        raise SourceError(f"{kind} is out of bounds")
    raise SourceError(f"unsupported locator extraction: {kind}")
