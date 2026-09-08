"""Distribution extraction refuses links, traversal and runtime material."""
import io
import tarfile
import zipfile

import pytest

from tools.verify_distribution import extract_sdist, wheel_payload


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/outside", "project\\..\\outside"])
def test_sdist_member_path_cannot_escape(tmp_path, name):
    source = tmp_path / "bad.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="unsafe"):
        extract_sdist(source, tmp_path / "extracted")


def test_sdist_rejects_symlinks_even_within_project(tmp_path):
    source = tmp_path / "bad.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        member = tarfile.TarInfo("project/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "pyproject.toml"
        archive.addfile(member)
    with pytest.raises(ValueError, match="unsafe"):
        extract_sdist(source, tmp_path / "extracted")


@pytest.mark.parametrize("name", ["kg_mnp/runtime/tokens.json", "kg_mnp/auth.sqlite3", "kg_mnp/__pycache__/app.pyc", "../outside"])
def test_wheel_refuses_runtime_files_and_traversal(tmp_path, name):
    wheel = tmp_path / "bad.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(name, b"synthetic")
    with pytest.raises(ValueError):
        wheel_payload(wheel)
