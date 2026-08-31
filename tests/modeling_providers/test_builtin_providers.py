from __future__ import annotations

import copy
import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

from kg_mnp.modeling.control_plane.errors import ModelingProviderError
from kg_mnp.modeling.control_plane.providers.execution import execute_provider
from kg_mnp.modeling.control_plane.providers.models import build_provider_request
from kg_mnp.modeling.control_plane.providers.recorded_model import (
    import_recorded_model_output,
    verify_model_invocation_record,
)
from kg_mnp.plugins import discovery
from kg_mnp.plugins.conformance import run_conformance
from kg_mnp.plugins.models import PluginStatus
from kg_mnp.plugins.registry import PluginRegistry
from kg_mnp.plugins.snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "provider_id",
    [
        "manual-candidate-provider",
        "baseline-reuse-provider",
        "rule-mapping-provider",
        "recorded-model-output-provider",
    ],
)
def test_builtin_provider_manifests_are_proposal_only_offline(provider_id: str) -> None:
    descriptor = PluginRegistry().get(provider_id)
    assert descriptor.manifest["plugin_api_version"] == "1.1.0"
    assert descriptor.manifest["authority_level"] == "PROPOSAL_ONLY"
    assert descriptor.manifest["network_policy"] == "DENY"
    assert "modeling-provider" in descriptor.manifest["plugin_kinds"]


def test_builtin_provider_conformance_and_core_owned_ids(prompt04_case: dict) -> None:
    registry = PluginRegistry()
    result = run_conformance(registry, "rule-mapping-provider")
    assert result.status == "PASS"
    snapshot = build_snapshot(registry.get("manual-candidate-provider"))
    request = build_provider_request(
        modeling_input_bundle_id=prompt04_case["input_bundle"]["modeling_input_bundle_id"],
        provider_snapshot_id=snapshot["snapshot_id"],
        capability="tbox-proposal",
        scope_id=prompt04_case["scope"]["scope_id"],
        baseline_snapshot_id=prompt04_case["baseline"]["baseline_snapshot_id"],
        terminology_catalog_id=prompt04_case["terminology"]["terminology_catalog_id"],
        term_alignment_set_id=prompt04_case["alignments"]["term_alignment_set_id"],
        kg_ir_dataset_ids=[prompt04_case["dataset"]["dataset_id"]],
        evidence_record_ids=prompt04_case["input_bundle"]["evidence_record_ids"],
        context={"manual_drafts": []},
    )
    response = execute_provider(registry, "manual-candidate-provider", request)
    assert response["authority_level"] == "PROPOSAL_ONLY"
    assert all("candidate_id" not in draft for draft in response["candidate_drafts"])


def test_recorded_output_rejects_authority_fields_and_tamper(prompt04_case: dict) -> None:
    kwargs = {
        "provider_name": "recorded-model-output-provider",
        "model_id": "fixture-model",
        "model_revision": "recorded",
        "request_artifact_ref": "request.json",
        "request_bytes": b"{}",
        "response_artifact_ref": "response.json",
        "prompt_template_id": "template-v1",
        "prompt_template_sha256": "0" * 64,
        "sampling_parameters": {},
    }
    raw = json.dumps({"candidate_drafts": []}).encode()
    drafts, record = import_recorded_model_output(raw, **kwargs)
    assert drafts == ()
    assert record["determinism_class"] == "RECORDED_BYTES_ONLY"
    malicious = json.dumps({"candidate_drafts": [{"confirmed": True}]}).encode()
    with pytest.raises(ModelingProviderError, match="authority field"):
        import_recorded_model_output(malicious, **kwargs)
    changed = copy.deepcopy(record)
    changed["response_sha256"] = "f" * 64
    with pytest.raises(ModelingProviderError, match="tampered"):
        verify_model_invocation_record(changed)


def test_independent_modeling_provider_wheel_is_disabled_then_conformant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = ROOT / "tests/fixtures/plugins/sample-modeling-provider"
    wheelhouse = tmp_path / "wheelhouse"
    site = tmp_path / "site"
    wheelhouse.mkdir()
    site.mkdir()
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(fixture),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheel = next(wheelhouse.glob("*.whl"))
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(site), str(wheel)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    distributions = tuple(metadata.distributions(path=[str(site)]))
    entry_points = tuple(
        point
        for distribution in distributions
        for point in distribution.entry_points
        if point.group == "kg_mnp.plugins"
    )
    monkeypatch.setattr(discovery, "_entry_points", lambda: entry_points)
    monkeypatch.syspath_prepend(str(site))
    sys.modules.pop("sample_modeling_provider.plugin", None)
    descriptors = discovery.discover_external_plugins()
    assert len(descriptors) == 1
    assert descriptors[0].status == PluginStatus.DISABLED
    assert "sample_modeling_provider.plugin" not in sys.modules
    disabled = PluginRegistry(descriptors=descriptors, discover_external=False)
    assert disabled.get("sample-modeling-provider").status == PluginStatus.DISABLED
    enabled = PluginRegistry(
        descriptors=descriptors,
        discover_external=False,
        allowlist=("sample-modeling-provider",),
    )
    result = run_conformance(enabled, "sample-modeling-provider")
    assert result.status == "PASS", result.errors
