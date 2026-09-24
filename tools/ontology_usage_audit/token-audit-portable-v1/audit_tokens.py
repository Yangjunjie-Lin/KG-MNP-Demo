"""Read-only per-run JSON token audit of the existing benchmark caller ledger.

No model client, generator import, scoring, credentials, or database writes.
snapshot emits one JSON document; watch emits JSON Lines and atomic JSON views.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "ontology-token-usage/1.0"
DEPENDENCY_SHA256 = "51a02667a44580e734c27f986efaf83c1e18b8fdb0195a13d9aacaebae775cab"
CATEGORIES = ("modeling", "testing", "unclassified")
MODELING_SYSTEMS = frozenset({"TwoAgentKernelV1", "NoConstrainedExtraction", "NoRetrieval",
    "NoValidationFeedback", "DirectBudgetControl", "DirectGeneralLLM", "DirectRetrievalContext"})
PROBE_JOBS = frozenset({"preflight", "model-recovery-synthetic-probe", "explicit-local-endpoint-recheck"})
TERMINAL = frozenset({"GENERATED", "FAILED", "NOT_APPLICABLE", "CANCELLED"})
STEP_ROLES = {"S1": "RuleAgent", "S2": "RuleAgent", "S3": "TaskExecutionAgent",
              "S4": "RuleAgent", "S5": "TaskExecutionAgent"}
PROGRAM_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class AuditError(Exception):
    """Only safe, fixed error codes are exposed to stdout."""


def now():
    return datetime.now(UTC).isoformat()


def load_helpers():
    freeze = Path(__file__).with_name("freeze.json")
    if freeze.exists() and json.loads(freeze.read_bytes())["files"]["audit_tokens.py"] != PROGRAM_SHA256:
        raise AuditError("AUDITOR_FROZEN_SOURCE_CHANGED")
    path = Path(__file__).resolve().parent.parent / "token-report-portable-v1/export_usage.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != DEPENDENCY_SHA256:
        raise AuditError("AUDITOR_DEPENDENCY_CHANGED")
    spec = importlib.util.spec_from_file_location("pinned_token_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_path(root, *parts):
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise AuditError("ARTIFACT_PATH_ESCAPE")
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise AuditError("ARTIFACT_LINK_REJECTED")
    return path


def totals(rows):
    rows = list(rows)
    result = {"caller_attempts": len(rows)}
    for kind in ("input", "output", "total"):
        values = [r[kind + "_tokens"] for r in rows]
        known = sum(v for v in values if v is not None)
        missing = sum(v is None for v in values)
        result[kind + "_tokens"] = known if not missing else None
        result["known_" + kind + "_tokens"] = known
        result["unknown_" + kind + "_calls"] = missing
    result["budget_charge_tokens_not_usage"] = sum(r["budget_charge"] for r in rows)
    result["in_flight_calls"] = sum(r["state"] == "RESERVED" for r in rows)
    result["inconsistent_usage_calls"] = sum(r["usage_status"] == "INCONSISTENT" for r in rows)
    result["coverage"] = "NO_REGISTERED_CALLS" if not rows else (
        "INCONSISTENT" if result["inconsistent_usage_calls"] else
        "INCOMPLETE" if any(result["unknown_" + k + "_calls"] for k in ("input", "output", "total")) else "COMPLETE")
    return result


def partitions(rows, field, keys):
    result = {key: totals(r for r in rows if r[field] == key) for key in keys}
    whole = totals(rows)
    for metric in ("caller_attempts", "known_input_tokens", "known_output_tokens", "known_total_tokens",
                   "unknown_input_calls", "unknown_output_calls", "unknown_total_calls", "budget_charge_tokens_not_usage"):
        if sum(group[metric] for group in result.values()) != whole[metric]:
            raise AuditError("CATEGORY_RECONCILIATION_FAILED")
    return result


def category(job, call):
    if job and job["system"] in MODELING_SYSTEMS:
        return "modeling", "benchmark", "REGISTERED_BENCHMARK_GENERATION_SYSTEM"
    if not job and call["job_id"] in PROBE_JOBS:
        return "testing", "diagnostic", "EXPLICIT_EXISTING_PROBE_JOB_ID"
    return "unclassified", "benchmark" if job else "unknown", "NO_SUPPORTED_PURPOSE_MAPPING"


class Reader:
    """Uses original rows/IDs and pinned report helpers, never a second usage ledger."""

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve(strict=True)
        safe_path(self.workspace, "budget.sqlite")
        safe_path(self.workspace, "jobs.sqlite")
        self.h = load_helpers()
        self.constants = {}
        self.source_hashes = {}
        self.cache = {}
        self.run_signatures = {}
        self.incremental = False

    def ledger(self, revision=None, job_id=None):
        # Both short read snapshots are held together; artifact IO happens after commit.
        with closing(self.h.read_db(self.workspace / "budget.sqlite")) as conn:
            conn.execute("ATTACH DATABASE ? AS jobdb", ((self.workspace / "jobs.sqlite").as_uri() + "?mode=ro",))
            conn.execute("BEGIN")
            conn.execute("SELECT 1 FROM attempts LIMIT 1").fetchone()
            conn.execute("SELECT 1 FROM jobdb.jobs LIMIT 1").fetchone()
            cutoff = now()
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            condition, params = [], []
            if revision:
                condition.append("j.revision=?")
                params.append(revision)
            if job_id:
                condition.append("a.job_id=?")
                params.append(job_id)
            where = " WHERE " + " AND ".join(condition) if condition else ""
            join = " LEFT JOIN jobdb.jobs j ON j.job_id=a.job_id"
            monitor = " LEFT JOIN monitored_attempts m USING(request_id)" if "monitored_attempts" in tables else ""
            charge = "COALESCE(m.charge,a.reserved)" if monitor else "a.reserved"
            attempts = [dict(r) for r in conn.execute(
                "SELECT a.*," + charge + " AS budget_charge FROM attempts a" + join + monitor + where +
                " ORDER BY a.started_at,a.request_id", params)]
            base = dict(conn.execute("SELECT COUNT(*) AS calls,COALESCE(SUM(a.usage),0) AS known_total,"
                "COALESCE(SUM(a.usage IS NULL),0) AS unknown_calls FROM attempts a" + join + where, params).fetchone())
            job_where = [("(started IS NOT NULL OR state IN ('RUNNING','GENERATED','FAILED','CANCELLED') "
                          "OR job_id IN (SELECT job_id FROM attempts))")]
            job_params = []
            if revision:
                job_where.append("revision=?")
                job_params.append(revision)
            if job_id:
                job_where = ["job_id=?"] + (["revision=?"] if revision else [])
                job_params = [job_id] + ([revision] if revision else [])
            jobs = {r["job_id"]: dict(r) for r in conn.execute(
                "SELECT job_id,revision,phase,task,sample,system,replicate,state,started,ended FROM jobdb.jobs WHERE " +
                " AND ".join(job_where), job_params)}
            vetoes = {r[0] for r in conn.execute("SELECT request_id FROM operator_terminal_transport_continuations "
                "WHERE json_extract(document,'$.failure_class')='PROVEN_LOCAL_PRIVATE_INPUT_VETO'")} if (
                "operator_terminal_transport_continuations" in tables) else set()
            conn.commit()
        if job_id and not attempts and job_id not in jobs:
            raise AuditError("JOB_NOT_FOUND_IN_SCOPE")
        return cutoff, attempts, jobs, vetoes, base

    def frozen_constants(self, revision):
        if revision in self.constants:
            return self.constants[revision]
        root = safe_path(self.workspace, "revisions", revision)
        path = safe_path(root, "code-lock.json")
        values, hashes = [], {}
        if path.is_file():
            lock = json.loads(path.read_bytes())
            for name, expected in lock["files"].items():
                if not name.endswith(("ontology_io/kernel.py", "ontology_io/engine.py", "modeling/five_stage/assistance.py")):
                    continue
                raw = safe_path(root, "code", name).read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise AuditError("FROZEN_STAGE_SOURCE_CHANGED")
                hashes[name] = expected
                values.extend(n.value for n in self.h.ast.walk(self.h.ast.parse(raw))
                              if isinstance(n, self.h.ast.Constant) and isinstance(n.value, str))
        self.constants[revision], self.source_hashes[revision] = values, hashes
        return values

    def paths(self, call, job):
        match = re.fullmatch(re.escape(call["job_id"]) + r":(?:attempt-(\d+):)?call-(\d+)", call["request_id"])
        if not job or not match:
            return match, None, None
        parts = ["revisions", job["revision"], "runs", call["job_id"]]
        if match[1]:
            parts.append("attempt-" + match[1])
        root = safe_path(self.workspace, *parts, "calls", match[2])
        return match, safe_path(root, "request.json"), safe_path(root, "response.json")

    @staticmethod
    def stamp(path):
        if path is None or not path.exists():
            return None
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def call_row(self, call, job, vetoes, diagnostics):
        # Final verified artifacts are immutable inputs to this observer. A new
        # one-shot Reader always verifies them again; watch is not a file-tamper monitor.
        base_signature = self.h.digest([call, job, call["request_id"] in vetoes])
        cached = self.cache.get(call["request_id"])
        if self.incremental and cached and cached[2] == base_signature and cached[1]["usage_status"] == "COMPLETE":
            return cached[1]
        match, request_path, response_path = self.paths(call, job)
        signature = self.h.digest([call, job, self.stamp(request_path), self.stamp(response_path),
                                   call["request_id"] in vetoes, diagnostics.get(call["request_id"])])
        cached = self.cache.get(call["request_id"])
        if cached and cached[0] == signature:
            return cached[1]
        raw = request_path.read_bytes() if request_path and request_path.is_file() else None
        request = json.loads(raw) if raw is not None else None
        req_hash = hashlib.sha256(raw).hexdigest() if raw is not None else None
        response, verification = None, "NO_MATCHED_ARTIFACT"
        issues = []
        if call["state"] == "RESERVED":
            verification = "IN_FLIGHT_AT_SNAPSHOT"
        else:
            candidate = json.loads(response_path.read_bytes()) if response_path and response_path.is_file() else diagnostics.get(call["request_id"])
            if candidate is not None:
                if self.h.digest(candidate) == call["result_hash"]:
                    response, verification = candidate, "VERIFIED_CANONICAL_SHA256"
                else:
                    verification = "HASH_MISMATCH_NO_BREAKDOWN_USED"
                    issues.append(verification)
        usage = self.h.provider_usage(response)
        inp, out, total = usage["input"], usage["output"], self.h.integer(call["usage"])
        if call["state"] == "RESERVED":
            inp, out, total = None, None, None
        consistent = inp is not None and out is not None and total is not None and inp + out == total == usage["total"]
        inconsistent = inp is not None and out is not None and total is not None and not consistent
        if inconsistent:
            issues.append("INPUT_OUTPUT_TOTAL_MISMATCH")
        if call["usage"] is not None and self.h.integer(call["usage"]) is None:
            raise AuditError("INVALID_LEDGER_USAGE")
        if self.h.integer(call["budget_charge"]) is None:
            raise AuditError("INVALID_BUDGET_CHARGE")
        stage, purpose, role, repair, basis = self.h.classify(request, job["system"] if job else "",
            self.frozen_constants(job["revision"]) if job else [])
        purpose_category, context, category_basis = category(job, call)
        if not job:
            stage = "TEST_DIAGNOSTIC" if purpose_category == "testing" else "UNKNOWN"
            purpose, role, basis = "diagnostic" if stage == "TEST_DIAGNOSTIC" else "unknown", "", category_basis
        row = {"request_id": call["request_id"], "job_id": call["job_id"],
            "attempt": int(match[1]) if match and match[1] else 1 if match else None,
            "call_index": int(match[2]) if match else None,
            "step": stage, "purpose": purpose, "role": role, "is_repair": repair,
            "usage_category": purpose_category, "execution_context": context, "category_basis": category_basis,
            "input_tokens": inp, "output_tokens": out, "total_tokens": total,
            "usage_status": "COMPLETE" if consistent else "INCONSISTENT" if inconsistent else "TOTAL_ONLY" if total is not None
                else "IN_FLIGHT" if call["state"] == "RESERVED" else "UNKNOWN",
            "state": call["state"], "budget_charge": call["budget_charge"],
            "started_at_utc": call["started_at"], "ended_at_utc": call["ended_at"],
            "request_file_sha256": req_hash, "response_semantic_sha256": call["result_hash"],
            "response_verification": verification, "step_basis": basis,
            "call_qualification": "LOCAL_VETO_REPRODUCED_HISTORICAL_USAGE_UNKNOWN" if call["request_id"] in vetoes else
                "REGISTERED_CALLER_ATTEMPT_NOT_PHYSICAL_HTTP_COUNT", "issues": issues}
        self.cache[call["request_id"]] = signature, row, base_signature
        return row

    def snapshot(self, revision=None, job_id=None):
        cutoff, attempts, jobs, vetoes, base = self.ledger(revision, job_id)
        diagnostics = self.h.diagnostic_artifacts(self.workspace)
        rows = [self.call_row(a, jobs.get(a["job_id"]), vetoes, diagnostics) for a in attempts]
        if len({r["request_id"] for r in rows}) != len(rows):
            raise AuditError("DUPLICATE_CALLER_ATTEMPT")
        summary = totals(rows)
        if (summary["caller_attempts"], summary["known_total_tokens"], summary["unknown_total_calls"]) != (
                base["calls"], base["known_total"], base["unknown_calls"]):
            raise AuditError("LEDGER_RECONCILIATION_FAILED")
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["job_id"]].append(row)
        reports = []
        all_ids = jobs.keys() | grouped.keys()
        for jid in sorted(all_ids):
            job, selected = jobs.get(jid), grouped[jid]
            signature = self.h.digest([job, selected, is_terminal(job, cutoff)])
            if not self.incremental or self.run_signatures.get(jid) != signature:
                reports.append(run_report(jid, job, selected, cutoff))
            self.run_signatures[jid] = signature
        if sum(totals(grouped[jid])["known_total_tokens"] for jid in all_ids) != summary["known_total_tokens"]:
            raise AuditError("RUN_RECONCILIATION_FAILED")
        return {"schema_version": SCHEMA, "kind": "token_usage_snapshot", "snapshot_at_utc": cutoff,
            "scope": {"adapter": "ontology_benchmark_caller_ledger", "workspace": str(self.workspace),
                      "revision": revision, "job_id": job_id, "null_filter_means": "all_recorded_history"},
            "totals": summary, "by_usage_category": partitions(rows, "usage_category", CATEGORIES),
            "by_execution_context": partitions(rows, "execution_context", ("benchmark", "diagnostic", "unknown")),
            "steps": step_reports(rows), "run_count": len(all_ids), "runs": reports,
            "issue_count": sum(len(row["issues"]) for row in rows),
            "runs_view": "changed_since_previous_poll" if self.incremental else "complete_selected_scope",
            "source": {"ledger_rows_sha256": self.h.digest(attempts), "call_table_sha256": self.h.digest(rows),
                "stage_source_files": self.source_hashes, "helper_sha256": DEPENDENCY_SHA256,
                "audit_program_sha256": PROGRAM_SHA256},
            "reconciliation": {"caller_attempts_counted_once": True, "known_tokens_equal_ledger": True,
                "categories_and_runs_partition_total": True, "databases_read_only": True, "new_model_calls": 0},
            "limitations": ["Totals cover registered caller attempts, not independently witnessed physical HTTP requests.",
                "Modeling includes generation/repair/direct baselines inside a benchmark; testing means explicit diagnostic probes.",
                "Usage category and execution context are separate axes; do not add their subtotals together.",
                "Unknown usage is null; budget charges and reservations are not actual token consumption.",
                "Zero registered calls does not prove step execution or unregistered provider usage is zero.",
                "No Codex chat, other projects, unregistered LLM judge or CPU-only test usage is inferred.",
                "Watch caches verified complete immutable call artifacts until ledger metadata changes; a fresh snapshot rechecks all hashes."]}


def step_reports(rows):
    steps = sorted(set(STEP_ROLES) | {r["step"] for r in rows})
    return [{"step": step, "role": STEP_ROLES.get(step), "execution_status": "NOT_INFERRED_FROM_TOKEN_AUDIT",
             "totals": totals(r for r in rows if r["step"] == step),
             "by_usage_category": partitions([r for r in rows if r["step"] == step], "usage_category", CATEGORIES)}
            for step in steps]


def is_terminal(job, cutoff):
    ended = job.get("ended") if job else None
    # A failed attempt can become PENDING for a genuine retry; only job state decides finality.
    return bool(job and job["state"] in TERMINAL and ended and
                datetime.fromisoformat(ended) <= datetime.fromisoformat(cutoff))


def run_report(job_id, job, rows, cutoff):
    summary = totals(rows)
    terminal = is_terminal(job, cutoff)
    return {"schema_version": SCHEMA, "kind": "run_token_usage", "job_id": job_id,
        "run_kind": "benchmark_job" if job else "detached_ledger_job_group_not_native_run",
        "run": {key: job[key] for key in ("revision", "phase", "task", "sample", "system", "replicate", "state", "started", "ended")} if job else None,
        "terminal_at_snapshot": terminal, "totals": summary,
        "final_total_tokens": summary["total_tokens"] if terminal else None,
        "by_usage_category": partitions(rows, "usage_category", CATEGORIES),
        "steps": step_reports(rows), "calls": rows}


def json_text(value, compact=False):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(",", ":") if compact else None, indent=None if compact else 2) + "\n"


def atomic_json(path, value, replace=False):
    """Only tool-owned views are replaceable. One-shot exports never overwrite."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_path(path.parent, path.name)
    if not replace:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json_text(value))
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".token-audit-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json_text(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def observer_lock(output_dir, workspace, revision):
    if output_dir.resolve().is_relative_to(workspace.resolve()):
        raise AuditError("OBSERVER_OUTPUT_MUST_BE_OUTSIDE_LEDGER_WORKSPACE")
    safe_path(output_dir.parent, output_dir.name)
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "observer-scope.json"
    scope = {"schema_version": SCHEMA, "workspace": str(workspace), "revision": revision}
    # Refuse to adopt/overwrite any pre-existing unrelated directory.
    if not marker.exists():
        if any(output_dir.iterdir()):
            raise AuditError("OUTPUT_DIRECTORY_NOT_OWNED_BY_AUDITOR")
        atomic_json(marker, scope)
    elif json.loads(safe_path(output_dir, marker.name).read_bytes()) != scope:
        raise AuditError("OBSERVER_SCOPE_CHANGED")
    lock_path = safe_path(output_dir, "observer.lock")
    stream = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    except (BlockingIOError, PermissionError) as exc:
        if not locked:
            raise AuditError("OBSERVER_ALREADY_RUNNING") from exc
        raise
    finally:
        if locked:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def publish(snapshot, output_dir, helper, emit, observed=None):
    changed = 0
    for report in snapshot["runs"]:
        filename = hashlib.sha256(report["job_id"].encode("utf-8")).hexdigest() + ".json"
        path = safe_path(output_dir, "runs", filename)
        digest = helper.digest(report)
        previous = observed.get(filename) if observed is not None else None
        if previous is None and path.exists():
            old = json.loads(path.read_bytes())
            previous = helper.digest(old["report"])
        if previous != digest:
            event = {"schema_version": SCHEMA, "kind": "run_token_usage_updated",
                     "observed_at_utc": snapshot["snapshot_at_utc"], "report_sha256": digest, "report": report}
            atomic_json(path, event, replace=True)
            emit(event)
            changed += 1
        if observed is not None:
            observed[filename] = digest
    # latest.json is compact (no complete run list); individual run files contain calls.
    latest = {key: value for key, value in snapshot.items() if key != "runs"}
    latest["run_reports"] = {"directory": "runs", "filename": "sha256(UTF-8 original job_id).json",
                             "view_semantics": "replaceable projection, never authoritative run state"}
    atomic_json(safe_path(output_dir, "latest.json"), latest, replace=True)
    return changed


def watch(reader, output_dir, revision=None, interval=30, max_polls=None, emit=None):
    emit = emit or (lambda event: print(json_text(event, compact=True), end="", flush=True))
    output_dir = Path(output_dir).resolve()
    reader.incremental = True
    with observer_lock(output_dir, reader.workspace, revision):
        atomic_json(output_dir / "observer-status.json", {"pid": os.getpid(), "started_at_utc": now(),
            "schema_version": SCHEMA, "status": "RUNNING", "interval_seconds": interval,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, replace=True)
        observed, polls = {}, 0
        try:
            while max_polls is None or polls < max_polls:
                try:
                    snapshot = reader.snapshot(revision=revision)
                except sqlite3.OperationalError as exc:
                    # Read contention must not interrupt generation or fake an empty total.
                    if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                        raise
                    emit({"schema_version": SCHEMA, "kind": "audit_read_retry", "observed_at_utc": now(),
                          "error": "LEDGER_BUSY_NO_NEW_SNAPSHOT", "new_model_calls": 0})
                    polls += 1
                    if max_polls is None or polls < max_polls:
                        time.sleep(interval)
                    continue
                changed = publish(snapshot, output_dir, reader.h, emit, observed)
                emit({"schema_version": SCHEMA, "kind": "token_usage_snapshot_summary", "snapshot_at_utc": snapshot["snapshot_at_utc"],
                      "updated_runs": changed, "totals": snapshot["totals"], "by_usage_category": snapshot["by_usage_category"]})
                polls += 1
                if max_polls is None or polls < max_polls:
                    time.sleep(interval)
        finally:
            atomic_json(output_dir / "observer-status.json", {"pid": os.getpid(), "ended_at_utc": now(),
                "schema_version": SCHEMA, "status": "STOPPED", "completed_polls": polls}, replace=True)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise AuditError("INVALID_ARGUMENTS")


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("mode", choices=("snapshot", "watch"))
        parser.add_argument("--workspace", type=Path, required=True)
        parser.add_argument("--revision")
        parser.add_argument("--job-id")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--output-dir", type=Path)
        parser.add_argument("--interval", type=float, default=30)
        parser.add_argument("--max-polls", type=int)
        args = parser.parse_args(argv)
        if not 1 <= args.interval <= 60 or (args.max_polls is not None and args.max_polls < 1):
            raise AuditError("INVALID_POLL_LIMIT")
        reader = Reader(args.workspace)
        if args.mode == "snapshot":
            if args.output_dir or args.max_polls:
                raise AuditError("SNAPSHOT_ARGUMENT_CONFLICT")
            report = reader.snapshot(args.revision, args.job_id)
            if args.output:
                if args.output.resolve().is_relative_to(reader.workspace):
                    raise AuditError("OUTPUT_MUST_BE_OUTSIDE_LEDGER_WORKSPACE")
                atomic_json(args.output, report)
            print(json_text(report), end="", flush=True)
        else:
            if not args.output_dir or args.output or args.job_id:
                raise AuditError("WATCH_REQUIRES_OUTPUT_DIR_ONLY")
            watch(reader, args.output_dir, args.revision, args.interval, args.max_polls)
        return 0
    except KeyboardInterrupt:
        print(json_text({"schema_version": SCHEMA, "ok": False, "error": "OBSERVER_INTERRUPTED"}, compact=True), end="", flush=True)
        return 130
    except (AuditError, OSError, ValueError, TypeError, LookupError, AttributeError,
            ImportError, SyntaxError, RuntimeError, sqlite3.Error) as exc:
        code = str(exc) if isinstance(exc, AuditError) else "AUDIT_FAILED"
        print(json_text({"schema_version": SCHEMA, "ok": False, "error": code,
                         "exception_type": type(exc).__name__}, compact=True), end="", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
