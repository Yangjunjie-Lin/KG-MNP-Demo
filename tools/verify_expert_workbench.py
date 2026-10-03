"""New synthetic service cases, independent MockTransport witness, real downloads.

No paid model, external receiver, production business action or publication.
Run only after source freeze when using the output as qualification evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.upgrade.expert_spy import ExpertSpy
from tests.upgrade.test_full_chain import build_case
from tests.upgrade.test_handoff_delivery import request_for
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    file_rows,
    json_bytes,
    read_archive,
    verify_rows,
)
from zhigou_toolchain.modeling.delivery.handoff import verify_handoff
from zhigou_toolchain.modeling.five_stage.coverage import (
    implementation_view,
    reconcile_physical_requests,
)
from zhigou_toolchain.modeling.five_stage.expert_runtime import usage_summary
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes
from zhigou_toolchain.services.handoff import download
from zhigou_toolchain.services.modeling_audit import (
    audit_index,
    download_audit,
    read_events,
)
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.projects import get_project


def run_case(output, pack):
    spy = ExpertSpy(revise_scope=True, qwen=pack != "hr")
    print("START synthetic expert " + pack, flush=True)
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        workspace = output / ("upgrade-hr0" if pack == "hr" else "upgrade-forest0")
        case = build_case(workspace, pack, expert_mode=True, record_trace=True, record_step_content=True)
        receipt = case["run"]("modeling.handoff.export", request_for(case), "expert-handoff")
    app, user, project = case["service"], case["principal"], case["project_id"]
    export_job = next(j for j in app.jobs.list_project(project) if j.operation_id == "modeling.handoff.export")
    raw = download(app, user, project, export_job.job_id)
    handoff = read_archive(raw)
    verified = verify_handoff(handoff)
    assert verified["status"] == "VERIFIED"
    assert receipt["sha256"] == digest(raw)
    token, _ = app.tokens.create(principal_id=user.principal_id, principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-download-test")
    try:
        with TestClient(create_app(app)) as client:
            response = client.get(f"/api/v1/projects/{project}/handoffs/{export_job.job_id}/archive", headers={"Authorization": "Bearer " + token})
            assert response.status_code == 200 and response.content == raw
    finally:
        app.tokens.revoke(app.authenticate("Bearer " + token).token_id)
    atomic_file(output / "ontology-handoff.zip", raw)
    atomic_file(output / "ontology.kgop", handoff["native/ontology.kgop"])
    session = read(get_project(app.root, project).root)
    loops = session["expert"]["loops"]
    assert all(r["decision"] == "PASS" for r in loops), [(r["operation"], r["stop_reason"]) for r in loops]
    audits, observed_total = {}, []
    for row in audit_index(app, user, project)["records"]:
        job = app.jobs.get(row["job_id"])
        archive = download_audit(app, user, project, job.job_id)
        files = read_archive(archive)
        if "model-trace.json" in files:
            trace = json.loads(files["model-trace.json"])
            calls = [e for e in trace["events"] if e["event"] == "llm_call"]
            # Select by independently recorded actual request bytes, never infer
            # the physical count from the event log being checked.
            wanted = {e["request_sha256"] for e in calls}
            from zhigou_toolchain.contracts.canonical import semantic_hash
            physical = [p for p in spy.requests if semantic_hash(p) in wanted]
            reconcile_physical_requests(physical, read_events(app, job), trace)
            observed_total.extend(physical)
        audits[f"audits/{job.job_id}.zip"] = archive
    assert len(observed_total) == len(spy.requests)
    tokens = usage_summary([c for r in loops for c in r["calls"]])
    assert tokens["physical_calls"] == len(spy.requests)
    audits["audits/expert-loops.json"] = json_bytes(loops)
    audits["audits/token_usage.json"] = json_bytes(tokens)
    audits["audits/independent-http-witness.json"] = json_bytes({"nature": "MOCK_TRANSPORT", "requests": spy.requests})
    audits["prompts/expert-configurations.json"] = json_bytes({"versions": session["expert"]["stages"], "history": session["expert"]["history"]})
    audits["methods.json"] = json_bytes(implementation_view())
    audits["manifest.json"] = json_bytes({"format": "LOCAL_EXPERT_AUDIT_NOT_EVOLUTION_V2", "files": file_rows(audits)})
    audit_raw = archive_mapping_bytes(audits)
    verify_rows(read_archive(audit_raw), json.loads(audits["manifest.json"])["files"])
    atomic_file(output / "expert-audits.zip", audit_raw)
    report = {"status": "PASS", "nature": "SYNTHETIC_ENGINEERING_MOCK_TRANSPORT", "live_calls": 0,
        "project_id": project, "package_id": case["built"]["package_id"], "export_job_id": export_job.job_id,
        "physical_requests": len(spy.requests), "token_usage": tokens, "methods": implementation_view(),
        "files": file_rows({"ontology-handoff.zip": raw, "expert-audits.zip": audit_raw}), "verification": verified,
        "download": "API_AND_SERVICE_SAME_BYTES", "human_review": "SYNTHETIC_TEST_IDENTITIES",
        "strict_v2": "BLOCKED_PROGRAM_PRE_MODEL_TURN_AND_MOCK", "receiver": "NOT_CONTACTED", "release": "NOT_PERFORMED"}
    atomic_file(output / "verification.json", json_bytes(report))
    print("END synthetic expert " + pack, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pack", choices=["hr", "forestry", "both"], default="both")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    packs = ["hr", "forestry-workorders"] if args.pack == "both" else ["hr" if args.pack == "hr" else "forestry-workorders"]
    reports = [run_case(args.output / pack, pack) for pack in packs]
    atomic_file(args.output / "verification.json", json_bytes({"cases": reports, "paid_calls": 0, "status": "PASS"}))


if __name__ == "__main__":
    main()
