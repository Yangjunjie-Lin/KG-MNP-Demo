from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp.ingestion.errors import SourceError
from kg_mnp.ingestion.security import safe_relative_display
from kg_mnp.ingestion.source_store import SourceStore


@pytest.mark.parametrize(
    "value",
    ["../escape", "/absolute", "C:/drive", "//server/share", "\\\\server\\share"],
)
def test_source_destination_path_traversal_drive_and_unc_are_rejected(value: str) -> None:
    with pytest.raises(SourceError):
        safe_relative_display(Path(value))


def test_source_record_never_serializes_absolute_origin(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "nested" / "sample.txt"
    source.parent.mkdir()
    source.write_text("evidence", encoding="utf-8")
    record = SourceStore(prompt03_workspace).add_file(source).source
    serialized = json.dumps(record, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert source.as_posix() not in serialized


def test_atomic_blob_failure_does_not_leave_authoritative_blob_or_record(
    prompt03_workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("evidence", encoding="utf-8")
    store = SourceStore(prompt03_workspace)

    def fail_write(*_args, **_kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr("kg_mnp.ingestion.source_store.atomic_write_bytes", fail_write)
    with pytest.raises(OSError, match="simulated"):
        store.add_file(source)
    assert store.list_sources() == ()
    assert not any(path.is_file() for path in store.blob_root.rglob("*"))


def test_source_store_identifier_cannot_escape_record_directory(prompt03_workspace: Path) -> None:
    store = SourceStore(prompt03_workspace)
    for identifier in ("../escape", "urn:kg-mnp:source:..", "urn:kg-mnp:source:C:/escape"):
        with pytest.raises(SourceError):
            store.load_source(identifier)


def test_source_store_rejects_symlinked_authority_directory(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    store = SourceStore(prompt03_workspace)
    blobs = store.blob_root
    external = tmp_path / "external"
    external.mkdir()
    blobs.rmdir()
    try:
        blobs.symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink creation unavailable on this platform: {exc}")
    with pytest.raises(SourceError, match="symlink"):
        SourceStore(prompt03_workspace)
