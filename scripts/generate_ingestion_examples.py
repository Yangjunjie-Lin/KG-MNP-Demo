"""Generate small deterministic optional-document ingestion fixtures."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import struct
import tempfile
import wave
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "runtime_outputs" / "prompt-03-examples"
EXPECTED_FILES = ("sample.docx", "sample.pdf", "sample.png", "sample.wav", "sample.xlsx")
FIXED_TIME = datetime(2000, 1, 1, tzinfo=UTC)
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _canonicalize_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        members = [(name, archive.read(name)) for name in sorted(archive.namelist())]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in members:
            if name == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>2000-01-01T00:00:00Z\g<2>",
                    data,
                )
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, data)
    path.write_bytes(buffer.getvalue())


def _write_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.properties.creator = "KG-MNP Toolchain"
    workbook.properties.created = FIXED_TIME.replace(tzinfo=None)
    workbook.properties.modified = FIXED_TIME.replace(tzinfo=None)
    sheet = workbook.active
    sheet.title = "Observations"
    sheet.append(("record_id", "value", "derived_value"))
    sheet.append(("sample-001", 42.5, "=B2*2"))
    workbook.save(path)
    _canonicalize_zip(path)


def _write_docx(path: Path) -> None:
    from docx import Document

    document = Document()
    document.core_properties.author = "KG-MNP Toolchain"
    document.core_properties.created = FIXED_TIME
    document.core_properties.modified = FIXED_TIME
    document.add_heading("Evidence-bound ingestion", level=1)
    document.add_paragraph("This deterministic DOCX fixture contains reviewable source text.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "record_id"
    table.cell(0, 1).text = "value"
    table.cell(1, 0).text = "sample-001"
    table.cell(1, 1).text = "42.50"
    document.save(path)
    _canonicalize_zip(path)


def _pdf_bytes() -> bytes:
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length 73 >>\nstream\nBT /F1 12 Tf 72 720 Td "
            b"(KG-MNP Prompt 3 deterministic PDF source.) Tj ET\nendstream"
        ),
    )
    output = bytearray(b"%PDF-1.4\n%KG-MNP\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def _write_png(path: Path) -> None:
    from PIL import Image

    image = Image.new("RGB", (16, 16), color=(32, 96, 64))
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _write_wav(path: Path) -> None:
    sample_rate = 8_000
    frames = bytearray()
    for index in range(sample_rate // 4):
        value = round(2_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(frames))


def generate(output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    writers = {
        "sample.docx": _write_docx,
        "sample.pdf": lambda path: path.write_bytes(_pdf_bytes()),
        "sample.png": _write_png,
        "sample.wav": _write_wav,
        "sample.xlsx": _write_xlsx,
    }
    for name in EXPECTED_FILES:
        temporary = output / f".{name}.tmp"
        writers[name](temporary)
        temporary.replace(output / name)
    return {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in EXPECTED_FILES
    }


def check() -> dict[str, str]:
    with (
        tempfile.TemporaryDirectory(prefix="kg-mnp-ingestion-a-") as first,
        tempfile.TemporaryDirectory(prefix="kg-mnp-ingestion-b-") as second,
    ):
        first_hashes = generate(Path(first))
        second_hashes = generate(Path(second))
    if first_hashes != second_hashes:
        raise SystemExit("generated ingestion fixtures are not byte deterministic")
    return first_hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    hashes = check() if arguments.check else generate(arguments.output.resolve())
    print(json.dumps(hashes, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
