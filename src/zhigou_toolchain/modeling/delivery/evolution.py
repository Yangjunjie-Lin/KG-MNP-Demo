"""External September 2026 v2 adapter; compatibility is not collection/evaluation."""
from __future__ import annotations

import json
import math
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
COLLECTOR_PATH = r"(?:executions/run-[A-Za-z0-9._-]+|reviews/[^/]+)\.jsonl"


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
    """External protocol rules, not the recorder's always-generate-ID policy."""
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
        if not isinstance(event, str) or not event.strip():
            issue("EVENT_REQUIRED", index)
            event = None
        if row.get("run_id") != run_id:
            issue("RUN_ID_MISMATCH", index)
        if not valid_time(row.get("ts")):
            issue("TIMEZONE_REQUIRED", index)
        if event not in EVENT_FIELDS:
            if event is not None:
                issue("UNKNOWN_EVENT", index, warning=True)
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
            if call_id is None:
                issue("CALL_ID_MISSING", index, warning=True)
            elif not isinstance(call_id, str) or not call_id:
                issue("CALL_ID_INVALID", index)
                continue
            kind = "llm" if event.startswith("llm") else "tool"
            if event.endswith("call"):
                if pending and (call_id is None or any(r.get("call_id") is None for _, r in pending.values())):
                    issue("PARALLEL_CALL_ID_REQUIRED", index, warning=not producer)
                key = call_id or f"position-{index}"
                if key in used:
                    issue("DUPLICATE_CALL_ID", index)
                used.add(key)
                pending[key] = (kind, row)
            else:
                key = call_id or next((k for k, (t, r) in pending.items() if t == kind
                    and r.get("call_id") is None
                    and (r.get("turn") == turn if kind == "llm" else r.get("tool") == row.get("tool"))), None)
                original = pending.pop(key, None)
                if original is None:
                    issue("ORPHAN_RESULT", index)
                else:
                    t, r = original
                    if t != kind or (kind == "llm" and r["turn"] != turn) or (kind == "tool" and (r["turn"] > turn or r["tool"] != row["tool"])):
                        issue("RESULT_PAIR_MISMATCH", index)
                if row.get("status", "ok") not in ("ok", "error"):
                    issue("RESULT_STATUS_INVALID", index)
                if "usage" in row and (not isinstance(row["usage"], dict) or set(row["usage"]) - {"input_tokens", "output_tokens"}
                        or any(type(v) is not int or v < 0 for v in row["usage"].values())):
                    issue("USAGE_INVALID", index)
            if "duration_ms" in row and (type(row["duration_ms"]) not in {int, float}
                    or not math.isfinite(row["duration_ms"]) or row["duration_ms"] < 0):
                issue("DURATION_INVALID", index)
        if event == "task_end":
            if pending:
                issue("UNCLOSED_PAIR", index)
            if row["status"] not in ("success", "failed", "cancelled"):
                issue("TASK_STATUS_INVALID", index)
            if type(row["duration_ms"]) not in {int, float} or not math.isfinite(row["duration_ms"]) or row["duration_ms"] < 0:
                issue("DURATION_INVALID", index)
    if pending:
        issue("UNCLOSED_PAIR")
    if producer and latest == 0:
        issue("PRE_MODEL_OR_PROGRAM_ONLY_UNDEFINED")
    return {"status": "BLOCKED" if errors else "LOCAL_PROTOCOL_VALID", "errors": errors, "warnings": warnings,
            "receiver_status": "NOT_CONTACTED", "evaluator_support": "NOT_CONFIRMED"}


def validate_review(row, run_ids, *, producer=False):
    errors, warnings = [], []
    if not isinstance(row, dict):
        return {"errors": ["REVIEW_OBJECT_REQUIRED"], "warnings": []}
    if not all(isinstance(row.get(k), str) and row[k] for k in ("review_id", "exec_id", "verdict", "reviewer", "ts")):
        errors.append("REVIEW_FIELDS_MISSING")
    if not isinstance(row.get("exec_id"), str) or row["exec_id"] not in run_ids:
        errors.append("REVIEW_EXECUTION_MISSING")
    if not valid_time(row.get("ts")):
        errors.append("REVIEW_TIMEZONE_REQUIRED")
    if row.get("verdict") not in ("pass", "fail"):
        errors.append("VERDICT_INVALID")
    if row.get("verdict") == "fail" and "annotations" not in row:
        (errors if producer else warnings).append("FAIL_ANNOTATIONS_MISSING")
    annotations = row.get("annotations", [])
    if not isinstance(annotations, list):
        errors.append("ANNOTATIONS_INVALID")
        annotations = []
    for annotation in annotations:
        if not isinstance(annotation, dict) or not all(k in annotation for k in ("aspect", "severity", "comment")):
            errors.append("ANNOTATION_FIELDS_MISSING")
            continue
        if not isinstance(annotation["aspect"], str) or not isinstance(annotation["comment"], str):
            errors.append("ANNOTATION_INVALID")
            continue
        if annotation.get("aspect") not in ASPECTS:
            warnings.append("UNKNOWN_ASPECT")
        if annotation.get("severity") not in tuple(SEVERITIES):
            errors.append("SEVERITY_INVALID")
    violations = row.get("violations", [])
    if not isinstance(violations, list):
        errors.append("VIOLATIONS_INVALID")
        violations = []
    for violation in violations:
        if not isinstance(violation, dict) or not all(k in violation for k in ("code", "evidence", "suggestion")):
            errors.append("VIOLATION_FIELDS_MISSING")
            continue
        if not isinstance(violation["code"], str) or not violation["code"]:
            errors.append("VIOLATION_CODE_INVALID")
        if "severity" in violation and violation["severity"] not in tuple(SEVERITIES):
            errors.append("SEVERITY_INVALID")
    return {"errors": errors, "warnings": warnings}


def validate_batch(files, *, producer=False, known_run_ids=()):
    """known_run_ids is injected by a trusted caller, never read from batch context.

    A local trusted reference proves only a precheck, not receiver collection.
    Invalid reviews are reported per line without discarding their valid peers.
    """
    from .bindings import context_traces
    from .exchange_io import safe_name
    require(len({safe_name(n).casefold() for n in files}) == len(files), "EXCHANGE_CASE_COLLISION")
    manifest = json.loads(files["upstream_manifest.json"]) if "upstream_manifest.json" in files else None
    declared = None
    if "upstream_manifest.json" in files:
        require(isinstance(manifest, dict) and isinstance(manifest.get("batch_id"), str)
                and bool(manifest["batch_id"]) and isinstance(manifest.get("files"), list)
                and ("ts" not in manifest or valid_time(manifest["ts"])), "BATCH_MANIFEST_INVALID")
        assert isinstance(manifest, dict)
        verify_rows(files, manifest["files"], upstream=True)
        declared = {r["name"] for r in manifest["files"]}
        require(all(re.fullmatch(COLLECTOR_PATH, n) for n in declared), "COLLECTOR_PATH_INVALID")
    names = {n for n in files if re.fullmatch(r"(?:executions|reviews)/[^/]+\.jsonl", n)}
    require(all(re.fullmatch(COLLECTOR_PATH, n) for n in names), "COLLECTOR_PATH_INVALID")
    if declared is not None:
        require(names == declared, "BATCH_UNDECLARED_FILE")
    context_traces(files, strict=False)
    runs, reports = set(), {}
    for name in sorted(n for n in names if n.startswith("executions/")):
        run_id = name[len("executions/run-"):-len(".jsonl")]
        require(run_id not in runs, "DUPLICATE_RUN_DELIVERY")
        reports[name] = validate_events(parse_jsonl(files[name]), run_id, producer=producer)
        if not reports[name]["errors"]:
            runs.add(run_id)
    review_ids = set()
    for name in sorted(n for n in names if n.startswith("reviews/")):
        reports[name] = {"errors": [], "warnings": [], "accepted": [], "quarantined": []}
        require(len(files[name]) <= 64_000_000, "TRACE_SIZE_LIMIT")
        for line, raw in enumerate(files[name].splitlines(), 1):
            try:
                row = json.loads(raw.decode("utf-8"))
                result = validate_review(row, runs | set(known_run_ids), producer=producer)
            except (ValueError, UnicodeError):
                row, result = None, {"errors": ["TRUNCATED_OR_INVALID_JSONL"], "warnings": []}
            review_id = row.get("review_id") if isinstance(row, dict) else None
            if isinstance(review_id, str):
                if review_id in review_ids:
                    result["errors"].append("DUPLICATE_REVIEW_ID")
                review_ids.add(review_id)
            for key in ("errors", "warnings"):
                reports[name][key].extend({"line": line, "code": code} for code in result[key])
            bucket = "quarantined" if result["errors"] else "accepted"
            reports[name][bucket].append({"line": line, "review": row})
    return {"status": "BLOCKED" if any(r["errors"] for r in reports.values()) else "LOCAL_PROTOCOL_VALID",
            "manifest": "VERIFIED" if manifest is not None else "ABSENT_SCAN_COMPATIBILITY", "files": reports,
            "reference_check": "LOCAL_PRECHECK_NOT_COLLECTION",
            "receiver_status": "NOT_CONTACTED"}


def evolution_files(traces, *, batch_id, deliverer=None, reviews=(), allow_synthetic=False, known_run_ids=(), include_context=True):
    require(isinstance(batch_id, str) and re.fullmatch(ID_PATTERN, batch_id), "BATCH_ID_REQUIRED")
    traces, reviews = list(traces), list(reviews)
    files, bindings, harnesses = {}, [], []
    for trace in traces:
        mode = trace["bindings"].get("execution_mode")
        require(mode == "LIVE" or (allow_synthetic and mode == "SYNTHETIC_MOCK"), "NON_LIVE_TRACE_NOT_COLLECTIBLE")
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
    times = [t["events"][-1]["ts"] for t in traces] + [r["ts"] for r in reviews]
    manifest = {"batch_id": batch_id, "files": file_rows(files, upstream=True)}
    if deliverer is not None:
        manifest["deliverer"] = deliverer
    if times:
        manifest["ts"] = max(times, key=datetime.fromisoformat)
    if include_context and traces:
        files["context/run_bindings.json"] = json_bytes(bindings)
        files["context/harness_manifest.json"] = json_bytes(harnesses)
    files["upstream_manifest.json"] = json_bytes(manifest)
    require(validate_batch(files, producer=True, known_run_ids=known_run_ids)["status"] == "LOCAL_PROTOCOL_VALID", "PRODUCER_BATCH_INVALID")
    return files


def export_batch(output, files, *, known_run_ids=()):
    # Sibling batches are one local delivery destination; duplicate external IDs
    # cannot be copied into a second batch and mistaken for new samples.
    import sqlite3
    from pathlib import Path

    from .exchange_io import checked_path, digest
    require(validate_batch(files, producer=True, known_run_ids=known_run_ids)["status"] == "LOCAL_PROTOCOL_VALID", "BATCH_PROTOCOL_INVALID")
    output = checked_path(Path(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    ledger = checked_path(output.parent / ".zhigou-evolution-deliveries.sqlite3")
    with sqlite3.connect(ledger, timeout=30) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS deliveries (run_id TEXT PRIMARY KEY, destination TEXT NOT NULL, digest TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS review_deliveries (review_id TEXT PRIMARY KEY, destination TEXT NOT NULL, digest TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        runs = {n[len("executions/run-"):-len(".jsonl")]: digest(raw) for n, raw in files.items() if n.startswith("executions/")}
        for run_id, sha in runs.items():
            previous = connection.execute("SELECT destination,digest FROM deliveries WHERE run_id=?", (run_id,)).fetchone()
            require(previous is None or previous == (str(output), sha), "DUPLICATE_RUN_DELIVERY")
        reviews = {r["review_id"]: digest(json_bytes(r)) for n, raw in files.items() if n.startswith("reviews/") and raw for r in parse_jsonl(raw)}
        for review_id, sha in reviews.items():
            previous = connection.execute("SELECT destination,digest FROM review_deliveries WHERE review_id=?", (review_id,)).fetchone()
            require(previous is None or previous == (str(output), sha), "DUPLICATE_REVIEW_DELIVERY")
        status = "EXPORTED"
        if output.exists():
            require(read_directory(output) == files, "BATCH_IDEMPOTENCY_CONFLICT")
            status = "ALREADY_EXPORTED"
        else:
            write_directory(output, files, manifest="upstream_manifest.json")
        for run_id, sha in runs.items():
            connection.execute("INSERT OR IGNORE INTO deliveries VALUES (?,?,?)", (run_id, str(output), sha))
        for review_id, sha in reviews.items():
            connection.execute("INSERT OR IGNORE INTO review_deliveries VALUES (?,?,?)", (review_id, str(output), sha))
    return {"status": status, "receiver_status": "NOT_CONTACTED"}
