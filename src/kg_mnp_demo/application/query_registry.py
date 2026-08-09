"""Closed, versioned Application Phase 01 query registry."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT
from .errors import ApplicationError, ErrorCode
from .policy import ABSOLUTE_RESULT_LIMIT, GraphRole, QueryCategory
from .query_validator import require_graph_binding_placeholder, validate_query_text


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    type: str
    required: bool
    allowed: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryDefinition:
    query_id: str
    version: str
    category: QueryCategory
    description: str
    semantic_purpose: str
    template_path: Path
    query_type: str
    parameters: tuple[ParameterSpec, ...]
    output_contract: str
    allowed_named_graphs: tuple[GraphRole, ...]
    graph_bindings: dict[str, GraphRole]
    maximum_result_count: int
    timeout_seconds: float
    template_sha256: str

    def load_template(self) -> str:
        data = self.template_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.template_sha256:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        return data.decode("utf-8")


class QueryRegistry:
    def __init__(self, definitions: tuple[QueryDefinition, ...], *, document_hash: str):
        self._definitions = {item.query_id: item for item in definitions}
        if len(self._definitions) != len(definitions):
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        self.document_hash = document_hash

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        *,
        root: Path = ROOT,
    ) -> "QueryRegistry":
        registry_path = path or root / "config/application/query-registry-1.0.0.yaml"
        try:
            raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED) from exc
        if not isinstance(raw, dict) or set(raw) != {
            "contract_version",
            "registry_id",
            "registry_version",
            "queries",
        }:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        if raw["contract_version"] != "1.0" or raw["registry_version"] != "1.0.0":
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        definitions: list[QueryDefinition] = []
        seen_casefold: set[str] = set()
        for record in raw.get("queries", []):
            if not isinstance(record, dict):
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            query_id = str(record.get("query_id", ""))
            if query_id.casefold() in seen_casefold:
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            seen_casefold.add(query_id.casefold())
            relative = Path(str(record.get("template", "")))
            if relative.is_absolute() or ".." in relative.parts:
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            template_path = (root / relative).resolve()
            query_root = (root / "queries/application").resolve()
            if query_root not in template_path.parents or not template_path.is_file():
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            params = tuple(
                ParameterSpec(
                    name=str(item["name"]),
                    type=str(item["type"]),
                    required=bool(item.get("required", True)),
                    allowed=tuple(str(value) for value in item.get("allowed", [])),
                )
                for item in record.get("input_parameters", [])
            )
            graph_bindings = {
                str(variable): GraphRole(role)
                for variable, role in record.get("graph_bindings", {}).items()
            }
            allowed_graphs = tuple(
                GraphRole(role) for role in record.get("allowed_named_graphs", [])
            )
            if set(graph_bindings.values()) - set(allowed_graphs):
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            maximum = int(record.get("maximum_result_count", 0))
            timeout = float(record.get("timeout_seconds", 0))
            if not 1 <= maximum <= ABSOLUTE_RESULT_LIMIT or not 0 < timeout <= 10:
                raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
            definition = QueryDefinition(
                query_id=query_id,
                version=str(record["version"]),
                category=QueryCategory(record["category"]),
                description=str(record["description"]),
                semantic_purpose=str(record["semantic_purpose"]),
                template_path=template_path,
                query_type=str(record["query_type"]).upper(),
                parameters=params,
                output_contract=str(record["output_contract"]),
                allowed_named_graphs=allowed_graphs,
                graph_bindings=graph_bindings,
                maximum_result_count=maximum,
                timeout_seconds=timeout,
                template_sha256=str(record["template_sha256"]),
            )
            template = definition.load_template()
            for variable in definition.graph_bindings:
                require_graph_binding_placeholder(template, variable)
            validate_query_text(
                template,
                allowed_types=(definition.query_type,),
                graph_variables=definition.graph_bindings,
                allow_placeholders=True,
            )
            definitions.append(definition)
        if not definitions:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        return cls(tuple(definitions), document_hash=semantic_hash(raw))

    def get(self, query_id: str) -> QueryDefinition:
        try:
            return self._definitions[query_id]
        except (KeyError, TypeError) as exc:
            raise ApplicationError(ErrorCode.INVALID_QUERY_ID) from exc

    def list(self) -> tuple[QueryDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def manifest(self) -> dict[str, Any]:
        return {
            "contract_version": "1.0",
            "query_registry_hash": self.document_hash,
            "queries": [
                {
                    "query_id": item.query_id,
                    "version": item.version,
                    "category": item.category.value,
                    "allowed_named_graphs": [role.value for role in item.allowed_named_graphs],
                    "maximum_result_count": item.maximum_result_count,
                    "timeout_seconds": item.timeout_seconds,
                    "template_sha256": item.template_sha256,
                }
                for item in self.list()
            ],
        }
