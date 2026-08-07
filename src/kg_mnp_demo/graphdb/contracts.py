from __future__ import annotations

import json
import re
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ..modeling.dependencies import ROOT

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/graphdb/"
SPECS = {
    "graphdb-runtime-policy": ("graphdb_runtime_policy.schema.json", SCHEMA_BASE + "runtime-policy/1.0"),
    "graphdb-import-manifest": ("graphdb_import_manifest.schema.json", SCHEMA_BASE + "import-manifest/1.0"),
    "import-plan": ("import_plan.schema.json", SCHEMA_BASE + "import-plan/1.0"),
    "query-suite-manifest": ("query_suite_manifest.schema.json", SCHEMA_BASE + "query-suite/1.0"),
    "import-attestation": ("import_attestation.schema.json", SCHEMA_BASE + "import-attestation/1.0"),
    "query-result": ("query_result.schema.json", SCHEMA_BASE + "query-result/1.0"),
    "forbidden-business-assertions": ("forbidden_business_assertions.schema.json", SCHEMA_BASE + "forbidden-business-assertions/1.0"),
}


class GraphDBContractError(ValueError):
    pass


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GraphDBContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def schema_path(name: str, *, root: Path = ROOT) -> Path:
    try:
        filename, _ = SPECS[name]
    except KeyError as exc:
        raise GraphDBContractError(f"unknown GraphDB contract: {name}") from exc
    return root / "schemas" / "graphdb" / filename


def load_graphdb_schema(name: str, *, root: Path = ROOT) -> dict[str, Any]:
    path = schema_path(name, root=root)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except Exception as exc:
        raise GraphDBContractError(f"cannot read GraphDB schema {path}: {exc}") from exc
    if schema.get("$schema") != DRAFT_2020_12 or schema.get("$id") != SPECS[name][1]:
        raise GraphDBContractError(f"invalid GraphDB schema identifier: {path}")
    Draft202012Validator.check_schema(schema)
    return schema


def graphdb_contract_names() -> tuple[str, ...]:
    return tuple(SPECS)


def validate_graphdb_contract(name: str, payload: Mapping[str, Any]) -> None:
    schema = load_graphdb_schema(name)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        raise GraphDBContractError(f"{name}: {errors[0].message}")
    if name == "graphdb-runtime-policy":
        from .policy import validate_graphdb_policy
        validate_graphdb_policy(payload)
    if name == "graphdb-import-manifest":
        _validate_import_manifest(payload)
    if name == "import-plan":
        _validate_import_plan(payload)
    if name == "query-suite-manifest":
        _validate_query_suite(payload)
    if name == "forbidden-business-assertions":
        _validate_forbidden_assertions(payload)


def _validate_forbidden_assertions(payload: Mapping[str, Any]) -> None:
    import hashlib
    from ..modeling.canonical_json import canonical_json_bytes

    records = list(payload["records"])
    projected = [
        record for record in records if record["projection_status"] == "PROJECTED"
    ]
    if int(payload["projection_record_count"]) != len(records):
        raise GraphDBContractError("forbidden assertion projection record count mismatch")
    if int(payload["forbidden_assertion_count"]) != len(
        {record["canonical_ntriples_line"] for record in projected}
    ):
        raise GraphDBContractError("forbidden assertion count mismatch")
    for record in records:
        projected_status = record["projection_status"] == "PROJECTED"
        projection_fields = (
            record["subject"], record["predicate"], record["object"],
            record["canonical_ntriples_line"],
        )
        if projected_status != all(value is not None for value in projection_fields):
            raise GraphDBContractError("forbidden assertion projection fields mismatch")
        if projected_status != (record["reason"] is None):
            raise GraphDBContractError("forbidden assertion projection reason mismatch")
    expected_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "records": records,
                "canonical_ntriples_sha256": payload["canonical_ntriples_sha256"],
            }
        )
    ).hexdigest()
    if payload["semantic_hash"] != expected_hash:
        raise GraphDBContractError("forbidden assertion semantic hash mismatch")


def _validate_import_manifest(payload: Mapping[str, Any]) -> None:
    from ..compilation.identifiers import artifact_id
    from .identifiers import publication_id, publication_semantic_hash, repository_id_for_publication

    if payload.get("repository_ruleset") != "empty" or payload.get("release_status") != "READY_FOR_GRAPHDB_IMPORT":
        raise GraphDBContractError("GraphDB import manifest is not import-ready")
    digest = publication_semantic_hash(payload)
    if payload.get("publication_semantic_hash") != digest or payload.get("publication_id") != publication_id(digest):
        raise GraphDBContractError("GraphDB publication identity mismatch")
    if payload.get("repository_id") != repository_id_for_publication(digest):
        raise GraphDBContractError("GraphDB repository identity mismatch")
    if len(payload["named_graphs"]) != len(set(payload["named_graphs"])):
        raise GraphDBContractError("GraphDB manifest named graph IRIs must be unique")
    paths: set[str] = set()
    artifact_ids: set[str] = set()
    for record in payload["artifact_manifest"]:
        relative_path = record["relative_path"]
        posix = PurePosixPath(relative_path)
        windows = PureWindowsPath(relative_path)
        if "\\" in relative_path or posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts or relative_path != posix.as_posix():
            raise GraphDBContractError(f"unsafe GraphDB artifact path: {relative_path}")
        expected_id = artifact_id({key: record[key] for key in ("relative_path", "role", "byte_sha256", "semantic_sha256")})
        if record["artifact_id"] != expected_id:
            raise GraphDBContractError(f"GraphDB artifact identity mismatch: {relative_path}")
        if relative_path in paths or record["artifact_id"] in artifact_ids:
            raise GraphDBContractError("GraphDB artifact paths and IDs must be unique")
        paths.add(relative_path)
        artifact_ids.add(record["artifact_id"])


def _validate_import_plan(payload: Mapping[str, Any]) -> None:
    from .identifiers import repository_id_for_publication
    from .import_plan import IMPORT_STEPS

    publication_id_value = str(payload["publication_id"])
    digest = publication_id_value.rsplit(":", 1)[-1]
    if payload["plan_id"] != f"urn:kg-mnp:graphdb-import-plan:{digest}":
        raise GraphDBContractError("GraphDB import plan identity mismatch")
    if payload["repository_id"] != repository_id_for_publication(digest):
        raise GraphDBContractError("GraphDB import plan repository mismatch")
    expected_steps = [
        {"step": index, "action": action}
        for index, action in enumerate(IMPORT_STEPS, start=1)
    ]
    if payload["steps"] != expected_steps:
        raise GraphDBContractError("GraphDB import plan steps are not the frozen sequence")


def _sparql_tokens(query: str) -> list[str]:
    cleaned: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(query):
        char = query[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if char == "#":
            while index < len(query) and query[index] not in "\r\n":
                index += 1
            continue
        if char == "<":
            while index < len(query) and query[index] != ">":
                index += 1
            index += 1
            continue
        cleaned.append(char)
        index += 1
    return [token.upper() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", "".join(cleaned))]


def _validate_query_suite(payload: Mapping[str, Any]) -> None:
    from rdflib.plugins.sparql.parser import parseQuery
    from .query_suite import query_suite_hash

    expected_ids = {f"{index:02d}-{name}" for index, name in enumerate((
        "repository-summary", "named-graph-counts", "business-assertions",
        "provenance-coverage", "review-audit-coverage", "tbox-version",
        "default-graph-storage", "no-tbox-in-business-graph",
        "no-rejected-business-facts", "no-blank-nodes",
    ), start=1)}
    query_ids = expected_ids - {"07-default-graph-storage"}
    if set(payload["queries"]) != query_ids or set(payload["verifications"]) != expected_ids:
        raise GraphDBContractError(
            "GraphDB verification suite must contain nine SPARQL checks and one Graph Store check"
        )
    graph_store = payload["verifications"]["07-default-graph-storage"]
    if graph_store != {
        "verification_type": "GRAPH_STORE_DEFAULT_GRAPH",
        "expected_statement_count": 0,
    }:
        raise GraphDBContractError("physical default graph must use Graph Store Protocol")
    forbidden = {"SERVICE", "LOAD", "INSERT", "DELETE", "CLEAR", "DROP", "CREATE", "MOVE", "COPY", "ADD"}
    for query_id, query in payload["queries"].items():
        tokens = _sparql_tokens(query)
        if forbidden.intersection(tokens) or not ({"SELECT", "ASK"} & set(tokens)):
            raise GraphDBContractError(f"unsafe GraphDB verification query: {query_id}")
        expected_type = "SPARQL_ASK" if "ASK" in tokens and "SELECT" not in tokens else "SPARQL_SELECT"
        verification = payload["verifications"].get(query_id)
        if verification != {
            "verification_type": expected_type,
            "query_id": query_id,
        }:
            raise GraphDBContractError(
                f"GraphDB verification type mismatch: {query_id}"
            )
        try:
            parseQuery(query)
        except Exception as exc:
            raise GraphDBContractError(f"invalid GraphDB verification query: {query_id}") from exc
    digest = query_suite_hash(payload)
    if payload["query_suite_hash"] != digest or payload["query_suite_id"] != f"urn:kg-mnp:graphdb-query-suite:{digest}":
        raise GraphDBContractError("GraphDB query suite identity mismatch")
    if set(payload["expected"]["named_graphs"]) != set(payload["expected"]["counts"]):
        raise GraphDBContractError("GraphDB query expected graph set/count keys mismatch")
    if len(payload["expected"]["tbox_versions"]) != int(payload["expected"]["tbox_module_count"]):
        raise GraphDBContractError("GraphDB TBox expected version set is incomplete")
    if set(payload["expected"]["ask"]) != {
        "08-no-tbox-in-business-graph", "10-no-blank-nodes"
    }:
        raise GraphDBContractError("GraphDB ASK expectation set mismatch")


validate_contract = validate_graphdb_contract
