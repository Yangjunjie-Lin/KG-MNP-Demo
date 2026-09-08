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
