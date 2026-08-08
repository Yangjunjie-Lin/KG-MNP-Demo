#!/usr/bin/env python3
"""Run the trusted Stage 08 WebVOWL/browser publication integration."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy/webvowl/docker-compose.integration.yml"
MALICIOUS_FIXTURE = ROOT / "tests/webvowl/fixtures/malicious-labels.ttl"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_graphdb_evidence() -> tuple[dict, dict]:
    from kg_mnp_demo.graphdb.contracts import (
        GraphDBContractError,
        validate_graphdb_contract,
    )
    from kg_mnp_demo.graphdb.identifiers import repository_id_for_publication

    expected_graphdb = _json(
        ROOT
        / "examples/graphdb/expected/full-confirmation/graphdb-import-manifest.json"
    )
    paths = sorted(
        (ROOT / "runtime_reports/graphdb").glob("*/verification/tbox-equivalence.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for tbox_path in paths:
        report_root = tbox_path.parents[1]
        attestation_path = report_root / "graphdb-import-attestation.json"
        if not attestation_path.is_file():
            continue
        tbox = _json(tbox_path)
        attestation = _json(attestation_path)
        try:
            validate_graphdb_contract("import-attestation", attestation)
            attestation_valid = True
        except GraphDBContractError:
            attestation_valid = False
        if not attestation_valid:
            continue
        publication_id = str(attestation.get("source_publication_id", ""))
        publication_hash = publication_id.rsplit(":", 1)[-1]
        hashes = {
            attestation.get("import_semantic_hash"),
            attestation.get("explicit_export_semantic_hash"),
            attestation.get("complete_export_semantic_hash"),
        }
        if (
            tbox.get("status") != "PASS"
            or tbox.get("equal") is not True
            or tbox.get("source") != "LIVE_GRAPHDB_EXPLICIT_EXPORT"
            or attestation.get("status") != "IMPORT_VERIFIED"
            or attestation.get("license_state") != "ACCEPTED"
            or attestation.get("repository_ruleset") != "empty"
            or len(hashes) != 1
            or attestation.get("expected_graph_count")
            != attestation.get("actual_graph_count")
            or attestation.get("expected_quad_count")
            != attestation.get("actual_quad_count")
            or attestation.get("physical_default_graph_count") != 0
            or attestation.get("violating_forbidden_assertion_count") != 0
            or attestation.get("inferred_statement_count") != 0
            or publication_id != expected_graphdb["publication_id"]
            or report_root.name != publication_hash
            or attestation.get("repository_id")
            != repository_id_for_publication(publication_hash)
        ):
            continue
        return tbox, attestation
    raise RuntimeError(
        "no co-located, contract-valid Stage 07 GraphDB/TBox evidence is verified"
    )


def _compose(
    project: str, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-p", project, "-f", str(COMPOSE), *args],
        cwd=ROOT,
        check=check,
        text=True,
    )


def _cleanup_compose_project(project: str) -> None:
    completed = _compose(project, "down", "-v", "--remove-orphans", check=False)
    if completed.returncode != 0:
        raise RuntimeError("WebVOWL Compose cleanup failed")
    checks = (
        ("containers", ["docker", "ps", "-a"], "{{.ID}}"),
        ("networks", ["docker", "network", "ls"], "{{.ID}}"),
        ("volumes", ["docker", "volume", "ls"], "{{.Name}}"),
    )
    for label, command, output_format in checks:
        probe = subprocess.run(
            [
                *command,
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--format",
                output_format,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        if probe.stdout.strip():
            raise RuntimeError(f"WebVOWL Compose cleanup left {label} behind")


def _runtime_image_digest(project: str) -> str:
    image_id = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(COMPOSE),
            "images",
            "-q",
            "webvowl",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not image_id:
        raise RuntimeError("WebVOWL runtime image identity is unavailable")
    digest = subprocess.run(
        ["docker", "image", "inspect", image_id, "--format", "{{.Id}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not digest.startswith("sha256:"):
        raise RuntimeError("WebVOWL runtime image digest is invalid")
    return digest


def _assert_loopback_publish(project: str) -> None:
    """Require the fixed-upstream relay to publish loopback and nothing else."""
    container = f"{project}-loopback-proxy-1"
    published = subprocess.run(
        ["docker", "port", container, "8080"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if published != "127.0.0.1:8080":
        raise RuntimeError(
            f"runtime port is not loopback-only: {published or 'missing'}"
        )


def _assert_loopback_port_available() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 8080))
    except OSError as exc:
        raise RuntimeError(
            "required loopback endpoint 127.0.0.1:8080 is already in use"
        ) from exc
    finally:
        probe.close()


def _runtime_egress_probe(container: str) -> dict:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "3",
            "--max-time",
            "5",
            "https://example.com/",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "status": "PASS" if result.returncode != 0 else "FAILED",
        "external_url": "https://example.com/",
        "connection_blocked": result.returncode != 0,
        "curl_exit_code": result.returncode,
    }


def _malicious_fixture_source() -> dict:
    """Return an isolated, hash-bound ontology source for browser security."""
    relative = MALICIOUS_FIXTURE.relative_to(ROOT).as_posix()
    return {
        "root": ROOT,
        "files": [
            {
                "role": "ROOT_ONTOLOGY",
                "path": relative,
                "sha256": hashlib.sha256(MALICIOUS_FIXTURE.read_bytes()).hexdigest(),
            }
        ],
    }


def main() -> int:
    from verify_owl2vowl_conversion import _exact_sources_ready
    from webvowl_browser_smoke import run as browser_run

    from kg_mnp_demo.compilation.manifest import json_bytes
    from kg_mnp_demo.publication.contracts import (
        validate_publication_attestation_evidence,
    )
    from kg_mnp_demo.publication.package_builder import (
        build_end_to_end_publication_package,
    )
    from kg_mnp_demo.publication.package_validator import (
        validate_end_to_end_publication_package_against_authorities,
    )
    from kg_mnp_demo.webvowl.converter import convert_with_owl2vowl_docker
    from kg_mnp_demo.webvowl.package_builder import build_webvowl_visualization_package
    from kg_mnp_demo.webvowl.policy import load_webvowl_policy
    from kg_mnp_demo.webvowl.runtime import runtime_descriptor, runtime_smoke
    from kg_mnp_demo.webvowl.source import build_visualization_source

    tbox, graphdb_attestation = _latest_graphdb_evidence()
    _assert_loopback_port_available()
    policy = load_webvowl_policy()
    if not _exact_sources_ready(policy):
        subprocess.run(
            [
                "python",
                "scripts/fetch_webvowl_upstream.py",
                "--output",
                "upstream-source",
            ],
            cwd=ROOT,
            check=True,
        )
    converter_image = "kg-mnp-owl2vowl:" + policy["owl2vowl"]["commit_sha"][:12]
    subprocess.run(
        [
            "docker",
            "build",
            "--target",
            "owl2vowl-cli-builder",
            "-t",
            converter_image,
            "-f",
            "deploy/webvowl/Dockerfile.integration",
            ".",
        ],
        cwd=ROOT,
        check=True,
    )
    source = build_visualization_source()
    raw_runs = (
        convert_with_owl2vowl_docker(source, image=converter_image),
        convert_with_owl2vowl_docker(source, image=converter_image),
    )
    output = ROOT / "runtime_outputs/webvowl/live-package"
    visualization = build_webvowl_visualization_package(
        output_dir=output,
        force=True,
        graphdb_tbox_semantic_hash=tbox["graphdb_tbox_semantic_hash"],
        raw_converter_runs=raw_runs,
    )
    project = (
        "kgmnp-webvowl-" + visualization["manifest"]["visualization_semantic_hash"][:12]
    )
    browser: dict = {"status": "FAILED", "error": "not run"}
    runtime: dict = {}
    runtime_container = f"{project}-webvowl-1"
    try:
        _compose(project, "up", "--build", "--detach")
        _assert_loopback_publish(project)
        deadline = time.monotonic() + 180
        while True:
            runtime = runtime_smoke(timeout=10)
            if runtime["status"] == "PASS":
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("WebVOWL runtime did not become healthy")
            time.sleep(3)
        runtime["egress_probe"] = _runtime_egress_probe(runtime_container)
        if runtime["egress_probe"]["status"] != "PASS":
            raise RuntimeError("WebVOWL runtime internet egress was not blocked")
        browser = browser_run(
            "http://127.0.0.1:8080", str(output / "visualization/kg-mnp.webvowl.json")
        )
        if browser.get("status") != "PASS":
            raise RuntimeError(
                "WebVOWL browser smoke failed: " + json.dumps(browser, sort_keys=True)
            )
        malicious = convert_with_owl2vowl_docker(
            _malicious_fixture_source(), image=converter_image
        )
        malicious_path = ROOT / "runtime_outputs/webvowl/malicious-labels.webvowl.json"
        malicious_path.write_bytes(json_bytes(malicious))
        security_browser = browser_run(
            "http://127.0.0.1:8080",
            str(malicious_path),
            require_security_expectations=True,
        )
        if security_browser.get("status") != "PASS":
            raise RuntimeError(
                "WebVOWL browser security probe failed: "
                + json.dumps(security_browser, sort_keys=True)
            )
        browser["security_probe"] = security_browser
        runtime_image_digest = _runtime_image_digest(project)
        publication = build_end_to_end_publication_package(
            scenario="full-confirmation",
            visualization_package=visualization,
            output_dir=ROOT / "runtime_outputs/publication/full-confirmation",
            force=True,
        )
        publication_validation = (
            validate_end_to_end_publication_package_against_authorities(
                ROOT / "runtime_outputs/publication/full-confirmation",
                scenario="full-confirmation",
                graphdb_tbox_semantic_hash=tbox["graphdb_tbox_semantic_hash"],
            )
        )
        if publication_validation.get("valid") is not True:
            raise RuntimeError("end-to-end publication authority validation failed")
        digest = publication["manifest"]["publication_semantic_hash"]
        report_dir = ROOT / "runtime_reports/publication" / digest
        report_dir.mkdir(parents=True, exist_ok=True)
        attestation = {
            "contract_version": "1.0",
            "status": "PUBLICATION_VERIFIED",
            "publication_id": publication["manifest"]["publication_id"],
            "publication_semantic_hash": publication["manifest"][
                "publication_semantic_hash"
            ],
            "visualization_id": visualization["manifest"]["visualization_id"],
            "visualization_semantic_hash": visualization["manifest"][
                "visualization_semantic_hash"
            ],
            "graphdb_tbox_semantic_hash": tbox["graphdb_tbox_semantic_hash"],
            "stage03_tbox_semantic_hash": tbox["stage03_tbox_semantic_hash"],
            "raw_vowl_hash": visualization["manifest"]["raw_converter_sha256"],
            "normalized_vowl_hash": visualization["manifest"]["normalized_vowl_sha256"],
            "coverage_status": visualization["coverage"]["status"],
            "browser_status": browser["status"],
            "graphdb_version": graphdb_attestation["graphdb_version"]["response"][
                "productVersion"
            ],
            "graphdb_license_state": graphdb_attestation["license_state"],
            "graphdb_oci_image_digest": graphdb_attestation["oci_image_digest"],
            "webvowl_upstream_commit": policy["webvowl"]["commit_sha"],
            "owl2vowl_upstream_commit": policy["owl2vowl"]["commit_sha"],
            "runtime_image_digest": runtime_image_digest,
            "browser_name": browser["browser_name"],
            "browser_version": browser["browser_version"],
            "browser_revision": browser["browser_revision"],
            "playwright_version": browser["playwright_version"],
        }
        runtime_report = {
            **runtime_descriptor(policy=policy, image_digest=runtime_image_digest),
            "smoke": runtime,
        }
        upstream_lock = _json(output / "source/upstream-lock.json")
        validate_publication_attestation_evidence(
            attestation,
            publication_manifest=publication["manifest"],
            visualization_manifest=visualization["manifest"],
            coverage=visualization["coverage"],
            representation_loss=visualization["representation_loss"],
            tbox_equivalence=tbox,
            upstream_lock=upstream_lock,
            browser_smoke=browser,
            webvowl_runtime=runtime_report,
        )
        records = {
            "publication-attestation.json": attestation,
            "publication-manifest.json": publication["manifest"],
            "visualization-manifest.json": visualization["manifest"],
            "ontology-visualization-coverage.json": visualization["coverage"],
            "representation-loss.json": visualization["representation_loss"],
            "tbox-equivalence.json": tbox,
            "webvowl-runtime.json": runtime_report,
            "browser-smoke.json": browser,
            "upstream-lock.json": upstream_lock,
        }
        summary = {
            name: hashlib.sha256(json_bytes(value)).hexdigest()
            for name, value in sorted(records.items())
        }
        records["hash-summary.json"] = {"contract_version": "1.0", "sha256": summary}
        for name, value in records.items():
            (report_dir / name).write_bytes(json_bytes(value))
        print(
            json.dumps(
                {
                    "status": "PUBLICATION_VERIFIED",
                    "publication_id": attestation["publication_id"],
                    "report_directory": report_dir.as_posix(),
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        _cleanup_compose_project(project)


if __name__ == "__main__":
    raise SystemExit(main())
