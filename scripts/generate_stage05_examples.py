#!/usr/bin/env python3
"""Generate Stage 05 review action fixtures and golden logs/packages."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.confirmation import build_confirmed_modeling_package
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.identifiers import candidate_id
from kg_mnp_demo.modeling.package_validation import load_term_type_index
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)
from kg_mnp_demo.modeling.review_policy import load_default_review_policy

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "review"
PROPOSALS = ROOT / "examples" / "modeling" / "expected-proposals"
INPUTS = ROOT / "examples" / "modeling" / "inputs"

REVIEWER = {
    "reviewer_id": "urn:kg-mnp:reviewer:professor-001",
    "display_name": "Reviewer One",
    "role": "Ontology Reviewer",
    "affiliation": "KG-MNP Review Board",
}
STARTED = "2026-08-06T00:00:00Z"
COMPLETED = "2026-08-06T02:00:00Z"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_bytes(canonical_json_bytes(payload) + b"\n")
    else:
        path.write_text(str(payload), encoding="utf-8")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _action(
    proposal: dict,
    *,
    target: dict,
    decision: str,
    rationale: str,
    decided_at: str,
    evidence_refs: list[str] | None = None,
    modified_candidate: dict | None = None,
) -> dict:
    payload = {
        "contract_version": "1.0",
        "proposal_id": proposal["proposal_id"],
        "proposal_semantic_hash": proposal["proposal_semantic_hash"],
        "reviewer_id": REVIEWER["reviewer_id"],
        "target": target,
        "decision": decision,
        "rationale": rationale,
        "decided_at": decided_at,
        "evidence_refs": evidence_refs or [],
    }
    if modified_candidate is not None:
        payload["modified_candidate"] = modified_candidate
    return payload


def _build_log(proposal: dict, actions: list[dict], session_label: str) -> dict:
    policy = load_default_review_policy()
    term_types = load_term_type_index()
    log = init_review_decision_log(
        proposal,
        reviewer_id=REVIEWER["reviewer_id"],
        display_name=REVIEWER["display_name"],
        role=REVIEWER["role"],
        started_at=STARTED,
        session_label=session_label,
        affiliation=REVIEWER["affiliation"],
        review_policy=policy,
    )
    for action in actions:
        log = record_review_action(
            proposal,
            log,
            action,
            review_policy=policy,
            term_types=term_types,
        )
    return finalize_review_decision_log(
        proposal,
        log,
        completed_at=COMPLETED,
        review_policy=policy,
    )


def _package(input_name: str, proposal: dict, log: dict, *, allow_blocked: bool = False) -> dict:
    dependencies = load_modeling_dependencies()
    cleaned = _load(INPUTS / f"{input_name}.json")
    return build_confirmed_modeling_package(
        cleaned,
        proposal,
        log,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        load_default_review_policy(),
        allow_blocked=allow_blocked,
        term_types=load_term_type_index(),
    )


def scenario_full_confirmation() -> None:
    proposal = _load(PROPOSALS / "partial-basic.proposal.json")
    actions = []
    for index, candidate in enumerate(
        [*proposal["candidate_entities"], *proposal["candidate_assertions"]],
        start=1,
    ):
        action = _action(
            proposal,
            target={"candidate_id": candidate["candidate_id"]},
            decision="CONFIRM",
            rationale=f"Source and mapping evidence support candidate confirmation #{index}.",
            decided_at=f"2026-08-06T00:{index:02d}:00Z",
            evidence_refs=[f"review-evidence-full-{index:03d}"],
        )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "full-confirmation" / f"action-{index:03d}.json",
            action,
        )
    log = _build_log(proposal, actions, "full-confirmation")
    package = _package("partial-basic", proposal, log)
    _write(EXAMPLES / "expected-logs" / "full-confirmation.log.json", log)
    _write(EXAMPLES / "expected-packages" / "full-confirmation.package.json", package)


def scenario_modified_confirmation() -> None:
    proposal = _load(PROPOSALS / "partial-basic.proposal.json")
    actions = []
    entities = proposal["candidate_entities"]
    assertions = proposal["candidate_assertions"]
    # Modify the subscriber entity IRI slightly via rationale-preserving content change
    # that keeps source fields and recomputes candidate_id.
    subscriber = next(
        item for item in entities if "Subscriber" in item["class_iri"]
    )
    modified = deepcopy(subscriber)
    modified["rationale"] = (
        "Human-reviewed Subscriber entity with clarified rationale after source audit."
    )
    modified["candidate_id"] = candidate_id(modified)
    index = 1
    for candidate in entities:
        if candidate["candidate_id"] == subscriber["candidate_id"]:
            action = _action(
                proposal,
                target={"candidate_id": candidate["candidate_id"]},
                decision="MODIFY_AND_CONFIRM",
                rationale="Adjust subscriber rationale after human audit of source evidence.",
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=["review-evidence-modified-001"],
                modified_candidate=modified,
            )
        else:
            action = _action(
                proposal,
                target={"candidate_id": candidate["candidate_id"]},
                decision="CONFIRM",
                rationale=f"Confirm entity candidate #{index}.",
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=[f"review-evidence-modified-{index:03d}"],
            )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "modified-confirmation" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    for candidate in assertions:
        action = _action(
            proposal,
            target={"candidate_id": candidate["candidate_id"]},
            decision="CONFIRM",
            rationale=f"Confirm assertion candidate #{index}.",
            decided_at=f"2026-08-06T00:{index:02d}:00Z",
            evidence_refs=[f"review-evidence-modified-{index:03d}"],
        )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "modified-confirmation" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    log = _build_log(proposal, actions, "modified-confirmation")
    package = _package("partial-basic", proposal, log)
    _write(EXAMPLES / "expected-logs" / "modified-confirmation.log.json", log)
    _write(EXAMPLES / "expected-packages" / "modified-confirmation.package.json", package)


def scenario_rejection() -> None:
    proposal = _load(PROPOSALS / "partial-basic.proposal.json")
    actions = []
    subscriber = next(
        item
        for item in proposal["candidate_entities"]
        if "Subscriber" in item["class_iri"]
    )
    index = 1
    for candidate in [*proposal["candidate_entities"], *proposal["candidate_assertions"]]:
        if candidate["candidate_id"] == subscriber["candidate_id"]:
            action = _action(
                proposal,
                target={"candidate_id": candidate["candidate_id"]},
                decision="REJECT",
                rationale="Subscriber candidate is out of scope for this dataset modeling run.",
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=["review-evidence-reject-001"],
            )
        else:
            action = _action(
                proposal,
                target={"candidate_id": candidate["candidate_id"]},
                decision="CONFIRM",
                rationale=f"Confirm in-scope candidate #{index}.",
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=[f"review-evidence-reject-{index:03d}"],
            )
        actions.append(action)
        _write(EXAMPLES / "actions" / "rejection" / f"action-{index:03d}.json", action)
        index += 1
    log = _build_log(proposal, actions, "rejection")
    package = _package("partial-basic", proposal, log)
    _write(EXAMPLES / "expected-logs" / "rejection.log.json", log)
    _write(EXAMPLES / "expected-packages" / "rejection.package.json", package)


def scenario_deferred_review() -> None:
    proposal = _load(PROPOSALS / "conflicting-values.proposal.json")
    actions = []
    index = 1
    for candidate in proposal["candidate_entities"]:
        action = _action(
            proposal,
            target={"candidate_id": candidate["candidate_id"]},
            decision="CONFIRM",
            rationale=f"Confirm entity while conflict remains deferred #{index}.",
            decided_at=f"2026-08-06T00:{index:02d}:00Z",
            evidence_refs=[f"review-evidence-defer-{index:03d}"],
        )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "deferred-review" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    for issue in proposal["issues"]:
        action = _action(
            proposal,
            target={"issue_id": issue["issue_id"]},
            decision="DEFER",
            rationale="Issue retained for a later modeling review session.",
            decided_at=f"2026-08-06T00:{index:02d}:00Z",
            evidence_refs=[f"review-evidence-defer-issue-{index:03d}"],
        )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "deferred-review" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    log = _build_log(proposal, actions, "deferred-review")
    package = _package("conflicting-values", proposal, log, allow_blocked=True)
    _write(EXAMPLES / "expected-logs" / "deferred-review.log.json", log)
    _write(EXAMPLES / "expected-packages" / "deferred-review.package.json", package)


def scenario_issue_resolution() -> None:
    proposal = _load(PROPOSALS / "conflicting-values.proposal.json")
    actions = []
    index = 1
    for candidate in proposal["candidate_entities"]:
        action = _action(
            proposal,
            target={"candidate_id": candidate["candidate_id"]},
            decision="CONFIRM",
            rationale=f"Confirm entity after conflict issue resolution #{index}.",
            decided_at=f"2026-08-06T00:{index:02d}:00Z",
            evidence_refs=[f"review-evidence-resolve-{index:03d}"],
        )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "issue-resolution" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    for issue in proposal["issues"]:
        if issue.get("blocking"):
            action = _action(
                proposal,
                target={"issue_id": issue["issue_id"]},
                decision="REJECT",
                rationale=(
                    "Blocking conflict is not modeling-relevant after human evidence review; "
                    "no status assertion is confirmed in this package."
                ),
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=["review-evidence-resolve-blocking-001"],
            )
        else:
            action = _action(
                proposal,
                target={"issue_id": issue["issue_id"]},
                decision="REJECT",
                rationale="Expected missing account fields are acknowledged and closed.",
                decided_at=f"2026-08-06T00:{index:02d}:00Z",
                evidence_refs=[f"review-evidence-resolve-issue-{index:03d}"],
            )
        actions.append(action)
        _write(
            EXAMPLES / "actions" / "issue-resolution" / f"action-{index:03d}.json",
            action,
        )
        index += 1
    log = _build_log(proposal, actions, "issue-resolution")
    package = _package("conflicting-values", proposal, log)
    _write(EXAMPLES / "expected-logs" / "issue-resolution.log.json", log)
    _write(EXAMPLES / "expected-packages" / "issue-resolution.package.json", package)


def write_reviewer() -> None:
    _write(EXAMPLES / "reviewers" / "reviewer-professor.json", REVIEWER)


def main() -> int:
    write_reviewer()
    scenario_full_confirmation()
    scenario_modified_confirmation()
    scenario_rejection()
    scenario_deferred_review()
    scenario_issue_resolution()
    print("Stage 05 examples generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
