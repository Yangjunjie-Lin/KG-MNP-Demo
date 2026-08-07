from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from ..compilation.artifacts import write_artifact_set
from ..compilation.policy import load_compiler_policy
from ..modeling.dependencies import load_modeling_dependencies
from ..modeling.review_policy import load_default_review_policy
from ._io import read_json
from .attestation import build_import_attestation, write_import_attestation
from .client import GraphDBClient
from .identifiers import repository_id_for_publication
from .importer import import_package
from .package_builder import build_graphdb_import_package
from .package_validator import validate_graphdb_import_package
from .policy import load_graphdb_policy
from .verifier import verify_imported_repository


def _authority_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--decision-log", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--compilation-dir", required=True, type=Path)


def _connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default="http://127.0.0.1:7200")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--timeout", type=float, default=10.0)


def add_graphdb_parser(subcommands: argparse._SubParsersAction) -> None:
    graphdb = subcommands.add_parser("graphdb", help="Stage 07 GraphDB package and runtime operations")
    commands = graphdb.add_subparsers(dest="graphdb_command", required=True)

    package = commands.add_parser("package", help="build, validate, or inspect import packages")
    package_commands = package.add_subparsers(dest="graphdb_package_command", required=True)
    build = package_commands.add_parser("build")
    _authority_arguments(build)
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--force", action="store_true")
    validate = package_commands.add_parser("validate")
    _authority_arguments(validate)
    validate.add_argument("--package-dir", required=True, type=Path)
    inspect = package_commands.add_parser("inspect")
    inspect.add_argument("--package-dir", required=True, type=Path)

    runtime = commands.add_parser("runtime")
    runtime_commands = runtime.add_subparsers(dest="graphdb_runtime_command", required=True)
    runtime_check = runtime_commands.add_parser("check")
    _connection_arguments(runtime_check)

    repository = commands.add_parser("repository")
    repository_commands = repository.add_subparsers(dest="graphdb_repository_command", required=True)
    create = repository_commands.add_parser("create")
    create.add_argument("--package-dir", required=True, type=Path)
    _connection_arguments(create)

    import_cmd = commands.add_parser("import")
    _authority_arguments(import_cmd)
    import_cmd.add_argument("--package-dir", required=True, type=Path)
    import_cmd.add_argument("--cleanup-failed-generated-repository", action="store_true")
    _connection_arguments(import_cmd)

    verify = commands.add_parser("verify")
    verify.add_argument("--package-dir", required=True, type=Path)
    verify.add_argument("--report-dir", type=Path)
    _connection_arguments(verify)

    attest = commands.add_parser("attest")
    attest.add_argument("--package-dir", required=True, type=Path)
    attest.add_argument("--report-dir", type=Path)
    attest.add_argument("--create-status", required=True, type=int)
    attest.add_argument("--import-status", required=True, type=int)
    _connection_arguments(attest)

    destroy = commands.add_parser("destroy-generated")
    destroy.add_argument("--repository-id", required=True)
    destroy.add_argument("--publication-id", required=True)
    destroy.add_argument("--confirm-generated-repository", action="store_true", required=True)
    _connection_arguments(destroy)


def _authorities(args: argparse.Namespace) -> tuple[dict[str, Any], ...]:
    dependencies = load_modeling_dependencies()
    return (
        read_json(args.input), read_json(args.proposal), read_json(args.decision_log),
        read_json(args.package), dependencies["ontology_baseline"],
        dependencies["mapping_rules"], dependencies["terminology_profile"],
        dependencies["proposal_policy"], load_default_review_policy(),
    )


def _client(args: argparse.Namespace) -> GraphDBClient:
    return GraphDBClient(base_url=args.base_url, timeout=args.timeout, allow_remote=args.allow_remote)


def _validate(args: argparse.Namespace) -> dict[str, Any]:
    values = _authorities(args)
    return validate_graphdb_import_package(
        args.package_dir,
        compilation_directory=args.compilation_dir,
        cleaned_partial_data=values[0], proposal=values[1],
        final_review_decision_log=values[2], confirmed_modeling_package=values[3],
        ontology_baseline=values[4], mapping_rules=values[5],
        terminology_profile=values[6], proposal_policy=values[7],
        review_policy=values[8], compiler_policy=load_compiler_policy(),
    )


def dispatch_graphdb(args: argparse.Namespace, json_print: Callable[..., None]) -> int:
    command = args.graphdb_command
    if command == "package" and args.graphdb_package_command == "build":
        values = _authorities(args)
        result = build_graphdb_import_package(
            args.compilation_dir, *values, load_compiler_policy(), output_dir=None
        )
        destination = args.output_dir or Path("runtime_outputs") / "graphdb" / result["manifest"]["publication_id"].rsplit(":", 1)[-1]
        write_artifact_set(destination, result["files"], force=args.force)
        json_print({"output": destination.as_posix(), **{key: result["manifest"][key] for key in ("publication_id", "publication_semantic_hash", "repository_id", "assembled_quad_count", "release_status")}})
        return 0
    if command == "package" and args.graphdb_package_command == "validate":
        json_print(_validate(args))
        return 0
    if command == "package" and args.graphdb_package_command == "inspect":
        manifest = read_json(args.package_dir / "graphdb-import-manifest.json")
        json_print({"inspection_only": True, "validated": False, "publication_id": manifest.get("publication_id"), "repository_id": manifest.get("repository_id"), "release_status_claim": manifest.get("release_status"), "artifact_count": len(manifest.get("artifact_manifest", []))})
        return 0
    if command == "runtime" and args.graphdb_runtime_command == "check":
        client = _client(args)
        policy = load_graphdb_policy()
        readiness = client.verify_runtime_readiness(
            expected_product_version=policy["graphdb"]["product_version"]
        )
        json_print({"base_url": client.base_url, **readiness})
        return 0
    if command == "repository" and args.graphdb_repository_command == "create":
        client = _client(args)
        manifest = read_json(args.package_dir / "graphdb-import-manifest.json")
        if manifest["repository_id"] in client.list_repositories():
            raise ValueError("refusing to overwrite an existing repository")
        status = client.create_repository((args.package_dir / "repository/repository-config.ttl").read_bytes())
        count = client.count_repository_statements(manifest["repository_id"])
        if count != 0:
            raise ValueError("fresh repository is not empty")
        json_print({"repository_id": manifest["repository_id"], "create_status": status, "initial_count": count})
        return 0
    if command == "import":
        validation = _validate(args)
        result = import_package(_client(args), args.package_dir, cleanup_failed_generated_repository=args.cleanup_failed_generated_repository)
        json_print({"package_validated": validation["valid"], **result})
        return 0
    if command in {"verify", "attest"}:
        client = _client(args)
        manifest = read_json(args.package_dir / "graphdb-import-manifest.json")
        report_dir = args.report_dir or Path("runtime_reports") / "graphdb" / manifest["publication_id"].rsplit(":", 1)[-1]
        verification = verify_imported_repository(client, args.package_dir, report_directory=report_dir)
        if command == "verify":
            json_print(verification)
            return 0
        readiness = client.verify_runtime_readiness(
            expected_product_version=load_graphdb_policy()["graphdb"]["product_version"]
        )
        attestation = build_import_attestation(source_publication_id=manifest["publication_id"], source_compilation_id=manifest["source_compilation_id"], repository_config_hash=manifest["repository_config_byte_hash"], import_dataset_hash=manifest["assembled_dataset_semantic_hash"], export_dataset_hash=verification["export_semantic_hash"], expected_graph_count=len(manifest["named_graphs"]), actual_graph_count=len(verification["actual_graph_counts"]), expected_quad_count=manifest["assembled_quad_count"], actual_quad_count=verification["actual_quad_count"], expected_named_graphs=manifest["named_graphs"], actual_named_graphs=list(verification["actual_graph_counts"]), verification=verification, graphdb_version=readiness["version"], image_digest=load_graphdb_policy()["graphdb"]["image_digest_amd64"], base_url=client.base_url, repository_id=manifest["repository_id"], create_status=args.create_status, import_status=args.import_status, license_state=readiness["license_state"], license_edition=readiness["edition"])
        path = report_dir / "graphdb-import-attestation.json"
        write_import_attestation(path, attestation)
        json_print({"output": path.as_posix(), "status": attestation["status"], "repository_id": manifest["repository_id"]})
        return 0
    if command == "destroy-generated":
        publication_hash = args.publication_id.rsplit(":", 1)[-1]
        expected = repository_id_for_publication(publication_hash)
        if args.repository_id != expected:
            raise ValueError("repository id is not bound to publication id")
        status = _client(args).delete_generated_repository(args.repository_id)
        json_print({"deleted": True, "repository_id": args.repository_id, "status": status})
        return 0
    raise ValueError("unknown graphdb command")
