"""Current immutable artifact commits preserve failed and concurrent writes."""
from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.modeling.control_plane.artifacts import transactional_write_files


def denied():
    error = PermissionError("simulated Windows sharing denial")
    error.winerror = 5
    return error


def write(root):
    return transactional_write_files(root, operation="commit-test",
                                     relative_destination="artifacts/proposals/example",
                                     files={"value.txt": b"actual bytes"})


def test_transient_windows_commit_denial_is_retried(tmp_path, monkeypatch):
    original = Path.rename
    calls = []

    def rename(source, target):
        calls.append(1)
        if len(calls) < 3:
            raise denied()
        return original(source, target)

    monkeypatch.setattr(Path, "rename", rename)
    result = write(tmp_path)
    assert len(calls) == 3
    assert (result / "value.txt").read_bytes() == b"actual bytes"


def test_permanent_commit_denial_never_returns_success(tmp_path, monkeypatch):
    calls = []

    def rename(_source, _target):
        calls.append(1)
        raise denied()

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(PermissionError):
        write(tmp_path)
    assert len(calls) == 6
    assert not (tmp_path / "artifacts/proposals/example").exists()


def test_retry_does_not_replace_concurrently_created_target(tmp_path, monkeypatch):
    def rename(_source, target):
        target.mkdir()
        (target / "user.txt").write_bytes(b"preserve")
        raise denied()

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(PermissionError):
        write(tmp_path)
    assert (tmp_path / "artifacts/proposals/example/user.txt").read_bytes() == b"preserve"


def test_non_windows_permission_denial_is_not_retried(tmp_path, monkeypatch):
    calls = []

    def rename(_source, _target):
        calls.append(1)
        raise PermissionError("permanent ACL denial")

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(PermissionError):
        write(tmp_path)
    assert len(calls) == 1


def test_staging_failure_preserves_unowned_destination(tmp_path, monkeypatch):
    original = Path.write_bytes
    target = tmp_path / "artifacts/proposals/example"

    def fail(source, data):
        if source.name == "value.txt":
            target.mkdir(parents=True)
            original(target / "user.txt", b"preserve")
            raise OSError("injected write failure")
        return original(source, data)

    monkeypatch.setattr(Path, "write_bytes", fail)
    with pytest.raises(OSError, match="injected write failure"):
        write(tmp_path)
    assert (target / "user.txt").read_bytes() == b"preserve"


def test_preexisting_staging_directory_is_not_removed(tmp_path):
    stale = tmp_path / "tmp/modeling/commit-test/example"
    stale.mkdir(parents=True)
    (stale / "user.txt").write_bytes(b"preserve")
    write(tmp_path)
    assert (stale / "user.txt").read_bytes() == b"preserve"


def test_immutable_reuse_rejects_unlisted_directory(tmp_path):
    target = write(tmp_path)
    (target / "unlisted").mkdir()
    with pytest.raises(ValueError, match="immutable artifact"):
        write(tmp_path)
    assert (target / "unlisted").is_dir()
