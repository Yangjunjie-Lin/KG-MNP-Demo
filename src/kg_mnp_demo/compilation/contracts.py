"""Stage 06 contract identifiers, deliberately separate from Stage 04/05."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

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
    registry = Registry().with_resources(
        (
            registered["$id"],
            Resource.from_contents(registered),
        )
        for registered in load_compilation_contract_registry().values()
    )
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise CompilationContractError(f"{name}: {errors[0].message}")
    if name == "compilation-manifest":
        _validate_manifest_semantics(payload)
    elif name == "shacl-validation-report":
        _validate_shacl_report_semantics(payload)


def _validate_manifest_semantics(manifest: Mapping[str, Any]) -> None:
    paths: set[str] = set()
    artifact_ids: set[str] = set()
    for record in manifest.get("artifact_manifest", []):
        relative_path = str(record["relative_path"])
        posix = PurePosixPath(relative_path)
        windows = PureWindowsPath(relative_path)
        if (
            "\\" in relative_path
            or posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or relative_path != posix.as_posix()
        ):
            raise CompilationContractError(
                f"compilation-manifest: artifact relative_path is unsafe: {relative_path}"
            )
        if relative_path in paths:
            raise CompilationContractError(
                f"compilation-manifest: duplicate artifact relative_path: {relative_path}"
            )
        paths.add(relative_path)
        artifact = str(record["artifact_id"])
        if artifact in artifact_ids:
            raise CompilationContractError(
                f"compilation-manifest: duplicate artifact_id: {artifact}"
            )
        artifact_ids.add(artifact)
        if "triple_count" in record and "quad_count" in record:
            raise CompilationContractError(
                f"compilation-manifest: triple_count and quad_count conflict: {relative_path}"
            )
    graph_iris = list(manifest.get("graph_iris", {}).values())
    if len(graph_iris) != len(set(graph_iris)):
        raise CompilationContractError("compilation-manifest: graph IRIs must be unique")


def _validate_shacl_report_semantics(report: Mapping[str, Any]) -> None:
    severity_counts = {
        "http://www.w3.org/ns/shacl#Violation": 0,
        "http://www.w3.org/ns/shacl#Warning": 0,
        "http://www.w3.org/ns/shacl#Info": 0,
    }
    result_ids: set[str] = set()
    for result in report.get("results", []):
        result_id = str(result["result_id"])
        if result_id in result_ids:
            raise CompilationContractError(
                f"shacl-validation-report: duplicate result_id: {result_id}"
            )
        result_ids.add(result_id)
        severity = result.get("severity")
        if isinstance(severity, Mapping) and severity.get("term_type") == "IRI":
            value = severity.get("value")
            if value in severity_counts:
                severity_counts[str(value)] += 1
    expected = {
        "violation_count": severity_counts["http://www.w3.org/ns/shacl#Violation"],
        "warning_count": severity_counts["http://www.w3.org/ns/shacl#Warning"],
        "info_count": severity_counts["http://www.w3.org/ns/shacl#Info"],
    }
    for field, count in expected.items():
        if report.get(field) != count:
            raise CompilationContractError(
                f"shacl-validation-report: {field} does not match results"
            )
    if expected["violation_count"] and report.get("status") != "VIOLATION":
        raise CompilationContractError(
            "shacl-validation-report: violations require VIOLATION status"
        )
    if not expected["violation_count"] and report.get("status") == "VIOLATION":
        raise CompilationContractError(
            "shacl-validation-report: VIOLATION status requires a violation result"
        )


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
