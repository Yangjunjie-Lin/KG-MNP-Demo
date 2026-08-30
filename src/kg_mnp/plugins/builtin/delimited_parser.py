"""Bounded deterministic CSV/TSV parser preserving formula-like text."""

import csv
from io import StringIO

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


class DelimitedTextParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        try:
            text = request.content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise PluginError("delimited text must be UTF-8 or UTF-8 BOM") from exc
        delimiter = "\t" if request.media_type == "text/tab-separated-values" else ","
        try:
            rows = csv.reader(StringIO(text, newline=""), delimiter=delimiter, quotechar='"', strict=True)
            units: list[ParsedUnit] = []
            for row_index, row in enumerate(rows, 1):
                if row_index > request.limits.max_table_rows:
                    raise PluginError("TABLE_ROW_LIMIT_EXCEEDED")
                if len(row) > request.limits.max_table_columns:
                    raise PluginError("TABLE_COLUMN_LIMIT_EXCEEDED")
                for column_index, value in enumerate(row, 1):
                    if len(value) > request.limits.max_cell_characters:
                        raise PluginError("CELL_CHARACTER_LIMIT_EXCEEDED")
                    flags = ("FORMULA_LIKE_CELL",) if value.startswith(("=", "+", "-", "@")) else ()
                    units.append(ParsedUnit("table-cell", value, {"locator_kind": "delimited-cell", "row": row_index, "column": column_index}, request.media_type, len(units), (("row", row_index), ("column", column_index), ("delimiter", delimiter), ("quote", '"'), ("encoding", "utf-8")), flags))
        except csv.Error as exc:
            raise PluginError(f"invalid delimited text: {exc}") from exc
        return tuple(units)
