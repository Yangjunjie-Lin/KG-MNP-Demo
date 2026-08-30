from __future__ import annotations

import zipfile
from dataclasses import replace
from io import BytesIO

import pytest
from prompt03_support import docx_bytes, pdf_bytes, xlsx_bytes

from kg_mnp.plugins.builtin import validate_zip_container
from kg_mnp.plugins.builtin.docx_parser import DocxParser
from kg_mnp.plugins.builtin.pdf_parser import PdfParser
from kg_mnp.plugins.builtin.xlsx_parser import XlsxParser
from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParseRequest, ResourceLimits

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _rewrite_zip(
    content: bytes,
    *,
    replacements: dict[str, bytes] | None = None,
    additions: dict[str, bytes] | None = None,
) -> bytes:
    output = BytesIO()
    replacements = replacements or {}
    additions = additions or {}
    with zipfile.ZipFile(BytesIO(content)) as source, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for entry in source.infolist():
            target.writestr(entry.filename, replacements.get(entry.filename, source.read(entry)))
        for name, value in additions.items():
            target.writestr(name, value)
    return output.getvalue()


def test_zip_slip_zip_bomb_and_entry_limits_are_rejected() -> None:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../escape.xml", b"x")
    with pytest.raises(PluginError, match="ZIP_SLIP"):
        validate_zip_container(output.getvalue(), ResourceLimits())
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.txt", b"0" * 100_000)
    with pytest.raises(PluginError, match="ZIP_BOMB"):
        validate_zip_container(
            output.getvalue(), replace(ResourceLimits(), max_compression_ratio=2)
        )
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("one", b"1")
        archive.writestr("two", b"2")
    with pytest.raises(PluginError, match="entry limit"):
        validate_zip_container(output.getvalue(), replace(ResourceLimits(), max_archive_entries=1))


def test_office_macro_external_relationship_and_xxe_are_rejected() -> None:
    base = docx_bytes()
    macro = _rewrite_zip(base, additions={"word/vbaProject.bin": b"macro"})
    with pytest.raises(PluginError, match="MACRO"):
        DocxParser().parse(ParseRequest(macro, DOCX_MEDIA, ResourceLimits()))
    external_relationship = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="x" Target="https://example.invalid/data" TargetMode="External"/>
</Relationships>"""
    external = _rewrite_zip(base, replacements={"_rels/.rels": external_relationship})
    with pytest.raises(PluginError, match="EXTERNAL_RELATIONSHIP"):
        DocxParser().parse(ParseRequest(external, DOCX_MEDIA, ResourceLimits()))
    entity = b"""<?xml version="1.0"?>
<!DOCTYPE document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>"""
    xxe = _rewrite_zip(base, replacements={"word/document.xml": entity})
    with pytest.raises(PluginError, match="XML_EXTERNAL_ENTITY"):
        DocxParser().parse(ParseRequest(xxe, DOCX_MEDIA, ResourceLimits()))


def test_billion_laughs_equivalent_and_archive_size_are_rejected() -> None:
    expansion = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol1 "&lol;&lol;&lol;&lol;">]>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&lol1;</w:t></w:r></w:p></w:body></w:document>"""
    attacked = _rewrite_zip(docx_bytes(), replacements={"word/document.xml": expansion})
    with pytest.raises(PluginError, match="XML_EXTERNAL_ENTITY"):
        DocxParser().parse(ParseRequest(attacked, DOCX_MEDIA, ResourceLimits()))
    with pytest.raises(PluginError, match="ZIP_BOMB"):
        DocxParser().parse(
            ParseRequest(
                docx_bytes(),
                DOCX_MEDIA,
                replace(ResourceLimits(), max_archive_uncompressed_bytes=100),
            )
        )


def test_spreadsheet_pdf_and_document_resource_limits_are_enforced() -> None:
    with pytest.raises(PluginError, match="ROW"):
        XlsxParser().parse(
            ParseRequest(
                xlsx_bytes(),
                XLSX_MEDIA,
                replace(ResourceLimits(), max_table_rows=1),
            )
        )
    with pytest.raises(PluginError, match="PAGE"):
        PdfParser().parse(
            ParseRequest(pdf_bytes(), "application/pdf", replace(ResourceLimits(), max_pdf_pages=0))
        )
    with pytest.raises(PluginError, match="BLOCK"):
        DocxParser().parse(
            ParseRequest(
                docx_bytes(), DOCX_MEDIA, replace(ResourceLimits(), max_document_blocks=1)
            )
        )


@pytest.mark.parametrize("marker", [b"/JavaScript", b"/JS\n", b"/EmbeddedFiles", b"/Launch"])
def test_pdf_active_content_markers_are_rejected(marker: bytes) -> None:
    with pytest.raises(PluginError, match="ACTIVE_CONTENT"):
        PdfParser().parse(ParseRequest(pdf_bytes() + marker, "application/pdf", ResourceLimits()))
