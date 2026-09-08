"""Deterministic PluginSnapshot generation and verification."""

from __future__ import annotations

import re
from importlib import resources
from typing import Any

from jsonschema import ValidationError

from kg_mnp.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

from .errors import PluginTamperedError
from .manifest import validate_manifest_distribution
from .models import PluginDescriptor


def snapshot_distribution_version(value: str) -> str:
    """Lossless spelling bridge for Python development/RC versions into SemVer.

    Stable versions are unchanged. Unsupported spellings still fail the frozen
    public schema instead of silently changing their version meaning.
    """
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:\.dev(\d+)|(a|b|rc)(\d+))", value)
    if match:
        base, dev, kind, number = match.groups()
        return base + "-" + ("dev." + dev if dev is not None else {"a":"alpha", "b":"beta", "rc":"rc"}[kind] + "." + number)
    return value


def _implementation_digest(descriptor: PluginDescriptor) -> str:
    files = validate_manifest_distribution(
        descriptor.manifest,
        distribution_name=descriptor.distribution_name,
        distribution_version=descriptor.distribution_version,
        distribution_root=descriptor.distribution_root,
        allow_bundled_version_upgrade=descriptor.builtin,
    )
    rows = []
    for relative, path in sorted(
        zip(descriptor.manifest["implementation_files"], files, strict=True)
    ):
        rows.append({"path": relative, "sha256": bytes_sha256(path.read_bytes())})
    if descriptor.builtin and "modeling-provider" in descriptor.manifest["plugin_kinds"]:
        # The plugin entry point re-exports core classes. Hashing that wrapper
        # alone would give changed provider algorithms the old snapshot ID.
        core_root = resources.files("kg_mnp.modeling.control_plane")
        for relative in ("mappings.py", "providers/builtin.py", "providers/models.py",
                         "providers/record_mapping.py", "providers/mixed_mapping.py", "providers/record_profile.py"):
            rows.append({"path": "kg_mnp/modeling/control_plane/" + relative,
                         "sha256": bytes_sha256(core_root.joinpath(relative).read_bytes())})
    return semantic_hash(rows)


def build_snapshot(
    descriptor: PluginDescriptor,
    *,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = descriptor.manifest
    distribution_version = snapshot_distribution_version(descriptor.distribution_version)
    if descriptor.builtin and manifest["plugin_api_version"] == "1.1.0":
        # The frozen API 1.1 Snapshot contract records the 0.4.0 compatibility
        # baseline. Current built-in implementation bytes remain bound by the
        # implementation digest and are validated from the installed 0.5.0
        # distribution before this snapshot is emitted.
        distribution_version = manifest["distribution"]["required_version"]
    core = {
        "manifest_kind": "KG_MNP_PLUGIN_SNAPSHOT",
        "schema_version": "1.0.0",
        "plugin_id": manifest["plugin_id"],
        "plugin_version": manifest["plugin_version"],
        "plugin_api_version": manifest["plugin_api_version"],
        "distribution_name": descriptor.distribution_name,
        "distribution_version": distribution_version,
        "entry_point": f"{manifest['entry_point']['group']}:{manifest['entry_point']['name']}",
        "manifest_sha256": bytes_sha256(descriptor.manifest_bytes),
        "manifest_semantic_sha256": semantic_hash(manifest),
        "implementation_digest": _implementation_digest(descriptor),
        "configuration_semantic_sha256": semantic_hash(configuration or {}),
        "capabilities": sorted(manifest["capabilities"]),
        "determinism": manifest["determinism"],
        "side_effects": sorted(manifest["side_effects"]),
    }
    if manifest["plugin_api_version"] == "1.1.0":
        core.update(
            {
                "schema_version": "1.1.0",
                "authority_level": manifest["authority_level"],
                "network_policy": manifest["network_policy"],
                "input_contracts": sorted(manifest["input_contracts"]),
                "output_contracts": sorted(manifest["output_contracts"]),
            }
        )
    snapshot = {**core, "snapshot_id": stable_urn("plugin-snapshot", core)}
    validate_contract("plugin-snapshot-v1-1" if manifest["plugin_api_version"] == "1.1.0" else "plugin-snapshot", snapshot)
    return snapshot


def verify_snapshot(
    descriptor: PluginDescriptor,
    snapshot: dict[str, Any],
    *,
    configuration: dict[str, Any] | None = None,
) -> None:
    try:
        contract = "plugin-snapshot-v1-1" if descriptor.manifest["plugin_api_version"] == "1.1.0" else "plugin-snapshot"
        validate_contract(contract, snapshot)
    except ValidationError as exc:
        raise PluginTamperedError(f"invalid PluginSnapshot: {exc.message}") from exc
    expected = build_snapshot(descriptor, configuration=configuration)
    if snapshot != expected:
        raise PluginTamperedError("Plugin manifest, implementation, or configuration changed")
