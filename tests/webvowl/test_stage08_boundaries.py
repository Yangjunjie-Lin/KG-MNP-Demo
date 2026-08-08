from __future__ import annotations

import hashlib
import json
import runpy
import subprocess
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

import pytest

from kg_mnp_demo.compilation.manifest import json_bytes
from kg_mnp_demo.publication.package_builder import (
    build_end_to_end_publication_package,
)
from kg_mnp_demo.webvowl.policy import load_webvowl_policy

ROOT = Path(__file__).resolve().parents[2]
NPM_SHRINKWRAP_SHA256 = (
    "74c5094525121337d6b71d0862ec9543a0356e536b00fe67b45f03d031f0fdda"
)
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
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    marker = "python - \"$ARTIFACT_DIR\" <<'PY'\n"
    assert workflow.count(marker) == 2
    block = workflow.rsplit(marker, 1)[1].split("\n          PY", 1)[0]
    return textwrap.dedent(block)


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


def test_stage08_runtime_dependencies_are_content_locked() -> None:
    shrinkwrap_path = ROOT / "deploy/webvowl/webvowl-npm-shrinkwrap.json"
    shrinkwrap_bytes = shrinkwrap_path.read_bytes()
    assert hashlib.sha256(shrinkwrap_bytes).hexdigest() == NPM_SHRINKWRAP_SHA256
    shrinkwrap = json.loads(shrinkwrap_bytes)
    assert shrinkwrap["name"] == "webvowl"
    assert shrinkwrap["version"] == "1.1.7"
    assert shrinkwrap["lockfileVersion"] == 1

    dependency_count = 0

    def verify_dependencies(dependencies: dict) -> None:
        nonlocal dependency_count
        for dependency in dependencies.values():
            dependency_count += 1
            assert dependency["version"]
            assert dependency["resolved"].startswith("https://registry.npmjs.org/")
            assert dependency["integrity"].startswith("sha512-")
            verify_dependencies(dependency.get("dependencies", {}))

    verify_dependencies(shrinkwrap["dependencies"])
    assert dependency_count == 993

    dockerfile = (ROOT / "deploy/webvowl/Dockerfile.integration").read_text(
        encoding="utf-8"
    )
    compose = (ROOT / "deploy/webvowl/docker-compose.integration.yml").read_text(
        encoding="utf-8"
    )
    assert NPM_SHRINKWRAP_SHA256 in dockerfile
    assert NPM_SHRINKWRAP_SHA256 in compose
    assert "sha256sum -c -" in dockerfile
    assert "sed -i '\\|fonts.googleapis.com|d'" in dockerfile
    assert "! grep -R -n 'fonts.googleapis.com' src" in dockerfile
    assert "npm ci --ignore-scripts --no-audit --no-fund" in dockerfile
    assert "npm install" not in dockerfile


def test_loopback_relay_is_not_a_general_forward_proxy() -> None:
    proxy = (ROOT / "deploy/webvowl/loopback-proxy.js").read_text(encoding="utf-8")
    compose = (ROOT / "deploy/webvowl/docker-compose.integration.yml").read_text(
        encoding="utf-8"
    )
    assert 'const upstreamHost = "webvowl"' in proxy
    assert "allowedHostHeaders" in proxy
    assert 'rawUrl.startsWith("//")' in proxy
    assert 'server.on("connect"' in proxy
    assert 'server.on("upgrade"' in proxy
    assert "hostname: upstreamHost" in proxy
    assert "hostname: request" not in proxy
    assert proxy.count("403 Forbidden") >= 2
    assert "host_ip: 127.0.0.1" in compose
    assert "internal: true" in compose
    assert compose.count("cap_drop:") == 2
    assert compose.count("- ALL") == 2


def test_browser_gate_freezes_runtime_and_actively_blocks_all_network_protocols() -> (
    None
):
    namespace = runpy.run_path(str(ROOT / "scripts/webvowl_browser_smoke.py"))
    assert namespace["EXPECTED_BROWSER_NAME"] == "chromium"
    assert namespace["EXPECTED_BROWSER_VERSION"] == "131.0.6778.33"
    assert namespace["EXPECTED_BROWSER_REVISION"] == "1148"
    assert namespace["EXPECTED_PLAYWRIGHT_VERSION"] == "1.49.1"
    assert namespace["NETWORK_SCHEMES"] == {"http", "https", "ws", "wss"}
    allowed = ("http", "127.0.0.1", 8080)
    is_allowed = namespace["_allowed_network_target"]
    assert is_allowed("http://127.0.0.1:8080/app.js", allowed)
    assert is_allowed("ws://127.0.0.1:8080/socket", allowed)
    assert not is_allowed("https://example.invalid/app.js", allowed)
    assert not is_allowed("wss://example.invalid/socket", allowed)

    source = (ROOT / "scripts/webvowl_browser_smoke.py").read_text(encoding="utf-8")
    for required in (
        'context.route("**/*", route_network)',
        'context.route_web_socket("**/*", route_web_socket)',
        'route.abort("blockedbyclient")',
        "context.add_init_script(",
        'proxy={"server": base_url.rstrip("/"), "bypass": "127.0.0.1"}',
        'service_workers="block"',
        "External WebSocket forbidden",
        "_probe_fixed_loopback_proxy(base_url)",
        '"upgrade_status": upgrade_status',
    ):
        assert required in source
    assert source.index('context.route_web_socket("**/*", route_web_socket)') < (
        source.index("context.add_init_script(")
    )

    integration = (ROOT / "scripts/webvowl_integration.py").read_text(encoding="utf-8")
    assert "tests/webvowl/fixtures/malicious-labels.ttl" in integration
    assert "_malicious_fixture_source()" in integration
    assert "copy.deepcopy" not in integration


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
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "stage08-publication-attestation-${{ github.sha }}" in workflow
    assert "object_pairs_hook=reject_duplicate_keys" in workflow
    assert workflow.count("attestation artifact sensitive-data scan: PASS") == 2
    assert "label=com.docker.compose.project" in workflow
    assert 'docker compose -p "$project"' in workflow
    assert "mapfile -t remaining < <(discover_projects)" in workflow
    assert "|| true" not in workflow

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Stage 08 WebVOWL and End-to-End Publication | PASS" in readme
    assert "Foundation pipeline status = COMPLETE through Stage 08" in readme
    assert "This completes the ontology and knowledge graph foundation." in readme
    assert "PUBLICATION_VERIFIED" in readme
    assert "LIVE ATTESTATION PENDING" not in readme

    stage08_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in (
            ROOT / "src/kg_mnp_demo/webvowl",
            ROOT / "src/kg_mnp_demo/publication",
        )
        for path in directory.glob("*.py")
    ).casefold()
    for forbidden in ("fastapi", "flask", "langchain", "neo4j", "openai"):
        assert forbidden not in stage08_sources
