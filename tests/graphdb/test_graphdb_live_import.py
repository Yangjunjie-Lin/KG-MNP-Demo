from __future__ import annotations

import json
import importlib.util
import base64
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ._helpers import ROOT


def _load_integration_module():
    path = ROOT / "scripts" / "graphdb_integration.py"
    spec = importlib.util.spec_from_file_location("graphdb_integration_cleanup_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_license_is_deleted_when_package_validation_fails(
    monkeypatch, tmp_path
):
    module = _load_integration_module()
    digest = "a" * 64
    built = {
        "manifest": {"publication_semantic_hash": digest},
        "files": {},
    }

    import kg_mnp_demo.compilation.artifacts as artifacts
    import kg_mnp_demo.compilation.policy as compilation_policy
    import kg_mnp_demo.graphdb.package_builder as package_builder
    import kg_mnp_demo.graphdb.package_validator as package_validator

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_authorities", lambda: ({},) * 9)
    monkeypatch.setattr(module, "COMPOSE_FILES", [tmp_path / "compose.yml"])
    monkeypatch.setenv("GRAPHDB_LICENSE_CONTENT", "runtime-only-test-license")
    monkeypatch.delenv("GRAPHDB_LICENSE_FILE", raising=False)
    monkeypatch.delenv("GRAPHDB_LICENSE_B64", raising=False)
    monkeypatch.setattr(package_builder, "build_graphdb_import_package", lambda *args: built)
    monkeypatch.setattr(artifacts, "write_artifact_set", lambda *args, **kwargs: None)
    monkeypatch.setattr(compilation_policy, "load_compiler_policy", lambda: {})

    def fail_validation(*args, **kwargs):
        raise RuntimeError("synthetic package validation failure")

    monkeypatch.setattr(package_validator, "validate_graphdb_import_package", fail_validation)

    with pytest.raises(RuntimeError, match="synthetic package validation failure"):
        module.main()

    runtime_root = tmp_path / "runtime_outputs" / "graphdb"
    assert not list(runtime_root.glob("*.graphdb-license"))
    assert not list(runtime_root.glob(".compose-license-*.yml"))
    assert module.COMPOSE_FILES == [tmp_path / "compose.yml"]


def test_license_b64_is_strict_and_requests_private_permissions(monkeypatch, tmp_path):
    module = _load_integration_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.delenv("GRAPHDB_LICENSE_FILE", raising=False)
    monkeypatch.delenv("GRAPHDB_LICENSE_CONTENT", raising=False)
    monkeypatch.setenv("GRAPHDB_LICENSE_B64", "not-base64!")

    with pytest.raises(RuntimeError, match="EXTERNAL_GRAPHDB_LICENSE_B64_INVALID"):
        module._license_runtime_file("4" * 64)
    assert not list(tmp_path.rglob("*.graphdb-license"))

    requested_modes = []
    monkeypatch.setenv(
        "GRAPHDB_LICENSE_B64",
        base64.b64encode(b"runtime-only-test-license").decode("ascii"),
    )
    monkeypatch.setattr(
        module.os,
        "chmod",
        lambda path, mode: requested_modes.append((path, mode)),
    )
    path, source_type = module._license_runtime_file("5" * 64)

    assert source_type == "B64"
    assert path.read_bytes() == b"runtime-only-test-license"
    assert requested_modes == [(path, 0o600)]
    path.unlink()


def test_multiple_license_sources_fail_with_stable_ambiguous_reason(
    monkeypatch, tmp_path
):
    module = _load_integration_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("GRAPHDB_LICENSE_CONTENT", "first")
    monkeypatch.setenv(
        "GRAPHDB_LICENSE_B64",
        base64.b64encode(b"second").decode("ascii"),
    )
    monkeypatch.delenv("GRAPHDB_LICENSE_FILE", raising=False)

    with pytest.raises(
        RuntimeError,
        match="EXTERNAL_GRAPHDB_LICENSE_SOURCE_AMBIGUOUS",
    ):
        module._license_runtime_file("6" * 64)


def test_live_default_dataset_probe_separates_merged_view_from_physical_storage():
    module = _load_integration_module()

    class Client:
        def get_default_graph(self, repository_id):
            assert repository_id == "kg-mnp-" + "1" * 20
            return SimpleNamespace(
                http_status=200,
                statement_count=0,
                semantic_hash="2" * 64,
                content_type="application/n-triples",
            )

        def sparql_select(self, repository_id, query):
            assert "GRAPH" not in query.upper()
            return {
                "head": {"vars": ["s", "p", "o"]},
                "results": {
                    "bindings": [
                        {
                            "s": {"type": "uri", "value": "urn:s"},
                            "p": {"type": "uri", "value": "urn:p"},
                            "o": {"type": "uri", "value": "urn:o"},
                        }
                    ]
                },
            }

    evidence = module._assert_default_dataset_semantics(
        Client(), "kg-mnp-" + "1" * 20
    )

    assert evidence["ordinary_default_dataset_visible_named_data"] is True
    assert evidence["physical_default_graph_statement_count"] == 0
    assert evidence["default_graph_http_status"] == 200


def test_live_inference_regression_requires_full_export_difference_and_fail_closed(
    monkeypatch, tmp_path
):
    module = _load_integration_module()
    repository_id = "kg-mnp-" + "3" * 20
    explicit = b"<urn:s> <urn:p> <urn:o> <urn:g> .\n"
    complete = explicit + b"<urn:s> <urn:inferred> <urn:o> <urn:g> .\n"

    class Client:
        deleted = False

        def create_repository(self, config):
            assert b'graphdb:ruleset "rdfsplus-optimized"' in config
            return 201

        def inspect_repository(self, requested_repository_id):
            assert requested_repository_id == repository_id
            return {"params": {"ruleset": {"value": "rdfsplus-optimized"}}}

        def import_nquads(self, requested_repository_id, data):
            assert requested_repository_id == repository_id
            assert data == explicit
            return 204

        def export_nquads(self, requested_repository_id, *, include_inferred=False):
            assert requested_repository_id == repository_id
            return complete if include_inferred else explicit

        def delete_generated_repository(self, requested_repository_id):
            assert requested_repository_id == repository_id
            self.deleted = True
            return 204

    labels = []
    monkeypatch.setattr(
        module,
        "_must_fail_verification",
        lambda client, package_dir, *, label: labels.append(label),
    )
    client = Client()
    built = {
        "manifest": {"repository_id": repository_id},
        "files": {
            "repository/repository-config.ttl": (
                b'[] <urn:unused> "value" ; graphdb:ruleset "empty" .\n'
            ),
            "import/knowledge-graph.nq": explicit,
        },
    }

    evidence = module._run_live_inference_regression(client, tmp_path, built)

    assert evidence["ruleset"] == "rdfsplus-optimized"
    assert evidence["inferred_statement_count"] == 1
    assert evidence["explicit_semantic_hash"] != evidence["complete_semantic_hash"]
    assert labels == ["inference-enabled repository"]
    assert client.deleted is True


def test_graphdb_live_import_is_fail_closed_without_external_license_or_verifies_with_one():
    env = os.environ.copy()
    has_license = any(
        env.get(name)
        for name in ("GRAPHDB_LICENSE_FILE", "GRAPHDB_LICENSE_CONTENT", "GRAPHDB_LICENSE_B64")
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/graphdb_integration.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if not has_license:
        assert result.returncode != 0
        assert "EXTERNAL_GRAPHDB_LICENSE_MISSING" in result.stdout
        assert "license" not in result.stderr.lower() or "EXTERNAL_GRAPHDB_LICENSE_MISSING" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == "IMPORT_VERIFIED"
