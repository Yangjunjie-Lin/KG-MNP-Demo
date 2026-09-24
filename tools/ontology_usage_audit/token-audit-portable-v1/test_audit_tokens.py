"""Synthetic local fixtures only; zero LLM or remote network calls."""
import contextlib
import hashlib
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audit_tokens", HERE / "audit_tokens.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.h = m.load_helpers()
        with contextlib.closing(sqlite3.connect(self.workspace / "budget.sqlite")) as c:
            c.executescript("CREATE TABLE attempts(request_id TEXT PRIMARY KEY,job_id TEXT,reserved INTEGER,state TEXT,"
                "started_at TEXT,ended_at TEXT,usage INTEGER,result_hash TEXT);"
                "CREATE TABLE monitored_attempts(request_id TEXT PRIMARY KEY,charge INTEGER);")
        with contextlib.closing(sqlite3.connect(self.workspace / "jobs.sqlite")) as c:
            c.execute("CREATE TABLE jobs(job_id TEXT PRIMARY KEY,revision TEXT,phase TEXT,task TEXT,sample TEXT,"
                      "system TEXT,replicate INTEGER,state TEXT,started TEXT,ended TEXT)")
        root = self.workspace / "revisions/r8/code/src/zhigou_toolchain/ontology_io"
        root.mkdir(parents=True)
        source = repr(self.h.PREFIXES["abox"]) + "\n" + repr(self.h.PREFIXES["vocabulary"]) + "\n"
        (root / "kernel.py").write_text(source, encoding="utf-8")
        self.source = root / "kernel.py"
        (self.workspace / "revisions/r8/code-lock.json").write_text(json.dumps({"files": {
            "src/zhigou_toolchain/ontology_io/kernel.py": hashlib.sha256(self.source.read_bytes()).hexdigest()}}), encoding="utf-8")

    def job(self, jid="job1", state="GENERATED", system="TwoAgentKernelV1", started="2020-01-01T00:00:00+00:00"):
        with contextlib.closing(sqlite3.connect(self.workspace / "jobs.sqlite")) as c:
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)", (jid, "r8", "full", "synthetic", "sample1",
                system, 1, state, started, "2020-01-01T00:01:00+00:00" if state in m.TERMINAL else None))
            c.commit()

    def call(self, jid="job1", attempt=1, index=1, state="SUCCEEDED", inp=2, out=3, total=5,
             response=True, repair=False, stage="abox", request_id=None, mismatch=False):
        rid = request_id or f"{jid}:attempt-{attempt:02d}:call-{index}"
        root = self.workspace / "revisions/r8/runs" / jid / f"attempt-{attempt:02d}/calls/{index}"
        root.mkdir(parents=True, exist_ok=True)
        content = {"input": {}, "candidate_vocabulary": {}, "extraction_constraints": "synthetic"} if stage == "abox" else {
            "input": {}, "reuse": {}, "retrieval": []}
        if repair:
            content["feedback"] = {}
        (root / "request.json").write_text(json.dumps({"instruction": self.h.PREFIXES[stage] + " synthetic",
            "content": content, "secret": "SECRET_MUST_NOT_BE_EXPORTED"}), encoding="utf-8")
        payload = {"receipt": {"usage": {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": total}},
                   "public_answer": "SECRET_MUST_NOT_BE_EXPORTED"}
        if response:
            (root / "response.json").write_text(json.dumps(payload), encoding="utf-8")
        with contextlib.closing(sqlite3.connect(self.workspace / "budget.sqlite")) as c:
            c.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)", (rid, jid, 128000, state,
                "2020-01-01T00:00:01+00:00", None if state in {"RESERVED", "INTERRUPTED_UNKNOWN"} else "2020-01-01T00:00:02+00:00",
                total, "wrong" if mismatch else self.h.digest(payload) if response else None))
            c.execute("INSERT INTO monitored_attempts VALUES (?,?)", (rid, total if total is not None else 128000))
            c.commit()
        return root

    def snapshot(self, **kwargs):
        return m.Reader(self.workspace).snapshot(**kwargs)

    def test_modeling_in_benchmark_is_not_testing_or_double_counted(self):
        self.job()
        self.call()
        self.call(jid="preflight", request_id="preflight-post-1", inp=None, out=None, total=7)
        s = self.snapshot()
        self.assertEqual(s["totals"]["total_tokens"], 12)
        self.assertEqual(s["by_usage_category"]["modeling"]["total_tokens"], 5)
        self.assertEqual(s["by_usage_category"]["testing"]["total_tokens"], 7)
        self.assertEqual(s["by_execution_context"]["benchmark"]["total_tokens"], 5)
        self.assertNotIn("SECRET_MUST_NOT_BE_EXPORTED", json.dumps(s))

    def test_stages_use_request_and_frozen_source_not_call_number(self):
        self.job()
        self.call(index=1, stage="abox", repair=True)
        self.call(index=2, stage="vocabulary")
        calls = self.snapshot()["runs"][0]["calls"]
        self.assertEqual([r["step"] for r in calls], ["S3", "S2"])
        self.assertTrue(calls[0]["is_repair"])

    def test_unknown_usage_never_becomes_zero_or_reservation(self):
        self.job(state="FAILED")
        self.call(state="INTERRUPTED_UNKNOWN", inp=None, out=None, total=None, response=False)
        s = self.snapshot()
        self.assertIsNone(s["totals"]["total_tokens"])
        self.assertEqual(s["totals"]["known_total_tokens"], 0)
        self.assertEqual(s["totals"]["budget_charge_tokens_not_usage"], 128000)
        self.assertIsNone(s["runs"][0]["final_total_tokens"])
        self.assertEqual(s["runs"][0]["calls"][0]["usage_status"], "UNKNOWN")

    def test_failed_retry_counted_once_and_keeps_unknown_final_total(self):
        self.job()
        self.call(state="FAILED", total=None, inp=None, out=None, response=False)
        self.call(attempt=2)
        s = self.snapshot()
        self.assertEqual(s["totals"]["caller_attempts"], 2)
        self.assertEqual(s["totals"]["known_total_tokens"], 5)
        self.assertIsNone(s["runs"][0]["final_total_tokens"])

    def test_retry_pending_is_not_final(self):
        self.job(state="PENDING")
        self.call()
        s = self.snapshot()
        self.assertFalse(s["runs"][0]["terminal_at_snapshot"])
        self.assertIsNone(s["runs"][0]["final_total_tokens"])

    def test_linked_pending_job_without_start_keeps_purpose(self):
        self.job(state="PENDING", started=None)
        self.call()
        self.assertEqual(self.snapshot()["by_usage_category"]["modeling"]["caller_attempts"], 1)

    def test_reserved_ignores_late_response(self):
        self.job(state="RUNNING")
        self.call(state="RESERVED", total=None)
        row = self.snapshot()["runs"][0]["calls"][0]
        self.assertEqual(row["usage_status"], "IN_FLIGHT")
        self.assertIsNone(row["input_tokens"])

    def test_response_hash_mismatch_does_not_invent_breakdown(self):
        self.job()
        self.call(mismatch=True)
        row = self.snapshot()["runs"][0]["calls"][0]
        self.assertEqual(row["total_tokens"], 5)
        self.assertIsNone(row["input_tokens"])
        self.assertIn("HASH_MISMATCH_NO_BREAKDOWN_USED", row["issues"])

    def test_inconsistent_breakdown_is_flagged(self):
        self.job()
        self.call(inp=8, out=9)
        s = self.snapshot()
        self.assertEqual(s["totals"]["coverage"], "INCONSISTENT")
        self.assertEqual(s["totals"]["inconsistent_usage_calls"], 1)

    def test_zero_usage_is_real_zero(self):
        self.job()
        self.call(inp=0, out=0, total=0)
        self.assertEqual(self.snapshot()["runs"][0]["final_total_tokens"], 0)

    def test_no_call_job_has_no_inferred_stage_execution(self):
        self.job()
        r = self.snapshot()["runs"][0]
        self.assertEqual(r["final_total_tokens"], 0)
        self.assertEqual(r["calls"], [])
        self.assertTrue(all(s["execution_status"] == "NOT_INFERRED_FROM_TOKEN_AUDIT" for s in r["steps"]))

    def test_empty_scope(self):
        self.assertEqual(self.snapshot()["totals"]["caller_attempts"], 0)

    def test_filter_and_no_silent_missing_job(self):
        self.job()
        self.call()
        self.call(jid="preflight", request_id="preflight-post-1")
        self.assertEqual(self.snapshot(revision="r8")["totals"]["caller_attempts"], 1)
        self.assertEqual(self.snapshot(job_id="preflight")["by_usage_category"]["testing"]["caller_attempts"], 1)
        with self.assertRaisesRegex(m.AuditError, "JOB_NOT_FOUND"):
            self.snapshot(job_id="does-not-exist")

    def test_unknown_system_and_orphan_do_not_become_testing(self):
        self.job(system="NewUnregisteredSystem")
        self.call()
        self.call(jid="unknown", request_id="unknown-probe")
        self.assertEqual(self.snapshot()["by_usage_category"]["unclassified"]["caller_attempts"], 2)

    def test_direct_is_direct_not_five_stage(self):
        self.job(system="DirectGeneralLLM")
        self.call()
        self.assertEqual(self.snapshot()["runs"][0]["calls"][0]["step"], "DIRECT")

    def test_optional_monitor_table_and_no_database_or_network_writes(self):
        self.job()
        self.call()
        with contextlib.closing(sqlite3.connect(self.workspace / "budget.sqlite")) as c:
            c.execute("DROP TABLE monitored_attempts")
        before = {p.name: p.read_bytes() for p in self.workspace.glob("*.sqlite")}
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            s = self.snapshot()
        after = {p.name: p.read_bytes() for p in self.workspace.glob("*.sqlite")}
        self.assertEqual(before, after)
        self.assertEqual(s["totals"]["budget_charge_tokens_not_usage"], 128000)

    def test_database_connection_rejects_writes(self):
        with contextlib.closing(self.h.read_db(self.workspace / "budget.sqlite")) as c, self.assertRaises(sqlite3.OperationalError):
            c.execute("DELETE FROM attempts")

    def test_frozen_source_tampering_rejected(self):
        self.job()
        self.call()
        self.source.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(m.AuditError, "FROZEN_STAGE_SOURCE_CHANGED"):
            self.snapshot()

    def test_dependency_tampering_rejected(self):
        with patch.object(m, "DEPENDENCY_SHA256", "0" * 64), self.assertRaisesRegex(m.AuditError, "AUDITOR_DEPENDENCY_CHANGED"):
            m.load_helpers()

    def test_path_escape_rejected(self):
        with self.assertRaisesRegex(m.AuditError, "ARTIFACT_PATH_ESCAPE"):
            m.safe_path(self.workspace, "..", "secret.json")

    def test_publish_idempotent_and_restart_deduplicates(self):
        self.job()
        self.call()
        output, events = self.root / "output", []
        output.mkdir()
        s = self.snapshot()
        self.assertEqual(m.publish(s, output, self.h, events.append), 1)
        self.assertEqual(m.publish(s, output, self.h, events.append), 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads((output / "latest.json").read_bytes())["totals"]["total_tokens"], 5)

    def test_incremental_reader_reports_changed_calls_only(self):
        self.job(state="RUNNING")
        self.call()
        r = m.Reader(self.workspace)
        r.incremental = True
        self.assertEqual(len(r.snapshot()["runs"]), 1)
        self.assertEqual(len(r.snapshot()["runs"]), 0)
        self.call(index=2)
        s = r.snapshot()
        self.assertEqual(len(s["runs"]), 1)
        self.assertEqual(s["runs"][0]["totals"]["total_tokens"], 10)

    def test_cli_stdout_is_one_json_and_existing_output_preserved(self):
        self.job()
        self.call()
        output = self.root / "snapshot.json"
        args = ["snapshot", "--workspace", str(self.workspace), "--output", str(output)]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(m.main(args), 0)
        self.assertEqual(json.loads(stream.getvalue()), json.loads(output.read_bytes()))
        before = output.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(args), 1)
        self.assertEqual(output.read_bytes(), before)

    def test_watch_emits_json_updates_without_touching_ledger(self):
        self.job()
        self.call()
        events = []
        m.watch(m.Reader(self.workspace), self.root / "watch", interval=1, max_polls=1, emit=events.append)
        self.assertEqual([e["kind"] for e in events], ["run_token_usage_updated", "token_usage_snapshot_summary"])
        self.assertEqual(json.loads((self.root / "watch/observer-status.json").read_bytes())["status"], "STOPPED")

    def test_watch_database_busy_emits_retry_not_zero_snapshot(self):
        reader = m.Reader(self.workspace)
        events = []
        with patch.object(reader, "snapshot", side_effect=sqlite3.OperationalError("database is locked")):
            m.watch(reader, self.root / "watch", interval=1, max_polls=1, emit=events.append)
        self.assertEqual([e["kind"] for e in events], ["audit_read_retry"])
        self.assertFalse((self.root / "watch/latest.json").exists())

    def test_observer_duplicate_scope_and_unrelated_directory_refused(self):
        output = self.root / "watch"
        with m.observer_lock(output, self.workspace, None), self.assertRaisesRegex(m.AuditError, "OBSERVER_ALREADY_RUNNING"), m.observer_lock(output, self.workspace, None):
            self.fail("duplicate observer")
        with self.assertRaisesRegex(m.AuditError, "OBSERVER_SCOPE_CHANGED"), m.observer_lock(output, self.workspace, "r8"):
            self.fail("scope change")
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        (unrelated / "data.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(m.AuditError, "OUTPUT_DIRECTORY_NOT_OWNED"), m.observer_lock(unrelated, self.workspace, None):
            self.fail("unrelated directory")

    def test_watch_cannot_create_output_inside_ledger(self):
        target = self.workspace / "bad-output"
        with self.assertRaisesRegex(m.AuditError, "OUTSIDE_LEDGER_WORKSPACE"), m.observer_lock(target, self.workspace, None):
            self.fail("output inside ledger")
        self.assertFalse(target.exists())

    def test_cli_errors_are_safe_json_not_exception_details(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = m.main(["snapshot", "--workspace", "SECRET_PATH_DOES_NOT_EXIST"])
        self.assertEqual(result, 1)
        self.assertNotIn("SECRET_PATH", stream.getvalue())
        self.assertFalse(json.loads(stream.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
