"""Current modeling resources plus read-only provider inspection."""
import json

from kg_mnp.plugins.conformance import run_conformance
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.services.resource_cli import main as resource_main


def main(argv=None):
    args = list(argv or [])
    if args[:2] == ["provider", "list"]:
        registry = PluginRegistry()
        print(json.dumps([{"plugin_id":p.plugin_id,"authority_level":p.manifest.get("authority_level"),"network_policy":p.manifest.get("network_policy")} for p in registry.list() if "modeling-provider" in p.manifest["plugin_kinds"]],sort_keys=True))
        return 0
    if len(args) >= 3 and args[:2] == ["provider", "conformance"]:
        result = run_conformance(PluginRegistry(),args[2])
        print(json.dumps({"plugin_id":result.plugin_id,"status":result.status}))
        return 0 if result.status == "PASS" else 2
    return resource_main("model",args)
