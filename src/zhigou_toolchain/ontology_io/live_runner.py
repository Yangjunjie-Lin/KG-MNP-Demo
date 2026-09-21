"""Durable full-matrix execution using existing engine + OS-isolated workers.

Model answers are never silently corrected by the supervisor. Code changes
require a new immutable revision. All phases share one global budget ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import configured_client

from .cli import ROOT, load, save
from .contracts import ModelingInput
from .formal_calls import ALL_SYSTEMS, CORE, TASKS, call_cap, task_protocol
from .live_budget import BudgetLedger
from .os_sandbox import DISTRO, VENV, run_job, stage_code, verify_canary
from .provenance import source_identity


def connect(workspace):
    conn = sqlite3.connect(Path(workspace) / "jobs.sqlite", timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def supervisor_lock(workspace):
    path = Path(workspace) / "supervisor.lock"
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def smoke_inputs():
    from .cq4oe import adapt_cq4oe
    text = "North Grove is a woodland. Every woodland is an ecosystem. Sensor Alpha monitors North Grove. Sensor Alpha is a sensor."
    a = ModelingInput(sample_id="smoke-text", benchmark_id="synthetic-engineering", task_id="text-new", dataset_version="v1",
        split="smoke", evaluation_scope="ENGINEERING_CHECK", group_id="smoke-text", mode="TEXT_NEW", text=text)
    b = adapt_cq4oe([{"id": "CQ1", "value": "Which calibration probes are installed in which chambers?"}], sample_id="smoke-cqs", task="cq2onto").model_copy(
        update={"evaluation_scope": "ENGINEERING_CHECK", "split": "smoke"})
    c = ModelingInput(sample_id="smoke-typed", benchmark_id="synthetic-engineering", task_id="schema_guided_abox", dataset_version="v1",
        split="smoke", evaluation_scope="ENGINEERING_CHECK", group_id="smoke-typed", mode="SCHEMA_ABOX",
        text="A is a city. B is a country. A is in B.", allowed_schema={"entity_types": [{"id": "City", "label": "City"}, {"id": "Country", "label": "Country"}],
            "relations": [{"id": "country", "label": "country", "domain": "City", "range": "Country"}], "hierarchy": []})
    return [("llms4ol_2026--flagship", a), ("cq4oe_0_0_1--cq2onto", b), ("llms4ol_2026--reuse", c)]


def initialize(workspace, revision):
    workspace = Path(workspace).resolve()
    ledger = BudgetLedger(workspace / "budget.sqlite")
    ledger.snapshot()  # Refuse initialization without the existing explicit authorization.
    if not revision.isalnum() or len(revision) > 30:
        raise ValueError("INVALID_REVISION_NAME")
    directory = workspace / "revisions" / revision
    directory.mkdir(parents=True, exist_ok=False)
    client = configured_client()
    try:
        binding = {"model_id": client.lock.model_id, "declared_revision": client.lock.revision,
            "reasoning_effort": getattr(client, "reasoning_effort", None), "endpoint_sha256": semantic_hash(client.lock.location)}
    finally:
        client.close()
    source = source_identity(ROOT)
    code_lock = stage_code(ROOT, directory / "code")
    isolation = verify_canary(directory / "code", directory, ROOT / "third_party/downloads/robot-1.9.7.jar")
    pip = subprocess.check_output(["wsl", "-d", DISTRO, "--exec", VENV + "/bin/python", "-m", "pip", "freeze"], timeout=30).decode()
    save(directory / "code-lock.json", code_lock)
    save(directory / "isolation.json", isolation)
    (directory / "worker-dependencies.lock").write_text(pip, encoding="utf-8")
    manifest = {"revision": revision, "source_identity": source, "worker_code_sha256": code_lock["sha256"],
        "binding": binding, "isolation": isolation, "worker_dependencies_sha256": hashlib.sha256(pip.encode()).hexdigest(),
        "phase_order": ["smoke", "pilot", "full"], "pilot_selection": "3_SORTED_HASH_GROUPS_PER_TASK_FROM_FROZEN_PILOT_NOT_FULL",
        "failure_policy": "RETAIN_ALL_NO_AUTOMATIC_RETRY_NO_SUCCESS_SUBSET_PRIMARY", "source_qualification": "LOCAL_HOLDOUT_POSSIBLE_PUBLIC_CONTAMINATION",
        "full_quality_scores_visible_to_generator": False, "framework": "EXISTING_NATIVE_SCORER_AFTER_FREEZE", "inference_concurrency": 1}
    manifest["launcher_sha256"] = {name: hashlib.sha256((ROOT / "src/zhigou_toolchain/ontology_io" / name).read_bytes()).hexdigest()
        for name in ("live_runner.py", "os_sandbox.py", "live_broker.py", "live_budget.py")}
    save(directory / "manifest.json", manifest)
    models = {k: binding[k] for k in ("model_id", "declared_revision", "reasoning_effort")}
    protocols = {key: task_protocol(key, **models) for key in TASKS}
    for key, protocol in protocols.items():
        save(directory / "protocols" / (key + ".json"), protocol.model_dump(mode="json"))
    phases = {"smoke": smoke_inputs(), "pilot": [], "full": []}
    old = ROOT / "runtime_reports/ontology-io-final-matrix-20260913"
    input_locks = {}
    for key in TASKS:
        prepared = old / "full/prepared" / key
        lock, rows = load(prepared / "prepared-lock.json"), load(prepared / "generation/inputs.json")
        if semantic_hash(rows) != lock["input_sha256"]:
            raise ValueError("FROZEN_FULL_INPUT_CHANGED")
        samples = [ModelingInput.model_validate(r) for r in rows]
        phases["full"].extend((key, s) for s in samples)
        input_locks[key] = {"legacy_prepared": str(prepared), "lock": lock, "effective_input_sha256": semantic_hash([s.model_dump(mode="json") for s in samples])}
        if key.startswith("llms4ol"):
            pilot_path = old / "pilot/prepared" / key
            pilot_rows = load(pilot_path / "generation/inputs.json")
            pilot_lock = load(pilot_path / "prepared-lock.json")
            if semantic_hash(pilot_rows) != pilot_lock["input_sha256"]:
                raise ValueError("FROZEN_PILOT_INPUT_CHANGED")
            pilot = [ModelingInput.model_validate(r) for r in pilot_rows]
            selected = sorted({s.group_id for s in pilot})[:3]
            chosen = [s for s in pilot if s.group_id in selected]
            if {s.group_id for s in chosen} & {s.group_id for s in samples}:
                raise ValueError("PILOT_FULL_SOURCE_OVERLAP")
            phases["pilot"].extend((key, s) for s in chosen)
    save(directory / "input-locks.json", input_locks)
    with connect(workspace) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS inputs (revision TEXT, phase TEXT, task TEXT, sample TEXT, payload TEXT,
                PRIMARY KEY(revision,phase,task,sample));
            CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, revision TEXT, phase TEXT, task TEXT, sample TEXT,
                system TEXT, replicate INTEGER, max_calls INTEGER, state TEXT, order_key TEXT, started TEXT, ended TEXT,
                result_path TEXT, result_hash TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(revision,phase,state,order_key);
        """)
        for phase, samples in phases.items():
            for key, sample in samples:
                conn.execute("INSERT INTO inputs VALUES (?,?,?,?,?)", (revision, phase, key, sample.sample_id, sample.model_dump_json()))
                protocol = protocols[key]
                for system in (ALL_SYSTEMS if phase == "full" else CORE):
                    try:
                        cap = call_cap(sample, protocol, system)
                        state = "PENDING"
                    except ValueError as exc:
                        if str(exc) != "ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE":
                            raise
                        cap, state = 0, "NOT_APPLICABLE"
                    for rep in range(3 if phase == "full" else 1):
                        identity = {"revision": revision, "phase": phase, "task": key, "sample": sample.sample_id, "system": system, "replicate": rep}
                        jid = semantic_hash(identity)[:24]
                        # Core first; paired sample/repeat blocks; fixed hash rotation of systems.
                        order = f"{int(system not in CORE)}:{key}:{sample.group_id}:{rep}:" + semantic_hash({**identity, "order_seed": 271828})
                        conn.execute("INSERT INTO jobs (job_id,revision,phase,task,sample,system,replicate,max_calls,state,order_key) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (jid, revision, phase, key, sample.sample_id, system, rep, cap, state, order))
    save(workspace / "active-revision.json", {"revision": revision, "manifest_sha256": semantic_hash(manifest)})
    return status(workspace, revision)


def status(workspace, revision):
    with connect(workspace) as conn:
        rows = [dict(r) for r in conn.execute("SELECT phase,state,COUNT(*) AS count FROM jobs WHERE revision=? GROUP BY phase,state", (revision,))]
    return {"revision": revision, "jobs": rows, "budget": BudgetLedger(Path(workspace) / "budget.sqlite").snapshot(), "research_score": None}


def execute(workspace, revision, phase, *, max_jobs=None):
    workspace = Path(workspace).resolve()
    rev = workspace / "revisions" / revision
    manifest = load(rev / "manifest.json")
    if not manifest["isolation"]["passed"]:
        raise ValueError("OS_ISOLATION_PRECHECK_REQUIRED")
    for name, digest in manifest["launcher_sha256"].items():
        if hashlib.sha256((ROOT / "src/zhigou_toolchain/ontology_io" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("LAUNCHER_CHANGED_REQUIRE_NEW_REVISION")
    if phase != "smoke":
        previous = "smoke" if phase == "pilot" else "pilot"
        with connect(workspace) as conn:
            pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE revision=? AND phase=? AND state IN ('PENDING','RUNNING')", (revision, previous)).fetchone()[0]
            failed_runtime = conn.execute("SELECT COUNT(*) FROM jobs WHERE revision=? AND phase=? AND error IS NOT NULL", (revision, previous)).fetchone()[0]
        if pending or failed_runtime:
            raise ValueError("PREVIOUS_PHASE_NOT_COMPLETE_OR_RUNTIME_FAILED")
    lock = load(rev / "code-lock.json")
    for name, digest in lock["files"].items():
        if hashlib.sha256((rev / "code" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("FROZEN_WORKER_CODE_CHANGED")
    ledger = BudgetLedger(workspace / "budget.sqlite")
    completed = 0
    with connect(workspace) as conn:
        # An interrupted job is not silently retried and its calls stay charged.
        conn.execute("UPDATE jobs SET state='FAILED', error='INTERRUPTED_UNKNOWN_OUTCOME' WHERE revision=? AND phase=? AND state='RUNNING'", (revision, phase))
    while max_jobs is None or completed < max_jobs:
        if (workspace / "STOP").exists():
            break
        with connect(workspace) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM jobs WHERE revision=? AND phase=? AND state='PENDING' ORDER BY order_key LIMIT 1", (revision, phase)).fetchone()
            if row is None:
                break
            row = dict(row)
            sample = json.loads(conn.execute("SELECT payload FROM inputs WHERE revision=? AND phase=? AND task=? AND sample=?",
                (revision, phase, row["task"], row["sample"])).fetchone()[0])
            conn.execute("UPDATE jobs SET state='RUNNING', started=? WHERE job_id=?", (datetime.now(UTC).isoformat(), row["job_id"]))
        protocol = load(rev / "protocols" / (row["task"] + ".json"))
        job = {"sample": sample, "protocol": protocol, "system": row["system"], "replicate_id": row["replicate"], "max_calls": row["max_calls"]}
        directory = rev / "runs" / row["job_id"]
        result_hash, result_path, error = None, None, None
        try:
            receipt = run_job(job, code=rev / "code", directory=directory, reasoner=ROOT / "third_party/downloads/robot-1.9.7.jar",
                ledger=ledger, job_id=row["job_id"], endpoint_sha256=manifest["binding"]["endpoint_sha256"])
            result_path = Path(receipt["result_path"])
            if result_path.is_symlink() or not result_path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("WORKER_RESULT_PATH_INVALID")
            result = load(result_path)
            result_hash = semantic_hash(result)
            state = result["status"]
            save(directory / "execution-receipt.json", receipt)
            if result.get("kernel", {}).get("validation", {}).get("validation_blockers"):
                error = "VALIDATOR_RUNTIME_INCOMPLETE"
            for response_path in (directory / "calls").glob("*/response.json"):
                response = load(response_path)
                if not response["ok"] and (response.get("transport") or response.get("error_code", "").startswith("TRANSPORT_")):
                    error = "TRANSPORT_INFRASTRUCTURE_FAILURE"
        except Exception as exc:  # noqa: BLE001 - durable failure denominator, no secret exception text
            state, error = "FAILED", type(exc).__name__
            directory.mkdir(parents=True, exist_ok=True)
            save(directory / "execution-error.json", {"type": error, "state": state, "budget": ledger.snapshot()})
        with connect(workspace) as conn:
            conn.execute("UPDATE jobs SET state=?, ended=?, result_path=?, result_hash=?, error=? WHERE job_id=?",
                (state, datetime.now(UTC).isoformat(), str(result_path) if result_path else None, result_hash, error, row["job_id"]))
        completed += 1
        progress = status(workspace, revision)
        save(workspace / "progress.json", {**progress, "last_job": row["job_id"], "last_status": state, "last_error": error})
        print(json.dumps({"phase": phase, "job": row["job_id"], "state": state, "error": error, "calls": progress["budget"]["calls"]}), flush=True)
        # Environment failures pause, rather than consuming the entire corpus.
        if error is not None or ledger.snapshot()["states"].get("USAGE_BOUND_VIOLATION"):
            break
    return status(workspace, revision)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "run", "status"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--phase", choices=["smoke", "pilot", "full"], default="smoke")
    parser.add_argument("--max-jobs", type=int)
    args = parser.parse_args(argv)
    if args.command == "init":
        with supervisor_lock(args.workspace):
            result = initialize(args.workspace, args.revision)
    elif args.command == "run":
        with supervisor_lock(args.workspace):
            result = execute(args.workspace, args.revision, args.phase, max_jobs=args.max_jobs)
    else:
        result = status(args.workspace, args.revision)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
