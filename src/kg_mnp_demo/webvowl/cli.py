from __future__ import annotations

import json
from pathlib import Path

from .package_builder import build_webvowl_visualization_package
from .package_validator import validate_webvowl_visualization_package
from .runtime import runtime_descriptor, runtime_smoke


def _print(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def add_webvowl_parser(subcommands):
    root = subcommands.add_parser(
        "webvowl", help="Stage 08 TBox-only WebVOWL projection"
    )
    commands = root.add_subparsers(dest="webvowl_command", required=True)
    package = commands.add_parser("package")
    package_commands = package.add_subparsers(dest="package_command", required=True)
    build = package_commands.add_parser("build")
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--force", action="store_true")
    validate = package_commands.add_parser("validate")
    validate.add_argument("--package-dir", required=True, type=Path)
    inspect = package_commands.add_parser("inspect")
    inspect.add_argument("--package-dir", required=True, type=Path)
    runtime = commands.add_parser("runtime")
    runtime_commands = runtime.add_subparsers(dest="runtime_command", required=True)
    verify = runtime_commands.add_parser("verify")
    verify.add_argument("--base-url", default="http://127.0.0.1:8080")
    return root


def dispatch_webvowl(args):
    if args.webvowl_command == "package":
        if args.package_command == "build":
            result = build_webvowl_visualization_package(
                output_dir=args.output_dir, force=args.force
            )
            _print(
                {
                    "output": str(args.output_dir) if args.output_dir else None,
                    "visualization_id": result["manifest"]["visualization_id"],
                    "visualization_semantic_hash": result["manifest"][
                        "visualization_semantic_hash"
                    ],
                    "release_status": result["manifest"]["release_status"],
                }
            )
            return 0
        if args.package_command == "validate":
            _print(validate_webvowl_visualization_package(args.package_dir))
            return 0
        manifest = json.loads(
            (args.package_dir / "visualization/visualization-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        _print(
            {
                "inspection_only": True,
                "validated": False,
                "visualization_id": manifest.get("visualization_id"),
                "release_status_claim": manifest.get("release_status"),
                "class_count": manifest.get("class_count"),
            }
        )
        return 0
    if args.runtime_command == "verify":
        smoke = runtime_smoke(args.base_url)
        _print({"runtime": runtime_descriptor(), "browser_smoke": smoke})
        return 0 if smoke.get("status") == "PASS" else 1
