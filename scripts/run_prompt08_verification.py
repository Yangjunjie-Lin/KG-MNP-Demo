"""Run a real command and retain exit status, logs, durations and file digests.

Usage: python scripts/run_prompt08_verification.py NAME -- COMMAND [ARGS...]
Writes only a newly-created ignored runtime_logs/prompt08 run directory.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
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


def main():
    name, separator, *command = sys.argv[1:]
    if separator != "--" or not name.replace("-", "").isalnum() or not command:
        raise SystemExit("NAME -- COMMAND required")
    directory = ROOT / "runtime_logs" / "prompt08" / (name + "-" + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    if command[:3] == ["python", "-m", "pytest"]:
        command = [sys.executable, *command[1:]]
        command.extend(["--junitxml=" + str(directory / "junit.xml"), "-p", "tests.prompt08_receipts"])
        env["P08_RECEIPT_ROOT"] = str(directory)
        (ROOT / "runtime").mkdir(exist_ok=True)
        command.append("--basetemp=" + str(ROOT / "runtime" / directory.name))
    start = time.time()
    print(json.dumps({"name": name, "directory": str(directory), "command": command}), flush=True)
    with (directory / "command.log").open("wb") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    receipt = {"name": name, "command": command, "exit_code": result.returncode,
               "status": "PASS" if result.returncode == 0 else "FAIL", "duration_seconds": time.time() - start,
               "platform": platform.platform(), "python": sys.version, "plugin_autoload": False,
               "dependencies": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()},
               "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir() if path.is_file()}}
    if (directory / "junit.xml").is_file():
        document = ElementTree.parse(directory / "junit.xml")
        receipt["junit_suites"] = [element.attrib for element in document.findall(".//testsuite")]
        receipt["skips"] = [{"test": case.attrib, "reason": skipped.attrib} for case in document.findall(".//testcase") for skipped in case.findall("skipped")]
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"receipt": str(directory / "receipt.json"), "exit_code": result.returncode}), flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
