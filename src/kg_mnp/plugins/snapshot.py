"""Deterministic PluginSnapshot generation and verification."""

from __future__ import annotations

from typing import Any

from jsonschema import ValidationError

from kg_mnp.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

from .errors import PluginTamperedError
from .manifest import validate_manifest_distribution
from .models import PluginDescriptor


def _implementation_digest(descriptor: PluginDescriptor) -> str:
    files = validate_manifest_distribution(
        descriptor.manifest,
        distribution_name=descriptor.distribution_name,
        distribution_version=descriptor.distribution_version,
        distribution_root=descriptor.distribution_root,
    )
    rows = []
    for relative, path in sorted(
        zip(descriptor.manifest["implementation_files"], files, strict=True)
    ):
        rows.append({"path": relative, "sha256": bytes_sha256(path.read_bytes())})
    return semantic_hash(rows)


def build_snapshot(
    descriptor: PluginDescriptor,
    *,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = descriptor.manifest
    core = {
        "manifest_kind": "KG_MNP_PLUGIN_SNAPSHOT",
        "schema_version": "1.0.0",
        "plugin_id": manifest["plugin_id"],
        "plugin_version": manifest["plugin_version"],
        "plugin_api_version": manifest["plugin_api_version"],
        "distribution_name": descriptor.distribution_name,
        "distribution_version": descriptor.distribution_version,
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
