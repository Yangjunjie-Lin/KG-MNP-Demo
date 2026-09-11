from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from kg_mnp.compilation.manifest import json_bytes
from kg_mnp.publication.package_builder import (
    build_end_to_end_publication_package,
)
from kg_mnp.webvowl.policy import load_webvowl_policy

ROOT = Path(__file__).resolve().parents[2]
STAGE08_ARTIFACT_FILES = (
    "browser-smoke.json",
    "hash-summary.json",
    "ontology-visualization-coverage.json",
    "publication-attestation.json",
    "publication-manifest.json",
    "representation-loss.json",
    "tbox-equivalence.json",
    "upstream-lock.json",
    "visualization-manifest.json",
    "webvowl-runtime.json",
)


def _stage08_artifact_scanner() -> str:
    return (ROOT/'tools/check_historical_attestation_artifacts.py').read_text(encoding='utf-8')


def _run_artifact_scanner(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-", str(root)],
        input=_stage08_artifact_scanner(),
        text=True,
        capture_output=True,
        check=False,
    )


@lru_cache(maxsize=1)
def _valid_stage08_artifacts() -> dict[str, bytes]:
    publication = build_end_to_end_publication_package(scenario="full-confirmation")
    visualization = publication["visualization"]
    manifest = visualization["manifest"]
    policy = load_webvowl_policy()
    tbox = json.loads(visualization["files"]["verification/tbox-equivalence.json"])
    attestation = {
        "contract_version": "1.0",
        "status": "PUBLICATION_VERIFIED",
        "publication_id": publication["manifest"]["publication_id"],
        "publication_semantic_hash": publication["manifest"][
            "publication_semantic_hash"
        ],
        "visualization_id": manifest["visualization_id"],
        "visualization_semantic_hash": manifest["visualization_semantic_hash"],
        "graphdb_tbox_semantic_hash": tbox["graphdb_tbox_semantic_hash"],
        "stage03_tbox_semantic_hash": tbox["stage03_tbox_semantic_hash"],
        "raw_vowl_hash": manifest["raw_converter_sha256"],
        "normalized_vowl_hash": manifest["normalized_vowl_sha256"],
        "coverage_status": visualization["coverage"]["status"],
        "browser_status": "PASS",
        "graphdb_version": "11.4.2",
        "graphdb_license_state": "ACCEPTED",
        "graphdb_oci_image_digest": "sha256:" + "0" * 64,
        "webvowl_upstream_commit": policy["webvowl"]["commit_sha"],
        "owl2vowl_upstream_commit": policy["owl2vowl"]["commit_sha"],
        "runtime_image_digest": "sha256:" + "1" * 64,
        "browser_name": "chromium",
        "browser_version": "131.0.6778.33",
        "browser_revision": "1148",
        "playwright_version": "1.49.1",
    }
    records = {
        "publication-attestation.json": attestation,
        "publication-manifest.json": publication["manifest"],
        "visualization-manifest.json": manifest,
        "ontology-visualization-coverage.json": visualization["coverage"],
        "representation-loss.json": visualization["representation_loss"],
        "tbox-equivalence.json": tbox,
        "webvowl-runtime.json": {
            "contract_version": "1.0",
            "runtime_id": "kg-mnp-webvowl-runtime",
            "bind_host": "127.0.0.1",
            "port": 8080,
            "external_exposure": "FORBIDDEN",
            "runtime_internet_access": "FORBIDDEN",
            "image_digest": "sha256:" + "1" * 64,
            "smoke": {
                "status": "PASS",
                "errors": [],
                "egress_probe": {
                    "status": "PASS",
                    "connection_blocked": True,
                },
            },
        },
        "browser-smoke.json": {
            "status": "PASS",
            "browser_name": "chromium",
            "browser_version": "131.0.6778.33",
            "browser_revision": "1148",
            "playwright_version": "1.49.1",
            "canonical_vowl_loaded": True,
            "class_nodes": manifest["class_count"],
            "property_nodes": manifest["object_property_count"]
            + manifest["datatype_property_count"],
            "svg_count": 1,
            "javascript_errors": [],
            "console_errors": [],
            "external_requests": [],
            "browser_http_egress_probe_blocked": True,
            "browser_websocket_egress_probe_blocked": True,
            "loopback_proxy_egress_probe": {"status": "PASS"},
            "security_probe": {
                "status": "PASS",
                "security_label_count": 3,
                "encoded_iri_count": 1,
                "security_labels_rendered_as_text": True,
                "encoded_iris_loaded": True,
                "script_executed": False,
                "injected_html_nodes": 0,
                "external_requests": [],
                "javascript_errors": [],
                "console_errors": [],
            },
        },
        "upstream-lock.json": json.loads(
            visualization["files"]["source/upstream-lock.json"]
        ),
    }
    encoded = {name: json_bytes(value) for name, value in records.items()}
    encoded["hash-summary.json"] = json_bytes(
        {
            "contract_version": "1.0",
            "sha256": {
                name: hashlib.sha256(data).hexdigest()
                for name, data in sorted(encoded.items())
            },
        }
    )
    assert set(encoded) == set(STAGE08_ARTIFACT_FILES)
    return encoded


def _write_valid_stage08_artifacts(root: Path) -> None:
    for name, data in _valid_stage08_artifacts().items():
        (root / name).write_bytes(data)


def test_only_current_workbench_dependencies_and_converter_build_are_supported() -> None:
    manifest = json.loads((ROOT / "workbench/package.json").read_bytes())
    locked = json.loads((ROOT / "workbench/package-lock.json").read_bytes())
    assert locked["lockfileVersion"] >= 3
    for section in ("dependencies", "devDependencies"):
        for name, version in manifest[section].items():
            assert version and not any(marker in version for marker in ("latest", "^", "~", "*"))
            assert locked["packages"]["node_modules/" + name]["version"] == version
    dockerfile = (ROOT / "deploy/webvowl/Dockerfile.integration").read_text(encoding="utf-8")
    assert "owl2vowl-cli-builder" in dockerfile and "${MAVEN_DIGEST}" in dockerfile
    for retired in ("webvowl-runtime", "webvowl-builder", "loopback-proxy", "EXPOSE", "CATALINA"):
        assert retired not in dockerfile


def test_no_old_webvowl_server_or_forward_proxy_is_distributed() -> None:
    for path in ("scripts/webvowl_integration.py", "scripts/webvowl_browser_smoke.py",
                 "deploy/webvowl/loopback-proxy.js", "deploy/webvowl/docker-compose.integration.yml"):
        assert not (ROOT / path).exists()


def test_current_browser_gate_actively_checks_all_network_protocols() -> None:
    source = (ROOT / "workbench/tests/security.e2e.ts").read_text(encoding="utf-8")
    for expected in ("http://external.invalid", "https://external.invalid",
                     "ws://external.invalid", "wss://external.invalid", "securitypolicyviolation",
                     "route.abort", "routeWebSocket", "expect(intercepted).toEqual([])"):
        assert expected in source
    assert "EXPECTED_PLAYWRIGHT_VERSION" not in source


@pytest.mark.parametrize(
    ("relative_path", "payload"),
    (
        ("authorization.json", {"status": "PASS"}),
        ("browser-smoke.json", {"AuThOrIzAtIoN": "Bearer redacted"}),
        ("browser-smoke.json", {"CoOkIe": "session=redacted"}),
        ("browser-smoke.json", {"Auths": {"registry": "redacted"}}),
        ("browser-smoke.json", {"source": "/home/runner/.M2/repository"}),
        ("browser-smoke.json", {"diagnostic": "PATH=/bin\nHOME=/home/runner"}),
        ("RAW-ENV.json", {"status": "PASS"}),
        ("ENV.JSON", {"status": "PASS"}),
    ),
)
def test_stage08_artifact_scan_fails_closed_case_insensitively(
    tmp_path: Path, relative_path: str, payload: dict
) -> None:
    _write_valid_stage08_artifacts(tmp_path)
    artifact = tmp_path / relative_path
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    result = _run_artifact_scanner(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr


def test_stage08_artifact_scan_allows_only_nonsecret_attestation_metadata(
    tmp_path: Path,
) -> None:
    _write_valid_stage08_artifacts(tmp_path)
    result = _run_artifact_scanner(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sensitive-data scan: PASS" in result.stdout


def test_stage08_artifact_scan_rejects_unexpected_benign_json(tmp_path: Path) -> None:
    _write_valid_stage08_artifacts(tmp_path)
    (tmp_path / "unexpected-benign.json").write_text("{}", encoding="utf-8")
    result = _run_artifact_scanner(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unexpected artifact files" in result.stderr


def test_stage08_ci_cleanup_and_publication_boundary_are_closed() -> None:
    workflow=(ROOT/'.github/workflows/ci-workbench.yml').read_text(encoding='utf-8')
    scanner=_stage08_artifact_scanner()
    assert 'object_pairs_hook=reject_duplicate_keys' in scanner
    assert 'attestation artifact sensitive-data scan: PASS' in scanner
    assert 'tools/run_browser_verification.py' in workflow
    assert 'docker compose' not in workflow and '|| true' not in workflow

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "# 知构工具链 · ZhiGou Toolchain" in readme
    assert 'Ontology Package' in readme
    assert 'CAS' in readme and 'Attestation' in readme
    assert 'Provider 只生成候选' in readme
    baseline = subprocess.run(["git", "rev-list", "-n", "1", "kg-mnp-phase06-baseline-2026-08-30"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert baseline.stdout.strip() == "e45da340267de8d4b7b3a54177822aa641e3a601"

    stage08_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in (
            ROOT / "src/zhigou_toolchain/webvowl",
            ROOT / "src/zhigou_toolchain/publication",
        )
        for path in directory.glob("*.py")
    ).casefold()
    for forbidden in ("fastapi", "flask", "langchain", "neo4j", "openai"):
        assert forbidden not in stage08_sources
