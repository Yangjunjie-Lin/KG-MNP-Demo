"""Stage 06 contract identifiers, deliberately separate from Stage 04/05."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ..modeling.dependencies import ROOT

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
COMPILATION_SCHEMA_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/compilation/"


@dataclass(frozen=True)
class CompilationContractSpec:
    name: str
    filename: str
    schema_id: str


COMPILATION_CONTRACT_SPECS = (
    CompilationContractSpec("common", "compilation_common.schema.json", f"{COMPILATION_SCHEMA_BASE}common/1.0"),
    CompilationContractSpec("compiler-policy", "compiler_policy.schema.json", f"{COMPILATION_SCHEMA_BASE}compiler-policy/1.0"),
    CompilationContractSpec("compilation-manifest", "compilation_manifest.schema.json", f"{COMPILATION_SCHEMA_BASE}compilation-manifest/1.0"),
    CompilationContractSpec("shacl-validation-report", "shacl_validation_report.schema.json", f"{COMPILATION_SCHEMA_BASE}shacl-validation-report/1.0"),
    CompilationContractSpec("owl-consistency-report", "owl_consistency_report.schema.json", f"{COMPILATION_SCHEMA_BASE}owl-consistency-report/1.0"),
)
CONTRACT_BY_NAME = {spec.name: spec for spec in COMPILATION_CONTRACT_SPECS}


class CompilationContractError(ValueError):
    pass


def compilation_schema_path(name: str, *, root: Path = ROOT) -> Path:
    try:
        spec = CONTRACT_BY_NAME[name]
    except KeyError as exc:
        raise CompilationContractError(f"unknown compilation contract: {name}") from exc
    return root / "schemas" / "compilation" / spec.filename


def load_compilation_schema(name: str, *, root: Path = ROOT) -> dict[str, Any]:
    import json
    path = compilation_schema_path(name, root=root)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("$schema") != DRAFT_2020_12:
        raise CompilationContractError(f"invalid schema draft: {path}")
    return value


def validate_compilation_contract(name: str, payload: Mapping[str, Any]) -> None:
    schema = load_compilation_schema(name)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        raise CompilationContractError(f"{name}: {errors[0].message}")


def compilation_contract_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in COMPILATION_CONTRACT_SPECS)


def load_compilation_contract_registry(*, root: Path = ROOT) -> dict[str, dict[str, Any]]:
    return {name: load_compilation_schema(name, root=root) for name in compilation_contract_names()}


def get_compilation_contract_schema(name: str) -> dict[str, Any]:
    return load_compilation_schema(name)


# Familiar aliases for callers already using the Stage 04 local-registry API.
contract_names = compilation_contract_names
load_contract_registry = load_compilation_contract_registry
get_contract_schema = get_compilation_contract_schema
validate_contract = validate_compilation_contract
