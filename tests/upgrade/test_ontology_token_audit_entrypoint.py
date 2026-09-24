"""Check the distributed entry point without runtime data or model access."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "tools/ontology_usage_audit/token-audit-portable-v1"


def test_distributed_auditor_imports_without_runtime_source():
    result = subprocess.run([sys.executable, str(ROOT / "tools/audit_ontology_tokens.py"), "--help"],
                            cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert "snapshot" in result.stdout and "watch" in result.stdout


def test_distributed_source_and_dependency_match_distribution_byte_pins():
    freeze = json.loads((BUNDLE / "freeze.json").read_bytes())
    for name, expected in freeze["files"].items():
        assert hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() == expected
    helper = BUNDLE / freeze["helper"]["path"]
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == freeze["helper"]["sha256"]


def test_distributed_cli_missing_workspace_is_safe_json(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "tools/audit_ontology_tokens.py"), "snapshot",
                             "--workspace", str(tmp_path / "PRIVATE_MISSING_WORKSPACE")],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False and report["error"] == "AUDIT_FAILED"
    assert "PRIVATE_MISSING_WORKSPACE" not in result.stdout
    assert result.stderr == ""
