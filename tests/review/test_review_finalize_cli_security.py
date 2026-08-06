"""CLI security tests for review finalize against illegal decision logs."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.modeling.cli import main
from kg_mnp_demo.modeling.review_identifiers import decision_log_hash, review_decision_id

from ._helpers import EXAMPLES, ROOT, load_expected_log, load_proposal


def test_review_finalize_cli_rejects_issue_confirm(tmp_path: Path, capsys):
    proposal = load_proposal("conflicting-values")
    draft = load_expected_log("deferred-review")
    session = dict(draft["review_session"])
    session.pop("completed_at", None)
    draft["review_session"] = session
    for decision in draft["decisions"]:
        if "issue_id" not in decision:
            continue
        decision["decision"] = "CONFIRM"
        decision["decision_id"] = review_decision_id(
            proposal_id=str(proposal["proposal_id"]),
            target_id=str(decision["issue_id"]),
            decision="CONFIRM",
            rationale=str(decision["rationale"]),
            reviewer_id=str(decision["reviewer_id"]),
            decided_at=str(decision["decided_at"]),
            evidence_refs=list(decision.get("evidence_refs") or []),
        )
        break
    draft["log_hash"] = decision_log_hash(draft)
    log_path = tmp_path / "illegal.log.json"
    log_path.write_text(json.dumps(draft), encoding="utf-8")
    output = tmp_path / "must-not-exist.final.json"
    code = main(
        [
            "review",
            "finalize",
            "--proposal",
            str(
                ROOT
                / "examples"
                / "modeling"
                / "expected-proposals"
                / "conflicting-values.proposal.json"
            ),
            "--decision-log",
            str(log_path),
            "--completed-at",
            "2026-08-06T02:00:00Z",
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert not output.exists()
    assert "error" in captured.err.lower() or "SemanticValidationError" in captured.err
    assert "CONFIRM" in captured.err or "not allowed" in captured.err
