"""Strictly offline JSON Schema registry for Stage 04 contracts."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
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

from kg_mnp_demo.loader import project_root

from .contracts import (
    CONTRACT_BY_FILENAME,
    CONTRACT_SPECS,
    DRAFT_2020_12,
    ContractRegistryError,
    normalize_contract_name,
)


DEFAULT_SCHEMA_DIRECTORY = project_root() / "schemas" / "modeling"


@dataclass(frozen=True)
class _ContractBundle:
    registry: Registry
    schemas_by_name: Mapping[str, dict[str, Any]]


def _iter_references(value: Any, base_uri: str) -> Iterator[tuple[str, str]]:
    """Yield ``(effective_base, ref)`` while respecting nested ``$id`` values."""

    if isinstance(value, dict):
        nested_base = base_uri
        identifier = value.get("$id")
        if isinstance(identifier, str):
            nested_base = urljoin(base_uri, identifier)
        reference = value.get("$ref")
        if isinstance(reference, str):
            yield nested_base, reference
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


def _load_bundle(schema_directory: Path) -> _ContractBundle:
    directory = schema_directory.resolve()
    if not directory.is_dir():
        raise ContractRegistryError(f"modeling schema directory is missing: {directory}")

    paths = sorted(directory.glob("*.schema.json"), key=lambda item: item.name)
    found_filenames = {path.name for path in paths}
    missing = sorted(set(CONTRACT_BY_FILENAME) - found_filenames)
    if missing:
        raise ContractRegistryError(
            "required modeling schema file(s) missing: " + ", ".join(missing)
        )

    schemas_by_id: dict[str, dict[str, Any]] = {}
    schema_paths_by_id: dict[str, Path] = {}
    schemas_by_filename: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractRegistryError(f"cannot load schema {path}: {exc}") from exc
        if not isinstance(schema, dict):
            raise ContractRegistryError(f"schema root must be an object: {path}")
        if schema.get("$schema") != DRAFT_2020_12:
            raise ContractRegistryError(
                f"schema {path.name} must declare Draft 2020-12"
            )
        identifier = schema.get("$id")
        if not isinstance(identifier, str) or not identifier:
            raise ContractRegistryError(f"schema {path.name} has no non-empty $id")
        previous = schema_paths_by_id.get(identifier)
        if previous is not None:
            raise ContractRegistryError(
                f"duplicate schema $id {identifier!r}: {previous.name}, {path.name}"
            )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ContractRegistryError(
                f"invalid Draft 2020-12 schema {path.name}: {exc.message}"
            ) from exc
        schemas_by_id[identifier] = schema
        schema_paths_by_id[identifier] = path
        schemas_by_filename[path.name] = schema

    for spec in CONTRACT_SPECS:
        schema = schemas_by_filename[spec.filename]
        if schema.get("$id") != spec.schema_id:
            raise ContractRegistryError(
                f"{spec.filename} declares {schema.get('$id')!r}; expected {spec.schema_id!r}"
            )

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
                path = schema_paths_by_id[identifier]
                raise ContractRegistryError(
                    f"unresolvable local $ref {reference!r} in {path.name}: {exc}"
                ) from exc
            target, _fragment = urldefrag(urljoin(base_uri, reference))
            source, _source_fragment = urldefrag(base_uri)
            if target != source:
                graph.setdefault(source, set()).add(target)
                graph.setdefault(target, set())
    _assert_acyclic(graph)

    schemas_by_name = {
        spec.name: schemas_by_filename[spec.filename] for spec in CONTRACT_SPECS
    }
    return _ContractBundle(registry=registry, schemas_by_name=schemas_by_name)


@lru_cache(maxsize=1)
def _default_bundle() -> _ContractBundle:
    return _load_bundle(DEFAULT_SCHEMA_DIRECTORY)


def _bundle(schema_directory: Path | str | None) -> _ContractBundle:
    if schema_directory is None:
        return _default_bundle()
    return _load_bundle(Path(schema_directory))


def load_contract_registry(schema_directory: Path | str | None = None) -> Registry:
    """Load the complete local registry without configuring remote retrieval."""

    return _bundle(schema_directory).registry


def get_contract_schema(
    contract_name: str,
    *,
    schema_directory: Path | str | None = None,
) -> dict[str, Any]:
    """Return an isolated copy of one schema from the closed catalog."""

    canonical_name = normalize_contract_name(contract_name)
    schema = _bundle(schema_directory).schemas_by_name[canonical_name]
    return copy.deepcopy(schema)


def validate_contract(
    contract_name: str,
    payload: Mapping[str, Any] | list[Any],
    *,
    schema_directory: Path | str | None = None,
) -> None:
    """Validate a payload with Draft 2020-12 and the offline local registry.

    ``jsonschema.ValidationError`` is intentionally allowed to propagate so
    callers retain its precise instance path, schema path, and validator.
    """

    canonical_name = normalize_contract_name(contract_name)
    bundle = _bundle(schema_directory)
    schema = bundle.schemas_by_name[canonical_name]
    validator = Draft202012Validator(
        schema,
        registry=bundle.registry,
        format_checker=FormatChecker(),
    )
    validator.validate(payload)


def contract_names() -> tuple[str, ...]:
    """Return canonical contract names in deterministic catalog order."""

    return tuple(spec.name for spec in CONTRACT_SPECS)
