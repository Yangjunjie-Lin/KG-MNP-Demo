"""Metadata-only Plugin discovery for built-ins and installed distributions."""

from __future__ import annotations

from importlib import metadata, resources, util
from pathlib import Path

from .errors import PluginManifestError
from .manifest import read_manifest_bytes, validate_manifest_distribution
from .models import PluginDescriptor, PluginStatus

EXTERNAL_MANIFEST_NAMES = ("kg_mnp_plugin_manifest.json", "plugin-manifest.json")
_IMPORT_NAMES = {
    "pypdf": "pypdf",
    "openpyxl": "openpyxl",
    "python-docx": "docx",
    "Pillow": "PIL",
    "defusedxml": "defusedxml",
}


def discover_builtin_plugins() -> tuple[PluginDescriptor, ...]:
    manifest_root = resources.files("kg_mnp.plugins.builtin").joinpath("manifests")
    package_root = Path(resources.files("kg_mnp.plugins"))
    descriptors: list[PluginDescriptor] = []
    for resource in sorted(manifest_root.iterdir(), key=lambda item: item.name):
        if not resource.name.endswith(".json"):
            continue
        raw = resource.read_bytes()
        manifest = read_manifest_bytes(raw, label=resource.name)
        missing = [
            dependency
            for dependency in manifest["requirements"]["optional_dependencies"]
            if util.find_spec(_IMPORT_NAMES.get(dependency, dependency.replace("-", "_"))) is None
        ]
        status = PluginStatus.MISSING_DEPENDENCY if missing else PluginStatus.ENABLED
        reason = (
            "missing optional dependency: " + ", ".join(missing)
            if missing
            else "built-in provider explicitly allowed by core policy"
        )
        descriptor = PluginDescriptor(
            plugin_id=manifest["plugin_id"],
            manifest=manifest,
            manifest_bytes=raw,
            distribution_name="kg-mnp-toolchain",
            distribution_version=metadata.version("kg-mnp-toolchain"),
            distribution_root=package_root,
            builtin=True,
            status=status,
            status_reason=reason,
        )
        validate_manifest_distribution(
            manifest,
            distribution_name=descriptor.distribution_name,
            distribution_version=descriptor.distribution_version,
            distribution_root=descriptor.distribution_root,
        )
        descriptors.append(descriptor)
    return tuple(descriptors)


def _entry_points():
    return metadata.entry_points(group="kg_mnp.plugins")


def _manifest_file(distribution: metadata.Distribution):
    files = distribution.files or ()
    candidates = [
        item for item in files if item.name in EXTERNAL_MANIFEST_NAMES
    ]
    if len(candidates) != 1:
        raise PluginManifestError(
            "external Plugin distribution must contain exactly one kg_mnp_plugin_manifest.json"
        )
    return candidates[0]


def discover_external_plugins() -> tuple[PluginDescriptor, ...]:
    """Discover entry points without calling EntryPoint.load()."""

    descriptors: list[PluginDescriptor] = []
    for entry_point in sorted(_entry_points(), key=lambda item: (item.name, item.value)):
        distribution = entry_point.dist
        if distribution is None:
            continue
        if distribution.metadata["Name"].casefold().replace("_", "-") == "kg-mnp-toolchain":
            continue
        try:
            relative = _manifest_file(distribution)
            path = Path(distribution.locate_file(relative))
            raw = path.read_bytes()
            manifest = read_manifest_bytes(raw, label=relative.name)
            if manifest["entry_point"] != {
                "group": "kg_mnp.plugins",
                "name": entry_point.name,
                "object": entry_point.value,
            }:
                raise PluginManifestError("entry point metadata does not match PluginManifest")
            root = Path(distribution.locate_file(""))
            validate_manifest_distribution(
                manifest,
                distribution_name=distribution.metadata["Name"],
                distribution_version=distribution.version,
                distribution_root=root,
            )
            missing = [
                dependency
                for dependency in manifest["requirements"]["optional_dependencies"]
                if util.find_spec(
                    _IMPORT_NAMES.get(dependency, dependency.replace("-", "_"))
                )
                is None
            ]
            status = PluginStatus.MISSING_DEPENDENCY if missing else PluginStatus.DISABLED
            reason = (
                "missing optional dependency: " + ", ".join(missing)
                if missing
                else "external installed code is disabled until explicitly allowed"
            )
        except (OSError, PluginManifestError) as exc:
            manifest = {"plugin_id": f"invalid-{entry_point.name}"}
            raw = b""
            root = Path(distribution.locate_file(""))
            status = PluginStatus.INVALID
            reason = str(exc)
        descriptors.append(
            PluginDescriptor(
                plugin_id=manifest["plugin_id"],
                manifest=manifest,
                manifest_bytes=raw,
                distribution_name=distribution.metadata["Name"],
                distribution_version=distribution.version,
                distribution_root=root,
                builtin=False,
                status=status,
                status_reason=reason,
                entry_point=entry_point,
            )
        )
    return tuple(descriptors)
