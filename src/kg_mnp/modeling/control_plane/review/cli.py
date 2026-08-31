"""Prompt 4 `kg-mnp review` explicit human-authority CLI."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml

from ..competency import structural_coverage
from ..confirmation import build_confirmed_package, verify_confirmed_package
from ..errors import (
    ConfirmedPackageError,
    ModelingConflictError,
    ModelingControlError,
    ReviewIncompleteError,
    ReviewPolicyError,
    StaleModelingArtifactError,
)
from ..prevalidation import verify_prevalidation
from ..run import advance_modeling_run
from ..service import ModelingWorkspaceService
from .actions import build_review_action, rebuild_candidate_revision
from .finalization import finalize_review
from .log import build_decision_log
from .policy import build_review_policy, verify_review_policy
from .queue import build_review_queue, verify_review_queue
from .replay import replay_review, review_status

SUCCESS = 0
REVIEW_INCOMPLETE = 24
REVIEW_POLICY_VIOLATION = 25
CONFIRMED_PACKAGE_INVALID = 26
STALE_MODELING_ARTIFACT = 27
MODELING_CONFLICT_UNRESOLVED = 28


def _emit(value: Any, *, error: bool = False) -> None:
    print(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if error else sys.stdout,
    )


def _read(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    return yaml.safe_load(raw) if path.suffix.casefold() in {".yaml", ".yml"} else json.loads(raw)


def _flags(argv: list[str] | None) -> tuple[list[str], bool]:
    values = list(argv or [])
    debug = "--debug" in values
    return [value for value in values if value not in {"--json", "--debug"}], debug


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp review")
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("queue")
    queue_commands = queue.add_subparsers(dest="operation", required=True)
    init = queue_commands.add_parser("init")
    init.add_argument("workspace", type=Path)
    init.add_argument("proposal_id")
    init.add_argument("--policy", required=True, type=Path)
    listing = queue_commands.add_parser("list")
    listing.add_argument("workspace", type=Path)
    listing.add_argument("review_id")

    candidate = commands.add_parser("candidate")
    candidate_commands = candidate.add_subparsers(dest="operation", required=True)
    inspect = candidate_commands.add_parser("inspect")
    inspect.add_argument("workspace", type=Path)
    inspect.add_argument("candidate_id")

    decide = commands.add_parser("decide")
    decide.add_argument("workspace", type=Path)
    decide.add_argument("review_id")
    decide.add_argument("candidate_id")
    decide.add_argument("--decision", required=True)
    decide.add_argument("--reviewer-id", required=True)
    decide.add_argument("--reviewer-role", required=True)
    decide.add_argument("--rationale", required=True)
    decide.add_argument("--modified-candidate", type=Path)
    decide.add_argument("--baseline-element-ref")
    decide.add_argument("--decided-at")

    apply = commands.add_parser("apply")
    apply.add_argument("workspace", type=Path)
    apply.add_argument("review_id")
    apply.add_argument("--decisions", required=True, type=Path)

    for name in ("status", "replay", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        command.add_argument("review_id")

    package = commands.add_parser("package")
    package_commands = package.add_subparsers(dest="operation", required=True)
    for operation in ("inspect", "validate"):
        command = package_commands.add_parser(operation)
        command.add_argument("workspace", type=Path)
        command.add_argument("package_id")
    return parser


def _review_authorities(
    service: ModelingWorkspaceService,
    review_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    queue = service.find_artifact(review_id)
    proposal = service.find_artifact(queue["proposal_id"])
    prevalidation = service.find_artifact(queue["formal_prevalidation_report_id"])
    policy = service.find_artifact(queue["review_policy_id"])
    actions = service.load_actions(review_id)
    verify_review_queue(
        queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
    )
    return queue, proposal, prevalidation, policy, actions


def _load_policy(path: Path, service: ModelingWorkspaceService) -> dict[str, Any]:
    value = _read(path)
    if not isinstance(value, dict):
        raise ReviewPolicyError("review policy file must contain an object")
    if value.get("manifest_kind") == "KG_MNP_ONTOLOGY_REVIEW_POLICY":
        verify_review_policy(value, project_lock_id=service.project_lock["lock_id"])
        return value
    return build_review_policy(
        project_lock_id=service.project_lock["lock_id"],
        profile=value.get("policy_profile", "PRODUCTION_MULTI_ROLE"),
    )


def _queue_init(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    proposal = service.find_artifact(args.proposal_id)
    prevalidation = service.latest_artifact("KG_MNP_FORMAL_PREVALIDATION_REPORT")
    verify_prevalidation(prevalidation, proposal=proposal)
    policy = _load_policy(args.policy, service)
    bundle = service.find_artifact(proposal["modeling_input_bundle_id"])
    if bundle["review_policy_id"] != policy["policy_id"]:
        raise ReviewPolicyError("review policy differs from the Modeling Input Bundle")
    question_set = service.find_artifact(proposal["competency_question_set_id"])
    coverage = structural_coverage(question_set, proposal)
    queue = build_review_queue(proposal, prevalidation, policy)
    service.write_review(
        queue["review_queue_id"],
        {
            "review-policy.json": policy,
            "review-queue.json": queue,
            "competency-question-coverage-report.json": coverage,
        },
    )
    run = service.latest_artifact("KG_MNP_ONTOLOGY_MODELING_RUN")
    service.update_modeling_run(
        advance_modeling_run(
            run,
            status="UNDER_REVIEW",
            proposal_id=proposal["proposal_id"],
            review_queue_id=queue["review_queue_id"],
        )
    )
    return queue


def _build_one_action(
    *,
    service: ModelingWorkspaceService,
    review_id: str,
    candidate_id: str,
    decision: str,
    reviewer_id: str,
    reviewer_role: str,
    rationale: str,
    modified_candidate_path: Path | None = None,
    baseline_element_ref: str | None = None,
    decided_at: str | None = None,
) -> dict[str, Any]:
    queue, proposal, _prevalidation, policy, actions = _review_authorities(service, review_id)
    modified = None
    if modified_candidate_path is not None:
        replacement = _read(modified_candidate_path)
        if not isinstance(replacement, dict):
            raise ReviewPolicyError("modified candidate file must contain an object")
        original, _ = service.find_candidate(candidate_id)
        bundle = service.find_artifact(proposal["modeling_input_bundle_id"])
        datasets = [service.find_artifact(value) for value in bundle["kg_ir_dataset_ids"]]
        evidence_ids = {
            record["evidence_id"]
            for dataset in datasets
            for record in dataset["evidence_records"]
        }
        baseline = service.find_artifact(proposal["baseline_snapshot_id"])
        all_candidate_ids = {
            item["candidate_id"]
            for item in [
                *proposal["tbox_candidates"],
                *proposal["mapping_candidates"],
                *proposal["abox_candidates"],
                *proposal["shacl_candidates"],
            ]
        }
        modified = rebuild_candidate_revision(
            original,
            replacement,
            scope=service.find_artifact(proposal["scope_id"]),
            evidence_ids=evidence_ids,
            baseline_element_ids={item["element_id"] for item in baseline["elements"]},
            candidate_ids=all_candidate_ids,
        )
    action = build_review_action(
        queue=queue,
        proposal=proposal,
        policy=policy,
        existing_actions=actions,
        decision=decision,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        rationale=rationale,
        candidate_id=candidate_id,
        modified_candidate=modified,
        baseline_element_ref=baseline_element_ref,
        decided_at=decided_at,
    )
    service.append_action(review_id, action)
    return action


def _apply(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    value = _read(args.decisions)
    rows = value.get("decisions", []) if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ReviewPolicyError("decision batch must be an array")
    action_ids: list[str] = []
    for row in rows:
        action = _build_one_action(
            service=service,
            review_id=args.review_id,
            candidate_id=row["candidate_id"],
            decision=row["decision"],
            reviewer_id=row["reviewer_id"],
            reviewer_role=row["reviewer_role"],
            rationale=row["rationale"],
            modified_candidate_path=Path(row["modified_candidate"])
            if row.get("modified_candidate")
            else None,
            baseline_element_ref=row.get("baseline_element_ref"),
            decided_at=row.get("decided_at"),
        )
        action_ids.append(action["action_id"])
    return {"review_queue_id": args.review_id, "action_ids": action_ids}


def _finalize(args: argparse.Namespace) -> Any:
    service = ModelingWorkspaceService(args.workspace)
    queue, proposal, prevalidation, policy, actions = _review_authorities(
        service, args.review_id
    )
    directory = service.review_directory(args.review_id)
    coverage = json.loads(
        (directory / "competency-question-coverage-report.json").read_text(encoding="utf-8")
    )
    scope = service.find_artifact(proposal["scope_id"])
    approval = service.latest_artifact("KG_MNP_ONTOLOGY_SCOPE_APPROVAL")
    finalization = finalize_review(
        queue=queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
        actions=actions,
        coverage_report=coverage,
        scope=scope,
        scope_approval=approval,
        current_project_lock_id=service.project_lock["lock_id"],
    )
    bundle = service.find_artifact(proposal["modeling_input_bundle_id"])
    package = build_confirmed_package(
        project_lock=service.project_lock,
        input_bundle=bundle,
        scope=scope,
        scope_approval=approval,
        question_set=service.find_artifact(proposal["competency_question_set_id"]),
        coverage_report=coverage,
        baseline=service.find_artifact(proposal["baseline_snapshot_id"]),
        terminology=service.find_artifact(proposal["terminology_catalog_id"]),
        alignments=service.find_artifact(proposal["term_alignment_set_id"]),
        field_mappings=service.find_artifact(proposal["field_mapping_candidate_set_id"]),
        proposal=proposal,
        prevalidation=prevalidation,
        review_policy=policy,
        finalization=finalization,
        actions=actions,
        review_queue=queue,
    )
    service.write_review_final(
        args.review_id,
        decision_log=finalization.decision_log,
        coverage_report=coverage,
    )
    service.write_confirmed(package["package_id"], package)
    run = service.latest_artifact("KG_MNP_ONTOLOGY_MODELING_RUN")
    service.update_modeling_run(
        advance_modeling_run(
            run,
            status="READY_FOR_COMPILATION",
            package_id=package["package_id"],
        )
    )
    return package


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "queue" and args.operation == "init":
        return _queue_init(args)
    if args.command == "queue":
        service = ModelingWorkspaceService(args.workspace)
        queue = service.find_artifact(args.review_id)
        actions = service.load_actions(args.review_id)
        return {"queue": queue, "status": review_status(queue, actions)}
    if args.command == "candidate":
        candidate, proposal = ModelingWorkspaceService(args.workspace).find_candidate(
            args.candidate_id
        )
        return {"proposal_id": proposal["proposal_id"], "candidate": candidate}
    if args.command == "decide":
        return _build_one_action(
            service=ModelingWorkspaceService(args.workspace),
            review_id=args.review_id,
            candidate_id=args.candidate_id,
            decision=args.decision,
            reviewer_id=args.reviewer_id,
            reviewer_role=args.reviewer_role,
            rationale=args.rationale,
            modified_candidate_path=args.modified_candidate,
            baseline_element_ref=args.baseline_element_ref,
            decided_at=args.decided_at,
        )
    if args.command == "apply":
        return _apply(args)
    if args.command in {"status", "replay"}:
        service = ModelingWorkspaceService(args.workspace)
        queue, proposal, prevalidation, policy, actions = _review_authorities(
            service, args.review_id
        )
        if args.command == "status":
            return review_status(queue, actions)
        result = replay_review(queue, actions)
        result["decision_log"] = build_decision_log(
            queue=queue,
            proposal=proposal,
            prevalidation=prevalidation,
            policy=policy,
            actions=actions,
        )
        return result
    if args.command == "finalize":
        return _finalize(args)
    if args.command == "package":
        package = ModelingWorkspaceService(args.workspace).find_artifact(args.package_id)
        if args.operation == "validate":
            verify_confirmed_package(package)
            return {"package_id": package["package_id"], "valid": True}
        return package
    raise ReviewIncompleteError("unknown review command")


def _code(exc: BaseException) -> int:
    if isinstance(exc, ModelingConflictError):
        return MODELING_CONFLICT_UNRESOLVED
    if isinstance(exc, StaleModelingArtifactError):
        return STALE_MODELING_ARTIFACT
    if isinstance(exc, ConfirmedPackageError):
        return CONFIRMED_PACKAGE_INVALID
    if isinstance(exc, ReviewPolicyError):
        return REVIEW_POLICY_VIOLATION
    return REVIEW_INCOMPLETE


def main(argv: list[str] | None = None) -> int:
    values, debug = _flags(argv)
    args = _parser().parse_args(values)
    try:
        _emit(_dispatch(args))
        return SUCCESS
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        ModelingControlError,
    ) as exc:
        if debug:
            traceback.print_exc()
        else:
            _emit({"error": type(exc).__name__, "message": str(exc)}, error=True)
        return _code(exc)
