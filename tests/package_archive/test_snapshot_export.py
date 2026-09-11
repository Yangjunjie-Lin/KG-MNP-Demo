"""Exports validate captured bytes, never a mutable-path cached verdict."""
import hashlib
import zipfile
from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.errors import PackageError
from kg_mnp.semantic_kernel.packaging import archive

FIXTURE = Path(__file__).parents[1] / "compatibility/fixtures/compiler-0.5.0.kgop"


def package(tmp_path):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == "4e6ba7225348a201c1ba2076e58f3c1bff370a97dae7000e99ebe53f9be3f983"
    target = tmp_path / "package"
    with zipfile.ZipFile(FIXTURE) as contents:
        contents.extractall(target)
    return target


def test_snapshot_export_verifies_once_and_exports_the_verified_bytes(tmp_path, monkeypatch):
    source = package(tmp_path)
    original = archive.verify_package
    calls = []
    def verify(snapshot):
        calls.append(snapshot)
        assert snapshot != source
        result = original(snapshot)
        # Simulate source mutation after validation; captured bytes remain valid.
        (source / "data/abox.nt").write_bytes(b"tampered after snapshot")
        return result
    monkeypatch.setattr(archive, "verify_package", verify)
    output = archive.archive_bytes(source)
    assert len(calls) == 1
    assert output == FIXTURE.read_bytes()


def test_tampering_before_capture_and_wrong_requested_identity_are_rejected(tmp_path):
    source = package(tmp_path)
    with pytest.raises(PackageError, match="identity"):
        archive.archive_bytes(source, expected_package_id="urn:wrong")
    (source / "data/abox.nt").write_bytes(b"tampered before snapshot")
    with pytest.raises(PackageError):
        archive.archive_bytes(source)


def test_snapshot_read_allocations_are_bounded_by_file_size(tmp_path, monkeypatch):
    source = package(tmp_path)
    original = Path.open
    reads = []
    class Reader:
        def __init__(self, path, stream):
            self.path, self.stream = path, stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def read(self, size):
            assert size <= self.path.stat().st_size + 1
            reads.append(size)
            return self.stream.read(size)
    def opened(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        return Reader(path, stream) if path.is_relative_to(source) and args and args[0] == "rb" else stream
    monkeypatch.setattr(Path, "open", opened)
    assert archive.archive_bytes(source) == FIXTURE.read_bytes()
    assert reads


def test_snapshot_rejects_a_file_growing_during_capture(tmp_path, monkeypatch):
    source = package(tmp_path)
    original = Path.open
    class GrowingReader:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def read(self, size):
            return self.stream.read(size) + b"x"
    def opened(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        return GrowingReader(stream) if path == source / "ontology-package.json" and args and args[0] == "rb" else stream
    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(PackageError, match="changed while capturing"):
        archive.archive_bytes(source)
