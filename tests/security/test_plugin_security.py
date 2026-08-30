from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kg_mnp.contracts.canonical import bytes_sha256
from kg_mnp.plugins.errors import PluginManifestError
from kg_mnp.plugins.manifest import (
    read_manifest_bytes,
    validate_manifest_distribution,
)
from kg_mnp.plugins.registry import PluginRegistry


def _manifest(plugin_id: str = "plain-text-parser") -> dict:
    return copy.deepcopy(PluginRegistry(discover_external=False).get(plugin_id).manifest)


def test_manifest_rejects_non_utf8_null_unknown_and_entrypoint_injection() -> None:
    with pytest.raises(PluginManifestError, match="UTF-8"):
        read_manifest_bytes(b"\xff\xfe")
    for mutation in (
        {"unexpected": True},
        {"entry_point": {"group": "kg_mnp.plugins", "name": "bad", "object": "os:system('x')"}},
    ):
        manifest = _manifest()
        manifest.update(mutation)
        with pytest.raises(PluginManifestError):
            read_manifest_bytes(json.dumps(manifest).encode("utf-8"))


def test_manifest_rejects_secret_extensions_and_implementation_path_escape(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    manifest["extensions"] = {"x-api-token": "secret"}
    with pytest.raises(PluginManifestError, match="secret"):
        read_manifest_bytes(json.dumps(manifest).encode("utf-8"))
    manifest = _manifest()
    manifest["distribution"] = {"name": "kg-mnp-toolchain", "required_version": "0.3.0"}
    for path in ("../escape.py", "/absolute.py", "C:/escape.py", "//server/share.py"):
        manifest["implementation_files"] = [path]
        with pytest.raises(PluginManifestError):
            validate_manifest_distribution(
                manifest,
                distribution_name="kg-mnp-toolchain",
                distribution_version="0.3.0",
                distribution_root=tmp_path,
            )


def test_configuration_schema_digest_id_and_remote_refs_fail_closed(tmp_path: Path) -> None:
    implementation = tmp_path / "plugin.py"
    implementation.write_text("class Plugin: pass\n", encoding="utf-8")
    schema = tmp_path / "configuration.schema.json"
    schema_value = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:test:configuration",
        "type": "object",
        "additionalProperties": False,
    }
    schema.write_text(json.dumps(schema_value), encoding="utf-8")
    manifest = _manifest("generic-normalizer")
    manifest.update(
        {
            "distribution": {"name": "fixture", "required_version": "1.0.0"},
            "implementation_files": ["plugin.py"],
            "configuration_contract": {
                "resource": "configuration.schema.json",
                "schema_id": "urn:test:configuration",
                "sha256": bytes_sha256(schema.read_bytes()),
            },
        }
    )
    validate_manifest_distribution(
        manifest,
        distribution_name="fixture",
        distribution_version="1.0.0",
        distribution_root=tmp_path,
    )
    manifest["configuration_contract"]["sha256"] = "0" * 64
    with pytest.raises(PluginManifestError, match="digest"):
        validate_manifest_distribution(
            manifest,
            distribution_name="fixture",
            distribution_version="1.0.0",
            distribution_root=tmp_path,
        )
    schema_value["properties"] = {"remote": {"$ref": "https://example.invalid/schema"}}
    schema.write_text(json.dumps(schema_value), encoding="utf-8")
    manifest["configuration_contract"]["sha256"] = bytes_sha256(schema.read_bytes())
    with pytest.raises(PluginManifestError, match="remote"):
        validate_manifest_distribution(
            manifest,
            distribution_name="fixture",
            distribution_version="1.0.0",
            distribution_root=tmp_path,
        )


def test_registry_source_contains_no_network_or_auto_install_path() -> None:
    import inspect

    from kg_mnp.plugins import discovery, registry

    source = inspect.getsource(discovery) + inspect.getsource(registry)
    for forbidden in ("requests.", "urllib.request", "subprocess", "pip install"):
        assert forbidden not in source
