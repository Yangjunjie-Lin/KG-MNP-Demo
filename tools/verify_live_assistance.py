"""Explicit synthetic LIVE API run, using production service/Worker and exact oracles.

No user documents or gold answers are sent to the model. Tests import synthetic
fixtures only; this is an engineering scenario, not a research accuracy claim.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from time import perf_counter
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", choices=["hr", "forestry-workorders", "repair"], default="hr")
    parser.add_argument("--resume-workspace", type=Path, help="Only a retained synthetic workspace created by this verifier")
    parser.add_argument("--original-models", action="store_true", help="Require prepared local BGE, reranker and Qwen tokenizer snapshots")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if args.original_models:
        import os

        from verify_original_multimodal import locked_model
        for prefix, model_id in (("BGE", "BAAI/bge-m3"), ("RERANKER", "BAAI/bge-reranker-v2-m3"), ("TOKENIZER", "Qwen/Qwen2.5-7B-Instruct")):
            lock, _manifest = locked_model(model_id)
            for key, value in (("MODEL", lock.model_id), ("REVISION", lock.revision), ("PATH", lock.location)):
                os.environ["ZHIGOU_" + prefix + "_" + key] = value
    from evaluate_research import fingerprint

    from tests.upgrade.test_full_chain import (
        build_case,
        test_forestry_real_work_orders_feedback_and_rollback,
        test_hr_formal_package_and_source_query,
    )
    output = root / "runtime_reports" / ("live-assistance-" + uuid4().hex)
    output.mkdir(parents=True)
    before, started = fingerprint(), perf_counter()
    print(json.dumps({"evidence": str(output), "data_origin": "SYNTHETIC", "mode": "LIVE"}), flush=True)
    report = {"source": before, "data_origin": "SYNTHETIC", "research_status": "INSUFFICIENT_EVIDENCE", "pack": args.pack}
    import zhigou_toolchain.services.modeling_assistance as assistance_service
    clients = []
    factory = assistance_service.configured_client
    def tracked_client():
        client = factory()
        clients.append(client)
        return client
    assistance_service.configured_client = tracked_client
    try:
        if args.pack == "repair":
            from tests.upgrade.test_no_baseline import run_new_ontology
            case = run_new_ontology(output / "workspace", live_repair=True)
            report.update(status="PASS", result=case)
            (output / "verification.json").write_text(json.dumps({**report, "source_unchanged": before == fingerprint(), "duration_seconds": perf_counter() - started}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"status": "PASS", "scenario": "LIVE_REPAIR_NEW_VERSION_RECHECK_REVIEW_EXACT_COMPILATION"}), flush=True)
            return 0
        configuration = {"retrieval": "BGE_FAISS", "chunking": "LOCAL_TOKENIZER"} if args.original_models else True
        case = resume(args.resume_workspace, args.pack, root, configuration) if args.resume_workspace else build_case(output / "workspace", args.pack, model_assistance=configuration)
        if args.pack == "hr":
            test_hr_formal_package_and_source_query(case)
        else:
            test_forestry_real_work_orders_feedback_and_rollback(case)
        receipt = case["proposed"]["model_assistance"]
        report.update(status="PASS", project_id=case["project_id"], package_id=case["built"]["package_id"],
            model_assistance=receipt, semantic_validation=case["proposed"]["automatic_validation"],
            exact_queries=case["built"]["reports"]["competency-question-test-report.json"])
    except Exception as exc:  # noqa: BLE001 - retained failure receipt, no secret-bearing error echo
        report.update(status="FAIL", error_type=type(exc).__name__, error_code=getattr(exc, "code", "SCENARIO_FAILED"),
            error_location=[{"file": Path(f.filename).name, "line": f.lineno, "function": f.name} for f in traceback.extract_tb(exc.__traceback__)])
        report["model_rejections"] = [c.last_rejection for c in clients if hasattr(c, "last_rejection")]
        report["transport_errors"] = [c.last_transport_error for c in clients if hasattr(c, "last_transport_error")]
        report["synthetic_rejected_proposals"] = [c.rejected_proposal for c in clients if hasattr(c, "rejected_proposal")]
    finally:
        assistance_service.configured_client = factory
    report.update(duration_seconds=perf_counter() - started, source_unchanged=before == fingerprint())
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "duration_seconds", "source_unchanged")}), flush=True)
    return int(report["status"] != "PASS")


def resume(workspace, pack, root, configuration=True):
    from tests.services.test_modeling_workflow import call
    from tests.upgrade.test_full_chain import finish_case
    from zhigou_toolchain.services.facade import ApplicationService
    from zhigou_toolchain.services.modeling_sessions import read
    from zhigou_toolchain.services.models import ServiceConfiguration
    from zhigou_toolchain.services.projects import get_project, load_catalog
    workspace = workspace.resolve(strict=True)
    if workspace.name != "workspace" or not workspace.parent.name.startswith("live-assistance-") or workspace.parent.parent != root / "runtime_reports":
        raise ValueError("Only retained synthetic verifier workspaces may be resumed")
    app = ApplicationService(ServiceConfiguration(str(workspace), review_profile="DEVELOPMENT_SINGLE_REVIEWER", reasoner_jar=str(root / "third_party/downloads/robot-1.9.7.jar")))
    catalog = load_catalog(workspace)
    if len(catalog["projects"]) != 1:
        raise ValueError("Single synthetic project required")
    project_id = next(iter(catalog["projects"]))
    jobs = app.jobs.list_project(project_id)
    proposal_job = next(j for j in jobs if j.operation_id == "modeling.proposal")
    params = app.jobs.parameters(proposal_job.job_id)
    identity = params.pop("__principal")
    principal = app.tokens.resolve(identity["token_id"])
    if principal.principal_id != "synthetic-upgrade-reviewer":
        raise ValueError("Synthetic identity required")
    session = read(get_project(app.root, project_id).root)
    params["model_assistance"]["expected_session_revision"] = session["revision"]
    if isinstance(configuration, dict):
        params["model_assistance"].update(configuration)
    suffix = uuid4().hex
    def run(operation, parameters, key):
        print(operation, flush=True)
        return call(app, principal, project_id, operation, parameters, suffix + key)
    prepared = next(j.result for j in jobs if j.operation_id == "modeling.prepare" and j.status == "SUCCEEDED")
    ingestion = next(j.result["run"] for j in jobs if j.operation_id == "ingestion.run" and j.status == "SUCCEEDED")
    proposed = run("modeling.proposal", params, "proposal")
    return finish_case(app, principal, project_id, run, pack, proposed, prepared, session["frozen"]["acceptance"], session, ingestion, {})


if __name__ == "__main__":
    raise SystemExit(main())
