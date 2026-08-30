"""Authoritative public Contract Catalog and deterministic catalog lock."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

from .canonical import (
    CANONICAL_JSON_PROFILE,
    bytes_sha256,
    semantic_hash,
    stable_urn,
)
from .document_io import atomic_write_json, deterministic_json_bytes
from .errors import ContractCatalogError, UnknownContractError
from .identifiers import validate_safe_relative_path, validate_semver

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_ENTRY_KEYS = {
    "name", "version", "schema_id", "resource_path", "scope", "stability",
    "authority_level", "sha256",
}


@dataclass(frozen=True)
class ContractSpec:
    name: str
    version: str
    schema_id: str
    resource_path: str
    scope: str
    stability: str
    authority_level: str
    sha256: str

    @property
    def filename(self) -> str:
        """Backward-compatible schema filename."""

        return Path(self.resource_path).name

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContractSpec:
        if set(value) != _ENTRY_KEYS:
            raise ContractCatalogError(
                f"catalog entry keys differ: {sorted(set(value) ^ _ENTRY_KEYS)}"
            )
        try:
            return cls(**value)
        except TypeError as exc:
            raise ContractCatalogError(f"invalid catalog entry: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "schema_id": self.schema_id,
            "resource_path": self.resource_path,
            "scope": self.scope,
            "stability": self.stability,
            "authority_level": self.authority_level,
            "sha256": self.sha256,
        }


def _package_root():
    return resources.files("kg_mnp.contracts")


def package_resource_bytes(relative: str) -> bytes:
    validate_safe_relative_path(relative)
    try:
        return _package_root().joinpath(relative).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise ContractCatalogError(f"missing packaged contract resource: {relative}") from exc


@dataclass(frozen=True)
class ContractCatalog:
    document: dict[str, Any]
    specs: tuple[ContractSpec, ...]

    @classmethod
    def load(cls, path: Path | str | None = None) -> ContractCatalog:
        try:
            raw = Path(path).read_bytes() if path is not None else package_resource_bytes("catalog.json")
            value = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractCatalogError(f"cannot load Contract Catalog: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractCatalogError("Contract Catalog root must be an object")
        if value.get("manifest_kind") != "KG_MNP_CONTRACT_CATALOG":
            raise ContractCatalogError("invalid Contract Catalog manifest_kind")
        if value.get("schema_version") != "1.0.0":
            raise ContractCatalogError("unsupported Contract Catalog schema_version")
        if value.get("canonicalization_profile") != CANONICAL_JSON_PROFILE:
            raise ContractCatalogError("unsupported Contract Catalog canonicalization profile")
        entries = value.get("contracts")
        if not isinstance(entries, list) or not entries:
            raise ContractCatalogError("Contract Catalog contracts must be non-empty")
        specs = tuple(ContractSpec.from_dict(entry) for entry in entries)
        _validate_specs(specs)
        return cls(document=value, specs=specs)

    @property
    def digest(self) -> str:
        return semantic_hash(self.document)

    def by_name(self, name: str) -> ContractSpec:
        normalized = normalize_contract_name(name, self.specs)
        return next(spec for spec in self.specs if spec.name == normalized)

    def filtered(self, *, scope: str) -> tuple[ContractSpec, ...]:
        return tuple(spec for spec in self.specs if spec.scope == scope)


def _validate_specs(specs: Iterable[ContractSpec], *, verify_hashes: bool = False) -> None:
    values = tuple(specs)
    dimensions = {
        "name": [spec.name for spec in values],
        "schema_id": [spec.schema_id for spec in values],
        "resource_path": [spec.resource_path for spec in values],
        "name/version": [(spec.name, spec.version) for spec in values],
    }
    for label, items in dimensions.items():
        if len(items) != len(set(items)):
            raise ContractCatalogError(f"duplicate Contract Catalog {label}")
    for spec in values:
        validate_semver(spec.version)
        validate_safe_relative_path(spec.resource_path)
        if spec.scope not in {"toolchain", "modeling"}:
            raise ContractCatalogError(f"invalid contract scope: {spec.scope}")
        if spec.stability not in {"stable", "retained", "experimental"}:
            raise ContractCatalogError(f"invalid contract stability: {spec.stability}")
        if spec.authority_level not in {
            "descriptive", "proposal", "confirmed-input", "control", "lock"
        }:
            raise ContractCatalogError(
                f"invalid contract authority level: {spec.authority_level}"
            )
        raw = package_resource_bytes(spec.resource_path)
        try:
            schema = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ContractCatalogError(f"invalid JSON Schema {spec.resource_path}: {exc}") from exc
        if schema.get("$id") != spec.schema_id:
            raise ContractCatalogError(
                f"{spec.resource_path} declares {schema.get('$id')!r}; expected {spec.schema_id!r}"
            )
        if schema.get("$schema") != DRAFT_2020_12:
            raise ContractCatalogError(f"{spec.resource_path} is not Draft 2020-12")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ContractCatalogError(
                f"invalid Draft 2020-12 schema {spec.resource_path}: {exc.message}"
            ) from exc
        if verify_hashes and bytes_sha256(raw) != spec.sha256:
            raise ContractCatalogError(f"schema digest mismatch: {spec.resource_path}")


def normalize_contract_name(
    value: str,
    specs: tuple[ContractSpec, ...] | None = None,
) -> str:
    catalog_specs = specs or ContractCatalog.load().specs
    if not isinstance(value, str) or not value.strip():
        raise UnknownContractError(value)
    candidate = value.strip()
    by_id = {spec.schema_id: spec.name for spec in catalog_specs}
    by_filename = {spec.filename: spec.name for spec in catalog_specs}
    names = {spec.name for spec in catalog_specs}
    if candidate in by_id:
        return by_id[candidate]
    if Path(candidate).name in by_filename:
        return by_filename[Path(candidate).name]
    candidate = candidate.removesuffix(".schema.json").replace("_", "-").lower()
    if candidate not in names:
        raise UnknownContractError(
            f"unknown contract {value!r}; known: {', '.join(sorted(names))}"
        )
    return candidate


def _catalog_with_current_hashes(document: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(document)
    for entry in updated["contracts"]:
        entry["sha256"] = bytes_sha256(package_resource_bytes(entry["resource_path"]))
    updated["contracts"] = sorted(
        updated["contracts"], key=lambda item: (item["scope"], item["name"], item["version"])
    )
    specs = tuple(ContractSpec.from_dict(entry) for entry in updated["contracts"])
    _validate_specs(specs, verify_hashes=True)
    return updated


def _expected_lock(catalog_document: dict[str, Any], catalog_bytes: bytes) -> dict[str, Any]:
    core: dict[str, Any] = {
        "manifest_kind": "KG_MNP_CONTRACT_CATALOG_LOCK",
        "schema_version": "1.0.0",
        "canonicalization_profile": CANONICAL_JSON_PROFILE,
        "catalog_file_sha256": bytes_sha256(catalog_bytes),
        "catalog_semantic_sha256": semantic_hash(catalog_document),
        "contracts": [
            {
                "name": item["name"],
                "version": item["version"],
                "schema_id": item["schema_id"],
                "resource_path": item["resource_path"],
                "sha256": item["sha256"],
            }
            for item in catalog_document["contracts"]
        ],
    }
    content_digest = semantic_hash(core)
    return {
        **core,
        "content_digest": content_digest,
        "lock_id": stable_urn("contract-catalog-lock", {"content_digest": content_digest}),
    }


def regenerate_catalog_files(*, check: bool = False) -> bool:
    """Regenerate catalog hashes and lock; return whether files already matched."""

    root = Path(__file__).resolve().parent
    catalog_path = root / "catalog.json"
    lock_path = root / "catalog.lock.json"
    current = json.loads(catalog_path.read_text(encoding="utf-8"))
    updated = _catalog_with_current_hashes(current)
    catalog_bytes = deterministic_json_bytes(updated)
    lock = _expected_lock(updated, catalog_bytes)
    lock_bytes = deterministic_json_bytes(lock)
    matches = (
        catalog_path.read_bytes() == catalog_bytes
        and lock_path.is_file()
        and lock_path.read_bytes() == lock_bytes
    )
    if check:
        if not matches:
            raise ContractCatalogError("Contract Catalog generated files are stale")
        return True
    if not matches:
        atomic_write_json(catalog_path, updated)
        atomic_write_json(lock_path, lock)
    return matches


def verify_catalog_lock() -> dict[str, Any]:
    catalog = ContractCatalog.load()
    _validate_specs(catalog.specs, verify_hashes=True)
    catalog_bytes = package_resource_bytes("catalog.json")
    expected = _expected_lock(catalog.document, catalog_bytes)
    try:
        actual = json.loads(package_resource_bytes("catalog.lock.json"))
    except json.JSONDecodeError as exc:
        raise ContractCatalogError(f"invalid catalog lock JSON: {exc}") from exc
    if actual != expected:
        raise ContractCatalogError("Contract Catalog lock mismatch")
    return copy.deepcopy(actual)

