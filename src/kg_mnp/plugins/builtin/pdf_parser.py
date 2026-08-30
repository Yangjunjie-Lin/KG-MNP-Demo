"""Bounded PDF page-text parser; active content denied and OCR not fabricated."""

import re
from io import BytesIO

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


class PdfParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        lowered = request.content.lower()
        if re.search(rb"/(?:javascript|js|embeddedfiles|launch)\b", lowered):
            raise PluginError("PDF_ACTIVE_CONTENT_REJECTED")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise PluginError("MISSING_DEPENDENCY: pypdf") from exc
        try:
            reader = PdfReader(BytesIO(request.content), strict=True)
        except Exception as exc:
            raise PluginError(f"invalid PDF: {exc}") from exc
        if len(reader.pages) > request.limits.max_pdf_pages:
            raise PluginError("PDF_PAGE_LIMIT_EXCEEDED")
        units: list[ParsedUnit] = []
        total = 0
        for page_number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise PluginError(f"PDF text extraction failed on page {page_number}: {exc}") from exc
            total += len(text)
            if total > request.limits.max_extracted_characters:
                raise PluginError("EXTRACTED_CHARACTER_LIMIT_EXCEEDED")
            flags = ("SCANNED_OR_IMAGE_ONLY_PAGE",) if not text.strip() else ("PDF_TEXT_ORDER_UNCERTAIN",)
            units.append(ParsedUnit("text-block", text, {"locator_kind": "pdf-page", "page": page_number}, request.media_type, page_number - 1, (("block_kind", "plain"),), flags))
        return tuple(units)
