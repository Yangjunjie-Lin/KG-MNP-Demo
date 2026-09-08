"""Fixed-revision full backend evidence, without historical aggregate recursion.

prepare collects every node once. run executes a disjoint serial/parallel
partition. summarize checks coverage equality, not cumulative PASS counts.
This records backend verification only and cannot authorize a release tag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILES = {"docs/verification/final-verification.json", "docs/verification/final-requirements.json",
                  "docs/release/release-candidate-notes.md", "docs/migration/final-retirement-ledger.json"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def fingerprint():
    paths = git("ls-files", "-z").split("\0")
    records = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths if p and p not in EVIDENCE_FILES}
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(), records


def save(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run(directory, name, command, *, pytest_run=False, cwd=ROOT, environment=None):
    folder = directory / name
    folder.mkdir(exist_ok=False)
    environment = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1", "KG_MNP_RECEIPT_ROOT":str(folder), **(environment or {})}
    if pytest_run:
        command = [*command, "-p", "tests.verification_receipts", f"--junitxml={folder / 'junit.xml'}"]
    start = time.monotonic()
    with (folder / "command.log").open("wb") as stream:
        result = subprocess.run(command, cwd=cwd, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=False)
    receipt = {"command":command, "cwd":str(cwd), "exit_code":result.returncode, "duration_seconds":time.monotonic()-start,
               "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}}
    if (folder / "junit.xml").exists():
        xml = ElementTree.parse(folder / "junit.xml")
        receipt["suites"] = [row.attrib for row in xml.findall(".//testsuite")]
        receipt["skips"] = [{"test":row.attrib,"reason":skip.attrib} for row in xml.findall(".//testcase") for skip in row.findall("skipped")]
    save(folder / "receipt.json", receipt)
    print(json.dumps({"name":name,"exit_code":result.returncode,"seconds":receipt["duration_seconds"]}), flush=True)
    return receipt


def assert_frozen(plan):
    if git("status", "--porcelain") or git("rev-parse", "HEAD") != plan["tested_commit"] or fingerprint()[0] != plan["tested_source_tree_digest"]:
        raise SystemExit("Tested inputs changed; create a new code freeze and acceptance plan")


def summarize(directory):
    """Reject missing/overlapping/partial phases and tampered evidence receipts."""
    collected_list = json.loads((directory / "collection/collection.json").read_bytes())
    collected = set(collected_list)
    intended, executed = set(), set()
    receipts, issues, skips = {}, [], []
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    if len(collected_list) != len(collected) or not collected:
        issues.append("collection is empty or contains duplicate nodeids")
    for name in ("serial", "parallel"):
        node_list = json.loads((directory / (name + ".json")).read_bytes())
        nodes = set(node_list)
        if len(nodes) != len(node_list) or intended & nodes:
            issues.append("partitions overlap or contain duplicates")
        intended |= nodes
        receipt = json.loads((directory / name / "receipt.json").read_bytes())
        receipts[name] = receipt
        for required in ("reports.json", "junit.xml", "command.log"):
            path = directory / name / required
            if not path.is_file() or receipt.get("files", {}).get(required) != hashlib.sha256(path.read_bytes()).hexdigest():
                issues.append(f"{name}: {required} digest missing or mismatched")
        reports = json.loads((directory / name / "reports.json").read_bytes())
        phases = {}
        for row in reports:
            key = (row["nodeid"], row["when"])
            if key in phases:
                issues.append(f"{name}: repeated execution phase {key}")
            phases[key] = row
            if row["outcome"] not in {"passed", "failed", "skipped"} or row["when"] not in {"setup", "call", "teardown"}:
                issues.append(f"{name}: invalid test outcome/phase")
        partition_executed = {node for node, _ in phases}
        if partition_executed != nodes:
            issues.append(f"{name}: executed nodes differ from its partition")
        executed |= partition_executed
        for node in nodes:
            setup, call, teardown = [phases.get((node, phase)) for phase in ("setup", "call", "teardown")]
            if not setup or not teardown or (setup["outcome"] == "passed" and not call):
                issues.append(f"{name}: incomplete execution {node}")
            if setup and setup["outcome"] != "passed" and call:
                issues.append(f"{name}: call after failed/skipped setup {node}")
            for row in (setup, call, teardown):
                if not row:
                    continue
                outcome = row["outcome"]
                if outcome == "failed":
                    counts["failed" if row["when"] == "call" else "errors"] += 1
                elif outcome == "skipped":
                    counts["xfailed" if row.get("wasxfail") else "skipped"] += 1
                    skips.append({"nodeid": node, "phase": row["when"], "reason": row.get("skip_reason"), "xfail": row.get("wasxfail")})
                elif row["when"] == "call":
                    counts["xpassed" if row.get("wasxfail") else "passed"] += 1
    good = intended == collected == executed and not issues and not counts["failed"] and not counts["errors"] and not counts["xpassed"] and all(r["exit_code"] == 0 for r in receipts.values())
    return {"collection_count": len(collected), "unique_executed_count": len(executed), "missing": sorted(collected-executed),
        "extra": sorted(executed-collected), "partitions_match_collection": intended == collected,
        "issues": issues, "counts": counts, "skips": skips, "receipts": receipts,
        "backend_status": "PASS" if good else "FAIL", "release_status": "NOT_ESTABLISHED_BY_BACKEND_TESTS"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "serial", "parallel", "summarize"])
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        if git("status", "--porcelain"):
            raise SystemExit("Code freeze requires a clean tracked/untracked working tree")
        directory = ROOT / "runtime_logs/p09" / ("fixed-" + git("rev-parse", "--short", "HEAD") + "-" + uuid4().hex[:8])
        directory.mkdir(parents=True)
        digest, files = fingerprint()
        initial_commit = git("rev-parse", "HEAD")
        receipt = run(directory, "collection", [sys.executable,"-m","pytest","--collect-only","-q"], pytest_run=True)
        if receipt["exit_code"]:
            raise SystemExit(receipt["exit_code"])
        nodes = json.loads((directory / "collection/collection.json").read_bytes())
        serial_prefixes = ("tests/services/", "tests/lifecycle", "tests/activation/", "tests/amendment/", "tests/application_governance/", "tests/review/", "tests/workspace/", "tests/ingestion/test_evolving_workspace.py", "tests/integrations/test_package_read_snapshots.py", "tests/integrations/test_object_query.py::test_object_query_uses_the_exact_verified_bytes_if_live_package_changes")
        serial = [node for node in nodes if node.startswith(serial_prefixes) or any(part in node.lower() for part in ("concurr", "fencing", "transaction", "atomic", "recovery", "locking"))]
        parallel = sorted(set(nodes) - set(serial))
        for name, values in (("serial",serial),("parallel",parallel)):
            save(directory / (name + ".json"), values)
            (directory / (name + ".args")).write_text("\n".join(values) + "\n", encoding="utf-8")
        assert_frozen({"tested_commit": initial_commit, "tested_source_tree_digest": digest})
        save(directory / "plan.json", {"tested_commit":git("rev-parse","HEAD"),"tested_source_tree_digest":digest,
             "files":files,"excluded_evidence_files":sorted(EVIDENCE_FILES),"python":sys.version,"platform":platform.platform(),
             "collection_count":len(nodes),"collection_digest":hashlib.sha256(json.dumps(nodes).encode()).hexdigest(),
             "serial_count":len(serial),"parallel_count":len(parallel)})
        print(json.dumps({"run_dir":str(directory),"nodes":len(nodes),"serial":len(serial),"parallel":len(parallel)}),flush=True)
        return
    directory = args.run_dir.resolve(strict=True)
    plan = json.loads((directory / "plan.json").read_bytes())
    assert_frozen(plan)
    if args.mode in {"serial","parallel"}:
        command = [sys.executable,"-m","pytest", "@" + str(directory / (args.mode + ".args")), "--basetemp="+str(directory/(args.mode+'-temp'))]
        if args.mode == "parallel":
            command.extend(["-p","xdist.plugin","-n","3"])
        result = run(directory,args.mode,command,pytest_run=True)
        assert_frozen(plan)
        raise SystemExit(result["exit_code"])
    result = {"tested_commit":plan["tested_commit"],"source_tree_digest":plan["tested_source_tree_digest"], **summarize(directory)}
    save(directory / "summary.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="receipts"}),flush=True)
    raise SystemExit(0 if result["backend_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
