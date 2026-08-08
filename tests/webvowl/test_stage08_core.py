from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kg_mnp_demo.modeling.dependencies import ROOT
from kg_mnp_demo.webvowl.contracts import (
    WebVOWLContractError,
    load_webvowl_schema,
    validate_webvowl_contract,
)
from kg_mnp_demo.webvowl.normalizer import NormalizationError, normalize_vowl_json
from kg_mnp_demo.webvowl.package_builder import build_webvowl_visualization_package
from kg_mnp_demo.webvowl.package_validator import validate_webvowl_visualization_package
from kg_mnp_demo.webvowl.policy import (
    OWL2VOWL_SHA,
    WEBVOWL_SHA,
    WebVOWLPolicyError,
    load_webvowl_policy,
    validate_webvowl_policy,
)
from kg_mnp_demo.webvowl.runtime import runtime_smoke
from kg_mnp_demo.webvowl.source import VisualizationSourceError, _safe_local
from kg_mnp_demo.webvowl.verifier import WebVOWLVerificationError, tbox_equivalence


def test_webvowl_contracts_and_policy_are_frozen() -> None:
    for name in (
        "webvowl-runtime-policy",
        "visualization-manifest",
        "coverage-report",
        "representation-loss",
    ):
        assert load_webvowl_schema(name)["additionalProperties"] is False
    policy = load_webvowl_policy()
    assert policy["webvowl"]["commit_sha"] == WEBVOWL_SHA
    assert policy["owl2vowl"]["commit_sha"] == OWL2VOWL_SHA
    assert policy["conversion"]["network_mode"] == "none"
    assert len(policy["conversion"]["audited_raw_sha256"]) == 64
    assert len(policy["conversion"]["audited_normalized_sha256"]) == 64
    assert len(policy["conversion"]["audited_source_tbox_sha256"]) == 64
    assert policy["network"]["bind_host"] == "127.0.0.1"
    assert policy["visualization"]["scope"] == "TBOX_ONLY"
    assert all(len(image["digest"]) == 71 for image in policy["images"].values())


def test_visualization_manifest_contract_recomputes_identity() -> None:
    manifest = build_webvowl_visualization_package()["manifest"]
    forged = copy.deepcopy(manifest)
    forged["class_count"] += 1
    with pytest.raises(WebVOWLContractError, match="identity/hash mismatch"):
        validate_webvowl_contract("visualization-manifest", forged)


@pytest.mark.parametrize(
    "base_url",
    (
        "https://example.invalid",
        "http://localhost:8080",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:8080/remote",
    ),
)
def test_runtime_smoke_rejects_non_loopback_targets_without_network(
    base_url: str,
) -> None:
    result = runtime_smoke(base_url)
    assert result["status"] == "FAILED"
    assert result["errors"] == ["runtime smoke requires http://127.0.0.1:8080"]


def test_policy_rejects_mutable_or_forged_upstream() -> None:
    policy = load_webvowl_policy()
    for mutate in (
        lambda p: p["webvowl"].update(commit_sha="0" * 40),
        lambda p: p["owl2vowl"].update(source_version="latest"),
        lambda p: p["retrieval"].update(fallback_branch="main"),
        lambda p: p["source_tree_hashes"].update(webvowl="0" * 40),
        lambda p: p["images"]["node"].update(digest="sha256:" + "0" * 64),
        lambda p: p["conversion"].update(audited_raw_sha256="0" * 64),
        lambda p: p["conversion"].update(audited_source_tbox_sha256="0" * 64),
        lambda p: p["webvowl"].update(
            repository="https://github.com/VisualDataWeb/OWL2VOWL.git"
        ),
    ):
        forged = copy.deepcopy(policy)
        mutate(forged)
        with pytest.raises(WebVOWLPolicyError):
            validate_webvowl_policy(forged)


def test_exact_source_and_runtime_have_no_mutable_fallback() -> None:
    fetch = Path("scripts/fetch_webvowl_upstream.py").read_text(encoding="utf-8")
    dockerfile = Path("deploy/webvowl/Dockerfile.integration").read_text(
        encoding="utf-8"
    )
    compose = Path("deploy/webvowl/docker-compose.integration.yml").read_text(
        encoding="utf-8"
    )
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    assert '"fetch", "--quiet", "origin", commit' in fetch
    assert '"checkout", "--quiet", "--detach", commit' in fetch
    assert '"--tags"' not in fetch
    assert "git clone" not in dockerfile
    assert dockerfile.count("@${") >= 4
    assert 'published: "8080"' in compose
    assert "host_ip: 127.0.0.1" in compose
    assert "no-new-privileges:true" in compose
    assert "internal: true" in compose
    assert "target: loopback-proxy" in compose
    assert "fonts.googleapis.com" in dockerfile
    assert "sed -i" in dockerfile
    assert dockerignore.startswith("**\n")
    assert "!runtime_" not in dockerignore and "!*.license" not in dockerignore


def test_normalizer_rejects_duplicate_unknown_and_abox_content() -> None:
    with pytest.raises(NormalizationError, match="duplicate JSON key"):
        normalize_vowl_json(
            '{"classAttribute":[],"classAttribute":[],"propertyAttribute":[]}'
        )
    with pytest.raises(NormalizationError, match="unsupported VOWL top-level"):
        normalize_vowl_json(
            {"classAttribute": [], "propertyAttribute": [], "runtime": {}}
        )
    with pytest.raises(NormalizationError, match="unsupported VOWL node fields"):
        normalize_vowl_json(
            {
                "classAttribute": [{"id": "1", "iri": "urn:test", "evil": True}],
                "propertyAttribute": [],
            }
        )
    with pytest.raises(NormalizationError, match="ABox individuals"):
        normalize_vowl_json(
            {"classAttribute": [], "propertyAttribute": [], "individual": [{"id": "1"}]}
        )
    with pytest.raises(NormalizationError, match="duplicate VOWL class internal id"):
        normalize_vowl_json(
            {
                "classAttribute": [
                    {"id": "1", "iri": "urn:a"},
                    {"id": "1", "iri": "urn:b"},
                ],
                "propertyAttribute": [],
            }
        )
    with pytest.raises(NormalizationError, match="dangling VOWL domain reference"):
        normalize_vowl_json(
            {
                "classAttribute": [{"id": "1", "iri": "urn:a"}],
                "propertyAttribute": [{"id": "1", "iri": "urn:p", "domain": "9"}],
            }
        )
    policy = load_webvowl_policy()["normalization_exclusion_policy"]
    controlled = normalize_vowl_json(
        {
            "classAttribute": [
                {
                    "id": "1",
                    "iri": "urn:class",
                    "instances": 0,
                    "individuals": [
                        {
                            "iri": "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#Code-Test"
                        }
                    ],
                }
            ],
            "propertyAttribute": [],
        },
        exclusion_policy=policy,
    )
    assert "individuals" not in controlled["classAttribute"][0]
    with pytest.raises(NormalizationError, match="ABox individuals"):
        normalize_vowl_json(
            {
                "classAttribute": [
                    {
                        "id": "1",
                        "iri": "urn:class",
                        "individuals": [{"iri": "urn:kg-mnp:data/business"}],
                    }
                ],
                "propertyAttribute": [],
            },
            exclusion_policy=policy,
        )
    with pytest.raises(NormalizationError, match="not closed"):
        normalize_vowl_json(
            {
                "class": [],
                "property": [],
                "classAttribute": [{"id": "1", "iri": "urn:test:Class"}],
                "propertyAttribute": [],
            }
        )
    with pytest.raises(NormalizationError, match="header fields"):
        normalize_vowl_json(
            {
                "header": {"attacker": "hidden"},
                "classAttribute": [],
                "propertyAttribute": [],
            }
        )


def test_visualization_source_rejects_path_escape() -> None:
    for path in (
        "../ontology/kg-mnp.ttl",
        "C:/outside.ttl",
        "\\\\server\\share\\ontology.ttl",
    ):
        with pytest.raises(VisualizationSourceError):
            _safe_local(ROOT, path)


def test_projection_is_deterministic_complete_and_abox_free() -> None:
    first = build_webvowl_visualization_package()
    second = build_webvowl_visualization_package()
    assert first["files"] == second["files"]
    assert first["coverage"]["status"] == "PASS"
    assert first["coverage"]["missing_required_terms"] == []
    assert first["coverage"]["unexpected_project_terms"] == []
    assert first["coverage"]["abox_leakage_hits"] == []
    assert "individual" not in first["normalized_vowl"]
    assert first["manifest"]["visualization_scope"] == "TBOX_ONLY"
    assert first["manifest"]["class_count"] > 0
    assert first["manifest"]["object_property_count"] > 0
    assert first["manifest"]["datatype_property_count"] > 0


def test_graphdb_tbox_must_be_compared_not_assumed() -> None:
    package = build_webvowl_visualization_package()
    report = json.loads(package["files"]["verification/tbox-equivalence.json"])
    assert report["status"] == "UNVERIFIED"
    assert report["graphdb_tbox_semantic_hash"] is None
    assert package["manifest"]["release_status"] == "VISUALIZATION_UNVERIFIED"
    source_hash = package["source"]["tbox_semantic_hash"]
    verified = build_webvowl_visualization_package(
        graphdb_tbox_semantic_hash=source_hash
    )
    assert verified["manifest"]["release_status"] == "VISUALIZATION_VALIDATED"
    assert (
        tbox_equivalence(
            stage03_semantic_hash=source_hash, graphdb_semantic_hash=source_hash
        )["equal"]
        is True
    )
    with pytest.raises(WebVOWLVerificationError):
        build_webvowl_visualization_package(graphdb_tbox_semantic_hash="0" * 64)


def test_webvowl_package_validator_reconstructs_exact_bytes(tmp_path: Path) -> None:
    out = tmp_path / "package"
    build_webvowl_visualization_package(output_dir=out)
    assert validate_webvowl_visualization_package(out)["valid"] is True
    path = out / "visualization" / "kg-mnp.webvowl.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["classAttribute"].pop()
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="bytes mismatch"):
        validate_webvowl_visualization_package(out)
