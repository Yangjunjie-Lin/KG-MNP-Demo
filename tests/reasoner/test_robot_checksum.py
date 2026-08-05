from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

import run_reasoner as reasoner


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_robot_version_url_and_checksum_are_fixed():
    assert reasoner.ROBOT_VERSION == "1.9.7"
    assert reasoner.EXPECTED_ROBOT_SHA256 == (
        "91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d"
    )
    assert reasoner.ROBOT_URL == (
        "https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar"
    )


def test_correct_cached_jar_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = b"checksum fixture"
    monkeypatch.setattr(reasoner, "EXPECTED_ROBOT_SHA256", _digest(content))
    jar = tmp_path / reasoner.ROBOT_JAR_NAME
    jar.write_bytes(content)

    def unexpected_download(*_args):
        raise AssertionError("a valid cache must not be downloaded again")

    monkeypatch.setattr(reasoner.urllib.request, "urlretrieve", unexpected_download)
    assert reasoner.ensure_robot(download_dir=tmp_path) == jar
    assert jar.read_bytes() == content


def test_local_checksum_sidecar_is_not_a_trust_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    trusted = b"trusted bytes"
    monkeypatch.setattr(reasoner, "EXPECTED_ROBOT_SHA256", _digest(trusted))
    jar = tmp_path / reasoner.ROBOT_JAR_NAME
    jar.write_bytes(trusted)
    (tmp_path / f"{reasoner.ROBOT_JAR_NAME}.sha256").write_text(
        "0" * 64,
        encoding="utf-8",
    )
    assert reasoner.ensure_robot(download_dir=tmp_path) == jar


def test_wrong_cached_jar_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    expected = b"expected"
    monkeypatch.setattr(reasoner, "EXPECTED_ROBOT_SHA256", _digest(expected))
    jar = tmp_path / reasoner.ROBOT_JAR_NAME
    jar.write_bytes(b"corrupt cache")

    with pytest.raises(reasoner.RobotChecksumError, match="cached ROBOT"):
        reasoner.ensure_robot(download_dir=tmp_path)
    assert not jar.exists()


def test_wrong_download_is_rejected_without_canonical_jar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(reasoner, "EXPECTED_ROBOT_SHA256", _digest(b"trusted"))

    def fake_download(url: str, destination: Path):
        assert url == reasoner.ROBOT_URL
        Path(destination).write_bytes(b"untrusted")
        return str(destination), None

    monkeypatch.setattr(reasoner.urllib.request, "urlretrieve", fake_download)
    with pytest.raises(reasoner.RobotChecksumError, match="downloaded ROBOT"):
        reasoner.ensure_robot(download_dir=tmp_path)
    assert not (tmp_path / reasoner.ROBOT_JAR_NAME).exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_jar_downloads_only_from_fixed_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    content = b"locally supplied fixture"
    monkeypatch.setattr(reasoner, "EXPECTED_ROBOT_SHA256", _digest(content))
    calls: list[str] = []

    def fake_download(url: str, destination: Path):
        calls.append(url)
        Path(destination).write_bytes(content)
        return str(destination), None

    monkeypatch.setattr(reasoner.urllib.request, "urlretrieve", fake_download)
    jar = reasoner.ensure_robot(download_dir=tmp_path)
    assert calls == [reasoner.ROBOT_URL]
    assert jar.read_bytes() == content
    assert list(tmp_path.glob("*.tmp")) == []


def test_download_exception_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def failed_download(url: str, destination: Path):
        assert url == reasoner.ROBOT_URL
        Path(destination).write_bytes(b"partial")
        raise OSError("simulated network failure")

    monkeypatch.setattr(reasoner.urllib.request, "urlretrieve", failed_download)
    with pytest.raises(OSError, match="network failure"):
        reasoner.ensure_robot(download_dir=tmp_path)
    assert not (tmp_path / reasoner.ROBOT_JAR_NAME).exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_hermit_version_comes_from_its_own_maven_metadata(tmp_path: Path):
    jar = tmp_path / "robot.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr(reasoner.HERMIT_POM_PROPERTIES, "version=1.4.5.456\n")
        archive.writestr(reasoner.ROBOT_POM_PROPERTIES, "version=1.9.7\n")
    assert reasoner.hermit_version_from_robot(jar) == "1.4.5.456"
    assert reasoner.robot_embedded_version(jar) == "1.9.7"


def test_missing_hermit_metadata_is_unknown_not_robot_version(tmp_path: Path):
    jar = tmp_path / "robot.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr(reasoner.ROBOT_POM_PROPERTIES, "version=1.9.7\n")
    assert reasoner.hermit_version_from_robot(jar) == reasoner.UNKNOWN
    assert reasoner.hermit_version_from_robot(jar) != reasoner.ROBOT_VERSION
