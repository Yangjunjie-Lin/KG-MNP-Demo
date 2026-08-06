from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .identifiers import validate_repository_id


class RepositoryConfigError(ValueError):
    pass


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return '"true"' if value else '"false"'
    if isinstance(value, int):
        return f'"{value}"'
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def repository_config_document(repository_id: str, *, label: str | None = None, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    validate_repository_id(repository_id)
    repository = (policy or {}).get("repository", {}) if policy else {}
    return {
        "repository_id": repository_id,
        # Keep the label stable so it does not introduce a repository-id/hash cycle.
        "repository_label": label or "KG-MNP Deterministic Knowledge Graph",
        "repository_type": "graphdb:SailRepository",
        "sail_type": "graphdb:Sail",
        "storage_type": "file-repository",
        "ruleset": repository.get("ruleset", "empty"),
        "disable_sameAs": repository.get("disable_sameAs", True),
        "enable_context_index": repository.get("context_index", True),
        "enable_fts_index": repository.get("literal_index", False),
        "query_timeout_seconds": int(repository.get("query_timeout_ms", 60000)) // 1000,
        "query_result_limit": repository.get("query_result_limit", 10000),
        "throw_query_evaluation_exception_on_timeout": True,
        "read_only": False,
        "inference": "FORBIDDEN",
    }


def render_repository_config_ttl(document: Mapping[str, Any]) -> bytes:
    required = {"repository_id", "repository_label", "ruleset", "disable_sameAs", "enable_context_index", "enable_fts_index", "query_timeout_seconds", "query_result_limit"}
    if not required <= set(document):
        raise RepositoryConfigError("repository config document is incomplete")
    validate_repository_id(str(document["repository_id"]))
    if document["ruleset"] != "empty" or document.get("inference") != "FORBIDDEN":
        raise RepositoryConfigError("repository ruleset must be empty and inference forbidden")
    lines = [
        "@prefix rep: <http://www.openrdf.org/config/repository#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix graphdb: <http://www.ontotext.com/config/graphdb#> .",
        "@prefix sr: <http://www.openrdf.org/config/repository/sail#> .",
        "@prefix sail: <http://www.openrdf.org/config/sail#> .",
        "",
        "_:repository a rep:Repository ;",
        f"    rep:repositoryID {_literal(document['repository_id'])} ;",
        f"    rdfs:label {_literal(document['repository_label'])} ;",
        "    rep:repositoryImpl _:impl .",
        "",
        "_:impl rep:repositoryType \"graphdb:SailRepository\" ;",
        "    sr:sailImpl _:sail .",
        "",
        "_:sail sail:sailType \"graphdb:Sail\" ;",
        "    graphdb:read-only \"false\" ;",
        "    graphdb:encrypt-storage \"false\" ;",
        f"    graphdb:ruleset {_literal(document['ruleset'])} ;",
        f"    graphdb:disable-sameAs {_literal(document['disable_sameAs'])} ;",
        "    graphdb:check-for-inconsistencies \"false\" ;",
        "    graphdb:entity-id-size \"32\" ;",
        f"    graphdb:enable-context-index {_literal(document['enable_context_index'])} ;",
        "    graphdb:enablePredicateList \"true\" ;",
        f"    graphdb:enable-fts-index {_literal(document['enable_fts_index'])} ;",
        f"    graphdb:query-timeout {_literal(document['query_timeout_seconds'])} ;",
        f"    graphdb:query-limit-results {_literal(document['query_result_limit'])} ;",
        f"    graphdb:throw-QueryEvaluationException-on-timeout {_literal(document['throw_query_evaluation_exception_on_timeout'])} ;",
        "    graphdb:imports \"\" ;",
        "    graphdb:repository-type \"file-repository\" ;",
        "    graphdb:storage-folder \"storage\" ;",
        "    graphdb:enable-literal-index \"false\" .",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def render_repository_config_nt(document: Mapping[str, Any]) -> bytes:
    validate_repository_id(str(document["repository_id"]))
    values = {
        "<http://www.openrdf.org/config/repository#repositoryID>": _literal(document["repository_id"]),
        "<http://www.w3.org/2000/01/rdf-schema#label>": _literal(document["repository_label"]),
        "<http://www.openrdf.org/config/repository#repositoryImpl>": "_:impl",
        "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>": "<http://www.openrdf.org/config/repository#Repository>",
    }
    lines = [f"_:repository {p} {o} ." for p, o in values.items()]
    impl_values = {
        "<http://www.openrdf.org/config/repository#repositoryType>": '"graphdb:SailRepository"',
        "<http://www.openrdf.org/config/repository/sail#sailImpl>": "_:sail",
    }
    sail_values = {
        "<http://www.openrdf.org/config/sail#sailType>": '"graphdb:Sail"',
        "<http://www.ontotext.com/config/graphdb#check-for-inconsistencies>": '"false"',
        "<http://www.ontotext.com/config/graphdb#disable-sameAs>": _literal(document["disable_sameAs"]),
        "<http://www.ontotext.com/config/graphdb#enable-literal-index>": '"false"',
        "<http://www.ontotext.com/config/graphdb#enable-context-index>": _literal(document["enable_context_index"]),
        "<http://www.ontotext.com/config/graphdb#enable-fts-index>": _literal(document["enable_fts_index"]),
        "<http://www.ontotext.com/config/graphdb#enablePredicateList>": '"true"',
        "<http://www.ontotext.com/config/graphdb#encrypt-storage>": '"false"',
        "<http://www.ontotext.com/config/graphdb#entity-id-size>": '"32"',
        "<http://www.ontotext.com/config/graphdb#imports>": '""',
        "<http://www.ontotext.com/config/graphdb#query-limit-results>": _literal(document["query_result_limit"]),
        "<http://www.ontotext.com/config/graphdb#query-timeout>": _literal(document["query_timeout_seconds"]),
        "<http://www.ontotext.com/config/graphdb#repository-type>": '"file-repository"',
        "<http://www.ontotext.com/config/graphdb#read-only>": _literal(document["read_only"]),
        "<http://www.ontotext.com/config/graphdb#ruleset>": _literal(document["ruleset"]),
        "<http://www.ontotext.com/config/graphdb#storage-folder>": '"storage"',
        "<http://www.ontotext.com/config/graphdb#throw-QueryEvaluationException-on-timeout>": _literal(document["throw_query_evaluation_exception_on_timeout"]),
    }
    lines.extend(f"_:impl {p} {o} ." for p, o in impl_values.items())
    lines.extend(f"_:sail {p} {o} ." for p, o in sail_values.items())
    return ("\n".join(sorted(lines)) + "\n").encode("utf-8")


def repository_config_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repository_config_semantic_hash(document: Mapping[str, Any]) -> str:
    from ..modeling.canonical_json import semantic_hash
    # The generated repository id is derived from the publication hash. It is
    # excluded here to avoid a circular identity definition.
    return semantic_hash(
        {key: document[key] for key in sorted(document) if key != "repository_id"}
    )
