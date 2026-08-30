from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

from kg_mnp.plugins import discovery
from kg_mnp.plugins.conformance import run_conformance
from kg_mnp.plugins.errors import (
    AmbiguousProviderSelectionError,
    PluginConformanceError,
    PluginManifestError,
    PluginTamperedError,
    ProviderSelectionError,
)
from kg_mnp.plugins.manifest import read_manifest_bytes
from kg_mnp.plugins.models import PluginDescriptor, PluginStatus
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.security import assert_safe_plugin_output
from kg_mnp.plugins.selection import select_provider
from kg_mnp.plugins.snapshot import build_snapshot, verify_snapshot

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BUILTINS = {
    "delimited-text-parser",
    "docx-parser",
    "generic-normalizer",
    "image-metadata-parser",
    "json-parser",
    "local-file-source",
    "markdown-parser",
    "pdf-parser",
    "plain-text-parser",
    "signature-media-detector",
    "structural-quality-evaluator",
    "wav-metadata-parser",
    "xlsx-parser",
}


def test_builtin_registry_is_stable_enabled_and_complete() -> None:
    descriptors = PluginRegistry(discover_external=False).list()
    assert {item.plugin_id for item in descriptors} == EXPECTED_BUILTINS
    assert all(item.status == PluginStatus.ENABLED for item in descriptors)
    assert all(item.manifest["determinism"] == "DETERMINISTIC" for item in descriptors)


def test_missing_optional_document_dependencies_do_not_disable_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hidden = {"pypdf", "openpyxl", "docx", "PIL", "defusedxml"}
    real_find_spec = discovery.util.find_spec
    monkeypatch.setattr(
        discovery.util,
        "find_spec",
        lambda name: None if name in hidden else real_find_spec(name),
    )
    statuses = {
        item.plugin_id: item.status
        for item in PluginRegistry(discover_external=False).list()
    }
    for plugin_id in ("docx-parser", "image-metadata-parser", "pdf-parser", "xlsx-parser"):
        assert statuses[plugin_id] == PluginStatus.MISSING_DEPENDENCY
    for plugin_id in (
        "delimited-text-parser",
        "generic-normalizer",
        "json-parser",
        "local-file-source",
        "markdown-parser",
        "plain-text-parser",
        "signature-media-detector",
        "structural-quality-evaluator",
        "wav-metadata-parser",
    ):
        assert statuses[plugin_id] == PluginStatus.ENABLED


def test_all_available_builtins_pass_request_response_conformance() -> None:
    registry = PluginRegistry(discover_external=False)
    results = [run_conformance(registry, item.plugin_id) for item in registry.list()]
    assert {item.plugin_id for item in results} == EXPECTED_BUILTINS
    assert [(item.plugin_id, item.errors) for item in results if item.status != "PASS"] == []


def test_snapshot_is_deterministic_and_manifest_tamper_is_detected() -> None:
    descriptor = PluginRegistry(discover_external=False).get("plain-text-parser")
    first = build_snapshot(descriptor)
    second = build_snapshot(descriptor)
    assert first == second
    tampered = replace(descriptor, manifest_bytes=descriptor.manifest_bytes + b" ")
    with pytest.raises(PluginTamperedError):
        verify_snapshot(tampered, first)


def test_snapshot_detects_declared_implementation_tamper(tmp_path: Path) -> None:
    descriptor = PluginRegistry(discover_external=False).get("plain-text-parser")
    snapshot = build_snapshot(descriptor)
    copied = tmp_path / "plugins"
    shutil.copytree(descriptor.distribution_root, copied)
    implementation = copied / descriptor.manifest["implementation_files"][0]
    implementation.write_text(implementation.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
    with pytest.raises(PluginTamperedError):
        verify_snapshot(replace(descriptor, distribution_root=copied), snapshot)


def test_duplicate_plugin_id_fails_closed() -> None:
    descriptor = PluginRegistry(discover_external=False).get("plain-text-parser")
    with pytest.raises(PluginManifestError, match="duplicate"):
        PluginRegistry(descriptors=(descriptor, descriptor), discover_external=False)


def test_provider_selection_is_deterministic_and_explicit_preference_wins() -> None:
    descriptor = PluginRegistry(discover_external=False).get("plain-text-parser")
    selected = select_provider(
        (descriptor,),
        plugin_kind="parser",
        capability="parse-text",
        media_type="text/plain",
        preference="plain-text-parser",
    )
    assert selected.descriptor.plugin_id == "plain-text-parser"
    assert selected.reason == "explicit provider preference"


def test_ambiguous_provider_network_and_nondeterminism_fail_closed() -> None:
    descriptor = PluginRegistry(discover_external=False).get("plain-text-parser")
    alternate_manifest = copy.deepcopy(descriptor.manifest)
    alternate_manifest["plugin_id"] = "alternate-text-parser"
    alternate = replace(descriptor, plugin_id="alternate-text-parser", manifest=alternate_manifest)
    with pytest.raises(AmbiguousProviderSelectionError):
        select_provider(
            (descriptor, alternate),
            plugin_kind="parser",
            capability="parse-text",
            media_type="text/plain",
        )
    network_manifest = copy.deepcopy(descriptor.manifest)
    network_manifest["side_effects"] = ["NETWORK"]
    network = replace(descriptor, manifest=network_manifest)
    with pytest.raises(ProviderSelectionError, match="MISSING_PROVIDER"):
        select_provider(
            (network,),
            plugin_kind="parser",
            capability="parse-text",
            media_type="text/plain",
        )
    nondeterministic_manifest = copy.deepcopy(descriptor.manifest)
    nondeterministic_manifest["determinism"] = "NONDETERMINISTIC"
    nondeterministic = replace(descriptor, manifest=nondeterministic_manifest)
    with pytest.raises(ProviderSelectionError, match="MISSING_PROVIDER"):
        select_provider(
            (nondeterministic,),
            plugin_kind="parser",
            capability="parse-text",
            media_type="text/plain",
        )


@pytest.mark.parametrize(
    "plugin_id",
    ["../escape", "C-drive", "with/slash", "with\\slash", ".", "..", "UPPER"],
)
def test_manifest_rejects_unsafe_plugin_identifiers(plugin_id: str) -> None:
    manifest = copy.deepcopy(
        PluginRegistry(discover_external=False).get("plain-text-parser").manifest
    )
    manifest["plugin_id"] = plugin_id
    with pytest.raises(PluginManifestError):
        read_manifest_bytes(json.dumps(manifest).encode("utf-8"))


def test_plugin_output_cannot_control_authoritative_ids_paths_or_size() -> None:
    for value in (
        {"evidence_id": "forged"},
        {"item_id": "forged"},
        {"output_path": "relative.json"},
        {"value": "C:\\secret\\file"},
    ):
        with pytest.raises(PluginConformanceError):
            assert_safe_plugin_output(value)
    with pytest.raises(PluginConformanceError, match="limit"):
        assert_safe_plugin_output({"value": "x" * 11}, max_characters=10)


def test_invalid_normalizer_response_is_a_conformance_failure(tmp_path: Path) -> None:
    implementation = tmp_path / "plugin.py"
    implementation.write_text("class Invalid: pass\n", encoding="utf-8")
    manifest = copy.deepcopy(
        PluginRegistry(discover_external=False).get("generic-normalizer").manifest
    )
    manifest.update(
        {
            "plugin_id": "invalid-normalizer",
            "distribution": {"name": "invalid-normalizer", "required_version": "1.0.0"},
            "entry_point": {
                "group": "kg_mnp.plugins",
                "name": "invalid-normalizer",
                "object": "invalid_plugin:Invalid",
            },
            "implementation_files": ["plugin.py"],
        }
    )

    class InvalidNormalizer:
        def normalize(self, request):
            return "invalid"

    raw = json.dumps(manifest, sort_keys=True).encode("utf-8")
    descriptor = PluginDescriptor(
        plugin_id="invalid-normalizer",
        manifest=manifest,
        manifest_bytes=raw,
        distribution_name="invalid-normalizer",
        distribution_version="1.0.0",
        distribution_root=tmp_path,
        builtin=False,
        status=PluginStatus.ENABLED,
        entry_point=SimpleNamespace(load=lambda: InvalidNormalizer),
    )
    result = run_conformance(
        PluginRegistry(descriptors=(descriptor,), discover_external=False),
        descriptor.plugin_id,
    )
    assert result.status == "FAIL"
    assert result.errors


def test_independent_wheel_is_discovered_without_import_then_explicitly_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = ROOT / "tests" / "fixtures" / "plugins" / "sample-uppercase-normalizer"
    wheelhouse = tmp_path / "wheelhouse"
    site = tmp_path / "site"
    wheelhouse.mkdir()
    site.mkdir()
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(fixture),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheel = next(wheelhouse.glob("*.whl"))
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(site), str(wheel)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    distributions = tuple(metadata.distributions(path=[str(site)]))
    entry_points = tuple(
        point
        for distribution in distributions
        for point in distribution.entry_points
        if point.group == "kg_mnp.plugins"
    )
    monkeypatch.setattr(discovery, "_entry_points", lambda: entry_points)
    monkeypatch.syspath_prepend(str(site))
    sys.modules.pop("sample_uppercase_normalizer.plugin", None)
    descriptors = discovery.discover_external_plugins()
    assert len(descriptors) == 1
    assert descriptors[0].status == PluginStatus.DISABLED
    assert "sample_uppercase_normalizer.plugin" not in sys.modules
    disabled = PluginRegistry(descriptors=descriptors, discover_external=False)
    assert disabled.get("sample-uppercase-normalizer").status == PluginStatus.DISABLED
    enabled = PluginRegistry(
        descriptors=descriptors,
        discover_external=False,
        allowlist=("sample-uppercase-normalizer",),
    )
    result = run_conformance(enabled, "sample-uppercase-normalizer")
    assert result.status == "PASS", result.errors
