"""Fresh three-scene service/Worker/compiler exports, with independent HTTP spy.

Model transport ONLY is MockTransport. Labels and synthetic identities are
explicit; no paid requests, release, actions or downstream receiver are involved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.upgrade.scenario_cases import build_scenario_case
from tests.upgrade.test_handoff_delivery import request_for
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    file_rows,
    json_bytes,
    read_archive,
    verify_rows,
)
from zhigou_toolchain.modeling.delivery.handoff import verify_handoff
from zhigou_toolchain.modeling.five_stage.coverage import reconcile_physical_requests
from zhigou_toolchain.modeling.five_stage.expert_runtime import usage_summary
from zhigou_toolchain.modeling.five_stage.scenarios import SCENES
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes
from zhigou_toolchain.services.handoff import download
from zhigou_toolchain.services.modeling_audit import (
    audit_index,
    download_audit,
    read_events,
)
from zhigou_toolchain.services.modeling_scenarios import selected_tables
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.projects import get_project


def run_case(output, scene):
    output.mkdir(parents=True, exist_ok=False)
    print("START " + scene, flush=True)
    workspace = output / ("upgrade-hr0" if scene == "organization_management" else "upgrade-forest0")
    case = build_scenario_case(workspace, scene)
    app, user, project, spy = case["service"], case["principal"], case["project_id"], case["spy"]
    readbacks = []
    for index, table in enumerate(selected_tables(case["effective"], "S3")):
        objects = case["run"]("ods.query", {"package_id": case["built"]["package_id"], "class_iri": table["class_iri"], "limit": 1000, "offset": 0}, f"scene-contract-read-{index}")
        assert objects["rows"], (table["record_id"], objects)
        readbacks.append({"object_family": table["record_id"], "class_iri": table["class_iri"], "result": objects})
    with patch("zhigou_toolchain.services.modeling_expert.configured_client", spy.client):
        receipt = case["run"]("modeling.handoff.export", request_for(case), "scene-handoff")
    job = next(j for j in app.jobs.list_project(project) if j.operation_id == "modeling.handoff.export")
    raw = download(app, user, project, job.job_id)
    files = read_archive(raw)
    verified = verify_handoff(files)
    assert verified["status"] == "VERIFIED" and receipt["sha256"] == digest(raw)
    token, identity = app.tokens.create(principal_id="synthetic-scene-downloader", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="isolated-check")
    try:
        with TestClient(create_app(app)) as client:
            response = client.get(f"/api/v1/projects/{project}/handoffs/{job.job_id}/archive", headers={"Authorization": "Bearer " + token})
            assert response.status_code == 200 and response.content == raw
    finally:
        app.tokens.revoke(identity.token_id)
    session = read(get_project(app.root, project).root)
    loops = session["expert"]["loops"]
    assert all(l["decision"] == "PASS" for l in loops)
    assert any(l["revision_round"] == 1 and [r["methods"][0]["decision"] for r in l["rounds"]] == ["REVISE", "PASS"] for l in loops)
    archives, physical = {}, []
    for row in audit_index(app, user, project)["records"]:
        audit_job = app.jobs.get(row["job_id"])
        archive = download_audit(app, user, project, audit_job.job_id)
        content = read_archive(archive)
        if "model-trace.json" in content:
            trace = json.loads(content["model-trace.json"])
            wanted = {e["request_sha256"] for e in trace["events"] if e["event"] == "llm_call"}
            requests = [p for p in spy.requests if semantic_hash(p) in wanted]
            reconcile_physical_requests(requests, read_events(app, audit_job), trace)
            physical.extend(requests)
        archives[f"audits/{audit_job.job_id}.zip"] = archive
    assert len(physical) == len(spy.requests)
    tokens = usage_summary([c for loop in loops for c in loop["calls"]])
    assert tokens["physical_calls"] == len(spy.requests)
    for request in spy.requests:
        body = json.loads(request["messages"][1]["content"])
        assert body["scenario_context"]["effective_configuration_digest"] == case["effective"]["digest"]
        assert "synthetic-independent-" not in json.dumps(request)
        assert "PREDECLARED_CAPABILITY_MEMBERSHIP_V1" not in json.dumps(request)
    stage_outputs = [{"operation": r["operation"], "job_id": r["result"].get("step_audit_anchor", {}).get("job_id"),
        "outputs": r["result"]["scenario_outputs"]} for r in case["results"] if r["result"].get("scenario_outputs")]
    assert {o["stage_id"] for r in stage_outputs for o in r["outputs"]} == set(range(1, 6))
    archives["audits/expert-loops.json"] = json_bytes(loops)
    archives["audits/token_usage.json"] = json_bytes(tokens)
    archives["audits/independent-http-witness.json"] = json_bytes({"nature": "MOCK_TRANSPORT", "requests": spy.requests})
    archives["audits/scenario-stage-outputs.json"] = json_bytes(stage_outputs)
    archives["audits/scenario-quality.json"] = json_bytes(case["quality"])
    archives["prompts/scenario-configuration.json"] = json_bytes(session["scenario"])
    archives["prompts/expert-configurations.json"] = json_bytes({"versions": session["expert"]["stages"], "history": session["expert"]["history"]})
    archives["manifest.json"] = json_bytes({"format": "LOCAL_SCENARIO_AUDIT_NOT_EVOLUTION_V2", "files": file_rows(archives)})
    audit_raw = archive_mapping_bytes(archives)
    verify_rows(read_archive(audit_raw), json.loads(archives["manifest.json"])["files"])
    products = {"ontology-handoff.zip": raw, "ontology.kgop": files["native/ontology.kgop"], "scenario-audits.zip": audit_raw,
        "stage-outputs.json": json_bytes(stage_outputs), "effective-configuration.json": json_bytes(case["effective"]),
        "quality.json": json_bytes(case["quality"]), "service-readbacks.json": json_bytes(readbacks)}
    for name, data in products.items():
        atomic_file(output / name, data)
    report = {"status": "PASS", "scene": scene, "effective_configuration_digest": case["effective"]["digest"],
        "project_id": project, "export_job_id": job.job_id, "package_id": case["built"]["package_id"], "physical_requests": len(spy.requests),
        "token_usage": tokens, "quality": case["quality"], "files": file_rows(products), "verification": verified,
        "nature": "SYNTHETIC_ENGINEERING_MOCK_TRANSPORT", "live_calls": 0, "human_review": "SYNTHETIC_TEST_IDENTITIES",
        "download": "API_AND_SERVICE_SAME_BYTES", "strict_v2": "BLOCKED_PROGRAM_PRE_MODEL_TURN_AND_MOCK",
        "receiver": "NOT_CONTACTED", "release": "NOT_PERFORMED"}
    atomic_file(output / "verification.json", json_bytes(report))
    print("END " + scene, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scene", choices=(*SCENES, "all"), default="all")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases = []
    for scene in SCENES if args.scene == "all" else [args.scene]:
        try:
            cases.append(run_case(args.output / scene, scene))
        except BaseException as exc:
            atomic_file(args.output / "FAILED.json", json_bytes({"status": "FAIL", "scene": scene,
                "error_type": type(exc).__name__, "reason": str(exc), "completed": cases}))
            raise
    atomic_file(args.output / "verification.json", json_bytes({"status": "PASS", "cases": cases, "paid_calls": 0,
        "configuration_mode": "SCENE_PROMPT_PRESETS_NO_STAGE_LEVELS"}))


if __name__ == "__main__":
    main()
