import pytest

from kg_mnp.plugins.manifest import _compatible_bundled_versions
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot, snapshot_distribution_version


@pytest.mark.parametrize("installed,expected", [("0.9.0.dev0",True),("0.9.0rc1",True),("0.4.0.dev0",False),("1.0.0",False),("1!0.9.0",False),("invalid",False)])
def test_bundled_version_comparison_preserves_major_and_minimum(installed, expected):
    assert _compatible_bundled_versions("0.4.0", installed) is expected


@pytest.mark.parametrize("value,expected", [("0.7.0","0.7.0"),("0.9.0.dev0","0.9.0-dev.0"),("0.9.0rc1","0.9.0-rc.1"),("0.9.0a2","0.9.0-alpha.2")])
def test_snapshot_prerelease_spelling_is_explicit(value, expected):
    assert snapshot_distribution_version(value) == expected


def test_current_development_distribution_can_discover_and_snapshot_parser():
    registry = PluginRegistry()
    descriptor = registry.get("json-parser")
    snapshot = build_snapshot(descriptor)
    assert snapshot["distribution_version"] == snapshot_distribution_version(descriptor.distribution_version)
    assert snapshot["implementation_digest"]
