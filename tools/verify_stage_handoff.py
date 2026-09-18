"""Freeze once, run unmodified source, retain raw FAIL, and package real service cases.

No live inference, repository commit, publication or deletion of history. A
failure to keep the source frozen aborts this qualification, never patches it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from xml.etree import ElementTree

from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    json_bytes,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.snapshot import (
    assert_unchanged,
    source_snapshot,
)
from zhigou_toolchain.modeling.delivery.stage import (
    compose_stage,
    export_stage,
    verify_stage_archive,
)

ROOT = Path(__file__).resolve().parents[1]
HYGIENE_NODES = ["tests/scripts/test_repo_hygiene.py::test_current_repository_passes",
                 "tests/refactor/test_repository_hygiene_refactor.py::test_refactor_hygiene_gate_passes_for_tracked_tree"]


def junit(path):
    if not Path(path).exists():
        return {"tests": 0, "failed": 0, "skipped": 0, "nodes": []}
    rows = []
    for row in ElementTree.parse(path).findall(".//testcase"):
        problem = row.find("failure")
        if problem is None:
            problem = row.find("error")
        skipped = row.find("skipped")
        rows.append({"node": row.get("classname") + "::" + row.get("name"),
            "outcome": "FAIL" if problem is not None else "SKIP" if skipped is not None else "PASS",
            "reason": (problem.text or problem.get("message", "")) if problem is not None else
                      (skipped.text or skipped.get("message", "")) if skipped is not None else None})
    return {"tests": len(rows), "failed": sum(r["outcome"] == "FAIL" for r in rows),
            "skipped": sum(r["outcome"] == "SKIP" for r in rows), "nodes": rows}


def safe_environment():
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "ZHIGOU_QWEN_", "KG_MNP_QWEN_", "ZHIGOU_STAGE_", "ZHIGOU_HANDOFF_EVIDENCE_"))}
    environment.update(PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    index = int(environment.get("GIT_CONFIG_COUNT", "0"))
    environment.update({f"GIT_CONFIG_KEY_{index}": "core.longpaths", f"GIT_CONFIG_VALUE_{index}": "true", "GIT_CONFIG_COUNT": str(index + 1)})
    return environment


def json_records(path):
    records = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            records.append(row)
    return records


def isolation_available():
    import shutil
    if shutil.which("wsl") is None or not (ROOT / "third_party/downloads/robot-1.9.7.jar").is_file():
        return False
    try:
        result = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "--exec", "sh", "-c",
            "command -v bwrap >/dev/null && test -x /home/yangjunjie/.cache/zhigou-ontology-eval-20260914/venv/bin/python"],
            capture_output=True, timeout=20, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run(output, name, command, snapshot, *, cwd=ROOT, pytest_args=None, extra_env=None):
    assert_unchanged(ROOT, snapshot)
    directory = output / "checks" / name
    directory.mkdir(parents=True, exist_ok=False)
    environment = {**safe_environment(), **(extra_env or {}), "KG_MNP_RECEIPT_ROOT": str(directory)}
    if pytest_args is not None:
        command = [sys.executable, "-m", "pytest", *pytest_args, "-q", "--tb=short", "-p", "tests.verification_receipts",
                   "--basetemp=" + str(directory / "temp"), "--junitxml=" + str(directory / "junit.xml")]
    print("START " + name, flush=True)
    clock = perf_counter()
    with (directory / "command.log").open("xb") as log:
        completed = subprocess.run(command, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False)
    record = {"name": name, "command": command, "exit_code": completed.returncode,
        "duration_seconds": perf_counter() - clock, "log": name + ".log", "log_sha256": digest(read_bounded(directory / "command.log")),
        **junit(directory / "junit.xml")}
    if name == "ontology" and completed.returncode == 0:
        report_root = Path((directory / "command.log").read_text(encoding="utf-8").strip().splitlines()[-1])
        require(report_root.resolve().is_relative_to((ROOT / "runtime_reports").resolve()), "ONTOLOGY_REPORT_PATH_INVALID")
        report = json.loads((report_root / "verification.json").read_bytes())
        require(report["source_unchanged"] is True, "ONTOLOGY_SOURCE_CHANGED")
        record.update(junit(report_root / "ontology.xml"), nested_report_root=str(report_root))
    if name in {"browser", "agent-browser"} and completed.returncode == 0:
        receipt = next(r for r in reversed(json_records(directory / "command.log")) if "evidence" in r)
        report_root = ROOT / receipt["evidence"]
        record.update(junit(report_root / "junit.xml"), nested_report_root=str(report_root))
    assert_unchanged(ROOT, snapshot)
    atomic_file(directory / "check.json", json_bytes(record))
    print("END " + name + " " + str(completed.returncode), flush=True)
    return record


def baseline_proof(baseline, output, checks):
    historical = json.loads((ROOT / "docs/ontology/evidence/preexisting-hygiene-failures.json").read_bytes())
    files = []
    for row in historical["files"]:
        name = row["path"]
        before, now = (baseline / name).read_bytes(), (ROOT / name).read_bytes()
        files.append({"path": name, "baseline_sha256": digest(before), "current_sha256": digest(now), "byte_identical": before == now})
    scans = {}
    for name, directory in (("baseline", baseline), ("current", ROOT)):
        process = subprocess.run([sys.executable, "scripts/check_repo_hygiene.py"], cwd=directory,
                                 env=safe_environment(), capture_output=True, check=False)
        raw = process.stdout + process.stderr
        atomic_file(output / (name + "-hygiene-scan.log"), raw)
        scans[name] = {"exit_code": process.returncode, "findings": [s.strip() for s in raw.decode("utf-8", errors="replace").splitlines() if s.startswith("- ")]}
    baseline_check = next(c for c in checks if c["name"] == "baseline-hygiene")
    current_check = next(c for c in checks if c["name"] == "current-hygiene")
    nodes_before = sorted(r["node"] for r in baseline_check["nodes"] if r["outcome"] == "FAIL")
    nodes_now = sorted(r["node"] for r in current_check["nodes"] if r["outcome"] == "FAIL")
    identical = (nodes_before == nodes_now and len(nodes_now) == 2 and scans["baseline"] == scans["current"]
                 and all(f["byte_identical"] for f in files))
    result = {"baseline_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=baseline, text=True).strip(),
        "baseline_clean": subprocess.check_output(["git", "status", "--porcelain"], cwd=baseline) == b"",
        "same_failures_reproduced": identical, "failed_nodes": nodes_now, "scans": scans, "files": files,
        "raw_status": "FAIL", "gate_unchanged": True, "historical_files_unchanged": True,
        "constraint_conflict": "No mechanism in the unchanged scanner can accept these absolute paths without changing originals or relaxing its rule. Neither was done."}
    require(identical and result["baseline_clean"], "BASELINE_FAILURE_REPRODUCTION_DIFFERED")
    return result


def add_full_receipts(evidence, full_root):
    """Keep raw pytest artifacts separate from the wrapper command's own log."""
    for name in ("backend.xml", "backend.log", "reports.json", "verification.json"):
        key = "relevant-test-receipts/full-backend-raw/" + name
        require(key not in evidence, "DUPLICATE_TEST_RECEIPT_PATH")
        evidence[key] = (Path(full_root) / name).read_bytes()


def check_attachment(path, output):
    """Read only the supplied upstream; preserve historical versions and bytes."""
    from tests.upgrade.test_meeting_handoff_input import import_input_case
    from zhigou_toolchain.modeling.delivery.exchange_io import read_archive
    from zhigou_toolchain.modeling.delivery.meeting_input import validate_input
    raw = read_bounded(path)
    archive = read_archive(raw)
    roots = [n.removesuffix("manifest.json") for n in archive if n.endswith("/upstream/manifest.json")]
    require(len(roots) == 1, "ATTACHMENT_UPSTREAM_ROOT_REQUIRED")
    files = {n.removeprefix(roots[0]): v for n, v in archive.items() if n.startswith(roots[0])}
    parsed = validate_input(files)
    result = import_input_case(output / "service", files)
    record = {"file": path.name, "sha256": digest(raw), "size_bytes": len(raw), "status": "NATIVE_INPUT_IMPORTED",
        "reference_domain_pack": parsed["manifest"].get("reference_domain_pack"), "upstream_file_count": len(files),
        "native_run_id": result["run"]["run_id"], "approval": result["approval"], "runtime_model_input": "UPSTREAM_GENERATION_ALLOWLIST_ONLY",
        "requested_attachment_status": "MATCH" if digest(raw) == "bbcf5bbf6c356018f83a2b33226a751181507176268cd0a4912795a1489b51a3" else "DIFFERENT_ATTACHMENT_NOT_A_SUBSTITUTE"}
    atomic_file(output / "attachment-check.json", json_bytes(record))
    print(json.dumps(record, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--parallel-full", action="store_true", help="Run the unchanged four-worker full suite alongside independent scoped checks")
    parser.add_argument("--input-archive", type=Path, help="Optional supplied explanation ZIP; import only its upstream subtree")
    args = parser.parse_args()
    output, baseline = args.output.resolve(), args.baseline.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    require(subprocess.check_output(["git", "status", "--porcelain"], cwd=baseline) == b"", "BASELINE_NOT_CLEAN")
    snapshot = source_snapshot(ROOT)
    atomic_file(output / "source-snapshot.json", json_bytes(snapshot))
    atomic_file(output / "source-diff.patch", subprocess.check_output(["git", "diff", "--binary", "HEAD", "--"], cwd=ROOT))
    print(json.dumps({"output": str(output), "snapshot_id": snapshot["snapshot_id"]}), flush=True)
    checks = []
    checks.append(run(output, "baseline-hygiene", [], snapshot, cwd=baseline, pytest_args=HYGIENE_NODES))
    checks.append(run(output, "current-hygiene", [], snapshot, pytest_args=HYGIENE_NODES))
    known = baseline_proof(baseline, output, checks)
    atomic_file(output / "known-baseline-failures.json", json_bytes(known))
    for name, command in (("ruff", [sys.executable, "-m", "ruff", "check", "."]), ("types", [sys.executable, "tools/check_types.py"])):
        checks.append(run(output, name, command, snapshot))
    full_command = [sys.executable, "tools/verify_zhigou_upgrade.py", "--backend-only", "--workers", "4", "--skip-model-probe"]
    pool = ThreadPoolExecutor(max_workers=1) if args.parallel_full else None
    full_future = pool.submit(run, output, "full-backend", full_command, snapshot) if pool else None
    checks.append(run(output, "focused", [], snapshot, pytest_args=["tests/upgrade/test_evolution_delivery.py", "tests/upgrade/test_meeting_handoff_input.py", "tests/upgrade/test_handoff_delivery.py", "tests/services/test_evolution_handoff.py"]))
    if args.input_archive:
        checks.append(run(output, "attachment-input", [sys.executable, "-c",
            "from pathlib import Path; import sys; from tools.verify_stage_handoff import check_attachment; check_attachment(Path(sys.argv[1]), Path(sys.argv[2]))",
            str(args.input_archive.resolve()), str(output / "attachment")], snapshot))
    checks.append(run(output, "new-stage", [], snapshot, pytest_args=["tests/upgrade/test_stage_handoff.py", "tests/upgrade/test_stage_archive_safety.py"],
        extra_env={"ZHIGOU_STAGE_SNAPSHOT_FILE": str(output / "source-snapshot.json"), "ZHIGOU_STAGE_EVIDENCE_ROOT": str(output / "cases")}))
    checks.append(run(output, "services", [], snapshot, pytest_args=["tests/services/test_five_stage_service.py", "tests/services/test_forestry_workflow.py", "tests/services/test_core_fencing.py", "tests/services/test_archive_read_authorization.py", "tests/jobs/test_lease_lock_wait.py"]))
    checks.append(run(output, "agent-audit", [], snapshot, pytest_args=["tests/upgrade/test_step_audit.py", "tests/upgrade/test_agent_roles.py"]))
    checks.append(run(output, "ontology", [sys.executable, "tools/evaluate_research.py", "--suite", "ontology"], snapshot))
    checks.append(full_future.result() if full_future else run(output, "full-backend", full_command, snapshot))
    if pool:
        pool.shutdown(wait=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    for name, command in (("frontend-lint", "lint"), ("frontend-types", "typecheck"), ("frontend-tests", "test"), ("frontend-build", "build")):
        checks.append(run(output, name, [npm, "--prefix", "workbench", "run", command] if command != "test" else [npm, "--prefix", "workbench", "test"], snapshot))
    workspace = json.loads((output / "cases/hr/workspace-reference.json").read_bytes())
    checks.append(run(output, "browser", [sys.executable, "tools/run_browser_verification.py", "--selected-test", "handoff.e2e.ts",
        "--existing-upgrade-workspace", workspace["workspace"], "--existing-export-job-id", workspace["export_job_id"], "--startup-timeout", "90"], snapshot))
    browser = checks[-1]
    if browser["exit_code"] == 0:
        receipt = json.loads((Path(browser["nested_report_root"]) / "managed-receipt.json").read_bytes())
        archives = [n for n in receipt["artifacts"] if n.endswith("synthetic-ontology-handoff.zip")]
        require(len(archives) == 1, "BROWSER_ARCHIVE_REQUIRED")
        downloaded = read_bounded(Path(browser["nested_report_root"]) / archives[0])
        require(downloaded == read_bounded(output / "cases/hr/ontology-handoff.zip"), "BROWSER_NOT_SAME_EXPORT_TASK")
    checks.append(run(output, "agent-browser", [sys.executable, "tools/run_browser_verification.py", "--selected-test", "agent-audit.e2e.ts", "--startup-timeout", "90"], snapshot))
    isolation_ready = isolation_available()
    if isolation_ready:
        checks.append(run(output, "isolation", [sys.executable, "tools/verify_handoff_isolation.py", str(output / "isolation")], snapshot))
    else:
        directory = output / "checks/isolation"
        directory.mkdir(parents=True)
        raw = b"NOT_RUN: fixed WSL/bubblewrap/runtime/reasoner environment unavailable; no unsandboxed fallback.\n"
        atomic_file(directory / "command.log", raw)
        checks.append({"name": "isolation", "exit_code": None, "status": "NOT_RUN", "skipped": 0, "log": "isolation.log", "log_sha256": digest(raw)})
    full_log = output / "checks/full-backend/command.log"
    full_root = Path(next(r["evidence"] for r in json_records(full_log) if "evidence" in r))
    full = json.loads((full_root / "verification.json").read_bytes())
    full_nodes = junit(full_root / "backend.xml")
    failures = sorted(r["node"] for r in full_nodes["nodes"] if r["outcome"] == "FAIL")
    summary = {"raw_status": "FAIL" if failures else "PASS", "source_unchanged": full["source_unchanged"],
        "collection": full["collection"], "new_regressions_status": "NO_NEW_FAILURES" if failures == known["failed_nodes"] else "NEW_OR_DIFFERENT_FAILURES",
        "source_snapshot_id": snapshot["snapshot_id"], "original_report": str(full_root.relative_to(ROOT)), **full_nodes}
    atomic_file(output / "full-regression-summary.json", json_bytes(summary))
    required = {"focused", "new-stage", "ruff", "types", "ontology", "services", "agent-audit", "agent-browser", "frontend-lint", "frontend-types", "frontend-tests", "frontend-build", "browser"}
    if args.input_archive:
        required.add("attachment-input")
    if isolation_ready:
        required.add("isolation")
    module_pass = all(c["exit_code"] == 0 and c["skipped"] == 0 for c in checks if c["name"] in required)
    after = assert_unchanged(ROOT, snapshot)
    stage = {"snapshot_id": snapshot["snapshot_id"], "source_before": snapshot["snapshot_id"], "source_after": after, "source_unchanged": True,
        "module_acceptance": "PASS" if module_pass else "FAIL", "full_repository_status": summary["raw_status"],
        "stage_classification": "ENGINEERING_WITH_KNOWN_REPOSITORY_FAILURES" if module_pass and summary["new_regressions_status"] == "NO_NEW_FAILURES" else "ENGINEERING_WITH_UNRESOLVED_FAILURES",
        "checks": checks, "created_at": datetime.now(UTC).isoformat(), "paid_model_calls": 0,
        "external_receiver": "NOT_CONTACTED", "real_human_run_reviews": "NOT_PERFORMED", "production_release": "NOT_PERFORMED"}
    atomic_file(output / "stage-verification.json", json_bytes(stage))
    from tests.upgrade.stage_support import case_files
    cases = {name: case_files(output / "cases" / name) for name in ("hr", "forestry")}
    evidence = {n: (output / n).read_bytes() for n in ("source-snapshot.json", "stage-verification.json", "full-regression-summary.json", "known-baseline-failures.json", "source-diff.patch")}
    for check in checks:
        directory = output / "checks" / check["name"]
        evidence["relevant-test-receipts/" + check["log"]] = (directory / "command.log").read_bytes()
        for name in ("junit.xml", "reports.json", "collection.json"):
            if (directory / name).exists():
                evidence["relevant-test-receipts/" + check["name"] + "-" + name] = (directory / name).read_bytes()
    add_full_receipts(evidence, full_root)
    if (output / "attachment/attachment-check.json").exists():
        evidence["relevant-test-receipts/attachment-check.json"] = (output / "attachment/attachment-check.json").read_bytes()
    for check in checks:
        if "nested_report_root" in check:
            nested = Path(check["nested_report_root"])
            for name in ("verification.json", "ontology.xml", "ontology.log", "managed-receipt.json", "junit.xml"):
                if (nested / name).exists():
                    evidence["relevant-test-receipts/" + check["name"] + "-" + name] = (nested / name).read_bytes()
    for name in ("receipt.json", "output/isolation-check.json"):
        if (output / "isolation" / name).exists():
            evidence["relevant-test-receipts/isolation-" + Path(name).name] = (output / "isolation" / name).read_bytes()
    readme = ("# 本体建模阶段工程交付\n\n本包为新建 HR/林业合成服务链，非生产发布或专家研究成绩。\n"
        "独立负例、原生图、当前依赖祖先与本地程序轨迹分别绑定；纯程序轨迹不进入 executions。\n"
        "完整回归保留已在干净基线复现的卫生 FAIL，不是全仓全绿。\n"
        "验包：python -m zhigou_toolchain.modeling.delivery.cli validate-stage ARCHIVE --sha256 TRUSTED_SIDECAR_SHA --replay-negatives\n"
        "完整验收资料仅供授权接收人，禁止给生成/修复模型读取。\n").encode()
    files = compose_stage(cases, evidence, snapshot["snapshot_id"], readme)
    archive = output / ("ontology-modeling-stage-handoff-" + snapshot["snapshot_id"][:12] + ".zip")
    verified = export_stage(archive, files)
    replayed = verify_stage_archive(archive, expected_sha256=verified["archive_sha256"], replay_negatives=True)
    assert_unchanged(ROOT, snapshot)
    atomic_file(output / "final-archive-verification.json", json_bytes(replayed))
    atomic_file(output / "archive-sidecar.json", json_bytes({"archive": archive.name, "sha256": verified["archive_sha256"], "size_bytes": verified["size_bytes"], "snapshot_id": snapshot["snapshot_id"]}))
    report = f"# 阶段验收实际结果\n\n源码快照：{snapshot['snapshot_id']}\nHEAD：{snapshot['git_head']}\nsource_unchanged=true\n\n本体交付模块：{stage['module_acceptance']}\n新增回归：{summary['new_regressions_status']}\n全仓原始结论：{summary['raw_status']}\n\n完整测试：{summary['tests']}，FAIL {summary['failed']}，SKIP {summary['skipped']}；每个节点及原因见 full-regression-summary.json。\n\n总 ZIP：{archive.name}\nSHA-256：{verified['archive_sha256']}\n字节数：{verified['size_bytes']}\n磁盘重读及负例重放：{replayed['status']}\n\n外部接收/本体评价协议未确认；未付费、未发布、未提交推送。生产 Worker 沙箱/LIVE broker 不在本轮范围。\n"
    atomic_file(output / "FINAL_REPORT.md", report.encode("utf-8"))
    print(json.dumps({"output": str(output), "archive": str(archive), "module_acceptance": stage["module_acceptance"],
        "new_regressions": summary["new_regressions_status"], "full_raw_status": summary["raw_status"], "sha256": verified["archive_sha256"], "size_bytes": verified["size_bytes"]}), flush=True)
    return 0 if module_pass and summary["new_regressions_status"] == "NO_NEW_FAILURES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
