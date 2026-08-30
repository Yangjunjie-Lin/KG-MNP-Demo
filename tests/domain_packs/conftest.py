from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def minimal_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "minimal"
    shutil.copytree(ROOT / "domain_packs" / "minimal", destination)
    return destination


def read_manifest(pack: Path) -> dict[str, object]:
    value = yaml.safe_load((pack / "pack.yaml").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_manifest(pack: Path, value: dict[str, object]) -> None:
    (pack / "pack.yaml").write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

