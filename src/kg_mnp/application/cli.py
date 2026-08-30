"""Independent CLI for the read-only Application Phase 01."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .errors import ApplicationError, ErrorCode
from .http import create_app
from .policy import LOCAL_BIND_HOST
from .publication_binding import PUBLICATION_SCENARIOS, PublicationBinding
from .query_registry import QueryRegistry
from .readonly_client import ReadOnlyGraphDBClient
from .service import ApplicationService


class _ApplicationArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, message)


def _json_print(payload: Any, *, error: bool = False) -> None:
    options = {"ensure_ascii": False, "indent": 2, "sort_keys": True}
    text = json.dumps(payload, **options)
    stream = sys.stderr if error else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    print(text, file=stream)


def _binding_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--publication-package", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument(
        "--publication-scenario",
        required=True,
        choices=sorted(PUBLICATION_SCENARIOS),
    )


def _runtime_arguments(parser: argparse.ArgumentParser) -> None:
    _binding_arguments(parser)
    parser.add_argument("--graphdb-url", default="http://127.0.0.1:7200")


def build_parser() -> argparse.ArgumentParser:
    parser = _ApplicationArgumentParser(
        prog="kg-mnp application",
        description="Read-only semantic query and traceability layer",
    )
    commands = parser.add_subparsers(dest="application_command", required=True)

    query = commands.add_parser("query", help="inspect or run registered queries")
    query_commands = query.add_subparsers(
        dest="application_query_command", required=True
    )
    query_commands.add_parser("list")
    describe = query_commands.add_parser("describe")
    describe.add_argument("query_id")
    run = query_commands.add_parser("run")
    run.add_argument("query_id")
    _runtime_arguments(run)
    for name in (
        "iri",
        "term",
        "subject",
        "predicate",
        "resource-id",
        "source-ref",
        "evidence-ref",
    ):
        run.add_argument(f"--{name}")
    object_group = run.add_mutually_exclusive_group()
    object_group.add_argument("--object-iri")
    object_group.add_argument("--object-literal")
    run.add_argument("--datatype-iri")
    run.add_argument("--language")
    run.add_argument("--limit", type=int)
    run.add_argument("--offset", type=int)

    publication = commands.add_parser("publication", help="verify publication binding")
    publication_commands = publication.add_subparsers(
        dest="application_publication_command", required=True
    )
    verify = publication_commands.add_parser("verify")
    _binding_arguments(verify)
    verify.add_argument("--repository-id")

    runtime = commands.add_parser("runtime", help="check runtime readiness")
    runtime_commands = runtime.add_subparsers(
        dest="application_runtime_command", required=True
    )
    check = runtime_commands.add_parser("check")
    _runtime_arguments(check)

    serve = commands.add_parser("serve", help="serve the local read-only API")
    _runtime_arguments(serve)
    serve.add_argument("--host", default=LOCAL_BIND_HOST)
    serve.add_argument("--port", type=int, default=8081)
    return parser


def _binding(args: argparse.Namespace, *, expected_repository_id: str | None = None) -> PublicationBinding:
    return PublicationBinding.verify(
        args.publication_package,
        args.attestation,
        expected_repository_id=expected_repository_id,
        publication_scenario=args.publication_scenario,
    )


def _service(args: argparse.Namespace) -> ApplicationService:
    return ApplicationService(
        binding=_binding(args),
        registry=QueryRegistry.load(),
        client=ReadOnlyGraphDBClient(args.graphdb_url),
    )


def _run_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in (
        "iri",
        "term",
        "subject",
        "predicate",
        "resource_id",
        "source_ref",
        "evidence_ref",
        "limit",
        "offset",
    ):
        value = getattr(args, name, None)
        if value is not None:
            values[name] = value
    if args.object_iri is not None:
        values["object"] = {"term_type": "IRI", "value": args.object_iri}
    if args.object_literal is not None:
        values["object"] = {
            "term_type": "LITERAL",
            "value": args.object_literal,
            "datatype_iri": args.datatype_iri,
            "language": args.language,
        }
    elif args.datatype_iri is not None or args.language is not None:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return values


def dispatch_application(args: argparse.Namespace) -> int:
    if args.application_command == "query" and args.application_query_command == "list":
        _json_print(QueryRegistry.load().manifest())
        return 0
    if (
        args.application_command == "query"
        and args.application_query_command == "describe"
    ):
        item = QueryRegistry.load().get(args.query_id)
        _json_print(
            {
                "query_id": item.query_id,
                "version": item.version,
                "category": item.category.value,
                "description": item.description,
                "semantic_purpose": item.semantic_purpose,
                "input_parameters": [vars(spec) for spec in item.parameters],
                "output_contract": item.output_contract,
                "allowed_named_graphs": [
                    role.value for role in item.allowed_named_graphs
                ],
                "maximum_result_count": item.maximum_result_count,
                "timeout_seconds": item.timeout_seconds,
            }
        )
        return 0
    if args.application_command == "query" and args.application_query_command == "run":
        service = _service(args)
        service.runtime_check()
        _json_print(service.run(args.query_id, _run_parameters(args)))
        return 0
    if (
        args.application_command == "publication"
        and args.application_publication_command == "verify"
    ):
        binding = _binding(args, expected_repository_id=args.repository_id)
        _json_print(
            {
                "status": "PUBLICATION_VERIFIED",
                "publication_authority_reconstruction": (
                    binding.publication_authority_reconstruction
                ),
                "publication_scenario": args.publication_scenario,
                "publication_id": binding.publication_id,
                "publication_semantic_hash": binding.publication_semantic_hash,
                "repository_id": binding.repository_id,
            }
        )
        return 0
    if (
        args.application_command == "runtime"
        and args.application_runtime_command == "check"
    ):
        _json_print(_service(args).runtime_check())
        return 0
    if args.application_command == "serve":
        if args.host != LOCAL_BIND_HOST or not 1 <= args.port <= 65535:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        service = _service(args)
        service.runtime_check()
        import uvicorn

        uvicorn.run(
            create_app(service),
            host=LOCAL_BIND_HOST,
            port=args.port,
            log_config=None,
            access_log=False,
        )
        return 0
    raise ApplicationError(ErrorCode.INVALID_PARAMETER)


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return dispatch_application(args)
    except ApplicationError as exc:
        _json_print(exc.to_dict(), error=True)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        error = ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED, str(exc))
        _json_print(error.to_dict(), error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
