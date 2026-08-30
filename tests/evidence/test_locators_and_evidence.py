from __future__ import annotations

import copy
from pathlib import Path

import pytest
from prompt03_support import docx_bytes, pdf_bytes, png_bytes, wav_bytes, xlsx_bytes

from kg_mnp.ingestion.errors import SourceError, SourceTamperedError
from kg_mnp.ingestion.evidence import build_evidence_bundle, verify_evidence_closure
from kg_mnp.ingestion.normalization import normalize_units
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.ingestion.validation import extract_locator_value, validate_locator
from kg_mnp.plugins.builtin.json_parser import JSONParser
from kg_mnp.plugins.builtin.normalizer import GenericNormalizer
from kg_mnp.plugins.models import ParseRequest, ResourceLimits
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot

LIMITS = ResourceLimits()


@pytest.mark.parametrize(
    ("content", "media_type", "locator", "expected"),
    [
        (b"abc", "application/octet-stream", {"locator_kind": "whole-source"}, None),
        (b"abc", "application/octet-stream", {"locator_kind": "byte-range", "start": 1, "end": 3}, b"bc"),
        (b"one\r\ntwo\n", "text/plain", {"locator_kind": "text-line-range", "start_line": 1, "end_line": 2}, "one\ntwo"),
        (b'{"a":{"b":1}}', "application/json", {"locator_kind": "json-pointer", "pointer": "/a/b"}, 1),
        (b"a,b\n1,2\n", "text/csv", {"locator_kind": "delimited-cell", "row": 2, "column": 2}, "2"),
        (b"a,b\n1,2\n", "text/csv", {"locator_kind": "delimited-range", "start_row": 1, "end_row": 2, "start_column": 1, "end_column": 2}, [["a", "b"], ["1", "2"]]),
    ],
)
def test_core_locator_extraction(
    content: bytes, media_type: str, locator: dict, expected: object
) -> None:
    extracted = extract_locator_value(
        content=content, media_type=media_type, locator=locator, limits=LIMITS
    )
    if locator["locator_kind"] == "whole-source":
        assert isinstance(extracted, str) and len(extracted) == 64
    else:
        assert extracted == expected


def test_document_spreadsheet_pdf_image_and_time_locators() -> None:
    assert extract_locator_value(
        content=xlsx_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        locator={"locator_kind": "spreadsheet-cell", "sheet": "Evidence", "row": 2, "column": 2},
        limits=LIMITS,
    ) == "=1+1"
    assert extract_locator_value(
        content=xlsx_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        locator={"locator_kind": "spreadsheet-range", "sheet": "Evidence", "start_row": 1, "end_row": 2, "start_column": 1, "end_column": 2},
        limits=LIMITS,
    ) == [["name", "value"], ["alpha", "=1+1"]]
    assert extract_locator_value(
        content=docx_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        locator={"locator_kind": "document-paragraph", "paragraph_index": 0},
        limits=LIMITS,
    ) == "Evidence paragraph"
    assert extract_locator_value(
        content=docx_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        locator={"locator_kind": "document-table-cell", "table_index": 0, "row": 1, "column": 1},
        limits=LIMITS,
    ) == "Evidence cell"
    assert "Evidence page" in extract_locator_value(
        content=pdf_bytes(),
        media_type="application/pdf",
        locator={"locator_kind": "pdf-page", "page": 1},
        limits=LIMITS,
    )
    assert extract_locator_value(
        content=png_bytes(),
        media_type="image/png",
        locator={"locator_kind": "image-region", "x": 0, "y": 0, "width": 2, "height": 3},
        limits=LIMITS,
    ) is None
    assert extract_locator_value(
        content=wav_bytes(),
        media_type="audio/wav",
        locator={"locator_kind": "time-range", "start_ms": 0, "end_ms": 10},
        limits=LIMITS,
    ) is None


@pytest.mark.parametrize(
    "locator",
    [
        {"locator_kind": "unknown"},
        {"locator_kind": "byte-range", "start": 2, "end": 1},
        {"locator_kind": "time-range", "start_ms": 1, "end_ms": 1},
        {"locator_kind": "text-line-range", "start_line": 2, "end_line": 1},
        {"locator_kind": "json-pointer", "pointer": "not/a/pointer"},
        {"locator_kind": "spreadsheet-cell", "sheet": "", "row": 1, "column": 1},
        {"locator_kind": "pdf-page", "page": 0},
    ],
)
def test_invalid_locator_shapes_and_order_are_rejected(locator: dict) -> None:
    with pytest.raises(SourceError):
        validate_locator(locator)


def test_out_of_bounds_locators_are_rejected() -> None:
    with pytest.raises(SourceError, match="out of bounds"):
        extract_locator_value(
            content=b"abc",
            media_type="application/octet-stream",
            locator={"locator_kind": "byte-range", "start": 0, "end": 4},
            limits=LIMITS,
        )
    with pytest.raises(SourceError, match="out of bounds"):
        extract_locator_value(
            content=b"one\n",
            media_type="text/plain",
            locator={"locator_kind": "text-line-range", "start_line": 1, "end_line": 2},
            limits=LIMITS,
        )
    with pytest.raises(SourceError, match="out of bounds"):
        extract_locator_value(
            content=png_bytes(),
            media_type="image/png",
            locator={"locator_kind": "image-region", "x": 1, "y": 1, "width": 2, "height": 3},
            limits=LIMITS,
        )


def test_evidence_decimal_reverification_and_all_closures(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    path = tmp_path / "decimal.json"
    path.write_bytes(b'{"value":1.2300}')
    store = SourceStore(prompt03_workspace)
    source = store.add_file(path).source
    content = store.blob_for(source).read_bytes()
    parsed = JSONParser().parse(ParseRequest(content, "application/json", LIMITS))
    normalized = normalize_units(GenericNormalizer(), parsed)
    snapshot = build_snapshot(PluginRegistry(discover_external=False).get("json-parser"))
    bundle = build_evidence_bundle(
        source=source,
        content=content,
        units=normalized,
        parser_snapshot_id=snapshot["snapshot_id"],
    )
    verify_evidence_closure(
        records=bundle.evidence_records,
        transformations=bundle.transformation_records,
        snapshots=(snapshot,),
        sources={source["source_id"]: (source, content)},
        limits=LIMITS,
    )
    leaf = next(
        item for item in bundle.evidence_records if item["locator"]["locator_kind"] == "json-pointer"
    )
    assert leaf["observed_value"] == {"decimal": "1.2300"}


def test_evidence_id_tamper_source_plugin_and_transformation_gaps_fail_closed(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    path = tmp_path / "sample.json"
    path.write_bytes(b'{"value":1}')
    store = SourceStore(prompt03_workspace)
    source = store.add_file(path).source
    content = store.blob_for(source).read_bytes()
    units = normalize_units(
        GenericNormalizer(), JSONParser().parse(ParseRequest(content, "application/json", LIMITS))
    )
    snapshot = build_snapshot(PluginRegistry(discover_external=False).get("json-parser"))
    bundle = build_evidence_bundle(
        source=source,
        content=content,
        units=units,
        parser_snapshot_id=snapshot["snapshot_id"],
    )
    tampered = list(copy.deepcopy(bundle.evidence_records))
    tampered[0]["evidence_id"] = "urn:kg-mnp:evidence:" + "0" * 64
    with pytest.raises(ValueError, match="mismatch"):
        verify_evidence_closure(
            records=tuple(tampered),
            transformations=bundle.transformation_records,
            snapshots=(snapshot,),
            sources={source["source_id"]: (source, content)},
            limits=LIMITS,
        )
    for sources, snapshots, transformations in (
        ({}, (snapshot,), bundle.transformation_records),
        ({source["source_id"]: (source, content)}, (), bundle.transformation_records),
        ({source["source_id"]: (source, content)}, (snapshot,), ()),
    ):
        with pytest.raises(SourceTamperedError):
            verify_evidence_closure(
                records=bundle.evidence_records,
                transformations=transformations,
                snapshots=snapshots,
                sources=sources,
                limits=LIMITS,
            )
