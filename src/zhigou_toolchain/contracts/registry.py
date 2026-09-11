"""Strictly offline Draft 2020-12 registry for all public contracts."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

from jsonschema import Draft202012Validator, FormatChecker, SchemaError
from referencing import Registry, Resource
from referencing.exceptions import (
    InvalidAnchor,
    NoSuchAnchor,
    NoSuchResource,
    PointerToNowhere,
    Unresolvable,
    Unretrievable,
)

from .catalog import (
    DRAFT_2020_12,
    ContractCatalog,
    ContractSpec,
    normalize_contract_name,
    package_resource_bytes,
    verify_catalog_lock,
)
from .errors import ContractRegistryError


@dataclass(frozen=True)
class ContractRegistry:
    """Closed schema set with no remote retrieval callback."""

    registry: Registry
    schemas_by_name: Mapping[str, dict[str, Any]]
    specs: tuple[ContractSpec, ...]

    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.specs)

    def get_schema(self, contract_name: str) -> dict[str, Any]:
        canonical = normalize_contract_name(contract_name, self.specs)
        return copy.deepcopy(self.schemas_by_name[canonical])

    def validate(
        self,
        contract_name: str,
        payload: Mapping[str, Any] | list[Any],
    ) -> None:
        canonical = normalize_contract_name(contract_name, self.specs)
        validator = Draft202012Validator(
            self.schemas_by_name[canonical],
            registry=self.registry,
            format_checker=FormatChecker(),
        )
        validator.validate(payload)

    def __len__(self) -> int:
        return len(self.specs)


def _iter_references(value: Any, base_uri: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        nested_base = base_uri
        if isinstance(value.get("$id"), str):
            nested_base = urljoin(base_uri, value["$id"])
        if isinstance(value.get("$ref"), str):
            yield nested_base, value["$ref"]
        for key, item in value.items():
            if key not in {"$id", "$ref"}:
                yield from _iter_references(item, nested_base)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_references(item, base_uri)


def _assert_acyclic(graph: Mapping[str, set[str]]) -> None:
    visited: set[str] = set()
    active: list[str] = []

    def visit(node: str) -> None:
        if node in active:
            start = active.index(node)
            cycle = " -> ".join([*active[start:], node])
            raise ContractRegistryError(f"cyclic cross-contract $ref dependency: {cycle}")
        if node in visited:
            return
        active.append(node)
        for target in sorted(graph.get(node, set())):
            visit(target)
        active.pop()
        visited.add(node)

    for identifier in sorted(graph):
        visit(identifier)


def _schema_bytes(
    spec: ContractSpec,
    schema_directory: Path | None,
) -> tuple[bytes, str]:
    if schema_directory is None:
        return package_resource_bytes(spec.resource_path), spec.resource_path
    path = schema_directory / spec.filename
    try:
        return path.read_bytes(), path.name
    except OSError as exc:
        raise ContractRegistryError(f"required schema file missing: {path.name}") from exc


def build_contract_registry(
    *,
    schema_directory: Path | str | None = None,
    specs: tuple[ContractSpec, ...] | None = None,
    verify_catalog: bool = True,
) -> ContractRegistry:
    """Build a closed local registry from packaged resources or a test directory."""

    catalog = ContractCatalog.load()
    selected = specs or catalog.specs
    directory = Path(schema_directory).resolve() if schema_directory is not None else None
    if directory is not None and not directory.is_dir():
        raise ContractRegistryError(f"schema directory is missing: {directory}")
    if directory is None and verify_catalog:
        verify_catalog_lock()

    schemas_by_id: dict[str, dict[str, Any]] = {}
    schemas_by_name: dict[str, dict[str, Any]] = {}
    labels_by_id: dict[str, str] = {}
    for spec in selected:
        raw, label = _schema_bytes(spec, directory)
        try:
            schema = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ContractRegistryError(f"cannot load schema {label}: {exc}") from exc
        if not isinstance(schema, dict):
            raise ContractRegistryError(f"schema root must be an object: {label}")
        if schema.get("$schema") != DRAFT_2020_12:
            raise ContractRegistryError(f"schema {label} must declare Draft 2020-12")
        identifier = schema.get("$id")
        if identifier != spec.schema_id:
            raise ContractRegistryError(
                f"{label} declares {identifier!r}; expected {spec.schema_id!r}"
            )
        if identifier in schemas_by_id:
            raise ContractRegistryError(
                f"duplicate schema $id {identifier!r}: {labels_by_id[identifier]}, {label}"
            )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ContractRegistryError(
                f"invalid Draft 2020-12 schema {label}: {exc.message}"
            ) from exc
        schemas_by_id[identifier] = schema
        schemas_by_name[spec.name] = schema
        labels_by_id[identifier] = label

    registry: Registry = Registry().with_resources(
        (identifier, Resource.from_contents(schema))
        for identifier, schema in sorted(schemas_by_id.items())
    )
    registry = registry.crawl()
    graph: dict[str, set[str]] = {identifier: set() for identifier in schemas_by_id}
    resolution_errors = (
        InvalidAnchor,
        NoSuchAnchor,
        NoSuchResource,
        PointerToNowhere,
        Unresolvable,
        Unretrievable,
    )
    for identifier, schema in sorted(schemas_by_id.items()):
        for base_uri, reference in _iter_references(schema, identifier):
            try:
                registry.resolver(base_uri=base_uri).lookup(reference)
            except resolution_errors as exc:
                raise ContractRegistryError(
                    f"unresolvable local $ref {reference!r} in {labels_by_id[identifier]}: {exc}"
                ) from exc
            source = urldefrag(base_uri)[0]
            target = urldefrag(urljoin(base_uri, reference))[0]
            if target != source:
                graph.setdefault(source, set()).add(target)
                graph.setdefault(target, set())
    _assert_acyclic(graph)
    return ContractRegistry(
        registry=registry,
        schemas_by_name=schemas_by_name,
        specs=selected,
    )


_DEFAULT_REGISTRY: ContractRegistry | None = None


def load_contract_registry() -> ContractRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = build_contract_registry()
    return _DEFAULT_REGISTRY


def get_contract_schema(contract_name: str) -> dict[str, Any]:
    return load_contract_registry().get_schema(contract_name)


def validate_contract(
    contract_name: str,
    payload: Mapping[str, Any] | list[Any],
) -> None:
    load_contract_registry().validate(contract_name, payload)


def contract_names() -> tuple[str, ...]:
    return load_contract_registry().names()

