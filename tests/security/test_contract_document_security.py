from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.contracts.document_io import read_document
from kg_mnp.contracts.errors import (
    DocumentError,
    DocumentTooLargeError,
    DuplicateKeyError,
)
from kg_mnp.contracts.identifiers import validate_safe_relative_path


@pytest.mark.parametrize(
    "content,suffix",
    [('{"x": 1, "x": 2}', ".json"), ("x: 1\nx: 2\n", ".yaml")],
)
def test_duplicate_mapping_keys_are_rejected(tmp_path: Path, content: str, suffix: str) -> None:
    path = tmp_path / f"duplicate{suffix}"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DuplicateKeyError):
        read_document(path)


def test_unsafe_yaml_tag_and_alias_bomb_are_rejected(tmp_path: Path) -> None:
    tagged = tmp_path / "tagged.yaml"
    tagged.write_text("value: !!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")
    with pytest.raises(DocumentError):
        read_document(tagged)
    aliases = tmp_path / "aliases.yaml"
    aliases.write_text("root: &a [1]\nvalues: [" + ",".join("*a" for _ in range(65)) + "]", encoding="utf-8")
    with pytest.raises(DocumentError, match="alias"):
        read_document(aliases)


def test_non_utf8_and_oversized_documents_are_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\xff\xfe")
    with pytest.raises(DocumentError, match="UTF-8"):
        read_document(invalid)
    large = tmp_path / "large.json"
    large.write_bytes(b" " * 33)
    with pytest.raises(DocumentTooLargeError):
        read_document(large, max_bytes=32)


@pytest.mark.parametrize(
    "value",
    ["../asset", "a/../asset", "/absolute", "C:/drive", r"C:\\drive", r"\\server\\share", "a//b", "a\\b", "a/./b", "a\x00b"],
)
def test_unsafe_relative_paths_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_safe_relative_path(value)


def test_safe_relative_posix_path_is_accepted() -> None:
    assert validate_safe_relative_path("ontology/module.ttl").as_posix() == "ontology/module.ttl"

