"""Non-executing Markdown block parser with line provenance."""

from zhigou_toolchain.plugins.builtin.text_parser import PlainTextParser
from zhigou_toolchain.plugins.models import ParsedUnit, ParseRequest


class MarkdownParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        lines = PlainTextParser().parse(request)
        result = []
        in_code = False
        for unit in lines:
            text = str(unit.value)
            if text.lstrip().startswith("```"):
                in_code = not in_code
                kind = "code-block"
            elif in_code:
                kind = "code-block"
            elif text.startswith("#"):
                kind = "heading"
            elif text.lstrip().startswith(("- ", "* ", "+ ")):
                kind = "list-item"
            else:
                kind = "paragraph"
            result.append(ParsedUnit("text-block", text, unit.locator, "text/markdown", unit.ordinal, (("block_kind", kind),)))
        return tuple(result)
