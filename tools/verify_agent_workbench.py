"""Generate a new synthetic S1-S5 audit example through the real service/Worker.

Run as python -m tools.verify_agent_workbench NEW_OUTPUT_DIRECTORY.
No model calls, production decisions or publication. Old outputs are not reused.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.upgrade.test_full_chain import build_case
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    file_rows,
    json_bytes,
    read_archive,
    verify_rows,
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
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    case = build_case(args.output / "upgrade-hr0", "hr", record_step_content=True)
    service, principal, project = case["service"], case["principal"], case["project_id"]
    index = audit_index(service, principal, project)
    files, stages, count = {}, set(), 0
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
        name = f"audits/{job.job_id}.zip"
        atomic_file(args.output / name, raw)
        files[name] = raw
    assert stages == {1, 2, 3, 4, 5}
    files["audit-index.json"] = json_bytes(index)
    files["README.md"] = "# 双 Agent 审计样例\n\n合成 HR 数据，真实服务和 Worker。包含五阶段处理前后文件；不是专家审核、LIVE 或生产发布。\n".encode()
    files["manifest.json"] = json_bytes({"format": "zhigou-agent-audit-example/1.0.0", "files": file_rows(files)})
    raw = archive_mapping_bytes(files)
    path = args.output / "modeling-agent-audits.zip"
    atomic_file(path, raw)
    reread = read_archive(path.read_bytes())
    verify_rows(reread, json.loads(reread["manifest.json"])["files"])
    report = {"status": "PASS", "nature": "SYNTHETIC_SERVICE_ENGINEERING", "live_model_calls": 0,
        "stages_with_real_tool_audits": sorted(stages), "jobs": len(index["records"]), "events": count,
        "file": path.name, "sha256": digest(raw), "size_bytes": len(raw), "project_id": project,
        "review": "SYNTHETIC_AUTHORIZED_TEST_IDENTITIES", "release": "NOT_RELEASED"}
    atomic_file(args.output / "verification.json", json_bytes(report))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
