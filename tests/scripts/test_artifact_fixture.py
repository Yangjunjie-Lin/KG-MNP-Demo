"""Fixture materialization has no authority and cannot replace existing data."""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.artifact_fixture import materialize_fixture


def test_fixture_materializes_exact_bytes_without_manifest_invention(tmp_path):
    out = tmp_path / "fixture"
    materialize_fixture(out, {"source/value.txt": b"original\r\n"})
    assert (out / "source/value.txt").read_bytes() == b"original\r\n"
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["source/value.txt"]
    with pytest.raises(FileExistsError):
        materialize_fixture(out, {"source/value.txt": b"changed"})
    assert (out / "source/value.txt").read_bytes() == b"original\r\n"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "a\\b", "a//b", "./a"])
def test_fixture_rejects_bad_members_before_creating_output(tmp_path, name):
    out = tmp_path / "fixture"
    with pytest.raises(ValueError, match="invalid fixture member"):
        materialize_fixture(out, {name: b"bad"})
    assert not out.exists()


def test_controlled_compatibility_script_can_be_invoked_standalone(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/activation_controlled_fixture.py"
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    # There is no longer a standalone state-writing command. Importing the
    # fixture must not start a controller, create state, or claim completion.
    assert result.stdout == ""
    assert not list(tmp_path.iterdir())
