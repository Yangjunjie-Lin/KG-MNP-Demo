"""Launch the optional DeepEval native bridge without inherited model credentials."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from zhigou_toolchain.ontology_io.deepeval_bridge import OFFLINE_SETTINGS
from zhigou_toolchain.ontology_io.provenance import source_identity

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, default=ROOT / "runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    identity = source_identity(ROOT)
    # Allow only ordinary runtime paths, never keys, endpoint configuration,
    # .env autoload, an authenticated Confident account, or model transports.
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(OFFLINE_SETTINGS, PYTHONUTF8="1", PYTHONPATH=str(ROOT / "src"))
    command = [sys.executable, "-m", "zhigou_toolchain.ontology_io.deepeval_bridge", "--upstream", str(args.upstream.resolve()),
        "--output", str(workspace / "equivalence.json")]
    try:
        process = subprocess.run(command, cwd=workspace, env=env, capture_output=True, timeout=120, check=False)
        (workspace / "worker.log").write_bytes(process.stdout + process.stderr)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
    unchanged = source_identity(ROOT) == identity
    report = {"exit_code": exit_code, "source_commit": identity["commit"], "source_fingerprint_sha256": identity["fingerprint"]["digest"],
        "source_unchanged": unchanged, "environment_policy": "CREDENTIAL_FREE_OFFLINE_ALLOWLIST", "research_scores": None,
        "scope": "DEEPEVAL_NATIVE_METRIC_BRIDGE_ENGINEERING_CHECK"}
    (workspace / "receipt.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return int(exit_code != 0 or not unchanged)


if __name__ == "__main__":
    raise SystemExit(main())
