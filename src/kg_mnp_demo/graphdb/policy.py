from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import yaml

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT

POLICY_PATH = ROOT / "config" / "graphdb" / "graphdb-runtime-1.0.0.yaml"


class GraphDBPolicyError(ValueError):
    pass


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _UniqueLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise GraphDBPolicyError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_graphdb_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError, GraphDBPolicyError) as exc:
        raise GraphDBPolicyError(f"cannot read GraphDB policy: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphDBPolicyError("GraphDB policy root must be an object")
    validate_graphdb_policy(value)
    return value


def validate_graphdb_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("contract_version") != "1.0":
        raise GraphDBPolicyError("unsupported GraphDB policy contract version")
    if policy.get("runtime_id") != "kg-mnp-graphdb-runtime":
        raise GraphDBPolicyError("unexpected GraphDB runtime id")
    graphdb = policy.get("graphdb")
    network = policy.get("network")
    repository = policy.get("repository")
    import_policy = policy.get("import")
    if not all(isinstance(value, Mapping) for value in (graphdb, network, repository, import_policy)):
        raise GraphDBPolicyError("GraphDB policy sections are incomplete")
    if graphdb.get("product_version") != "11.4.2" or graphdb.get("image_tag") != "11.4.2":
        raise GraphDBPolicyError("GraphDB version/tag is not frozen to 11.4.2")
    for field in ("image_digest_amd64", "image_digest_arm64", "image_manifest_digest"):
        value = graphdb.get(field)
        if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
            raise GraphDBPolicyError(f"{field} must be a full SHA-256 digest")
    if network.get("host") != "127.0.0.1" or network.get("external_exposure") != "FORBIDDEN":
        raise GraphDBPolicyError("GraphDB must bind only to 127.0.0.1")
    if int(network.get("port", 0)) != 7200:
        raise GraphDBPolicyError("GraphDB port must be 7200")
    if repository.get("ruleset") != "empty" or repository.get("inference") != "FORBIDDEN":
        raise GraphDBPolicyError("GraphDB inference policy must be empty/FORBIDDEN")
    if repository.get("overwrite_existing_repository") != "FORBIDDEN":
        raise GraphDBPolicyError("existing repositories may not be overwritten")
    if repository.get("initial_repository_must_be_empty") is not True:
        raise GraphDBPolicyError("fresh repository requirement is missing")
    if import_policy.get("authoritative_format") != "NQUADS" or import_policy.get("preserve_named_graphs") is not True:
        raise GraphDBPolicyError("N-Quads named-graph preservation is required")
    if import_policy.get("default_graph_import") != "FORBIDDEN":
        raise GraphDBPolicyError("default graph import is forbidden")


def graphdb_policy_semantic_hash(policy: Mapping[str, Any] | None = None) -> str:
    value = dict(policy or load_graphdb_policy())
    return semantic_hash(value)


def graphdb_policy_hash(policy: Mapping[str, Any] | None = None) -> str:
    return graphdb_policy_semantic_hash(policy)
