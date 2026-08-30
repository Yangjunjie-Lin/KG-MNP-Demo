from __future__ import annotations

import json
from pathlib import Path

from .package_builder import build_end_to_end_publication_package
from .package_validator import (
    validate_end_to_end_publication_package_against_authorities,
)


def _print(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def add_publication_parser(subcommands):
    pub = subcommands.add_parser(
        "publication", help="Stage 08 end-to-end publication package"
    )
    commands = pub.add_subparsers(dest="publication_command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--scenario", default="full-confirmation")
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--force", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("--package-dir", required=True, type=Path)
    validate.add_argument("--scenario", default="full-confirmation")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--package-dir", required=True, type=Path)
    return pub


def dispatch_publication(args):
    if args.publication_command == "build":
        result = build_end_to_end_publication_package(
            scenario=args.scenario, output_dir=args.output_dir, force=args.force
        )
        _print(
            {
                "output": str(args.output_dir) if args.output_dir else None,
                "publication_id": result["manifest"]["publication_id"],
                "publication_semantic_hash": result["manifest"][
                    "publication_semantic_hash"
                ],
                "publication_status": result["manifest"]["publication_status"],
            }
        )
        return 0
    if args.publication_command == "validate":
        _print(
            validate_end_to_end_publication_package_against_authorities(
                args.package_dir, scenario=args.scenario
            )
        )
        return 0
    manifest = json.loads(
        (args.package_dir / "publication-manifest.json").read_text(encoding="utf-8")
    )
    _print(
        {
            "inspection_only": True,
            "validated": False,
            "publication_id": manifest.get("publication_id"),
            "publication_status_claim": manifest.get("publication_status"),
            "artifact_count": len(manifest.get("artifact_manifest", [])),
        }
    )
    return 0
