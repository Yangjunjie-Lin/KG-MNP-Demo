"""External September 2026 v2 adapter; compatibility is not collection/evaluation."""
from __future__ import annotations

import json
import re
from datetime import datetime

from .exchange_io import (
    file_rows,
    json_bytes,
    read_directory,
    require,
    verify_rows,
    write_directory,
)

HARNESS_KEYS = ("tasks", "prompts", "tools", "rules", "knowledge", "ontology")
EVENT_FIELDS = {
    "task_start": ("task_id", "task_input", "harness"),
    "llm_call": ("turn", "messages"), "llm_output": ("turn", "content"),
    "tool_call": ("turn", "tool", "args"), "tool_result": ("turn", "tool", "result"),
    "task_end": ("status", "answer", "duration_ms"),
}
ID_PATTERN = r"[A-Za-z0-9._-]+"
ASPECTS = {"引用准确性", "事实正确性", "格式合规", "完整性", "其他"}
SEVERITIES = {"info", "minor", "major", "critical"}
VIOLATIONS = {"citation_unverified", "bad_law_ref", "bad_decision", "answer_not_object",
              "status_answer_mismatch", "empty_answer", "assess_error", "decision_reasons_missing"}


def valid_time(value):
    try:
        return isinstance(value, str) and "T" in value and datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def parse_jsonl(raw):
    require(isinstance(raw, bytes) and len(raw) <= 64_000_000, "TRACE_SIZE_LIMIT")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (ValueError, UnicodeError):
        raise ValueError("TRUNCATED_OR_INVALID_JSONL") from None
    require(rows and all(isinstance(r, dict) for r in rows), "INVALID_JSONL_RECORD")
    return rows


def validate_events(events, run_id, *, producer=False):
    """Report original warning/error distinctions; producers additionally require IDs."""
    errors, warnings = [], []
    def issue(code, line=0, warning=False):
        (warnings if warning else errors).append({"code": code, "line": line})
    if not isinstance(run_id, str) or not re.fullmatch(ID_PATTERN, run_id):
        issue("RUN_ID_INVALID")
    if not events or events[0].get("event") != "task_start" or events[-1].get("event") != "task_end":
        issue("TASK_BOUNDARIES_REQUIRED")
    for event in ("task_start", "task_end"):
        if sum(r.get("event") == event for r in events) != 1:
            issue("TASK_BOUNDARY_NOT_UNIQUE")
    pending, used, latest = {}, set(), 0
    for index, row in enumerate(events, 1):
        event = row.get("event")
        if row.get("run_id") != run_id:
            issue("RUN_ID_MISMATCH", index)
        if not valid_time(row.get("ts")):
            issue("TIMEZONE_REQUIRED", index)
        if event not in EVENT_FIELDS:
            issue("UNKNOWN_EVENT", index, warning=not producer)
            continue
        if not all(k in row for k in EVENT_FIELDS[event]):
            issue("EVENT_FIELDS_MISSING", index)
            continue
        if event == "task_start":
            harness = row["harness"]
            if not isinstance(harness, dict) or any(not isinstance(harness.get(k), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", harness[k]) for k in HARNESS_KEYS):
                issue("HARNESS_INVALID", index)
            elif set(harness) - set(HARNESS_KEYS):
                issue("UNKNOWN_HARNESS_KEY", index, warning=True)
        if event in {"llm_call", "llm_output", "tool_call", "tool_result"}:
            turn = row["turn"]
            if type(turn) is not int or turn < 1:
                issue("PRE_MODEL_OR_PROGRAM_ONLY_UNDEFINED" if turn is None else "TURN_INVALID", index)
                continue
            if event == "llm_call":
                if turn != latest + 1:
                    issue("LLM_TURN_SEQUENCE", index)
                latest = turn
                if not isinstance(row["messages"], list):
                    issue("MESSAGES_INVALID", index)
            elif event == "tool_call" and turn != latest:
                issue("TOOL_CURRENT_TURN_MISMATCH", index)
            elif turn > latest:
                issue("TURN_NOT_YET_OPENED", index)
            call_id = row.get("call_id")
            if not call_id:
                issue("CALL_ID_MISSING", index, warning=not producer)
            elif not isinstance(call_id, str):
                issue("CALL_ID_INVALID", index)
                continue
            kind = "llm" if event.startswith("llm") else "tool"
            if event.endswith("call"):
                key = call_id or f"position-{index}"
                if key in used:
                    issue("DUPLICATE_CALL_ID", index)
                used.add(key)
                pending[key] = (kind, row)
            else:
                key = call_id or next((k for k, (t, r) in pending.items() if t == kind
                    and (r.get("turn") == turn if kind == "llm" else r.get("tool") == row.get("tool"))), None)
                original = pending.pop(key, None)
                if original is None:
                    issue("ORPHAN_RESULT", index)
                else:
                    t, r = original
                    if t != kind or (kind == "llm" and r["turn"] != turn) or (kind == "tool" and (r["turn"] > turn or r["tool"] != row["tool"])):
                        issue("RESULT_PAIR_MISMATCH", index)
                if row.get("status", "ok") not in {"ok", "error"}:
                    issue("RESULT_STATUS_INVALID", index)
                if "usage" in row and (not isinstance(row["usage"], dict) or any(type(v) is not int or v < 0 for v in row["usage"].values())):
                    issue("USAGE_INVALID", index)
        if event == "task_end":
            if pending:
                issue("UNCLOSED_PAIR", index)
            if row["status"] not in {"success", "failed", "cancelled"}:
                issue("TASK_STATUS_INVALID", index)
            if type(row["duration_ms"]) not in {int, float} or row["duration_ms"] < 0:
                issue("DURATION_INVALID", index)
    if pending:
        issue("UNCLOSED_PAIR")
    if producer and latest == 0:
        issue("PRE_MODEL_OR_PROGRAM_ONLY_UNDEFINED")
    return {"status": "BLOCKED" if errors else "LOCAL_PROTOCOL_VALID", "errors": errors, "warnings": warnings,
            "receiver_status": "NOT_CONTACTED", "evaluator_support": "NOT_CONFIRMED"}


def validate_review(row, run_ids, *, producer=False):
    errors, warnings = [], []
    if not all(k in row for k in ("review_id", "exec_id", "verdict", "annotations", "reviewer", "ts")):
        errors.append("REVIEW_FIELDS_MISSING")
    if row.get("exec_id") not in run_ids:
        errors.append("REVIEW_EXECUTION_MISSING")
    if not valid_time(row.get("ts")):
        errors.append("REVIEW_TIMEZONE_REQUIRED")
    if row.get("verdict") == "fail" and not row.get("annotations"):
        (errors if producer else warnings).append("FAIL_ANNOTATIONS_MISSING")
    for annotation in row.get("annotations", []):
        if annotation.get("aspect") not in ASPECTS:
            warnings.append("UNKNOWN_ASPECT")
        if annotation.get("severity") not in SEVERITIES:
            errors.append("SEVERITY_INVALID")
    for violation in row.get("violations", []):
        if violation.get("code") not in VIOLATIONS:
            errors.append("UNCONFIRMED_VIOLATION_CODE")
    # The attachment does not supply v0's complete verdict enum.
    if row.get("verdict") != "fail":
        (errors if producer else warnings).append("VERDICT_ENUM_NOT_CONFIRMED")
    return {"errors": errors, "warnings": warnings}


def validate_batch(files, *, producer=False):
    manifest = json.loads(files["upstream_manifest.json"]) if "upstream_manifest.json" in files else None
    declared = None
    if manifest is not None:
        require(all(k in manifest for k in ("batch_id", "deliverer", "ts", "files")) and valid_time(manifest["ts"]), "BATCH_MANIFEST_INVALID")
        verify_rows(files, manifest["files"], upstream=True)
        declared = {r["name"] for r in manifest["files"]}
        require(all(re.fullmatch(r"(?:executions/run-[A-Za-z0-9._-]+|reviews/[A-Za-z0-9._-]+)\.jsonl", n) for n in declared), "COLLECTOR_PATH_INVALID")
    names = {n for n in files if re.fullmatch(r"(?:executions/run-[A-Za-z0-9._-]+|reviews/[A-Za-z0-9._-]+)\.jsonl", n)}
    if declared is not None:
        require(names == declared, "BATCH_UNDECLARED_FILE")
    runs, reports = set(), {}
    for name in sorted(n for n in names if n.startswith("executions/")):
        run_id = name[len("executions/run-"):-len(".jsonl")]
        require(run_id not in runs, "DUPLICATE_RUN_DELIVERY")
        runs.add(run_id)
        reports[name] = validate_events(parse_jsonl(files[name]), run_id, producer=producer)
    review_ids = set()
    for name in sorted(n for n in names if n.startswith("reviews/")):
        reports[name] = {"errors": [], "warnings": []}
        for row in parse_jsonl(files[name]):
            require(row.get("review_id") not in review_ids, "DUPLICATE_REVIEW_ID")
            review_ids.add(row.get("review_id"))
            result = validate_review(row, runs, producer=producer)
            for key in ("errors", "warnings"):
                reports[name][key].extend(result[key])
    return {"status": "BLOCKED" if any(r["errors"] for r in reports.values()) else "LOCAL_PROTOCOL_VALID",
            "manifest": "VERIFIED" if manifest else "ABSENT_SCAN_COMPATIBILITY", "files": reports,
            "receiver_status": "NOT_CONTACTED"}


def evolution_files(traces, *, batch_id, deliverer, reviews=()):
    require(re.fullmatch(ID_PATTERN, batch_id) and traces, "BATCH_ID_OR_TRACES_REQUIRED")
    files, bindings, harnesses = {}, [], []
    for trace in traces:
        run_id = trace["bindings"]["transport_run_id"]
        report = validate_events(trace["events"], run_id, producer=True)
        require(not report["errors"], "STRICT_V2_BLOCKED:" + ",".join(sorted({e["code"] for e in report["errors"]})))
        require(trace["capture_status"] == "COMPLETE", "TRACE_REDACTED_OR_PARTIAL")
        name = "executions/run-" + run_id + ".jsonl"
        require(name not in files, "DUPLICATE_RUN_DELIVERY")
        files[name] = b"".join(json_bytes(r) for r in trace["events"])
        bindings.append(trace["bindings"])
        harnesses.append(trace["harness_manifest"])
    if reviews:
        files["reviews/reviews-" + batch_id + ".jsonl"] = b"".join(json_bytes(r) for r in reviews)
    # Stable upon re-export: use the actual latest recorded event, not export time.
    timestamp = max(t["events"][-1]["ts"] for t in traces)
    files["upstream_manifest.json"] = json_bytes({"batch_id": batch_id, "deliverer": deliverer, "ts": timestamp,
                                                 "files": file_rows(files, upstream=True)})
    files["context/run_bindings.json"] = json_bytes(bindings)
    files["context/harness_manifest.json"] = json_bytes(harnesses)
    require(validate_batch(files, producer=True)["status"] == "LOCAL_PROTOCOL_VALID", "PRODUCER_BATCH_INVALID")
    return files


def export_batch(output, files):
    # Sibling batches are one local delivery destination; duplicate external IDs
    # cannot be copied into a second batch and mistaken for new samples.
    import sqlite3
    from pathlib import Path

    from .exchange_io import checked_path, digest
    require(validate_batch(files, producer=True)["status"] == "LOCAL_PROTOCOL_VALID", "BATCH_PROTOCOL_INVALID")
    output = checked_path(Path(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    ledger = checked_path(output.parent / ".zhigou-evolution-deliveries.sqlite3")
    with sqlite3.connect(ledger, timeout=30) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS deliveries (run_id TEXT PRIMARY KEY, destination TEXT NOT NULL, digest TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        runs = {n[len("executions/run-"):-len(".jsonl")]: digest(raw) for n, raw in files.items() if n.startswith("executions/")}
        for run_id, sha in runs.items():
            previous = connection.execute("SELECT destination,digest FROM deliveries WHERE run_id=?", (run_id,)).fetchone()
            require(previous is None or previous == (str(output), sha), "DUPLICATE_RUN_DELIVERY")
        status = "EXPORTED"
        if output.exists():
            require(read_directory(output) == files, "BATCH_IDEMPOTENCY_CONFLICT")
            status = "ALREADY_EXPORTED"
        else:
            write_directory(output, files, manifest="upstream_manifest.json")
        for run_id, sha in runs.items():
            connection.execute("INSERT OR IGNORE INTO deliveries VALUES (?,?,?)", (run_id, str(output), sha))
    return {"status": status, "receiver_status": "NOT_CONTACTED"}
