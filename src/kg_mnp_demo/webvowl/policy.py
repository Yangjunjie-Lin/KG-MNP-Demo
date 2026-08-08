from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT

POLICY_PATH = ROOT / "config" / "webvowl" / "webvowl-runtime-1.0.0.yaml"
WEBVOWL_SHA = "28e7dd9540622e8cb723dc000824b5eef5ae775f"
OWL2VOWL_SHA = "c6331c4c79b0034b8537a11cccd1a6587cedb0b9"
WEBVOWL_REPOSITORY = "https://github.com/VisualDataWeb/WebVOWL.git"
OWL2VOWL_REPOSITORY = "https://github.com/VisualDataWeb/OWL2VOWL.git"
AUDITED_RAW_SHA256 = "c61ea6ff3badeb9e1e89aa06f9faa09086face68197794738b027a785fba750f"
AUDITED_NORMALIZED_SHA256 = (
    "461ca94d9034c2ce762fa7a19bfd5cce5bd244ccaf3a970200a632062b0e66b6"
)
AUDITED_RAW_FIXTURE = "examples/publication/fixtures/owl2vowl-0.3.7-raw.json"
AUDITED_SOURCE_TBOX_SHA256 = (
    "4d66605486f5f581a8d83344e2144639e1c03a8bc8320d1bc30e69ab9058da95"
)
WEBVOWL_NPM_SHRINKWRAP = "deploy/webvowl/webvowl-npm-shrinkwrap.json"
WEBVOWL_NPM_SHRINKWRAP_SHA256 = (
    "74c5094525121337d6b71d0862ec9543a0356e536b00fe67b45f03d031f0fdda"
)
IMAGE_LOCKS = {
    "maven": (
        "maven:3.9.16-eclipse-temurin-8-noble",
        "sha256:0537e78bbba084ec350fcaa0dedef6efa34440e4e464bbb284f0f1e47043f629",
    ),
    "node": (
        "node:12-alpine",
        "sha256:4517380049fc3c9aacceae7764fcf3500354b0ac8a47e4afb35b5bbeb75b9498",
    ),
    "tomcat_jdk": (
        "tomcat:9.0.118-jdk8-temurin-noble",
        "sha256:41836df54c3781e0e835e61a4761b566d0de9187eb6c56340191b343e1fe3101",
    ),
    "tomcat_jre": (
        "tomcat:9.0.118-jre8-temurin-noble",
        "sha256:6ac38ff9831b03e18e83174eca45d746f2accde3a5c8f8bc48ba2c9fd63b8b17",
    ),
}


class WebVOWLPolicyError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    pass


def _map(
    loader: _Loader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    out: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in out:
            raise WebVOWLPolicyError(f"duplicate YAML key: {key}")
        out[key] = loader.construct_object(value_node, deep=deep)
    return out


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _map)


def load_webvowl_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
    except (OSError, UnicodeError, yaml.YAMLError, WebVOWLPolicyError) as exc:
        raise WebVOWLPolicyError(f"cannot read WebVOWL policy: {exc}") from exc
    if not isinstance(value, dict):
        raise WebVOWLPolicyError("WebVOWL policy root must be an object")
    validate_webvowl_policy(value)
    repository_root = path.resolve().parents[2]
    shrinkwrap = repository_root / WEBVOWL_NPM_SHRINKWRAP
    try:
        shrinkwrap_hash = hashlib.sha256(shrinkwrap.read_bytes()).hexdigest()
    except OSError as exc:
        raise WebVOWLPolicyError(f"cannot read WebVOWL npm shrinkwrap: {exc}") from exc
    if shrinkwrap.is_symlink() or shrinkwrap_hash != WEBVOWL_NPM_SHRINKWRAP_SHA256:
        raise WebVOWLPolicyError("WebVOWL npm shrinkwrap file hash mismatch")
    from .contracts import validate_webvowl_contract

    validate_webvowl_contract("webvowl-runtime-policy", value, repository_root)
    return value


def validate_webvowl_policy(policy: Mapping[str, Any]) -> None:
    if (
        policy.get("contract_version") != "1.0"
        or policy.get("runtime_id") != "kg-mnp-webvowl-runtime"
    ):
        raise WebVOWLPolicyError("unsupported WebVOWL runtime identity")
    if policy.get("runtime_version") != "1.0.0":
        raise WebVOWLPolicyError("unsupported WebVOWL runtime version")
    for name, sha, version in (
        ("webvowl", WEBVOWL_SHA, "1.1.7"),
        ("owl2vowl", OWL2VOWL_SHA, "0.3.7"),
    ):
        section = policy.get(name)
        if (
            not isinstance(section, Mapping)
            or section.get("commit_sha") != sha
            or section.get("source_version") != version
        ):
            raise WebVOWLPolicyError(f"{name} upstream lock mismatch")
        expected_repository = (
            WEBVOWL_REPOSITORY if name == "webvowl" else OWL2VOWL_REPOSITORY
        )
        if section.get("repository") != expected_repository:
            raise WebVOWLPolicyError(f"{name} repository is not the frozen upstream")
    trees = policy.get("source_tree_hashes", {})
    if trees != {
        "webvowl": "48eb27270c30aea2f464e2bb142f2142c1d341e4",
        "owl2vowl": "fcac129cfaf33f05ce62fd9c41b9fe05ce260e88",
    }:
        raise WebVOWLPolicyError("upstream source tree hash lock mismatch")
    network = policy.get("network", {})
    if (
        network.get("bind_host") != "127.0.0.1"
        or int(network.get("port", 0)) != 8080
        or network.get("external_exposure") != "FORBIDDEN"
        or network.get("runtime_internet_access") != "FORBIDDEN"
    ):
        raise WebVOWLPolicyError("WebVOWL runtime must be loopback-only and offline")
    visualization = policy.get("visualization", {})
    if (
        visualization.get("scope") != "TBOX_ONLY"
        or visualization.get("abox_visualization") != "FORBIDDEN"
        or visualization.get("graphdb_is_semantic_authority") is not False
        or visualization.get("ontology_is_semantic_authority") is not True
    ):
        raise WebVOWLPolicyError("invalid WebVOWL semantic boundary")
    conversion = policy.get("conversion", {})
    if (
        conversion.get("source") != "STAGE03_ROOT_PLUS_RUNTIME_DEPENDENCIES"
        or conversion.get("remote_iri_loading") != "FORBIDDEN"
        or conversion.get("external_import_resolution") != "FORBIDDEN"
        or conversion.get("deterministic_normalization") != "REQUIRED"
        or conversion.get("network_mode") != "none"
        or conversion.get("audited_raw_fixture") != AUDITED_RAW_FIXTURE
        or conversion.get("audited_source_tbox_sha256") != AUDITED_SOURCE_TBOX_SHA256
        or conversion.get("audited_raw_sha256") != AUDITED_RAW_SHA256
        or conversion.get("audited_normalized_sha256") != AUDITED_NORMALIZED_SHA256
    ):
        raise WebVOWLPolicyError("invalid WebVOWL conversion policy")
    exclusion = policy.get("normalization_exclusion_policy", {}).get(
        "class_individuals", {}
    )
    if (
        exclusion.get("field") != "classAttribute[].individuals"
        or exclusion.get("action") != "REMOVE_FROM_PRESENTATION_PROJECTION"
        or exclusion.get("allowed_iri_prefix")
        != "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#Code-"
        or exclusion.get("evidence") != "ontology/mnp-code-list.ttl"
        or not exclusion.get("reason")
    ):
        raise WebVOWLPolicyError("normalization exclusion policy mismatch")
    images = policy.get("images")
    if not isinstance(images, Mapping) or not images:
        raise WebVOWLPolicyError("base image lock is missing")
    if set(images) != set(IMAGE_LOCKS):
        raise WebVOWLPolicyError("base image lock set mismatch")
    for name, image in images.items():
        if not isinstance(image, Mapping) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(image.get("digest", ""))
        ):
            raise WebVOWLPolicyError(f"base image digest is not full: {name}")
        expected_reference, expected_digest = IMAGE_LOCKS[name]
        if (image.get("reference"), image.get("digest")) != (
            expected_reference,
            expected_digest,
        ):
            raise WebVOWLPolicyError(f"base image lock mismatch: {name}")
    if policy.get("build_dependencies") != {
        "webvowl_npm_shrinkwrap": {
            "path": WEBVOWL_NPM_SHRINKWRAP,
            "sha256": WEBVOWL_NPM_SHRINKWRAP_SHA256,
            "install_mode": "NPM_CI",
        }
    }:
        raise WebVOWLPolicyError("WebVOWL npm shrinkwrap lock mismatch")
    if policy.get("license") != {"webvowl": "MIT", "owl2vowl": "MIT"}:
        raise WebVOWLPolicyError("upstream MIT license record is missing")
    if policy.get("retrieval", {}).get("method") != "ISOLATED_GIT_FETCH_EXACT_COMMIT":
        raise WebVOWLPolicyError("exact isolated upstream retrieval is required")
    if policy.get("retrieval", {}).get("fallback_branch") != "FORBIDDEN":
        raise WebVOWLPolicyError("mutable upstream fallback is forbidden")


def webvowl_policy_hash(policy: Mapping[str, Any] | None = None) -> str:
    return semantic_hash(dict(policy or load_webvowl_policy()))
