from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.errors import PackageError
from kg_mnp.semantic_kernel.packaging.archive import (
    ZIP_DATE,
    ZIP_MODE,
    archive_bytes,
    archive_mapping_bytes,
    verify_kgop,
)


def _entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = ZIP_MODE
    archive.writestr(info, data)


def test_archive_is_byte_deterministic_and_independently_verified(prompt05_case: dict, tmp_path: Path) -> None:
    first = archive_bytes(prompt05_case["result"].package_directory)
    second = archive_bytes(prompt05_case["result"].package_directory)
    assert first == second
    path = tmp_path / "package.kgop"
    path.write_bytes(first)
    report = verify_kgop(path)
    assert report["status"] == "VALID"
    assert report["contents"] == sorted(report["contents"])
    assert all(".." not in name and "\\" not in name for name in report["contents"])


def test_corrupt_duplicate_traversal_and_compression_bomb_archives_are_normalized(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.kgop"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(PackageError) as corrupt_error:
        verify_kgop(corrupt)
    assert corrupt_error.value.code == "PACKAGE_ARCHIVE_INVALID"

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        _entry(archive, "ontology-package.json", b"{}")
        _entry(archive, "ontology-package.json", b"{}")
        _entry(archive, "ontology-package.lock.json", b"{}")
    duplicate = tmp_path / "duplicate.kgop"
    duplicate.write_bytes(output.getvalue())
    with pytest.raises(PackageError, match="duplicate"):
        verify_kgop(duplicate)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        _entry(archive, "../escape", b"x")
        _entry(archive, "ontology-package.json", b"{}")
        _entry(archive, "ontology-package.lock.json", b"{}")
    traversal = tmp_path / "traversal.kgop"
    traversal.write_bytes(output.getvalue())
    with pytest.raises(ValueError, match="traversal"):
        verify_kgop(traversal)

    bomb = tmp_path / "bomb.kgop"
    bomb.write_bytes(archive_mapping_bytes({"a.bin": b"0" * 100_000, "ontology-package.json": b"{}", "ontology-package.lock.json": b"{}"}))
    with pytest.raises(PackageError, match="compression"):
        verify_kgop(bomb, max_compression_ratio=2)

