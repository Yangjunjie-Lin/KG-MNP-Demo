"""Deterministic `.kgop` ZIP export and independent verification."""

from __future__ import annotations

import hashlib
import io
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from ..errors import PackageError
from ..security import validate_relative_path
from .verifier import verify_package

ZIP_DATE = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644 << 16


def archive_mapping_bytes(files: dict[str, bytes]) -> bytes:
    """Build canonical ZIP bytes from a closed mapping of safe POSIX paths."""

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for relative, data in sorted(files.items()):
            validate_relative_path(relative)
            info = zipfile.ZipInfo(relative, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ZIP_MODE
            info.flag_bits = 0
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def archive_bytes(package_directory: Path | str) -> bytes:
    root = Path(package_directory).resolve(strict=True)
    verify_package(root)
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    return archive_mapping_bytes(files)


def export_kgop(package_directory: Path | str, destination: Path | str) -> dict[str, Any]:
    data = archive_bytes(package_directory)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return {"archive_path": str(target), "archive_sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def verify_kgop(path: Path | str, *, max_uncompressed_bytes: int = 1_073_741_824, max_compression_ratio: int = 100) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    if source.is_symlink() or not source.is_file():
        raise PackageError("archive is missing or unsafe", code="PACKAGE_ARCHIVE_INVALID")
    raw = source.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [item.filename for item in archive.infolist()]
            if len(names) != len(set(names)):
                raise PackageError("duplicate ZIP entry", code="PACKAGE_ARCHIVE_INVALID")
            if names != sorted(names) or "ontology-package.json" not in names or "ontology-package.lock.json" not in names:
                raise PackageError("archive contents/order is invalid", code="PACKAGE_ARCHIVE_INVALID")
            total = 0
            files: dict[str, bytes] = {}
            for info in archive.infolist():
                validate_relative_path(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if PurePosixPath(info.filename).is_absolute() or info.is_dir() or info.date_time != ZIP_DATE or info.external_attr != ZIP_MODE or mode != 0o100000:
                    raise PackageError("archive metadata is non-deterministic or unsafe", code="PACKAGE_ARCHIVE_INVALID")
                total += info.file_size
                ratio = info.file_size / max(info.compress_size, 1)
                if total > max_uncompressed_bytes or ratio > max_compression_ratio:
                    raise PackageError("archive size/compression limit exceeded", code="PACKAGE_ARCHIVE_INVALID")
                files[info.filename] = archive.read(info)
    except PackageError:
        raise
    except (EOFError, OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise PackageError(
            f"archive container is invalid: {type(exc).__name__}",
            code="PACKAGE_ARCHIVE_INVALID",
        ) from exc
    with tempfile.TemporaryDirectory(prefix="kg-mnp-kgop-verify-") as directory:
        root = Path(directory)
        for relative, data in sorted(files.items()):
            target = root / PurePosixPath(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        package = verify_package(root)
        if archive_mapping_bytes(files) != raw:
            raise PackageError("archive bytes are not in canonical KGOP form", code="PACKAGE_ARCHIVE_INVALID")
    return {"status": "VALID", "package_id": package["package_id"], "lock_id": package["lock_id"], "archive_sha256": hashlib.sha256(raw).hexdigest(), "entry_count": len(names), "uncompressed_size": total, "contents": names}
