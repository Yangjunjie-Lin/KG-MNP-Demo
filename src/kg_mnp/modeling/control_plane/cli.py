"""Current modeling resources plus read-only provider inspection."""

from kg_mnp.contracts.cli import emit_json
from kg_mnp.plugins.conformance import run_conformance
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.services.resource_cli import main as resource_main


def main(argv=None):
    args = list(argv or [])
    if args[:2] == ["provider", "list"]:
        registry = PluginRegistry()
        emit_json([{"plugin_id":p.plugin_id,"authority_level":p.manifest.get("authority_level"),"network_policy":p.manifest.get("network_policy")} for p in registry.list() if "modeling-provider" in p.manifest["plugin_kinds"]])
        return 0
    if len(args) >= 3 and args[:2] == ["provider", "conformance"]:
        result = run_conformance(PluginRegistry(),args[2])
        emit_json({"plugin_id":result.plugin_id,"status":result.status})
        return 0 if result.status == "PASS" else 2
    return resource_main("model",args)
