"""Append explicit revised budget authorization, preserving original evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io import budget_monitor
from zhigou_toolchain.ontology_io.cli import load, save
from zhigou_toolchain.ontology_io.live_budget import BudgetLedger
from zhigou_toolchain.ontology_io.live_runner import supervisor_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--bounded-transport-recovery", action="store_true", help="Explicit full-run authority: at most three attempts, only transient transport failures")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("NEW_AUTHORIZATION_OUTPUT_REQUIRED")
    user = load(args.authorization)
    ledger = BudgetLedger(args.workspace / "budget.sqlite")
    with supervisor_lock(args.workspace):
        old = ledger.snapshot()
        with ledger.connection() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
        document = {"policy_id": args.policy_id, "kind": budget_monitor.POLICY_KIND,
            "user_request": user["user_request"], "context": user["context"], "model_id": budget_monitor.MODEL,
            "endpoint_sha256": semantic_hash(budget_monitor.ENDPOINT), "reasoning_effort": "low",
            "max_calls": old["max_calls"], "max_reserved_tokens": old["max_reserved_tokens"],
            "acknowledged_violation_ids": sorted(r["request_id"] for r in rows if r["state"] == "USAGE_BOUND_VIOLATION"),
            "prior_attempts_sha256": semantic_hash(rows),
            "acknowledged_stop_sha256": hashlib.sha256((args.workspace / "STOP").read_bytes()).hexdigest(),
            "output_reservation_tokens": budget_monitor.OUTPUT_RESERVATION,
            "settlement": "KNOWN_SUCCESSES_ACTUAL_FAILURES_OR_UNKNOWNS_KEEP_RESERVATION", "single_request_hard_cap_guaranteed": False}
        if args.bounded_transport_recovery:
            document["transport_recovery"] = {"max_attempts": 3, "backoff_seconds": 5, "semantic_retry": False}
        reference = budget_monitor.authorize(ledger, document)
        args.output.mkdir(parents=True)
        save(args.output / "policy.json", document)
        save(args.output / "reference.json", reference)
        save(args.output / "receipt.json", {"legacy_before": old, "legacy_after": ledger.snapshot(),
            "monitor": budget_monitor.snapshot(ledger, reference), "model_calls_by_this_command": 0})
    print(json.dumps({"reference": str(args.output / "reference.json"), "monitor": budget_monitor.snapshot(ledger, reference)}))


if __name__ == "__main__":
    main()
