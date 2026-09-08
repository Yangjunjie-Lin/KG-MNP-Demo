"""Materialize reconstructed bytes for isolated compatibility fixtures/probes.

No authority, compiler, lock, atomic publication, force replacement or cleanup
is implemented here. A partially written fixture remains failed-run evidence.
Product writes belong to the fenced Workspace workflow, not this utility.
"""
from collections.abc import Mapping
from pathlib import Path, PurePosixPath


def materialize_fixture(destination: Path, files: Mapping[str, bytes]) -> None:
    for name, data in files.items():
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or PurePosixPath(name).is_absolute()
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or not isinstance(data, bytes)):
            raise ValueError("invalid fixture member")
    # mkdir(exist_ok=False) deliberately refuses every preexisting target.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(files.items()):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
