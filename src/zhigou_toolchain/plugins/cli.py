"""Public `kg-mnp plugin` command."""

from __future__ import annotations

import argparse
import traceback

from zhigou_toolchain.contracts.cli import command_result, emit_json

from .conformance import run_conformance
from .errors import PluginError
from .registry import PluginRegistry
from .snapshot import build_snapshot

SUCCESS = 0
PLUGIN_INVALID = 9
PLUGIN_UNAVAILABLE = 10
INTERNAL_ERROR = 8


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp plugin")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="operation", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--json", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("plugin_id")
    inspect.add_argument("--json", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("plugin_id")
    validate.add_argument("--json", action="store_true")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("plugin_id")
    snapshot.add_argument("--json", action="store_true")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    conformance = commands.add_parser("conformance")
    conformance.add_argument("plugin_id")
    conformance.add_argument("--enable", action="store_true")
    conformance.add_argument("--json", action="store_true")
    return parser


def _descriptor(descriptor) -> dict:
    return {
        "plugin_id": descriptor.plugin_id,
        "plugin_version": descriptor.manifest.get("plugin_version"),
        "plugin_api_version": descriptor.manifest.get("plugin_api_version"),
        "plugin_kinds": descriptor.manifest.get("plugin_kinds", []),
        "capabilities": descriptor.manifest.get("capabilities", []),
        "media_types": descriptor.manifest.get("media_types", []),
        "determinism": descriptor.manifest.get("determinism"),
        "side_effects": descriptor.manifest.get("side_effects", []),
        "status": descriptor.status.value,
        "status_reason": descriptor.status_reason,
        "builtin": descriptor.builtin,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    command = f"plugin {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    subject = getattr(arguments, "plugin_id", "local-plugin-registry")
    try:
        registry = PluginRegistry()
        if arguments.operation == "list":
            result = [_descriptor(item) for item in registry.list()]
        elif arguments.operation == "inspect":
            result = _descriptor(registry.get(arguments.plugin_id))
        elif arguments.operation == "validate":
            descriptor = registry.get(arguments.plugin_id)
            build_snapshot(descriptor)
            result = {"plugin_id": descriptor.plugin_id, "valid": True}
        elif arguments.operation == "snapshot":
            result = build_snapshot(registry.get(arguments.plugin_id))
        elif arguments.operation == "doctor":
            descriptors = registry.list()
            result = {
                "plugin_count": len(descriptors),
                "statuses": {status: sum(item.status.value == status for item in descriptors) for status in sorted({item.status.value for item in descriptors})},
                "network_access": False,
                "external_auto_import": False,
            }
        else:
            descriptor = registry.get(arguments.plugin_id)
            if not descriptor.enabled and arguments.enable:
                registry.enable(arguments.plugin_id)
            conformance = run_conformance(registry, arguments.plugin_id)
            result = {
                "plugin_id": conformance.plugin_id,
                "status": conformance.status,
                "checks": [
                    {"check": name, "status": status}
                    for name, status in conformance.checks
                ],
                "errors": list(conformance.errors),
            }
            if conformance.status != "PASS":
                raise PluginError("; ".join(conformance.errors) or "conformance failed")
        payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=subject, result=result)
        if use_json:
            emit_json(payload)
        elif isinstance(result, list):
            for item in result:
                print(f"{item['plugin_id']} {item['status']} {item['determinism']}")
        else:
            emit_json(result)
        return SUCCESS
    except PluginError as exc:
        code = PLUGIN_UNAVAILABLE if "unavailable" in str(exc).casefold() or "not enabled" in str(exc).casefold() else PLUGIN_INVALID
        payload = command_result(command, status="ERROR", code=code, subject=subject, errors=[{"code": "PLUGIN_ERROR", "message": str(exc)}])
        if use_json:
            emit_json(payload)
        else:
            print(f"ERROR {exc}")
        if arguments.debug:
            traceback.print_exc()
        return code
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        if arguments.debug:
            traceback.print_exc()
        else:
            print(f"ERROR internal plugin command failure: {exc}")
        return INTERNAL_ERROR
