"""Command line entry points for the read-only workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .binding import WorkbenchBinding
from .errors import WorkbenchError, WorkbenchErrorCode
from .manifest import build_workbench_package, validate_workbench_package
from .policy import load_workbench_policy
from .relay import Phase01Relay
from .runtime import create_workbench_app


def _binding(value: str) -> WorkbenchBinding:
    return WorkbenchBinding.load(Path(value))


def _runtime(
    phase01_artifact_directory: str,
    phase01_url: str,
) -> tuple[WorkbenchBinding, Phase01Relay]:
    binding = _binding(phase01_artifact_directory)
    relay = Phase01Relay(phase01_url, binding)
    binding.verify_health(relay.health())
    return binding, relay


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp workbench",
        description="Read-only semantic evidence workbench",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    package = commands.add_parser("package")
    package_commands = package.add_subparsers(
        dest="package_command",
        required=True,
    )
    build = package_commands.add_parser("build")
    build.add_argument("--phase01-artifact-dir", required=True)
    build.add_argument("--output-dir", required=True)
    validate = package_commands.add_parser("validate")
    validate.add_argument("--phase01-artifact-dir", required=True)
    validate.add_argument("--package-dir", required=True)

    runtime = commands.add_parser("runtime")
    runtime_commands = runtime.add_subparsers(
        dest="runtime_command",
        required=True,
    )
    check = runtime_commands.add_parser("check")
    check.add_argument("--phase01-artifact-dir", required=True)
    check.add_argument("--phase01-url", required=True)

    serve = commands.add_parser("serve")
    serve.add_argument("--phase01-artifact-dir", required=True)
    serve.add_argument("--phase01-url", required=True)
    serve.add_argument("--package-dir", required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8092)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "package":
            binding = _binding(arguments.phase01_artifact_dir)
            if arguments.package_command == "build":
                result = build_workbench_package(
                    Path(arguments.output_dir),
                    binding,
                )
            else:
                result = validate_workbench_package(
                    Path(arguments.package_dir),
                    binding,
                )
            print(json.dumps(result, sort_keys=True))
            return 0

        if arguments.command == "runtime":
            binding, relay = _runtime(
                arguments.phase01_artifact_dir,
                arguments.phase01_url,
            )
            print(
                json.dumps(
                    {
                        **binding.public_status(),
                        "phase01_health_status": relay.health()["status"],
                        "status": "WORKBENCH_READY",
                    },
                    sort_keys=True,
                )
            )
            return 0

        policy = load_workbench_policy()
        if (
            arguments.host != policy["network"]["bind_host"]
            or not 1 <= arguments.port <= 65535
        ):
            raise WorkbenchError(
                WorkbenchErrorCode.WORKBENCH_NOT_READY
            )
        binding, relay = _runtime(
            arguments.phase01_artifact_dir,
            arguments.phase01_url,
        )
        validate_workbench_package(Path(arguments.package_dir), binding)
        app = create_workbench_app(
            binding=binding,
            relay=relay,
            package_directory=Path(arguments.package_dir),
        )
        import uvicorn

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=arguments.port,
            access_log=False,
        )
        return 0
    except WorkbenchError as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
