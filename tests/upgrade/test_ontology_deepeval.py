"""Optional DeepEval integration must preserve native numbers without networking."""
from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from zhigou_toolchain.ontology_io.deepeval_bridge import (
    OFFLINE_SETTINGS,
    require_offline_settings,
)


def test_deepeval_import_requires_explicit_offline_profile(monkeypatch):
    for key in OFFLINE_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="OFFLINE_PROFILE"):
        require_offline_settings()


def test_scoring_profile_cannot_inherit_provider_or_cloud_credentials(monkeypatch):
    for key, value in OFFLINE_SETTINGS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CONFIDENT_API_KEY", "synthetic-do-not-export")
    with pytest.raises(ValueError, match="CREDENTIALS"):
        require_offline_settings()


def test_native_sync_async_equivalence_in_credential_free_worker(tmp_path):
    try:
        installed = version("deepeval")
    except PackageNotFoundError:
        pytest.skip("Optional DeepEval dependency absent; not a passing integration claim")
    if installed != "4.1.0":
        pytest.skip("Optional DeepEval version differs from audited 4.1.0 lock")
    root = Path(__file__).resolve().parents[2]
    upstream = root / "runtime/ontology-io/upstream/llms4ol_2026/315a9a5d883eada26e00fef1356a05802936c584"
    if not (upstream / "asset-lock.json").exists():
        pytest.skip("Pinned native scorer assets not prepared")
    output = tmp_path / "worker"
    process = subprocess.run([sys.executable, str(root / "tools/check_ontology_deepeval.py"),
        "--workspace", str(output), "--upstream", str(upstream)], capture_output=True, timeout=150, check=False)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    report = json.loads((output / "equivalence.json").read_bytes())
    assert report["metric_comparisons"] == 80 and all(r["equivalent"] for r in report["rows"])
    assert report["network_attempts"] == [] and report["llm_judge_calls"] == 0 and report["live_generation_calls"] == 0
    assert report["research_scores"] is None and report["failed_metric_state_cleared"]
    assert next(r["deepeval"] for r in report["rows"] if r["case"] == 0 and r["metric"] == "graph_similarity") == 1 / 3
