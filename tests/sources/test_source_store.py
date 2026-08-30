from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp.contracts.registry import validate_contract
from kg_mnp.ingestion.errors import SourceError, SourceTamperedError
from kg_mnp.ingestion.limits import DEFAULT_LIMITS
from kg_mnp.ingestion.security import safe_relative_display
from kg_mnp.ingestion.source_store import SourceStore


def test_single_file_registration_contract_layout_and_no_path_leak(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "évidence.txt"
    source.write_text("alpha\n", encoding="utf-8")
    store = SourceStore(prompt03_workspace)
    result = store.add_file(source)
    validate_contract("source-asset", result.source)
    assert not result.duplicate
    assert result.source["original_name"] == "évidence.txt"
    assert result.source["blob_path"].startswith("sources/blobs/sha256/")
    assert str(tmp_path) not in json.dumps(result.source, ensure_ascii=False)
    assert store.verify_source(result.source["source_id"]) == result.source


def test_same_content_different_names_and_paths_has_same_source_id(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    left = tmp_path / "left" / "one.txt"
    right = tmp_path / "right" / "two.txt"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_bytes(b"same\n")
    right.write_bytes(b"same\n")
    store = SourceStore(prompt03_workspace)
    first = store.add_file(left)
    second = store.add_file(right)
    assert first.source["source_id"] == second.source["source_id"]
    assert second.duplicate
    assert len(store.list_sources()) == 1


def test_different_content_has_different_source_id(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("left", encoding="utf-8")
    right.write_text("right", encoding="utf-8")
    store = SourceStore(prompt03_workspace)
    assert store.add_file(left).source["source_id"] != store.add_file(right).source["source_id"]


def test_source_batch_is_sorted_unique_deterministic_and_closed(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    store = SourceStore(prompt03_workspace)
    identifiers = []
    for name in ("b.txt", "a.txt"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        identifiers.append(store.add_file(path).source["source_id"])
    first = store.create_batch(reversed(identifiers), labels=("z", "a", "a"))
    second = store.create_batch(identifiers, labels=("a", "z"))
    assert first == second
    assert first["sources"] == sorted(set(identifiers))
    assert first["labels"] == ["a", "z"]
    assert store.load_batch(first["batch_id"]) == first


def test_directory_order_recursion_hidden_and_count_limits(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    root = tmp_path / "inputs"
    root.mkdir()
    (root / "b.txt").write_text("b", encoding="utf-8")
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "c.txt").write_text("c", encoding="utf-8")
    store = SourceStore(prompt03_workspace)
    shallow = store.add_directory(root)
    assert [item.source["safe_display_path"] for item in shallow] == ["a.txt", "b.txt"]
    recursive = store.add_directory(root, recursive=True)
    assert [item.source["safe_display_path"] for item in recursive] == [
        "a.txt",
        "b.txt",
        "nested/c.txt",
    ]
    limited = SourceStore(
        prompt03_workspace,
        limits=replace(DEFAULT_LIMITS, max_sources_per_batch=2),
    )
    with pytest.raises(SourceError, match="COUNT"):
        limited.add_directory(root, recursive=True)


def test_source_size_and_unsafe_display_paths_are_rejected(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "large.txt"
    source.write_bytes(b"12345")
    store = SourceStore(prompt03_workspace, limits=replace(DEFAULT_LIMITS, max_source_bytes=4))
    with pytest.raises(SourceError, match="SIZE"):
        store.add_file(source)
    for value in (Path("../escape"), Path("C:/escape"), Path("/escape")):
        with pytest.raises(SourceError):
            safe_relative_display(value)


def test_blob_record_and_batch_tamper_are_detected(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("alpha", encoding="utf-8")
    store = SourceStore(prompt03_workspace)
    record = store.add_file(source).source
    batch = store.create_batch([record["source_id"]])
    blob = store.blob_for(record)
    blob.write_bytes(b"tampered")
    with pytest.raises(SourceTamperedError, match="hash"):
        store.verify_source(record["source_id"])
    blob.write_text("alpha", encoding="utf-8")
    batch_path = store.batches_root / f"{batch['batch_id'].rsplit(':', 1)[-1]}.json"
    document = json.loads(batch_path.read_bytes())
    document["labels"] = ["tampered"]
    batch_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises((ValueError, ValidationError)):
        store.load_batch(batch["batch_id"])


def test_mime_conflict_and_unknown_binary_are_honestly_recorded(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    disguised = tmp_path / "sample.pdf"
    disguised.write_text("plain text", encoding="utf-8")
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"\x00\xff\x10\x80")
    store = SourceStore(prompt03_workspace)
    conflict = store.add_file(disguised).source
    unknown = store.add_file(binary).source
    assert conflict["detected_media_type"] == "text/plain"
    assert conflict["metadata"]["media_conflicts"]
    assert unknown["detected_media_type"] == "application/octet-stream"


def test_symlink_and_non_regular_source_are_rejected(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable on this platform: {exc}")
    with pytest.raises(SourceError, match="SYMLINK"):
        SourceStore(prompt03_workspace).add_file(link)


@pytest.mark.skipif(os.name == "nt", reason="POSIX FIFO semantics are exercised by Ubuntu CI")
def test_fifo_is_rejected(prompt03_workspace: Path, tmp_path: Path) -> None:
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(SourceError, match="regular"):
        SourceStore(prompt03_workspace).add_file(fifo)


def test_hash_collision_simulation_never_overwrites_existing_record(
    prompt03_workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    forced = "urn:kg-mnp:source:" + "f" * 64
    monkeypatch.setattr("kg_mnp.ingestion.source_store.stable_urn", lambda *_args, **_kwargs: forced)
    store = SourceStore(prompt03_workspace)
    original = store.add_file(first).source
    with pytest.raises(SourceTamperedError, match="collision"):
        store.add_file(second)
    assert store.load_source(forced) == original
