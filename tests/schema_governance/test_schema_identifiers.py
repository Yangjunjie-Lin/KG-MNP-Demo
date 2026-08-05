"""Offline JSON Schema identifier governance tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_schema_identifiers as checker  # noqa: E402


def _namespace_config(root: Path) -> Path:
    config = root / "config" / "namespaces.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "\n".join(
            [
                'schemas:',
                '  base: "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/"',
                '  modeling: "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/"',
                '  legacy: "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config


def _write_schema(path: Path, identifier: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "$schema": checker.DRAFT_2020_12,
                "$id": identifier,
                "type": "object",
            }
        ),
        encoding="utf-8",
    )


def test_schema_namespaces_are_stable_project_https_namespaces():
    raw = yaml.safe_load(
        (ROOT / "config" / "namespaces.yaml").read_text(encoding="utf-8")
    )
    schemas = raw["schemas"]
    assert set(schemas) >= {"base", "modeling", "legacy"}
    for value in schemas.values():
        parsed = urlsplit(value)
        assert value.endswith("/")
        assert parsed.scheme == "https"
        assert parsed.netloc == "yangjunjie-lin.github.io"
        assert value.startswith(checker.PROJECT_PAGES_BASE)
        assert "example.org" not in value.lower()
        assert "localhost" not in value.lower()
        assert "file://" not in value.lower()
    assert schemas["modeling"].startswith(schemas["base"])
    assert schemas["legacy"].startswith(schemas["base"])


def test_repository_schema_identifiers_pass_offline_gate():
    result = checker.audit_schema_identifiers()
    assert result.ok, "\n".join(result.errors)
    assert len(result.paths) == len(result.identifiers) == len(set(result.identifiers))
    assert "examples/eligibility-use-case/schemas/mnp_case_input.schema.json" in result.paths


def test_legacy_schema_uses_legacy_namespace_draft_and_contract_version():
    namespaces = checker.load_schema_namespaces()
    path = (
        ROOT
        / "examples"
        / "eligibility-use-case"
        / "schemas"
        / "mnp_case_input.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema["$schema"] == checker.DRAFT_2020_12
    assert schema["$id"].startswith(namespaces.legacy)
    assert schema["$id"].endswith("/1.0")
    assert not schema["$id"].endswith("mnp_case_input.schema.json")
    assert "example.org" not in schema["$id"].lower()


def test_gate_discovers_tracked_and_non_ignored_untracked_schemas(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    _namespace_config(tmp_path)
    tracked = tmp_path / "schemas" / "modeling" / "tracked.schema.json"
    intended = tmp_path / "examples" / "planned.schema.json"
    _write_schema(
        tracked,
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/tracked/1.0",
    )
    subprocess.run(["git", "add", tracked.relative_to(tmp_path)], cwd=tmp_path, check=True)
    _write_schema(
        intended,
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/planned/1.0",
    )

    found = checker.tracked_and_intended_schema_files(tmp_path)

    assert {path.relative_to(tmp_path).as_posix() for path in found} == {
        "examples/planned.schema.json",
        "schemas/modeling/tracked.schema.json",
    }


@pytest.mark.parametrize(
    "identifier",
    [
        "http://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/test/1.0",
        "https://example.org/" + "kg-mnp/schemas/test.schema.json",
        "https://localhost/schemas/test/1.0",
        "file:///tmp/test.schema.json",
        "D:\\schemas\\test.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/test",
    ],
)
def test_gate_rejects_non_project_or_non_https_identifiers(
    tmp_path: Path, identifier: str
):
    config = _namespace_config(tmp_path)
    schema = tmp_path / "examples" / "eligibility-use-case" / "schemas" / "bad.schema.json"
    _write_schema(schema, identifier)

    result = checker.audit_schema_identifiers(
        root=tmp_path, namespace_config=config, paths=(schema,)
    )

    assert not result.ok


def test_gate_rejects_duplicate_identifiers(tmp_path: Path):
    config = _namespace_config(tmp_path)
    identifier = (
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/duplicate/1.0"
    )
    first = tmp_path / "examples" / "first.schema.json"
    second = tmp_path / "examples" / "second.schema.json"
    _write_schema(first, identifier)
    _write_schema(second, identifier)

    result = checker.audit_schema_identifiers(
        root=tmp_path, namespace_config=config, paths=(first, second)
    )

    assert any("duplicate $id" in error for error in result.errors)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps([]), "root must be an object"),
        (
            json.dumps(
                {
                    "$id": "https://yangjunjie-lin.github.io/"
                    "KG-MNP-Demo/schemas/test/1.0"
                }
            ),
            "$schema must equal",
        ),
        (json.dumps({"$schema": checker.DRAFT_2020_12}), "$id must be"),
    ],
)
def test_gate_rejects_malformed_schema_documents(
    tmp_path: Path, payload: str, expected: str
):
    config = _namespace_config(tmp_path)
    schema = tmp_path / "examples" / "bad.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text(payload, encoding="utf-8")

    result = checker.audit_schema_identifiers(
        root=tmp_path, namespace_config=config, paths=(schema,)
    )

    assert any(expected in error for error in result.errors)
