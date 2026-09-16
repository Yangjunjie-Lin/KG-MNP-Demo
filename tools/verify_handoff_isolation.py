"""Actual WSL/bubblewrap generation + repair with synthetic recording, no paid calls."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

from zhigou_toolchain.modeling.delivery.exchange_io import atomic_file, json_bytes
from zhigou_toolchain.ontology_io.os_sandbox import command, stage_code, wsl_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    public, generated, code = output / "input", output / "output", output / "code"
    public.mkdir()
    generated.mkdir()
    source = stage_code(root, code)
    fixtures = root / "tests/fixtures/ontology_io/kernel"
    sample = json.loads((fixtures / "primitive-input.json").read_bytes())
    protocol = yaml.safe_load((root / "config/ontology_io/protocols/kernel-engineering.yaml").read_text(encoding="utf-8"))
    protocol["kernel_profile"]["reasoner_jar"] = "/opt/robot.jar"
    atomic_file(public / "job.json", json_bytes({"sample": sample, "protocol": protocol, "system": "TwoAgentKernelV1", "replicate_id": 0}))
    atomic_file(public / "recording.json", (fixtures / "primitive-recording.json").read_bytes())
    atomic_file(public / "public-input.txt", b"PUBLIC_CANARY_INPUT")
    forbidden = []
    for name in ("acceptance_private/expected_answers.json", "tests/gold.json", "references/whole-package.zip", "docs/ontology/evidence/check.json"):
        path = output / "private" / name
        atomic_file(path, b"SYNTHETIC_PRIVATE_ACCESS_CANARY")
        forbidden.extend([wsl_path(path), "/proc/1/root" + wsl_path(path)])
    for name in ("docs/ontology/references/meeting-handoff-v2.original.zip", "docs/ontology/evidence/attachment-check.json", "tests/upgrade/test_full_chain.py"):
        path = root / name
        if not path.is_file():
            raise ValueError("PRIVATE_PROBE_TARGET_MISSING")
        forbidden.append(wsl_path(path))
    invocation = command(code, public, generated, root / "third_party/downloads/robot-1.9.7.jar",
                         extra=["--recording-check", "--forbidden", *forbidden])
    result = subprocess.run(invocation, capture_output=True, timeout=180, check=False)
    atomic_file(output / "stdout.log", result.stdout)
    atomic_file(output / "stderr.log", result.stderr)
    report = json.loads((generated / "isolation-check.json").read_bytes()) if (generated / "isolation-check.json").exists() else {}
    receipt = {"exit_code": result.returncode, "status": "PASS" if result.returncode == 0 and report.get("generation_status") == "GENERATED" and report.get("repair_cycles", 0) >= 1 else "FAIL",
               "source": source, "report": report, "live_inference_calls": 0,
               "scope": "ACTUAL_RESEARCH_KERNEL_GENERATION_AND_REPAIR_PROCESS_NOT_PRODUCTION_WORKER_SANDBOX"}
    atomic_file(output / "receipt.json", json_bytes(receipt))
    print(json.dumps({"status": receipt["status"], "exit_code": result.returncode, "output": str(output)}, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
