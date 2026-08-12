"""CLI for Phase04 governance workspaces; no semantic mutation commands exist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.diagnostics.engine import AuthoritySnapshot

from .authority_binding import load_verified_phase03_authority
from .contracts import strict_json_file
from .errors import GovernanceError
from .runtime import create_governance_app
from .workspace import GovernanceWorkspaceStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp governance",
        description="Human-governed future semantic amendment requests",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def authority(command: argparse.ArgumentParser) -> None:
        command.add_argument("--diagnostic-package", required=True, type=Path)
        command.add_argument("--phase03-attestation", required=True, type=Path)
        command.add_argument("--authority-snapshot", required=True, type=Path)
        command.add_argument("--workspace", required=True, type=Path)

    initialize = commands.add_parser("initialize")
    authority(initialize)
    verify = commands.add_parser("verify")
    authority(verify)
    inspect = commands.add_parser("inspect")
    authority(inspect)

    proposal = commands.add_parser("proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    create = proposal_commands.add_parser("create")
    authority(create)
    create.add_argument("--request", required=True, type=Path)
    submit = proposal_commands.add_parser("submit")
    authority(submit)
    submit.add_argument("--proposal-id", required=True)
    submit.add_argument("--expected-workspace-revision", required=True, type=int)
    submit.add_argument("--expected-head-hash")
    review = proposal_commands.add_parser("review")
    authority(review)
    review.add_argument("--proposal-id", required=True)
    review.add_argument("--request", required=True, type=Path)

    serve = commands.add_parser("serve")
    authority(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=0)
    return parser


def _context(arguments):
    snapshot = AuthoritySnapshot.from_dict(
        strict_json_file(arguments.authority_snapshot)
    )

    def current():
        return load_verified_phase03_authority(
            diagnostic_package=arguments.diagnostic_package,
            phase03_attestation=arguments.phase03_attestation,
            authority_snapshot=snapshot,
        )

    return current, GovernanceWorkspaceStore(arguments.workspace, current)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        current, store = _context(arguments)
        if arguments.command == "initialize":
            workspace = store.initialize(current())
            result = {
                "workspace_id": workspace.value["workspace_id"],
                "workspace_hash": workspace.value["workspace_hash"],
                "status": "GOVERNANCE_WORKSPACE_ACTIVE",
            }
        elif arguments.command in {"verify", "inspect"}:
            result = store.load().reconstruct()
        elif arguments.command == "proposal" and arguments.proposal_command == "create":
            request = strict_json_file(arguments.request)
            result = store.mutate(
                lambda workspace: workspace.create_proposal(**request)
            )
        elif arguments.command == "proposal" and arguments.proposal_command == "submit":
            result = store.mutate(
                lambda workspace: workspace.submit_proposal(
                    arguments.proposal_id,
                    expected_workspace_revision=arguments.expected_workspace_revision,
                    expected_head_hash=arguments.expected_head_hash,
                )
            )
        elif arguments.command == "proposal" and arguments.proposal_command == "review":
            request = strict_json_file(arguments.request)
            result = store.mutate(
                lambda workspace: workspace.review_proposal(
                    arguments.proposal_id, **request
                )
            )
        else:
            if arguments.host != "127.0.0.1" or not 0 <= arguments.port <= 65535:
                raise ValueError("governance runtime must bind 127.0.0.1")
            import uvicorn

            uvicorn.run(
                create_governance_app(store),
                host="127.0.0.1",
                port=arguments.port,
                access_log=False,
            )
            return 0
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (GovernanceError, ValueError, OSError, KeyError, TypeError) as exc:
        code = (
            exc.code.value
            if isinstance(exc, GovernanceError)
            else "GOVERNANCE_NOT_READY"
        )
        print(
            json.dumps(
                {"code": code, "detail": str(exc), "status": "FAILED"}, sort_keys=True
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
