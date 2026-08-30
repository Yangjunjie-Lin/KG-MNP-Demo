"""UTF-8/BOM plain-text parser with 1-based line locators."""

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


class PlainTextParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        try:
            text = request.content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise PluginError("plain text must be UTF-8 or UTF-8 BOM") from exc
        lines = text.splitlines(keepends=True) or [""]
        units = []
        total = 0
        for index, line in enumerate(lines, 1):
            value = line.rstrip("\r\n")
            if len(value) > request.limits.max_text_line_length:
                raise PluginError("TEXT_LINE_LENGTH_LIMIT_EXCEEDED")
            total += len(value)
            if total > request.limits.max_extracted_characters:
                raise PluginError("EXTRACTED_CHARACTER_LIMIT_EXCEEDED")
            units.append(ParsedUnit("text-block", value, {"locator_kind": "text-line-range", "start_line": index, "end_line": index}, "text/plain", index - 1))
        return tuple(units)
