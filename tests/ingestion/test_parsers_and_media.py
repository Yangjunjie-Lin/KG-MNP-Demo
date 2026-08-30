from __future__ import annotations

from dataclasses import replace

import pytest
from prompt03_support import docx_bytes, pdf_bytes, png_bytes, wav_bytes, xlsx_bytes

from kg_mnp.ingestion.media_detection import detect_media_type
from kg_mnp.plugins.builtin.delimited_parser import DelimitedTextParser
from kg_mnp.plugins.builtin.docx_parser import DocxParser
from kg_mnp.plugins.builtin.image_metadata_parser import ImageMetadataParser
from kg_mnp.plugins.builtin.json_parser import JSONParser
from kg_mnp.plugins.builtin.markdown_parser import MarkdownParser
from kg_mnp.plugins.builtin.pdf_parser import PdfParser
from kg_mnp.plugins.builtin.text_parser import PlainTextParser
from kg_mnp.plugins.builtin.wav_metadata_parser import WavMetadataParser
from kg_mnp.plugins.builtin.xlsx_parser import XlsxParser
from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParseRequest, ResourceLimits

LIMITS = ResourceLimits()


def test_media_detection_uses_signature_structure_and_reports_conflicts() -> None:
    pdf = detect_media_type(pdf_bytes(), "disguised.txt", declared_media_type="text/plain")
    assert pdf.detected_media_type == "application/pdf"
    assert pdf.selected_parser_capability == "parse-pdf"
    assert len(pdf.conflicts) == 2
    xlsx = detect_media_type(xlsx_bytes(), "book.bin")
    assert xlsx.detected_media_type.endswith("spreadsheetml.sheet")
    video = detect_media_type(b"not a supported video parser", "clip.mp4")
    assert video.detected_media_type == "text/plain"
    assert video.conflicts
    binary_video = detect_media_type(b"\x00\x00\x00\x18ftypmp42\xff", "clip.mp4")
    assert binary_video.detected_media_type == "video/mp4"
    assert binary_video.selected_parser_capability is None


def test_plain_text_bom_lines_limits_and_empty_source() -> None:
    units = PlainTextParser().parse(ParseRequest(b"\xef\xbb\xbfalpha\r\nbeta\n", "text/plain", LIMITS))
    assert [item.value for item in units] == ["alpha", "beta"]
    assert units[0].locator == {
        "locator_kind": "text-line-range",
        "start_line": 1,
        "end_line": 1,
    }
    empty = PlainTextParser().parse(ParseRequest(b"", "text/plain", LIMITS))
    assert len(empty) == 1 and empty[0].value == ""
    with pytest.raises(PluginError, match="LINE_LENGTH"):
        PlainTextParser().parse(
            ParseRequest(b"12345", "text/plain", replace(LIMITS, max_text_line_length=4))
        )


def test_markdown_classifies_without_executing_links_or_html() -> None:
    units = MarkdownParser().parse(
        ParseRequest(b"# Heading\n- item\n<script>alert(1)</script>\n```\ncode\n```\n", "text/markdown", LIMITS)
    )
    kinds = [dict(item.metadata)["block_kind"] for item in units]
    assert kinds == ["heading", "list-item", "paragraph", "code-block", "code-block", "code-block"]
    assert units[2].value == "<script>alert(1)</script>"


def test_json_duplicate_depth_decimal_exponent_and_integer_preservation() -> None:
    units = JSONParser().parse(
        ParseRequest(b'{"decimal":1.2300,"exponent":1e3,"integer":2}', "application/json", LIMITS)
    )
    by_pointer = {item.locator["pointer"]: item.value for item in units}
    assert by_pointer == {
        "/decimal": {"decimal": "1.2300"},
        "/exponent": {"decimal": "1E+3"},
        "/integer": 2,
    }
    with pytest.raises(PluginError, match="DUPLICATE_JSON_KEY"):
        JSONParser().parse(ParseRequest(b'{"a":1,"a":2}', "application/json", LIMITS))
    with pytest.raises(PluginError, match="DEPTH"):
        JSONParser().parse(
            ParseRequest(b'{"a":{"b":1}}', "application/json", replace(LIMITS, max_json_depth=1))
        )


def test_csv_tsv_formula_empty_and_resource_limits() -> None:
    csv_units = DelimitedTextParser().parse(
        ParseRequest(b"name,value,empty\nalpha,=1+1,\n", "text/csv", LIMITS)
    )
    formula = next(item for item in csv_units if item.value == "=1+1")
    assert formula.quality_flags == ("FORMULA_LIKE_CELL",)
    assert csv_units[-1].value == ""
    tsv_units = DelimitedTextParser().parse(
        ParseRequest(b"a\tb\n1\t2\n", "text/tab-separated-values", LIMITS)
    )
    assert dict(tsv_units[0].metadata)["delimiter"] == "\t"
    with pytest.raises(PluginError, match="COLUMN"):
        DelimitedTextParser().parse(
            ParseRequest(b"a,b\n", "text/csv", replace(LIMITS, max_table_columns=1))
        )
    with pytest.raises(PluginError, match="CELL_CHARACTER"):
        DelimitedTextParser().parse(
            ParseRequest(b"12345\n", "text/csv", replace(LIMITS, max_cell_characters=4))
        )


def test_xlsx_formula_docx_paragraph_and_table_cell() -> None:
    xlsx = XlsxParser().parse(
        ParseRequest(
            xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            LIMITS,
        )
    )
    formula = next(item for item in xlsx if item.value == "=1+1")
    assert formula.quality_flags == ("FORMULA_PRESERVED_AS_TEXT",)
    assert formula.locator == {
        "locator_kind": "spreadsheet-cell",
        "sheet": "Evidence",
        "row": 2,
        "column": 2,
    }
    docx = DocxParser().parse(
        ParseRequest(
            docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            LIMITS,
        )
    )
    assert any(item.locator["locator_kind"] == "document-paragraph" for item in docx)
    assert any(item.locator["locator_kind"] == "document-table-cell" for item in docx)


def test_pdf_text_empty_page_and_active_content() -> None:
    units = PdfParser().parse(ParseRequest(pdf_bytes("Evidence page"), "application/pdf", LIMITS))
    assert len(units) == 1
    assert "Evidence page" in units[0].value
    assert units[0].quality_flags == ("PDF_TEXT_ORDER_UNCERTAIN",)
    empty = PdfParser().parse(ParseRequest(pdf_bytes(""), "application/pdf", LIMITS))
    assert empty[0].quality_flags == ("SCANNED_OR_IMAGE_ONLY_PAGE",)
    active = pdf_bytes() + b"\n/JS\n"
    with pytest.raises(PluginError, match="ACTIVE_CONTENT"):
        PdfParser().parse(ParseRequest(active, "application/pdf", LIMITS))


def test_image_metadata_and_pixel_limit_do_not_claim_vision() -> None:
    units = ImageMetadataParser().parse(ParseRequest(png_bytes(), "image/png", LIMITS))
    metadata = dict(units[0].metadata)
    assert metadata["width"] == 2 and metadata["height"] == 3
    assert units[0].value is None
    assert units[0].quality_flags == ("MISSING_OCR_OR_VISION_PROVIDER",)
    with pytest.raises(PluginError, match="PIXEL"):
        ImageMetadataParser().parse(
            ParseRequest(png_bytes(), "image/png", replace(LIMITS, max_image_pixels=5))
        )


def test_wav_metadata_duration_and_corruption_without_transcription() -> None:
    units = WavMetadataParser().parse(ParseRequest(wav_bytes(), "audio/wav", LIMITS))
    metadata = dict(units[0].metadata)
    assert metadata["duration_ms"] == 10
    assert units[0].quality_flags == ("MISSING_TRANSCRIPTION_PROVIDER",)
    with pytest.raises(PluginError, match="corrupt WAV"):
        WavMetadataParser().parse(ParseRequest(b"RIFFbad", "audio/wav", LIMITS))
    with pytest.raises(PluginError, match="DURATION"):
        WavMetadataParser().parse(
            ParseRequest(wav_bytes(), "audio/wav", replace(LIMITS, max_audio_duration_ms=9))
        )
