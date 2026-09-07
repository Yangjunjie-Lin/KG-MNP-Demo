"""Windows transient-sharing retry never bypasses a failed artifact commit."""
from __future__ import annotations

import pytest

from kg_mnp.compilation import artifacts


def denied():
    error = PermissionError("simulated Windows sharing denial")
    error.winerror = 5
    return error


def test_transient_windows_commit_denial_is_retried(tmp_path, monkeypatch):
    original = artifacts.os.replace
    calls = []

    def replace(source, target):
        calls.append(1)
        if len(calls) < 3:
            raise denied()
        original(source, target)

    monkeypatch.setattr(artifacts.os, "replace", replace)
    monkeypatch.setattr(artifacts.time, "sleep", lambda _: None)
    artifacts.write_artifact_set(tmp_path / "out", {"data/value.txt": b"actual bytes"})
    assert len(calls) == 3
    assert (tmp_path / "out/data/value.txt").read_bytes() == b"actual bytes"


def test_permanent_commit_denial_never_returns_success(tmp_path, monkeypatch):
    calls = []

    def replace(_source, _target):
        calls.append(1)
        raise denied()

    monkeypatch.setattr(artifacts.os, "replace", replace)
    monkeypatch.setattr(artifacts.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        artifacts.write_artifact_set(tmp_path / "out", {"value.txt": b"actual bytes"})
    assert len(calls) == 6
    assert not (tmp_path / "out").exists()


def test_retry_does_not_replace_concurrently_created_target(tmp_path, monkeypatch):
    staging, target = tmp_path / "staging", tmp_path / "out"
    staging.mkdir()

    def replace(_source, destination):
        destination.mkdir()
        (destination / "user.txt").write_bytes(b"preserve")
        raise denied()

    monkeypatch.setattr(artifacts.os, "replace", replace)
    with pytest.raises(PermissionError):
        artifacts._commit_staging(staging, target)
    assert (target / "user.txt").read_bytes() == b"preserve"


def test_non_windows_permission_denial_is_not_retried(tmp_path, monkeypatch):
    calls = []

    def replace(_source, _target):
        calls.append(1)
        raise PermissionError("permanent ACL denial")

    monkeypatch.setattr(artifacts.os, "replace", replace)
    with pytest.raises(PermissionError):
        artifacts.write_artifact_set(tmp_path / "out", {"value.txt": b"actual bytes"})
    assert len(calls) == 1
