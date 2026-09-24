"""Read-only token snapshot; no inference, DB writes, scoring or source edits.

Uses only Python standard library, including the bundled runtime's sqlite3.
All token totals originate in the original caller ledger. Response artifacts
only add provider input/output counters after canonical-hash verification.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def integer(value):
    return value if type(value) is int and value >= 0 else None


def provider_usage(response):
    metadata = (response or {}).get("receipt") or (response or {}).get("public_response") or response or {}
    usage = metadata.get("usage") or {}
    return {"input": integer(usage.get("prompt_tokens", usage.get("input_tokens"))),
            "output": integer(usage.get("completion_tokens", usage.get("output_tokens"))),
            "total": integer(usage.get("total_tokens"))}


def diagnostic_artifacts(workspace):
    """Only explicitly identified public diagnostic artifacts; never private configs."""
    reports = workspace.parent
    paths = [reports / "ontology-luna-20260921/live-limit-probe-01/response.json",
             reports / "gateway-repair-20260921/forwarding-probe-02/response-public.json"]
    endpoint = reports / "endpoint-recheck-20260921/live-matrix-01"
    if endpoint.is_dir():
        paths.extend(sorted(endpoint.glob("*/response-public.json")))
    found = {}
    for path in paths:
        result_path = path.with_name("result.json")
        if not path.is_file() or not result_path.is_file():
            continue
        if not path.resolve().is_relative_to(reports.resolve()) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("DIAGNOSTIC_PATH_ESCAPE")
        rid = json.loads(result_path.read_bytes()).get("request_id")
        if isinstance(rid, str):
            found[rid] = json.loads(path.read_bytes())
    preflight = workspace / "probe-result.json"
    if preflight.is_file():
        found["preflight-post-1"] = json.loads(preflight.read_bytes()).get("reply")
    return found


def read_db(path):
    conn = sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def aggregate(rows):
    rows = list(rows)
    return {"calls": len(rows), "known_total": sum(r["total_tokens"] for r in rows if r["total_tokens"] is not None),
        "known_input": sum(r["input_tokens"] for r in rows if r["input_tokens"] is not None),
        "known_output": sum(r["output_tokens"] for r in rows if r["output_tokens"] is not None),
        "unknown_total_calls": sum(r["total_tokens"] is None for r in rows),
        "missing_breakdown_calls": sum(r["input_tokens"] is None or r["output_tokens"] is None for r in rows),
        "budget_charge": sum(r["budget_charge"] for r in rows),
        "exact_total": sum(r["total_tokens"] for r in rows) if all(r["total_tokens"] is not None for r in rows) else None}


PREFIXES = {
    "reuse": "Round 1: rank supplied ontology cards",
    "vocabulary": "Design the source-supported class, entity and relation vocabulary",
    "legacy_plan": "Plan the requested primitive ontology",
    "triples": "Construct primitive ontology triples",
    "abox": "Extract every source-supported factual triple",
    "tbox": "Build a complete OWL TBox in Turtle",
    "terms": "Identify all classes and properties required by each CQ",
}


def classify(request, system, source_constants):
    """Attribute captured requests by validated frozen-source signatures, not call number."""
    if request is None:
        return "UNKNOWN", "未取得请求记录", "", False, "NO_RECORDED_REQUEST"
    instruction, content = request.get("instruction", ""), request.get("content") or {}
    if not isinstance(instruction, str) or not isinstance(content, dict):
        return "UNKNOWN", "请求结构未匹配", "", False, "UNMATCHED"
    repair = "feedback" in content and content["feedback"] is not None
    if system in {"DirectGeneralLLM", "DirectBudgetControl", "DirectRetrievalContext"}:
        revised = "Independently self-check your previous output" in instruction
        return "DIRECT", "直接复核" if revised else "直接生成", "直接对照", False, "RECORDED_SYSTEM_DIRECT_NOT_FIVE_STAGE"
    supported = {name for name, prefix in PREFIXES.items() if instruction.startswith(prefix)
                 and any(s.startswith(prefix) for s in source_constants)}
    if "reuse" in supported and {"object_families", "cards", "business_rules"} <= content.keys():
        return "S2", "本体复用选择", "RuleAgent", repair, "RECORDED_REQUEST_AND_FROZEN_SOURCE_SIGNATURE"
    if "vocabulary" in supported and {"input", "reuse", "retrieval"} <= content.keys():
        return "S2", "词汇设计修复" if repair else "词汇设计", "RuleAgent", repair, "RECORDED_REQUEST_AND_FROZEN_SOURCE_SIGNATURE"
    if supported & {"tbox", "terms"} and {"input", "reuse", "retrieval"} <= content.keys():
        return "S2", "CQ设计修复" if repair else "CQ本体设计", "RuleAgent", repair, "RECORDED_REQUEST_AND_FROZEN_SOURCE_SIGNATURE"
    if "legacy_plan" in supported and {"input", "profile"} <= content.keys():
        return "S2", "本体规划", "RuleAgent", repair, "RECORDED_REQUEST_AND_FROZEN_SOURCE_SIGNATURE"
    if supported & {"triples", "abox"} and ({"input", "candidate_vocabulary", "extraction_constraints"} <= content.keys()
                                           or {"input", "design"} <= content.keys()):
        return "S3", "事实修复" if repair else "事实抽取", "TaskExecutionAgent", repair, "RECORDED_REQUEST_AND_FROZEN_SOURCE_SIGNATURE"
    return "UNKNOWN", "步骤未匹配", "", repair, "UNMATCHED_NO_GUESSED_STAGE"


def extract(workspace, active_revision):
    started = datetime.now(UTC).isoformat()
    with closing(read_db(workspace / "budget.sqlite")) as conn:
        conn.execute("BEGIN")
        attempts = [dict(r) for r in conn.execute("SELECT a.*,COALESCE(m.charge,a.reserved) AS budget_charge,m.policy_id "
            "FROM attempts a LEFT JOIN monitored_attempts m USING(request_id) ORDER BY a.started_at,a.request_id")]
        base_totals = dict(conn.execute("SELECT COUNT(*) AS calls,COALESCE(SUM(usage),0) AS known_total,"
            "SUM(CASE WHEN usage IS NULL THEN 1 ELSE 0 END) AS unknown_total_calls FROM attempts").fetchone())
        local_veto = {r[0] for r in conn.execute("SELECT request_id FROM operator_terminal_transport_continuations "
            "WHERE json_extract(document,'$.failure_class')='PROVEN_LOCAL_PRIVATE_INPUT_VETO'")}
        conn.commit()
    ledger_read_ended = datetime.now(UTC).isoformat()
    with closing(read_db(workspace / "jobs.sqlite")) as conn:
        conn.execute("BEGIN")
        jobs = {r["job_id"]: dict(r) for r in conn.execute("SELECT job_id,revision,phase,task,sample,system,replicate,state,started,ended "
            "FROM jobs WHERE started IS NOT NULL OR state IN ('GENERATED','FAILED','RUNNING')")}
        inventory = [dict(r) for r in conn.execute("SELECT phase,state,COUNT(*) AS count FROM jobs WHERE revision=? GROUP BY phase,state", (active_revision,))]
        conn.commit()
    metadata_read_ended = datetime.now(UTC).isoformat()
    constants, locks, issues = {}, {}, []

    def source_constants(revision):
        if revision in constants:
            return constants[revision]
        root = workspace / "revisions" / revision
        lock_path = root / "code-lock.json"
        if not lock_path.exists():
            constants[revision] = []
            return []
        lock = json.loads(lock_path.read_bytes())
        values, hashes = [], {}
        for name, expected in lock["files"].items():
            if not name.endswith(("ontology_io/kernel.py", "ontology_io/engine.py", "modeling/five_stage/assistance.py")):
                continue
            path = root / "code" / name
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("FROZEN_STAGE_SOURCE_CHANGED")
            hashes[name] = expected
            values.extend(n.value for n in ast.walk(ast.parse(raw)) if isinstance(n, ast.Constant) and isinstance(n.value, str))
        constants[revision], locks[revision] = values, hashes
        return values

    diagnostics = diagnostic_artifacts(workspace)
    rows = []
    for call in attempts:
        job = jobs.get(call["job_id"])
        revision = job["revision"] if job else "HISTORICAL_PROBE"
        request, response, response_state, req_hash = None, None, "NO_MATCHED_ARTIFACT", ""
        match = re.fullmatch(re.escape(call["job_id"]) + r":(?:attempt-(\d+):)?call-(\d+)", call["request_id"])
        attempt_number = int(match[1]) if match and match[1] else 1 if match else None
        call_number = int(match[2]) if match else None
        if job and match:
            call_dir = workspace / "revisions" / revision / "runs" / call["job_id"]
            if match[1]:
                call_dir /= "attempt-" + match[1]
            call_dir = call_dir / "calls" / match[2]
            if not call_dir.resolve().is_relative_to(workspace.resolve()) or any(p.is_symlink() for p in (call_dir, *call_dir.parents)):
                raise ValueError("CALL_PATH_ESCAPE")
            request_path, response_path = call_dir / "request.json", call_dir / "response.json"
            if request_path.is_file():
                raw = request_path.read_bytes()
                request, req_hash = json.loads(raw), hashlib.sha256(raw).hexdigest()
            if call["state"] == "RESERVED":
                response_state = "IN_FLIGHT_AT_SNAPSHOT"
            elif response_path.is_file():
                candidate = json.loads(response_path.read_bytes())
                if digest(candidate) != call["result_hash"]:
                    response_state = "HASH_MISMATCH_NO_BREAKDOWN_USED"
                    issues.append({"request_id": call["request_id"], "issue": response_state})
                else:
                    response, response_state = candidate, "VERIFIED_CANONICAL_SHA256"
        elif call["request_id"] in diagnostics and call["state"] != "RESERVED":
            candidate = diagnostics[call["request_id"]]
            if digest(candidate) != call["result_hash"]:
                response_state = "HASH_MISMATCH_NO_BREAKDOWN_USED"
                issues.append({"request_id": call["request_id"], "issue": response_state})
            else:
                response, response_state = candidate, "VERIFIED_CANONICAL_SHA256_DIAGNOSTIC"
        usage = provider_usage(response)
        input_tokens, output_tokens = usage["input"], usage["output"]
        total_tokens = integer(call["usage"])
        if call["state"] == "RESERVED":
            input_tokens, output_tokens, total_tokens = None, None, None
        consistent = (input_tokens is not None and output_tokens is not None and total_tokens is not None
                      and input_tokens + output_tokens == total_tokens and usage["total"] == total_tokens)
        if input_tokens is not None and output_tokens is not None and total_tokens is not None and not consistent:
            issues.append({"request_id": call["request_id"], "issue": "INPUT_OUTPUT_TOTAL_MISMATCH"})
        stage, purpose, role, repair, stage_basis = classify(request, job["system"] if job else "", source_constants(revision) if job else [])
        if not job:
            stage, purpose, role, stage_basis = "HISTORICAL_PROBE", "历史诊断（阶段不适用）", "", "LEDGER_ONLY_NO_GUESSED_STAGE"
        usage_status = ("COMPLETE" if consistent else "INCONSISTENT" if input_tokens is not None and output_tokens is not None and total_tokens is not None
                        else "TOTAL_ONLY" if total_tokens is not None else "IN_FLIGHT" if call["state"] == "RESERVED" else "UNKNOWN")
        rows.append({"revision": revision, "phase": job["phase"] if job else "diagnostic", "task": job["task"] if job else "diagnostic",
            "system": job["system"] if job else "diagnostic", "job_id": call["job_id"], "sample_id": job["sample"] if job else "",
            "replicate": job["replicate"] if job else None, "attempt": attempt_number, "call_index": call_number,
            "stage": stage, "purpose": purpose, "role": role, "is_repair": repair,
            "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens,
            "usage_status": usage_status, "state": call["state"], "budget_charge": call["budget_charge"],
            "request_id": call["request_id"], "started_at_utc": call["started_at"], "ended_at_utc": call["ended_at"],
            "request_file_sha256": req_hash, "response_semantic_sha256": call["result_hash"] or "",
            "response_verification": response_state, "stage_basis": stage_basis,
            "call_qualification": "LOCAL_VETO_REPRODUCED_HISTORICAL_USAGE_UNKNOWN" if call["request_id"] in local_veto else "REGISTERED_CALLER_ATTEMPT_NOT_INDEPENDENT_PHYSICAL_HTTP_COUNT"})
    if len({r["request_id"] for r in rows}) != len(rows):
        raise ValueError("DUPLICATE_LEDGER_CALL")
    all_totals = aggregate(rows)
    if any(all_totals[k] != base_totals[k] for k in ("calls", "known_total", "unknown_total_calls")):
        raise ValueError("LEDGER_RECONCILIATION_FAILED")
    active = [r for r in rows if r["revision"] == active_revision]
    full = [r for r in active if r["phase"] == "full"]
    scopes = [{"scope": "全部历史（含诊断、失败与重试）", **all_totals},
              {"scope": "当前r8全部阶段", **aggregate(active)},
              {"scope": "当前r8全量阶段", **aggregate(full)}]
    groups = defaultdict(list)
    for r in active:
        groups[(r["phase"], r["system"], r["stage"], r["purpose"], r["role"], r["is_repair"])].append(r)
    stages = [{"phase": k[0], "system": k[1], "stage": k[2], "purpose": k[3], "role": k[4], "is_repair": k[5], **aggregate(v)} for k, v in sorted(groups.items())]
    by_job = defaultdict(list)
    for row in rows:
        by_job[row["job_id"]].append(row)
    processes = []
    for job_id, job in sorted(jobs.items(), key=lambda pair: (pair[1]["revision"], pair[1]["phase"], pair[1]["started"] or "", pair[0])):
        selected = by_job.get(job_id, [])
        if not selected and job["state"] == "RUNNING" and (job["started"] or "") > started:
            continue
        values = aggregate(selected)
        final_at_cutoff = bool(job["ended"] and datetime.fromisoformat(job["ended"]) <= datetime.fromisoformat(started)
                               and job["state"] in {"GENERATED", "FAILED"})
        processes.append({**job, **values, "final_total": values["exact_total"] if final_at_cutoff else None,
            "total_status": "完整报告用量" if final_at_cutoff and values["exact_total"] is not None else "用量不完整或仍在执行",
            "execution_attempts_with_calls": len({r["attempt"] for r in selected}),
            "s2_known_total": sum(r["total_tokens"] or 0 for r in selected if r["stage"] == "S2"),
            "s3_known_total": sum(r["total_tokens"] or 0 for r in selected if r["stage"] == "S3"),
            "direct_known_total": sum(r["total_tokens"] or 0 for r in selected if r["stage"] == "DIRECT"),
            "unclassified_known_total": sum(r["total_tokens"] or 0 for r in selected if r["stage"] == "UNKNOWN")})
    active_processes = [r for r in processes if r["revision"] == active_revision]
    if sum(r["known_total"] for r in active_processes) != aggregate(active)["known_total"]:
        raise ValueError("PROCESS_TOTAL_RECONCILIATION_FAILED")
    source_scopes = Counter(r["response_verification"] for r in rows)
    return {"snapshot_started_at_utc": started, "ledger_read_ended_at_utc": ledger_read_ended,
        "job_metadata_read_ended_at_utc": metadata_read_ended, "active_revision": active_revision,
        "phase_inventory": inventory, "scopes": scopes, "stages": stages, "calls": rows, "processes": processes,
        "source_snapshot_sha256": digest(attempts), "call_table_sha256": digest(rows), "frozen_stage_sources": locks,
        "source_coverage": dict(source_scopes), "issues": issues,
        "reconciliation": {"all_ledger_calls_included_once": True, "all_known_ledger_tokens_reconciled": True,
                           "active_process_totals_reconciled": True, "no_db_writes": True, "new_model_calls": 0},
        "limitations": ["当前为累计快照；全量仍在执行，不能预填最终总量。", "调用数表示账本登记的caller尝试，包括失败、重试及本地拒绝，不等于已独立证明的HTTP发送次数。",
            "未知用量为空，不填0；预算占用包含保守预留，不是实际token使用量。", "阶段根据实际记录请求和对应冻结源码的结构特征匹配；未匹配时保持未知，不按调用序号猜阶段。",
            "直接对照方法不冒称S1–S5；修复调用计入实际返回的S2/S3，S4自身为程序校验。", "历史诊断的分项若没有已关联的原响应则不补造；原账本中的总token仍完整计入。",
            "只统计LLM token；不把程序处理、Java推理器或本报告的计算计为LLM用量。"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--revision", default="r8luna")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = extract(args.workspace.resolve(strict=True), args.revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"snapshot": data["snapshot_started_at_utc"], "scopes": data["scopes"],
        "stage_mapping": dict(Counter(r["stage"] for r in data["calls"] if r["revision"] == args.revision)),
        "source_coverage": data["source_coverage"], "issue_count": len(data["issues"]), "reconciliation": data["reconciliation"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
