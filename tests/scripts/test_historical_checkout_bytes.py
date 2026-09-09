"""Fresh Windows checkouts must preserve hash-bound historical artifact bytes."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FROZEN_PATHS = (
    "examples/compilation/expected",
    "examples/graphdb/expected",
    "examples/publication/expected",
    "examples/publication/fixtures/owl2vowl-0.3.7-raw.json",
    "config/webvowl/webvowl-runtime-1.0.0.yaml",
    "config/graphdb/graphdb-runtime-1.0.0.yaml",
)


@pytest.mark.parametrize("directory", FROZEN_PATHS)
def test_windows_checkout_filter_preserves_every_frozen_artifact(directory):
    paths = subprocess.check_output(["git", "ls-files", "-z", "--", directory], cwd=ROOT).decode().split("\0")
    assert any(paths)
    for path in filter(None, paths):
        reference = "HEAD:" + path
        committed = subprocess.check_output(["git", "cat-file", "blob", reference], cwd=ROOT)
        filtered = subprocess.check_output(["git", "-c", "core.autocrlf=true", "cat-file", "--filters", reference], cwd=ROOT)
        assert filtered == committed, f"Windows checkout changes frozen bytes: {path}"
        assert (ROOT / path).read_bytes() == committed, f"Working copy changes frozen bytes: {path}"
