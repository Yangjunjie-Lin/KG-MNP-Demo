"""Reconcile methods and physical requests through the real service/Worker.

Run as python -m tools.verify_agent_workbench NEW_OUTPUT_DIRECTORY.
--mock-model replaces only external network transport; no paid calls. Old
outputs are not reused. Default remains deterministic (zero model requests).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from tests.upgrade.prompt_spy import PromptSpy
from tests.upgrade.test_full_chain import build_case
from tests.upgrade.test_no_baseline import run_new_ontology
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    file_rows,
    json_bytes,
    read_archive,
    verify_rows,
)
from zhigou_toolchain.modeling.five_stage.coverage import (
    implementation_view,
    reconcile_physical_requests,
)
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes
from zhigou_toolchain.services.modeling_audit import (
    audit_index,
    download_audit,
    read_events,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mock-model", action="store_true", help="Explicit synthetic-only MockTransport; no network")
    parser.add_argument("--pack", choices=["hr", "forestry", "both"], default="both")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    print(json.dumps({"preflight": {"workspace": "NEW_SYNTHETIC_ONLY", "step_content_enabled": True,
        "model_trace_enabled": True, "identity": "SYNTHETIC_AUTHORIZED_TEST_IDENTITY", "paid_calls": "FORBIDDEN",
        "network": "MOCK_TRANSPORT" if args.mock_model else "NO_INFERENCE"}}), flush=True)
    files, stages, count, cases, total_physical = {}, set(), 0, {}, 0
    packs = ["hr", "forestry"] if args.pack == "both" else [args.pack]
    if args.mock_model:
        packs.append("repair")
    for pack in packs:
        spy = PromptSpy()
        with patch("zhigou_toolchain.services.modeling_assistance.configured_client", spy.client), patch("zhigou_toolchain.services.modeling_five_stage.configured_client", spy.client):
            case = run_new_ontology(args.output / "upgrade-repair", live_repair=True, record_audit=True, return_runtime=True) if pack == "repair" else build_case(
                args.output / ("upgrade-" + pack), "hr" if pack == "hr" else "forestry-workorders",
                record_step_content=True, record_trace=True, model_assistance=args.mock_model)
            if args.mock_model and pack != "repair":
                case["run"]("modeling.scope.draft", {"run_id": case["ingestion"]["run_id"],
                    "business_goal": "Synthetic audit scope", "business_rules": ["Preserve explicit source evidence"]}, "audit-scope")
        service, principal, project = case["service"], case["principal"], case["project_id"]
        index = audit_index(service, principal, project)
        reports, accounted = [], 0
        for row in index["records"]:
            assert row["availability"] == "AVAILABLE"
            job = service.jobs.get(row["job_id"])
            events = read_events(service, job)
            stages.update(e["metadata"]["stage_id"] for e in events if e["metadata"]["kind"] == "TOOL")
            count += len(events)
            raw = download_audit(service, principal, project, job.job_id)
            inner = read_archive(raw)
            manifest = json.loads(inner["manifest.json"])
            assert manifest["pair_status"] == "CLOSED"
            verify_rows(inner, manifest["files"])
            coverage = json.loads(inner["coverage.json"])
            if "model-trace.json" in inner:
                trace = json.loads(inner["model-trace.json"])
                observed = [r["request"] for r in spy.requests if r["native_agent_run_id"] == trace["bindings"]["native_agent_run_id"]]
                coverage["independent_call_accounting"] = reconcile_physical_requests(observed, events, trace)
                accounted += len(observed)
                if observed:
                    # Deliberately omit an inner llm_call from a COPY: the
                    # independent network witness must detect the missing row.
                    altered = {**trace, "events": list(trace["events"])}
                    altered["events"].remove(next(e for e in altered["events"] if e["event"] == "llm_call"))
                    try:
                        reconcile_physical_requests(observed, events, altered)
                    except ValueError:
                        coverage["missing_inner_call_negative"] = "DETECTED"
                    else:
                        raise AssertionError("Missing physical call was not detected")
            reports.append({"job_id": job.job_id, "attempt": job.attempt, "coverage": coverage})
            name = f"{pack}/audits/{job.job_id}.zip"
            atomic_file(args.output / name, raw)
            files[name] = raw
        assert accounted == len(spy.requests)
        total_physical += accounted
        summary = {"project_id": project, "session_id": case["session"]["session_id"], "package_id": case["built"]["package_id"],
            "runs": reports, "physical_requests": accounted, "method_registry": implementation_view(),
            "effective_dependency_selection": audit_index(service, principal, project, package_id=case["built"]["package_id"]),
            "external_receiver": "NOT_CONTACTED", "training_eligibility": "NOT_CONFIRMED",
            "original_models": {"BGE": "NOT_RUN_NO_LOCAL_MODEL_RUN", "reranker": "NOT_RUN", "tokenizer": "UNICODE_SUBSTITUTE_NOT_TOKENIZER"}}
        cases[pack] = {k: summary[k] for k in ("project_id", "session_id", "package_id", "physical_requests")}
        files[f"{pack}/coverage.json"] = json_bytes(summary)
        files[f"{pack}/audit-index.json"] = json_bytes(index)
        files[f"{pack}/independent-network-witness.json"] = json_bytes({"nature": "MOCK_TRANSPORT" if args.mock_model else "NO_MODEL", "requests": spy.requests})
        atomic_file(args.output / pack / "coverage.json", files[f"{pack}/coverage.json"])
    assert stages == {1, 2, 3, 4, 5}
    files["README.md"] = "# 双 Agent 审计核对\n\n合成 HR/林业，真实服务/Worker/CAS/编译，外部模型仅 MockTransport。逐方法状态与独立网络核账见 coverage.json；无模型依赖的调用不造 Prompt。不是专家审核、LIVE 或生产发布；严格 v2 程序 turn 仍受阻。\n".encode()
    files["manifest.json"] = json_bytes({"format": "zhigou-agent-audit-example/1.0.0", "files": file_rows(files)})
    raw = archive_mapping_bytes(files)
    path = args.output / "modeling-agent-audits.zip"
    atomic_file(path, raw)
    reread = read_archive(path.read_bytes())
    verify_rows(reread, json.loads(reread["manifest.json"])["files"])
    report = {"status": "PASS", "claim_scope": "RECORDED_BOUNDARIES_AND_INDEPENDENT_REQUESTS_NOT_ALL_ALGORITHMS", "nature": "SYNTHETIC_SERVICE_ENGINEERING", "live_model_calls": 0,
        "stages_with_real_tool_audits": sorted(stages), "events": count, "cases": cases,
        "mock_physical_requests": total_physical, "file": path.name, "sha256": digest(path.read_bytes()), "size_bytes": path.stat().st_size,
        "review": "SYNTHETIC_AUTHORIZED_TEST_IDENTITIES", "release": "NOT_RELEASED"}
    atomic_file(args.output / "verification.json", json_bytes(report))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
