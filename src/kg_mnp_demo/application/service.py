"""Deterministic read-only query orchestration bound to a verified publication."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from rdflib import URIRef

from ..graphdb.rdf_semantics import graphdb_semantic_hash_nquads
from ..modeling.canonical_json import semantic_hash
from .errors import ApplicationError, ErrorCode
from .contracts import validate_application_contract
from .identifiers import (
    RDFTermInput,
    parse_rdf_term,
    serialize_rdf_term,
    validate_bounded_string,
    validate_enum,
    validate_iri,
    validate_stable_identifier,
)
from .policy import DEFAULT_RESULT_LIMIT
from .publication_binding import PUBLICATION_SCENARIOS, PublicationBinding
from .query_registry import ParameterSpec, QueryDefinition, QueryRegistry
from .query_validator import validate_bound_graph_values, validate_query_text
from .readonly_client import ReadOnlyGraphDBClient
from .result_normalizer import normalize_select
from .traceability import build_traceability


def _canonical_parameter(value: Any) -> Any:
    if isinstance(value, RDFTermInput):
        if value.term_type == "IRI":
            return {"term_type": "IRI", "value": value.value}
        return {"term_type": "LITERAL", "value": value.value, "datatype_iri": value.datatype_iri, "language": value.language}
    return value


class ApplicationService:
    def __init__(
        self,
        *,
        binding: PublicationBinding,
        registry: QueryRegistry,
        client: ReadOnlyGraphDBClient,
    ) -> None:
        self.binding = binding
        self.registry = registry
        self.client = client

    def runtime_check(self) -> dict[str, Any]:
        try:
            health = self.client.health()
            if not isinstance(health, dict) or health.get("healthy") is not True:
                raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
            info = self.client.repository_info(self.binding.repository_id)
            reported_id = info.get("id") or info.get("repositoryID")
            if reported_id != self.binding.repository_id:
                raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
            if self.binding.attestation.get("status") != "PUBLICATION_VERIFIED":
                raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
            reconstruction = self.binding.publication_authority_reconstruction
            if (
                reconstruction.get("status") != "PASS"
                or reconstruction.get("scenario") not in PUBLICATION_SCENARIOS
                or reconstruction.get("scenario")
                != self.binding.publication_scenario
                or reconstruction.get("publication_id") != self.binding.publication_id
                or reconstruction.get("deterministic_reconstruction_match") is not True
            ):
                raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
            explicit_nquads = self.client.export_explicit_nquads(
                self.binding.repository_id
            )
            live_semantic_hash = graphdb_semantic_hash_nquads(explicit_nquads)
            if live_semantic_hash != self.binding.graphdb_semantic_hash:
                raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
        except ApplicationError as exc:
            if exc.code == ErrorCode.APPLICATION_NOT_READY:
                raise
            raise ApplicationError(ErrorCode.APPLICATION_NOT_READY) from exc
        except Exception as exc:
            raise ApplicationError(ErrorCode.APPLICATION_NOT_READY) from exc
        return {
            "status": "APPLICATION_READY",
            "read_only": True,
            "publication_id": self.binding.publication_id,
            "publication_semantic_hash": self.binding.publication_semantic_hash,
            "repository_id": self.binding.repository_id,
            "expected_graphdb_semantic_hash": self.binding.graphdb_semantic_hash,
            "live_graphdb_semantic_hash": live_semantic_hash,
            "repository_semantic_identity_verified": True,
            "publication_authority_reconstruction": reconstruction,
            "health": health,
        }

    def _parameter_value(self, spec: ParameterSpec, raw: Any) -> Any:
        if spec.type == "iri":
            return validate_iri(raw)
        if spec.type == "rdf_term":
            return parse_rdf_term(raw)
        if spec.type == "stable_identifier":
            return validate_stable_identifier(raw)
        if spec.type == "string":
            return validate_bounded_string(raw)
        if spec.type == "enum":
            return validate_enum(raw, spec.allowed)
        if spec.type in {"limit", "offset"}:
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                raise ApplicationError(ErrorCode.INVALID_PARAMETER)
            return raw
        raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)

    def _validate_parameters(
        self, definition: QueryDefinition, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        specs = {spec.name: spec for spec in definition.parameters}
        if set(parameters) - set(specs):
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        result: dict[str, Any] = {}
        for spec in definition.parameters:
            if spec.name not in parameters:
                if spec.required:
                    raise ApplicationError(ErrorCode.INVALID_PARAMETER)
                continue
            result[spec.name] = self._parameter_value(spec, parameters[spec.name])
        limit = result.get("limit", min(DEFAULT_RESULT_LIMIT, definition.maximum_result_count))
        if limit < 1 or limit > definition.maximum_result_count:
            raise ApplicationError(ErrorCode.RESULT_LIMIT_EXCEEDED)
        offset = result.get("offset", 0)
        if offset > 1_000_000:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        if any(spec.type == "limit" for spec in definition.parameters):
            result["limit"] = limit
        if any(spec.type == "offset" for spec in definition.parameters):
            result["offset"] = offset
        return result

    def _render(
        self, definition: QueryDefinition, parameters: dict[str, Any]
    ) -> tuple[str, int]:
        query = definition.load_template()
        rendered_graphs: dict[str, tuple[str, ...]] = {}
        for variable, role in definition.graph_bindings.items():
            iris = self.binding.graph_iris(role)
            rendered_graphs[variable] = iris
            serialized = " ".join(serialize_rdf_term(URIRef(iri)) for iri in iris)
            query = query.replace(f"@@GRAPH_{variable}@@", serialized)
        for name, value in parameters.items():
            marker = f"@@PARAM_{name}@@"
            if marker not in query:
                continue
            if isinstance(value, RDFTermInput):
                serialized = serialize_rdf_term(value.as_rdflib())
            else:
                serialized = serialize_rdf_term(URIRef(value))
            query = query.replace(marker, serialized)
        limit = int(parameters.get("limit", definition.maximum_result_count))
        fetch_limit = min(limit + 1, 1000)
        query = query.replace("@@LIMIT@@", str(fetch_limit))
        query = query.replace("@@OFFSET@@", str(int(parameters.get("offset", 0))))
        if "@@" in query:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        validate_bound_graph_values(query, rendered_graphs)
        validate_query_text(
            query,
            allowed_types=(definition.query_type,),
            graph_variables=definition.graph_bindings,
        )
        return query, limit

    def run(self, query_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        definition = self.registry.get(query_id)
        validated = self._validate_parameters(definition, parameters)
        query, requested_limit = self._render(definition, validated)
        if definition.query_type != "SELECT":
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        raw = self.client.select(
            self.binding.repository_id,
            query,
            timeout=definition.timeout_seconds,
        )
        variables, normalized = normalize_select(raw)
        truncated = len(normalized) > requested_limit
        rows = normalized[:requested_limit]
        canonical_parameters = {
            key: _canonical_parameter(validated[key]) for key in sorted(validated)
        }
        traceability = build_traceability(
            binding=self.binding,
            category=definition.category,
            parameters=canonical_parameters,
            rows=rows,
        )
        semantic = {
            "contract_version": "1.0",
            "query_id": definition.query_id,
            "query_version": definition.version,
            "publication_id": self.binding.publication_id,
            "publication_semantic_hash": self.binding.publication_semantic_hash,
            "repository_id": self.binding.repository_id,
            "parameters": canonical_parameters,
            "variables": variables,
            "results": rows,
            "traceability": traceability,
            "result_count": len(rows),
            "truncated": truncated,
        }
        result_hash = semantic_hash(semantic)
        result = {
            **semantic,
            "result_semantic_hash": result_hash,
            "runtime_metadata": {
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
                "served_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        }
        validate_application_contract("traceability-result", traceability)
        validate_application_contract("query-result", result)
        return result
