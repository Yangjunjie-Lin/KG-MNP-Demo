"""Global budget, IPC and OS policy tests; no paid inference in this module."""
from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock
from zhigou_toolchain.ontology_io.cli import load, save
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.formal_calls import task_protocol
from zhigou_toolchain.ontology_io.live_broker import dispatch
from zhigou_toolchain.ontology_io.live_budget import BudgetLedger
from zhigou_toolchain.ontology_io.live_inventory import snapshot
from zhigou_toolchain.ontology_io.live_runner import supervisor_lock
from zhigou_toolchain.ontology_io.os_sandbox import command, stage_code


def ledger(tmp_path, calls=3, tokens=100):
    value = BudgetLedger(tmp_path / "budget.sqlite")
    value.initialize({"user_request": "EXPLICIT_SYNTHETIC_TEST_AUTHORIZATION", "max_calls": calls, "max_reserved_tokens": tokens})
    return value


def test_global_cap_is_atomic_across_threads(tmp_path):
    budget = ledger(tmp_path, calls=5, tokens=50)

    def reserve(i):
        try:
            budget.reserve(str(i), "same-experiment", 10)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(reserve, range(20)))
    assert sum(results) == 5
    assert budget.snapshot()["calls"] == 5 and budget.snapshot()["remaining_reserved_tokens"] == 0


def test_unknown_crash_and_failed_calls_never_refund_or_repeat(tmp_path):
    budget = ledger(tmp_path)
    budget.reserve("a", "job", 30)
    budget.reserve("b", "job", 30)
    budget.finish("b", status="FAILED", usage=None, result_hash="x")
    resumed = BudgetLedger(tmp_path / "budget.sqlite")
    assert resumed.snapshot()["reserved_tokens"] == 60 and resumed.snapshot()["known_tokens"] is None
    with pytest.raises(sqlite3.IntegrityError):
        resumed.reserve("a", "job", 30)
    assert resumed.snapshot()["calls"] == 2
    with pytest.raises(ValueError, match="IMMUTABLE"):
        resumed.initialize({"user_request": "different", "max_calls": 100, "max_reserved_tokens": 10000})


def test_provider_usage_overrun_is_retained_and_stops(tmp_path):
    budget = ledger(tmp_path)
    budget.reserve("a", "job", 20)
    with pytest.raises(ValueError, match="EXCEEDED"):
        budget.finish("a", status="SUCCEEDED", usage=30, result_hash="x")
    assert budget.snapshot()["states"] == {"USAGE_BOUND_VIOLATION": 1}
    assert budget.snapshot()["reserved_tokens"] == 30
    with pytest.raises(ValueError, match="LATCHED"):
        budget.reserve("another", "job", 1)


def test_broker_forbids_file_or_url_schema_oracle_before_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr("zhigou_toolchain.ontology_io.live_broker.configured_client", lambda: pytest.fail("must reject before client"))
    request = {"instruction": "x", "content": {}, "schema": {"$ref": "file:///scoring/gold.json"}, "allowed_iris": []}
    with pytest.raises(ValueError, match="REFERENCE_FORBIDDEN"):
        dispatch(request, protocol=None, ledger=ledger(tmp_path), job_id="job", request_id="id", directory=tmp_path / "call")


def test_os_mount_policy_has_no_host_drive_home_or_network_access(tmp_path):
    args = command(tmp_path / "code", tmp_path / "input", tmp_path / "output", tmp_path / "robot.jar")
    assert "--unshare-all" in args and "--unshare-user" in args and "--disable-userns" in args
    assert "--clearenv" in args and "--share-net" not in args
    writable = [args[i + 1:i + 3] for i, a in enumerate(args) if a == "--bind"]
    assert len(writable) == 1 and writable[0][1] == "/out"
    mounts = [args[i + 2] for i, a in enumerate(args) if a in {"--bind", "--ro-bind"}]
    assert "/mnt" not in mounts and "/home" not in mounts and "/" not in mounts


def test_source_snapshot_does_not_include_tutorial_answers_tests_or_scoring(tmp_path):
    root = tmp_path / "repo"
    (root / "src/zhigou_toolchain/modeling/five_stage/resources/tutorial/output").mkdir(parents=True)
    (root / "src/zhigou_toolchain/__init__.py").write_text("# code")
    (root / "src/zhigou_toolchain/modeling/five_stage/resources/tutorial/output/gold.json").write_text("SECRET")
    (root / "src/kg_mnp").mkdir()
    copied = stage_code(root, tmp_path / "frozen")
    assert set(copied["files"]) == {"zhigou_toolchain/__init__.py"}


def test_only_one_supervisor_can_run(tmp_path):
    with supervisor_lock(tmp_path), pytest.raises(OSError), supervisor_lock(tmp_path):
        pass


@pytest.mark.parametrize("ok,completion", [(False, 23), (False, 27832), (True, 27832)])
def test_broker_accounts_for_rejected_response_and_latches_any_overrun(tmp_path, monkeypatch, ok, completion):
    protocol = task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="r1", reasoning_effort=None)
    client = CompatibleClient(ModelLock("fixture", "r1", "http://localhost:1/v1"))
    monkeypatch.setattr("zhigou_toolchain.ontology_io.live_broker.configured_client", lambda: client)
    response = {"ok": ok, "receipt" if ok else "public_response": {
        "usage": {"prompt_tokens": 11, "completion_tokens": completion, "total_tokens": completion + 11}}}
    monkeypatch.setattr("zhigou_toolchain.ontology_io.live_broker.subprocess.run", lambda *a, **kw:
        SimpleNamespace(returncode=0, stdout=json.dumps(response).encode()))
    budget = ledger(tmp_path, tokens=100000)
    request = {"instruction": "x", "content": {}, "schema": {"type": "object"}, "allowed_iris": []}
    options = {"protocol": protocol, "ledger": budget, "job_id": "job", "request_id": "attempt", "directory": tmp_path / "call"}
    if completion > 8192:
        with pytest.raises(ValueError, match="EXCEEDED"):
            dispatch(request, **options)
        assert budget.snapshot()["provider_limit_latched"]
        with pytest.raises(ValueError, match="LATCHED"):
            budget.reserve("later", "job", 1)
    else:
        assert dispatch(request, **options) == response
        assert budget.snapshot()["states"] == {"FAILED": 1}
    assert budget.snapshot()["known_tokens"] == completion + 11
    assert json.loads((tmp_path / "call/response.json").read_bytes()) == response


def snapshot_fixture(tmp_path):
    from tests.upgrade.test_ontology_io_integrity import (
        RecordedClient,
        protocol,
        sample,
    )
    task, item, p = "llms4ol_2026--flagship", sample(), protocol()
    rev = tmp_path / "revisions/r1"
    path = rev / "runs/smoke/output/result"
    result = generate_sample(item, p, "DirectGeneralLLM", path, client=RecordedClient([{"triples": [["Oak", "is-a", "Tree"]]}]))
    response = {"ok": True, "receipt": result["calls"][0]}
    save(rev / "runs/smoke/calls/1/response.json", response)
    budget = ledger(tmp_path)
    budget.reserve("smoke:call-1", "smoke", 20)
    budget.finish("smoke:call-1", status="SUCCEEDED", usage=None, result_hash=semantic_hash(response))
    save(rev / "manifest.json", {"binding": {"model_id": p.model_id, "declared_revision": p.declared_revision},
        "source_identity": {"commit": "a" * 40, "fingerprint": {"digest": "b" * 64}}})
    save(rev / "protocols" / (task + ".json"), p.model_dump(mode="json"))
    with sqlite3.connect(tmp_path / "jobs.sqlite") as conn:
        conn.executescript("""
            CREATE TABLE jobs (job_id TEXT,revision TEXT,phase TEXT,task TEXT,sample TEXT,system TEXT,
                replicate INTEGER,state TEXT,result_path TEXT,result_hash TEXT,error TEXT);
            CREATE TABLE inputs (revision TEXT,phase TEXT,task TEXT,sample TEXT,payload TEXT);
        """)
        for phase in ("smoke", "pilot", "full"):
            conn.execute("INSERT INTO inputs VALUES (?,?,?,?,?)", ("r1", phase, task, item.sample_id, item.model_dump_json()))
        rows = [("smoke", "smoke", "GENERATED", "DirectGeneralLLM", 0, str(path / "result.json"), semantic_hash(result)),
            ("pilot", "pilot", "FAILED", "DirectGeneralLLM", 0, None, None),
            *[(f"full-{rep}", "full", "PENDING", "DirectGeneralLLM", rep, None, None) for rep in range(3)],
            ("na", "full", "NOT_APPLICABLE", "NoRetrieval", 0, None, None)]
        for jid, phase, state, system, rep, result_path, result_hash in rows:
            conn.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (jid, "r1", phase, task, item.sample_id, system, rep, state, result_path, result_hash, None))
    return path


def test_snapshot_retains_every_slot_and_replays_without_credentials_gold_or_network(tmp_path, monkeypatch):
    snapshot_fixture(tmp_path)
    before = {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in ("jobs.sqlite", "budget.sqlite")}
    read_bytes = Path.read_bytes

    def guarded_read(path):
        assert "scoring" not in path.parts and "gold.json" not in path.parts
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("offline means no network"))
    monkeypatch.setattr(httpx.Client, "request", lambda *a, **k: pytest.fail("offline means no network"))
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_TEXT_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name in ("first", "second"):
        result = snapshot(tmp_path, "r1", tmp_path / name)
        assert result["model_calls"] == 0 and result["job_slots"] == 6 and result["verified_generated_artifacts"] == 1
    assert load(tmp_path / "first/report.json") == load(tmp_path / "second/report.json")
    lock = load(tmp_path / "first/evidence-lock.json")
    assert list(lock) == sorted(lock)
    report = load(tmp_path / "first/report.json")
    full = next(r for r in report["results"] if r["phase"] == "full" and r["system"] == "DirectGeneralLLM")
    assert full["sample_count"] == full["group_count"] == 1 and full["planned_runs"] == full["not_run"] == 3
    assert full["score"] is None and full["tokens"] is None and full["completion"] == 0
    assert len((tmp_path / "first/jobs.jsonl").read_text().splitlines()) == 6
    assert load(tmp_path / "first/comparison.json")["improvement_supported"] is None
    assert before == {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in before}
    with pytest.raises(FileExistsError):
        snapshot(tmp_path, "r1", tmp_path / "first")


@pytest.mark.parametrize("tamper", ["result", "artifact", "response"])
def test_snapshot_fails_closed_on_changed_frozen_evidence(tmp_path, tamper):
    path = snapshot_fixture(tmp_path)
    if tamper == "result":
        save(path / "result.json", {"status": "GENERATED", "fake": True})
    elif tamper == "artifact":
        (path / "artifacts/ontology.ttl").write_text("", encoding="utf-8")
    else:
        save(tmp_path / "revisions/r1/runs/smoke/calls/1/response.json", {"ok": True, "fake": True})
    with pytest.raises(ValueError, match="CHANGED"):
        snapshot(tmp_path, "r1", tmp_path / "export")
    assert not (tmp_path / "export").exists()
