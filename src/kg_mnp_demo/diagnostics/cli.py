"""CLI for deterministic local build, validation and read-only inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .authority_loader import load_verified_authority_snapshot
from .engine import reconstruct_diagnostics
from .errors import DiagnosticError
from .runtime import create_diagnostics_app
from .validator import (
    validate_diagnostic_package,
    validate_diagnostic_package_against_authorities,
)

PACKAGE_FILENAME = "deterministic-diagnostic-package.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp diagnostics",
        description="Read-only deterministic semantic diagnostics",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def authority_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--publication-package", required=True, type=Path)
        command.add_argument("--publication-attestation", required=True, type=Path)
        command.add_argument(
            "--publication-scenario",
            required=True,
            choices=(
                "full-confirmation",
                "modified-confirmation",
                "rejection",
                "issue-resolution",
            ),
        )
        command.add_argument("--phase01-artifact-dir", required=True, type=Path)
        command.add_argument("--phase02-artifact-dir", required=True, type=Path)

    build = commands.add_parser("build")
    authority_arguments(build)
    build.add_argument("--output-dir", required=True, type=Path)

    validate = commands.add_parser("validate")
    authority_arguments(validate)
    validate.add_argument("--package", required=True, type=Path)

    inspect = commands.add_parser("inspect")
    inspect.add_argument("--package", required=True, type=Path)
    inspect.add_argument("--diagnostic-id")

    runtime = commands.add_parser("runtime")
    runtime_commands = runtime.add_subparsers(dest="runtime_command", required=True)
    check = runtime_commands.add_parser("check")
    check.add_argument("--package", required=True, type=Path)

    serve = commands.add_parser("serve")
    serve.add_argument("--package", required=True, type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "build":
            snapshot = load_verified_authority_snapshot(
                publication_package_directory=arguments.publication_package,
                publication_attestation_path=arguments.publication_attestation,
                publication_scenario=arguments.publication_scenario,
                phase01_artifact_directory=arguments.phase01_artifact_dir,
                phase02_artifact_directory=arguments.phase02_artifact_dir,
            )
            package = reconstruct_diagnostics(snapshot)
            output = Path(arguments.output_dir)
            output.mkdir(parents=True, exist_ok=True)
            target = output / PACKAGE_FILENAME
            target.write_bytes(package.canonical_bytes())
            print(json.dumps({
                "package": target.name,
                "package_id": package["manifest"]["package_id"],
                "package_semantic_hash": package.package_semantic_hash,
                "status": "DIAGNOSTICS_VALIDATED",
            }, sort_keys=True))
            return 0
        if arguments.command == "validate":
            snapshot = load_verified_authority_snapshot(
                publication_package_directory=arguments.publication_package,
                publication_attestation_path=arguments.publication_attestation,
                publication_scenario=arguments.publication_scenario,
                phase01_artifact_directory=arguments.phase01_artifact_dir,
                phase02_artifact_directory=arguments.phase02_artifact_dir,
            )
            result = validate_diagnostic_package_against_authorities(
                arguments.package,
                snapshot,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        if arguments.command == "inspect":
            package = validate_diagnostic_package(arguments.package)
            result = package["summary"]
            if arguments.diagnostic_id:
                identifier = arguments.diagnostic_id
                if not identifier.startswith("urn:kg-mnp:diagnostic:"):
                    identifier = f"urn:kg-mnp:diagnostic:{identifier}"
                result = next(
                    issue for issue in package["issues"]
                    if issue["diagnostic_id"] == identifier
                )
            print(canonical_json_bytes(result).decode("utf-8"))
            return 0
        if arguments.command == "runtime":
            package = validate_diagnostic_package(arguments.package)
            print(json.dumps({
                "package_id": package["manifest"]["package_id"],
                "read_only": True,
                "status": "DIAGNOSTICS_READY",
            }, sort_keys=True))
            return 0
        if arguments.host != "127.0.0.1" or not 0 <= arguments.port <= 65535:
            raise ValueError("diagnostics runtime must use loopback and a valid port")
        app = create_diagnostics_app(arguments.package)
        import uvicorn

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=arguments.port,
            access_log=False,
        )
        return 0
    except (DiagnosticError, ValueError, OSError, StopIteration) as exc:
        print(json.dumps({
            "code": "DIAGNOSTICS_NOT_READY",
            "detail": str(exc),
            "status": "FAILED",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
