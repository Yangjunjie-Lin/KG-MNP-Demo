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
                  "docs/release/release-candidate-notes.md"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def fingerprint():
    paths = git("ls-files", "-z").split("\0")
    records = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths if p and p not in EVIDENCE_FILES}
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(), records


def save(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run(directory, name, command, *, pytest_run=False):
    folder = directory / name
    folder.mkdir(exist_ok=False)
    environment = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1", "KG_MNP_RECEIPT_ROOT":str(folder)}
    if pytest_run:
        command = [*command, "-p", "tests.verification_receipts", f"--junitxml={folder / 'junit.xml'}"]
    start = time.monotonic()
    with (folder / "command.log").open("wb") as stream:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=False)
    receipt = {"command":command, "exit_code":result.returncode, "duration_seconds":time.monotonic()-start,
               "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}}
    if (folder / "junit.xml").exists():
        xml = ElementTree.parse(folder / "junit.xml")
        receipt["suites"] = [row.attrib for row in xml.findall(".//testsuite")]
        receipt["skips"] = [{"test":row.attrib,"reason":skip.attrib} for row in xml.findall(".//testcase") for skip in row.findall("skipped")]
    save(folder / "receipt.json", receipt)
    print(json.dumps({"name":name,"exit_code":result.returncode,"seconds":receipt["duration_seconds"]}), flush=True)
    return receipt


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
        receipt = run(directory, "collection", [sys.executable,"-m","pytest","--collect-only","-q"], pytest_run=True)
        if receipt["exit_code"]:
            raise SystemExit(receipt["exit_code"])
        nodes = json.loads((directory / "collection/collection.json").read_bytes())
        serial_prefixes = ("tests/services/", "tests/lifecycle", "tests/activation/", "tests/amendment/", "tests/application_governance/", "tests/review/", "tests/workspace/")
        serial = [node for node in nodes if node.startswith(serial_prefixes) or any(part in node.lower() for part in ("concurr", "fencing", "transaction", "atomic", "recovery", "locking"))]
        parallel = sorted(set(nodes) - set(serial))
        for name, values in (("serial",serial),("parallel",parallel)):
            save(directory / (name + ".json"), values)
            (directory / (name + ".args")).write_text("\n".join(values) + "\n", encoding="utf-8")
        digest, files = fingerprint()
        save(directory / "plan.json", {"tested_commit":git("rev-parse","HEAD"),"tested_source_tree_digest":digest,
             "files":files,"excluded_evidence_files":sorted(EVIDENCE_FILES),"python":sys.version,"platform":platform.platform(),
             "collection_count":len(nodes),"collection_digest":hashlib.sha256(json.dumps(nodes).encode()).hexdigest(),
             "serial_count":len(serial),"parallel_count":len(parallel)})
        print(json.dumps({"run_dir":str(directory),"nodes":len(nodes),"serial":len(serial),"parallel":len(parallel)}),flush=True)
        return
    directory = args.run_dir.resolve(strict=True)
    plan = json.loads((directory / "plan.json").read_bytes())
    if git("rev-parse","HEAD") != plan["tested_commit"] or fingerprint()[0] != plan["tested_source_tree_digest"]:
        raise SystemExit("Tested inputs changed; create a new code freeze and acceptance plan")
    if args.mode in {"serial","parallel"}:
        command = [sys.executable,"-m","pytest", "@" + str(directory / (args.mode + ".args"))]
        if args.mode == "parallel":
            command.extend(["-p","xdist.plugin","-n","3"])
        result = run(directory,args.mode,command,pytest_run=True)
        raise SystemExit(result["exit_code"])
    collected = set(json.loads((directory / "collection/collection.json").read_bytes()))
    intended = set()
    executed = set()
    receipts = {}
    for name in ("serial","parallel"):
        nodes = set(json.loads((directory / (name + ".json")).read_bytes()))
        if intended & nodes:
            raise SystemExit("Partitions overlap")
        intended |= nodes
        receipts[name] = json.loads((directory / name / "receipt.json").read_bytes())
        reports = json.loads((directory / name / "reports.json").read_bytes())
        executed |= {row["nodeid"] for row in reports}
    result = {"tested_commit":plan["tested_commit"],"source_tree_digest":plan["tested_source_tree_digest"],
              "collection_count":len(collected),"unique_executed_count":len(executed),"missing":sorted(collected-executed),
              "extra":sorted(executed-collected),"partitions_match_collection":intended==collected,"receipts":receipts,
              "backend_status":"PASS" if intended==collected==executed and all(r["exit_code"]==0 for r in receipts.values()) else "FAIL",
              "release_status":"NOT_ESTABLISHED_BY_BACKEND_TESTS"}
    save(directory / "summary.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="receipts"}),flush=True)


if __name__ == "__main__":
    main()
