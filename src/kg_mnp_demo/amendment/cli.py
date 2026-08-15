"""Offline Phase 05 command line boundary."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .artifact_verifier import verify_application_phase05_artifact
from .authority_binding import load_production_phase05_authority
from .contracts import strict_json_file, validate_amendment_contract
from .errors import AmendmentError
from .intake import validate_intake
from .republication import prepare_production_reentry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp amendment",
        description="Controlled ABox amendment re-entry and deterministic republication",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    upstream = commands.add_parser("upstream")
    upstream_commands = upstream.add_subparsers(dest="upstream_command", required=True)
    verify = upstream_commands.add_parser("verify")
    _authority_args(verify)

    intake = commands.add_parser("intake")
    intake_commands = intake.add_subparsers(dest="intake_command", required=True)
    validate = intake_commands.add_parser("validate")
    validate.add_argument("--manifest", required=True, type=Path)
    validate.add_argument("--base-input", type=Path)
    validate.add_argument("--revised-input", type=Path)
    inspect = intake_commands.add_parser("inspect")
    inspect.add_argument("--manifest", required=True, type=Path)

    reentry = commands.add_parser("reentry")
    reentry_commands = reentry.add_subparsers(dest="reentry_command", required=True)
    reentry_verify = reentry_commands.add_parser("verify")
    _authority_args(reentry_verify)
    reentry_verify.add_argument("--amendment-request-id", required=True)
    reentry_verify.add_argument("--manifest", required=True, type=Path)
    reentry_verify.add_argument("--base-input", required=True, type=Path)
    reentry_verify.add_argument("--revised-input", required=True, type=Path)
    reentry_verify.add_argument("--output", type=Path)

    republication = commands.add_parser("republication")
    republication_commands = republication.add_subparsers(
        dest="republication_command", required=True
    )
    republication_verify = republication_commands.add_parser("verify")
    republication_verify.add_argument("--result", required=True, type=Path)

    artifact = commands.add_parser("artifact")
    artifact_commands = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_verify = artifact_commands.add_parser("verify")
    artifact_verify.add_argument("directory", type=Path)
    _authority_args(artifact_verify)
    return parser


def _authority_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stage08-artifact", required=True, type=Path)
    parser.add_argument("--publication-attestation", type=Path)
    parser.add_argument("--phase01-artifact", required=True, type=Path)
    parser.add_argument("--phase02-artifact", required=True, type=Path)
    parser.add_argument("--phase03-artifact", required=True, type=Path)
    parser.add_argument("--phase04-artifact", required=True, type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument("--publication-scenario", default="full-confirmation")


def _read(path: Path) -> dict[str, Any]:
    value = strict_json_file(path)
    return value


def _json(value: Any) -> None:
    print(canonical_json_bytes(value).decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "upstream":
            authority = load_production_phase05_authority(
                stage08_artifact=args.stage08_artifact,
                phase01_artifact=args.phase01_artifact,
                phase02_artifact=args.phase02_artifact,
                phase03_artifact=args.phase03_artifact,
                phase04_artifact=args.phase04_artifact,
                expected_commit_sha=args.expected_commit_sha,
                publication_scenario=args.publication_scenario,
                publication_attestation=args.publication_attestation,
            )
            _json(
                {
                    "status": "UPSTREAM_PHASE04_VERIFIED",
                    "commit_sha": authority.commit_sha,
                    "production_pending_amendments": authority.production_pending_amendments,
                    "binding": authority.binding,
                }
            )
            return 0
        if args.command == "intake":
            manifest = _read(args.manifest)
            if args.intake_command == "inspect":
                _json({"inspection_only": True, "validated": False, **manifest})
                return 0
            base = _read(args.base_input) if args.base_input else None
            revised = _read(args.revised_input) if args.revised_input else None
            _json(
                {
                    "status": "VALIDATED",
                    "intake_id": manifest["intake_id"],
                    "actual_changed_json_pointers": validate_intake(
                        manifest,
                        base_cleaned_data=base,
                        revised_cleaned_data=revised,
                    )["actual_changed_json_pointers"],
                }
            )
            return 0
        if args.command == "reentry":
            authority = load_production_phase05_authority(
                stage08_artifact=args.stage08_artifact,
                phase01_artifact=args.phase01_artifact,
                phase02_artifact=args.phase02_artifact,
                phase03_artifact=args.phase03_artifact,
                phase04_artifact=args.phase04_artifact,
                expected_commit_sha=args.expected_commit_sha,
                publication_scenario=args.publication_scenario,
                publication_attestation=args.publication_attestation,
            )
            manifest = _read(args.manifest)
            base = _read(args.base_input)
            revised = _read(args.revised_input)
            prepared = prepare_production_reentry(
                authority=authority,
                amendment_request_id=args.amendment_request_id,
                intake_manifest=manifest,
                base_cleaned_data=base,
                revised_cleaned_data=revised,
                base_publication_id=authority.publication_id,
                base_publication_semantic_hash=authority.publication_semantic_hash,
            )
            if args.output:
                args.output.write_bytes(
                    canonical_json_bytes(prepared.to_dict()) + b"\n"
                )
            _json(prepared.to_dict())
            return 0
        if args.command == "republication":
            result = _read(args.result)
            validate_amendment_contract("republication-result", result)
            _json({"status": result["status"], "valid": True})
            return 0
        if args.command == "artifact":
            _json(
                verify_application_phase05_artifact(
                    args.directory,
                    stage08_artifact=args.stage08_artifact,
                    phase01_artifact=args.phase01_artifact,
                    phase02_artifact=args.phase02_artifact,
                    phase03_artifact=args.phase03_artifact,
                    phase04_artifact=args.phase04_artifact,
                    expected_commit_sha=args.expected_commit_sha,
                    publication_scenario=args.publication_scenario,
                    publication_attestation=args.publication_attestation,
                )
            )
            return 0
    except (AmendmentError, ValueError, OSError, KeyError) as exc:
        _json(
            {
                "code": getattr(exc, "code", "PHASE05_NOT_VERIFIED"),
                "detail": str(exc),
                "status": "FAILED",
            }
        )
        return 2
    return 2
