"""Root `kg-mnp compile` and `kg-mnp package` command surfaces."""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.cli import emit_json
from zhigou_toolchain.domain_packs.registry import discover_domain_packs_root
from zhigou_toolchain.environment import get_setting

from .artifact_resolver import WorkspaceArtifactResolver
from .compiler import SemanticCompiler
from .contracts import verify_artifact
from .errors import EXIT_CODES, SemanticKernelError
from .identifiers import package_storage_key
from .packaging.archive import verify_kgop
from .packaging.verifier import verify_package
from .security import safe_child

COMPILE_HELP = """usage: kg-mnp compile <command> [options]

commands:
  input verify|inspect   reconstruct confirmed-package authority closure
  plan                   create/inspect/validate a deterministic plan
  build                  compile and validate an ontology package
  inspect                inspect a compilation build
  validate               validate a compilation build package
  reproduce              compare a build with its immutable package
  reports                list build validation reports
"""

PACKAGE_HELP = """usage: kg-mnp package <command> [options]

commands:
  list             list VALIDATED_UNPUBLISHED packages
  inspect          inspect a package manifest
  verify           strictly verify a package directory
  export           create a deterministic .kgop archive
  verify-archive   independently verify a .kgop archive
  contents         list .kgop entries
"""


def _read_json(path: Path | str) -> dict[str, Any]:
    unresolved = Path(path)
    if unresolved.is_symlink():
        raise ValueError("unsafe JSON artifact")
    source = unresolved.resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 16_777_216:
        raise ValueError("unsafe JSON artifact")
    value = json.loads(source.read_bytes())
    if not isinstance(value, dict):
        raise TypeError("JSON artifact root must be an object")
    return value


def _load_cq_plan(workspace: str, reference: str) -> dict[str, Any]:
    root = Path(workspace).resolve(strict=True)
    if reference.startswith("urn:kg-mnp:"):
        return WorkspaceArtifactResolver(root).resolve(reference).document
    return _read_json(safe_child(root, reference, must_exist=True))


def _compiler(workspace: str, args: argparse.Namespace) -> SemanticCompiler:
    pack_root = args.domain_packs_root if getattr(args, "domain_packs_root", None) else discover_domain_packs_root()
    reasoner = getattr(args, "reasoner_jar", None) or get_setting("ROBOT_JAR")
    return SemanticCompiler(workspace, domain_packs_root=pack_root, reasoner_jar=reasoner)


def _common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain-packs-root")
    parser.add_argument("--reasoner-jar")


def _compile_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp compile", add_help=True)
    commands = parser.add_subparsers(dest="command", required=True)
    input_command = commands.add_parser("input")
    input_command.add_argument("action", choices=("verify", "inspect"))
    input_command.add_argument("workspace")
    input_command.add_argument("--confirmed", required=True)
    _common_options(input_command)
    plan = commands.add_parser("plan")
    plan.add_argument("first")
    plan.add_argument("second", nargs="?")
    plan.add_argument("--confirmed")
    plan.add_argument("--package-name")
    plan.add_argument("--package-version")
    plan.add_argument("--ontology-iri")
    plan.add_argument("--version-iri")
    plan.add_argument("--cq-plan")
    _common_options(plan)
    build = commands.add_parser("build")
    build.add_argument("workspace")
    build.add_argument("--plan")
    build.add_argument("--confirmed")
    build.add_argument("--package-name")
    build.add_argument("--package-version")
    build.add_argument("--ontology-iri")
    build.add_argument("--version-iri")
    build.add_argument("--cq-plan")
    _common_options(build)
    for name in ("inspect", "validate", "reproduce", "reports"):
        command = commands.add_parser(name)
        command.add_argument("workspace")
        command.add_argument("build_id")
        _common_options(command)
    return parser


def _require_plan_options(args: argparse.Namespace) -> None:
    missing = [name for name in ("confirmed", "package_name", "package_version", "ontology_iri", "version_iri", "cq_plan") if not getattr(args, name, None)]
    if missing:
        raise ValueError("missing required plan options: " + ", ".join("--" + name.replace("_", "-") for name in missing))


def _run_compile(arguments: list[str]) -> tuple[str, str | None, Any]:
    if len(arguments) >= 4 and arguments[:2] in (["plan", "inspect"], ["plan", "validate"]):
        workspace = Path(arguments[2]).resolve(strict=True)
        plan_id = arguments[3]
        plan = WorkspaceArtifactResolver(workspace).resolve(plan_id).document
        if arguments[1] == "validate":
            verify_artifact(plan, id_field="plan_id", urn_kind="semantic-compilation-plan", contract="semantic-compilation-plan")
            result: Any = {"plan_id": plan_id, "status": "VALID"}
        else:
            result = plan
        return f"compile plan {arguments[1]}", plan_id, result
    args = _compile_parser().parse_args(arguments)
    if args.command == "input":
        compiler = _compiler(args.workspace, args)
        result = compiler.attest(args.confirmed)
        return f"compile input {args.action}", args.confirmed, result
    if args.command == "plan":
        if args.first in {"inspect", "validate"}:
            if args.second is None:
                raise ValueError("plan inspect/validate requires a workspace and plan ID")
            # Syntax is: plan inspect <workspace> <plan-id>; argparse consumes
            # only two positionals, so preserve a compact alternative via ID lookup.
            raise ValueError("use: kg-mnp compile inspect|validate <workspace> <plan-id>")
        _require_plan_options(args)
        compiler = _compiler(args.first, args)
        cq_plan = _load_cq_plan(args.first, args.cq_plan)
        plan, _ = compiler.create_plan(package_id=args.confirmed, package_name=args.package_name, package_version=args.package_version, ontology_iri=args.ontology_iri, version_iri=args.version_iri, cq_test_plan=cq_plan)
        return "compile plan", plan["plan_id"], plan
    if args.command == "build":
        compiler = _compiler(args.workspace, args)
        plan_id = args.plan
        if plan_id is None:
            _require_plan_options(args)
            cq_plan = _load_cq_plan(args.workspace, args.cq_plan)
            plan, _ = compiler.create_plan(package_id=args.confirmed, package_name=args.package_name, package_version=args.package_version, ontology_iri=args.ontology_iri, version_iri=args.version_iri, cq_test_plan=cq_plan)
            plan_id = plan["plan_id"]
        result = compiler.build(plan_id)
        return "compile build", result.build_id, {"build_id": result.build_id, "package_id": result.package_id, "package_directory": str(result.package_directory)}
    workspace = Path(args.workspace).resolve(strict=True)
    build_dir = workspace / "artifacts" / "builds" / "compilation" / args.build_id.rsplit(":", 1)[-1]
    if not build_dir.is_dir():
        # Build directories use the stable URN today; retain lookup by run document.
        records = WorkspaceArtifactResolver(workspace).index
        run = records.get(args.build_id)
        if run is not None:
            build_dir = workspace / Path(run.relative_path).parent
    run = _read_json(build_dir / "semantic-compilation-run.json")
    package_id = run["package_id"]
    package_dir = workspace / "artifacts" / "packages" / package_storage_key(package_id)
    if args.command == "inspect":
        return "compile inspect", args.build_id, run
    if args.command == "validate":
        return "compile validate", args.build_id, verify_package(package_dir)
    if args.command == "reproduce":
        compiler = _compiler(str(workspace), args)
        result = compiler.reproduce(run["plan_id"])
        return "compile reproduce", args.build_id, result
    reports = sorted(path.name for path in (workspace / "artifacts" / "validation" / "compilation" / args.build_id.rsplit(":", 1)[-1]).glob("*.json"))
    return "compile reports", args.build_id, reports


def _package_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp package")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("workspace")
    for name in ("inspect", "verify", "export"):
        command = commands.add_parser(name)
        command.add_argument("workspace")
        command.add_argument("package_id")
        _common_options(command)
    for name in ("verify-archive", "contents"):
        command = commands.add_parser(name)
        command.add_argument("archive")
    return parser


def _find_package(workspace: Path, package_id: str) -> Path:
    path = workspace / "artifacts" / "packages" / package_storage_key(package_id)
    if not path.is_dir():
        raise ValueError("ontology package is not present in the workspace")
    return path


def _run_package(arguments: list[str]) -> tuple[str, str | None, Any]:
    args = _package_parser().parse_args(arguments)
    if args.command in {"verify-archive", "contents"}:
        result = verify_kgop(args.archive)
        return f"package {args.command}", str(args.archive), result if args.command == "verify-archive" else result["contents"]
    workspace = Path(args.workspace).resolve(strict=True)
    if args.command == "list":
        rows = []
        for manifest in sorted((workspace / "artifacts" / "packages").glob("*/ontology-package.json")):
            verify_package(manifest.parent)
            value = _read_json(manifest)
            rows.append({"package_id": value["package_id"], "package_name": value["package_name"], "package_version": value["package_version"], "package_status": value["package_status"]})
        return "package list", str(workspace), rows
    package_dir = _find_package(workspace, args.package_id)
    if args.command == "inspect":
        return "package inspect", args.package_id, _read_json(package_dir / "ontology-package.json")
    if args.command == "verify":
        return "package verify", args.package_id, verify_package(package_dir)
    compiler = _compiler(str(workspace), args)
    return "package export", args.package_id, compiler.export(args.package_id)


def _entry(arguments: list[str], *, package: bool) -> int:
    json_output = "--json" in arguments
    debug = "--debug" in arguments
    filtered = [item for item in arguments if item not in {"--json", "--debug"}]
    command = "package" if package else "compile"
    try:
        label, subject, result = (_run_package(filtered) if package else _run_compile(filtered))
        envelope = {"command": label, "status": "OK", "code": 0, "subject": subject, "errors": [], "warnings": [], "result": result}
        if json_output:
            emit_json(envelope)
        else:
            emit_json(result)
        return 0
    except (SemanticKernelError, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        code_name = exc.code if isinstance(exc, SemanticKernelError) else "COMPILATION_FAILED"
        code = EXIT_CODES.get(code_name, 30)
        envelope = {"command": command, "status": "ERROR", "code": code, "subject": None, "errors": [{"code": code_name, "message": str(exc)}], "warnings": [], "result": None}
        if json_output:
            emit_json(envelope)
        else:
            print(f"{code_name}: {exc}")
        if debug:
            traceback.print_exc()
        return code


def compile_main(argv: list[str] | None = None) -> int:
    arguments = list(argv or [])
    if arguments in ([], ["-h"], ["--help"]):
        print(COMPILE_HELP, end="")
        return 0
    return _entry(arguments, package=False)


def package_main(argv: list[str] | None = None) -> int:
    arguments = list(argv or [])
    if arguments in ([], ["-h"], ["--help"]):
        print(PACKAGE_HELP, end="")
        return 0
    return _entry(arguments, package=True)
