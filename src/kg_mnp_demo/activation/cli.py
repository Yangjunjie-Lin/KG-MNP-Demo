"""Production-only command line boundary for Phase 06 activation governance."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .authority_binding import load_production_phase06_authority
from .errors import ActivationError, ActivationErrorCode
from .runtime import (
    ActivationRuntimeConfig,
    create_production_activation_controller,
    create_production_active_resolver,
)


def _runtime_arguments(parser: argparse.ArgumentParser) -> None:
    """Declare physical trust roots that are frozen at process startup."""

    parser.add_argument("--publication-package", required=True, type=Path)
    parser.add_argument("--publication-attestation", required=True, type=Path)
    parser.add_argument("--phase01-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase02-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase03-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase04-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase05-artifact-dir", required=True, type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument(
        "--state-dir", type=Path, default=Path("runtime_outputs/activation")
    )
    parser.add_argument("--publication-scenario", default="full-confirmation")
    parser.add_argument("--graphdb-url", default="http://127.0.0.1:7200")


def _registry_cas_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-registry-revision", required=True, type=int)
    parser.add_argument("--expected-head-event-hash", required=True)


def _registry_anchor_arguments(
    parser: argparse.ArgumentParser, *, required: bool = False
) -> None:
    parser.add_argument("--expected-registry-hash", required=required)
    parser.add_argument("--expected-head-event-hash", required=required)


def _leaf(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],  # type: ignore[name-defined]
    name: str,
    *,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = commands.add_parser(name, help=help_text)
    _runtime_arguments(parser)
    return parser


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp activation",
        description="Human-governed selection of verified immutable publications",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    upstream = commands.add_parser("upstream")
    upstream_commands = upstream.add_subparsers(dest="upstream_command", required=True)
    _leaf(
        upstream_commands,
        "verify",
        help_text="verify the physical production authority",
    )

    registry = commands.add_parser("registry")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    _leaf(
        registry_commands,
        "init",
        help_text="bootstrap the current reference at generation zero",
    )

    status = _leaf(
        commands,
        "status",
        help_text="inspect a fully verified registry snapshot",
    )
    _registry_anchor_arguments(status)

    proposal = commands.add_parser("proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_create = _leaf(
        proposal_commands,
        "create",
        help_text="create a new-publication activation proposal",
    )
    proposal_create.add_argument("--target-publication-id", required=True)
    proposal_create.add_argument("--rationale", required=True)
    proposal_create.add_argument("--created-by-label", required=True)
    proposal_create.add_argument(
        "--explicit-human-intent", action="store_true", required=True
    )
    _registry_cas_arguments(proposal_create)

    proposal_submit = _leaf(
        proposal_commands,
        "submit",
        help_text="submit a draft activation proposal",
    )
    proposal_submit.add_argument("--proposal-id", required=True)
    _registry_cas_arguments(proposal_submit)

    review = commands.add_parser("review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_record = _leaf(
        review_commands,
        "record",
        help_text="record an explicit human deployment decision",
    )
    review_record.add_argument("--proposal-id", required=True)
    review_record.add_argument(
        "--decision",
        required=True,
        choices=("APPROVE_FOR_ACTIVATION", "REJECT", "DEFER"),
    )
    review_record.add_argument("--reviewed-by-label", required=True)
    review_record.add_argument("--review-note", required=True)
    review_record.add_argument(
        "--explicit-human-action", action="store_true", required=True
    )
    _registry_cas_arguments(review_record)

    execute = _leaf(
        commands,
        "execute",
        help_text="reverify a reviewed target and atomically select it",
    )
    execute.add_argument("--proposal-id", required=True)
    execute.add_argument("--review-decision-id", required=True)
    execute.add_argument("--expected-generation", required=True, type=int)
    execute.add_argument("--expected-pointer-hash", required=True)

    rollback = commands.add_parser("rollback")
    rollback_commands = rollback.add_subparsers(dest="rollback_command", required=True)
    rollback_propose = _leaf(
        rollback_commands,
        "propose",
        help_text="propose selecting a prior verified publication",
    )
    rollback_propose.add_argument("--target-publication-id", required=True)
    rollback_propose.add_argument("--rationale", required=True)
    rollback_propose.add_argument("--created-by-label", required=True)
    rollback_propose.add_argument(
        "--explicit-human-intent", action="store_true", required=True
    )
    _registry_cas_arguments(rollback_propose)

    resolve_current = _leaf(
        commands,
        "resolve-current",
        help_text="resolve and reverify the selected immutable publication",
    )
    _registry_anchor_arguments(resolve_current, required=True)

    verify = _leaf(
        commands,
        "verify",
        help_text="validate the authority, registry, event chain, and pointer",
    )
    _registry_anchor_arguments(verify, required=True)

    # ``artifact verify`` is intentionally not registered until an independent
    # Phase 06 artifact verifier exists.
    return parser


def _runtime_config(arguments: argparse.Namespace) -> ActivationRuntimeConfig:
    return ActivationRuntimeConfig(
        publication_package_directory=arguments.publication_package,
        publication_attestation_path=arguments.publication_attestation,
        phase01_artifact_directory=arguments.phase01_artifact_dir,
        phase02_artifact_directory=arguments.phase02_artifact_dir,
        phase03_artifact_directory=arguments.phase03_artifact_dir,
        phase04_artifact_directory=arguments.phase04_artifact_dir,
        phase05_artifact_directory=arguments.phase05_artifact_dir,
        expected_commit_sha=arguments.expected_commit_sha,
        state_directory=arguments.state_dir,
        publication_scenario=arguments.publication_scenario,
        graphdb_url=arguments.graphdb_url,
    )


def _json(value: Any) -> None:
    print(canonical_json_bytes(value).decode("utf-8"))


def _anchors(arguments: argparse.Namespace) -> dict[str, str | None]:
    return {
        "expected_registry_hash": arguments.expected_registry_hash,
        "expected_head_event_hash": arguments.expected_head_event_hash,
    }


def dispatch_activation(arguments: argparse.Namespace) -> int:
    """Dispatch one parsed command through production-only constructors."""

    config = _runtime_config(arguments)
    if arguments.command == "upstream":
        authority = load_production_phase06_authority(**config.authority_arguments())
        _json(
            {
                "authority_binding": authority.binding,
                "authority_binding_hash": authority.authority_binding_hash,
                "production_activation_candidates": (
                    authority.production_activation_candidate_count
                ),
                "status": "UPSTREAM_PHASE05_VERIFIED_FOR_ACTIVATION",
            }
        )
        return 0

    if arguments.command == "resolve-current":
        resolver = create_production_active_resolver(config)
        _json(resolver.resolve_current(**_anchors(arguments)))
        return 0

    controller = create_production_activation_controller(config)
    if arguments.command == "registry":
        registry, pointer = controller.initialize()
        _json(
            {
                "current_pointer": pointer,
                "registry": registry,
                "status": "ACTIVATION_REGISTRY_INITIALIZED",
            }
        )
        return 0
    if arguments.command in {"status", "verify"}:
        _json(controller.status(**_anchors(arguments)))
        return 0
    if arguments.command == "proposal":
        if arguments.proposal_command == "create":
            result = controller.create_proposal(
                target_publication_id=arguments.target_publication_id,
                activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
                rationale=arguments.rationale,
                created_by_label=arguments.created_by_label,
                explicit_human_intent=arguments.explicit_human_intent,
                expected_registry_revision=arguments.expected_registry_revision,
                expected_head_event_hash=arguments.expected_head_event_hash,
            )
        else:
            result = controller.submit_proposal(
                arguments.proposal_id,
                expected_registry_revision=arguments.expected_registry_revision,
                expected_head_event_hash=arguments.expected_head_event_hash,
            )
        _json(result)
        return 0
    if arguments.command == "review":
        _json(
            controller.record_review(
                arguments.proposal_id,
                decision=arguments.decision,
                reviewed_by_label=arguments.reviewed_by_label,
                review_note=arguments.review_note,
                explicit_human_action=arguments.explicit_human_action,
                expected_registry_revision=arguments.expected_registry_revision,
                expected_head_event_hash=arguments.expected_head_event_hash,
            )
        )
        return 0
    if arguments.command == "execute":
        _json(
            controller.execute(
                arguments.proposal_id,
                arguments.review_decision_id,
                expected_generation=arguments.expected_generation,
                expected_pointer_hash=arguments.expected_pointer_hash,
            )
        )
        return 0
    if arguments.command == "rollback":
        _json(
            controller.propose_rollback(
                target_publication_id=arguments.target_publication_id,
                rationale=arguments.rationale,
                created_by_label=arguments.created_by_label,
                explicit_human_intent=arguments.explicit_human_intent,
                expected_registry_revision=arguments.expected_registry_revision,
                expected_head_event_hash=arguments.expected_head_event_hash,
            )
        )
        return 0
    raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return dispatch_activation(arguments)
    except ActivationError as exc:
        _json(exc.to_dict())
    except (ApplicationError, KeyError, OSError, TypeError, ValueError) as exc:
        _json(
            ActivationError(
                ActivationErrorCode.PHASE06_NOT_VERIFIED, str(exc)
            ).to_dict()
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
