"""PluginManifest v1 parsing and validation without implementation import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError
from packaging.version import InvalidVersion, Version

from kg_mnp.contracts.canonical import bytes_sha256
from kg_mnp.contracts.registry import validate_contract

from .errors import PluginManifestError
from .security import (
    assert_safe_configuration,
    validate_implementation_files,
    validate_plugin_id,
)


def read_manifest_bytes(raw: bytes, *, label: str = "PluginManifest") -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PluginManifestError(f"invalid UTF-8 JSON {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise PluginManifestError(f"{label} root must be an object")
    try:
        contract = "plugin-manifest-v1-1" if value.get("plugin_api_version") == "1.1.0" else "plugin-manifest"
        validate_contract(contract, value)
    except ValidationError as exc:
        raise PluginManifestError(f"invalid {label}: {exc.message}") from exc
    validate_plugin_id(value["plugin_id"])
    assert_safe_configuration(value.get("extensions", {}), "extensions")
    if "NETWORK" in value["side_effects"]:
        # Discovery remains possible; selection will fail closed in offline mode.
        pass
    return value


def load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PluginManifestError(f"cannot read PluginManifest: {path.name}: {exc}") from exc
    return read_manifest_bytes(raw, label=path.name), raw


def validate_manifest_distribution(
    manifest: dict[str, Any],
    *,
    distribution_name: str,
    distribution_version: str,
    distribution_root: Path,
    allow_bundled_version_upgrade: bool = False,
) -> tuple[Path, ...]:
    expected = manifest["distribution"]
    if expected["name"].casefold().replace("_", "-") != distribution_name.casefold().replace("_", "-"):
        raise PluginManifestError("Plugin distribution name mismatch")
    bundled_toolchain_upgrade = (
        allow_bundled_version_upgrade
        and
        distribution_name == "kg-mnp-toolchain"
        and _compatible_bundled_versions(
            expected["required_version"], distribution_version
        )
    )
    if (
        expected["required_version"] != distribution_version
        and not bundled_toolchain_upgrade
    ):
        raise PluginManifestError(
            f"Plugin distribution version mismatch: expected {expected['required_version']}, "
            f"found {distribution_version}"
        )
    implementation_files = validate_implementation_files(
        distribution_root, manifest["implementation_files"]
    )
    configuration = manifest["configuration_contract"]
    if configuration is not None:
        schema_path = validate_implementation_files(
            distribution_root, [configuration["resource"]]
        )[0]
        raw = schema_path.read_bytes()
        if bytes_sha256(raw) != configuration["sha256"]:
            raise PluginManifestError("Plugin configuration schema digest mismatch")
        try:
            schema = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PluginManifestError("invalid Plugin configuration schema JSON") from exc
        if not isinstance(schema, dict) or schema.get("$id") != configuration["schema_id"]:
            raise PluginManifestError("Plugin configuration schema ID mismatch")

        def reject_remote_refs(value: Any) -> None:
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str) and reference.startswith(("http://", "https://")):
                    raise PluginManifestError("remote Plugin configuration $ref rejected")
                for item in value.values():
                    reject_remote_refs(item)
            elif isinstance(value, list):
                for item in value:
                    reject_remote_refs(item)

        reject_remote_refs(schema)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise PluginManifestError(
                f"invalid Plugin configuration schema: {exc.message}"
            ) from exc
    return implementation_files


def _compatible_bundled_versions(required: str, installed: str) -> bool:
    """Permit only explicitly identified built-ins shipped by a newer toolchain.

    External distributions retain exact version matching. Bundled manifests
    preserve their introduction-version bytes while their API contract and
    implementation digest remain independently verified.
    """

    try:
        required_version, installed_version = Version(required), Version(installed)
    except InvalidVersion:
        return False
    return (installed_version.epoch == required_version.epoch == 0
            and installed_version.major == required_version.major and installed_version >= required_version)


def manifest_file_digest(raw: bytes) -> str:
    return bytes_sha256(raw)
