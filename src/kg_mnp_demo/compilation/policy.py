"""Frozen Stage 06 compiler policy and offline profile loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
from typing import Any, Mapping

import yaml

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT
from .contracts import CompilationContractError, validate_compilation_contract

POLICY_PATH = ROOT / "config" / "compilation" / "compiler-policy-1.0.0.yaml"
SHACL_PROFILE_PATH = ROOT / "config" / "compilation" / "shacl-profiles.yaml"


class CompilerPolicyError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CompilerPolicyError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompilerPolicyError(f"policy root must be an object: {path}")
    return value


def validate_compiler_policy(policy: Mapping[str, Any]) -> None:
    try:
        validate_compilation_contract("compiler-policy", policy)
    except CompilationContractError as exc:
        raise CompilerPolicyError(str(exc)) from exc

    expected_scalars = {
        "contract_version": "1.0",
        "compiler_policy_id": "kg-mnp-stage06-formal-compiler",
        "input_package_status": "READY_FOR_COMPILATION",
        "blocked_package_policy": "REJECT",
        "schema_delta_policy": "FORBIDDEN",
    }
    expected_sections = {
        "literal_validation": {
            "xsd_date_lexical": "YYYY-MM-DD",
            "xsd_datetime_lexical": "YYYY-MM-DDTHH:MM:SS[.fraction]Z",
            "xsd_datetime_timezone": "UTC_Z_ONLY",
            "calendar_validation": "STRICT",
            "cross_datatype_coercion": "FORBIDDEN",
        },
        "candidate_compilation": {
            "ENTITY": "RDF_TYPE_ASSERTION",
            "CLASS_ASSERTION": "RDF_TYPE_ASSERTION",
            "OBJECT_PROPERTY_ASSERTION": "OBJECT_PROPERTY_TRIPLE",
            "DATA_PROPERTY_ASSERTION": "TYPED_LITERAL_TRIPLE",
            "MAPPING_ASSERTION": "FORBIDDEN_UNTIL_TYPED_OBJECT_CONTRACT",
        },
        "asserted_graph_policy": {
            "inference_materialization": "FORBIDDEN",
            "blank_nodes": "FORBIDDEN",
            "unreviewed_assertions": "FORBIDDEN",
            "rejected_items": "AUDIT_ONLY",
            "deferred_items": "AUDIT_ONLY",
        },
        "serialization": {
            "authoritative_abox": "CANONICAL_NTRIPLES",
            "authoritative_dataset": "CANONICAL_NQUADS",
            "human_readable_abox": "DETERMINISTIC_TURTLE",
            "human_readable_dataset": "DETERMINISTIC_TRIG",
            "line_endings": "LF",
            "encoding": "UTF-8",
        },
        "shacl": {
            "default_profiles": ["foundation-instance"],
            "violation_policy": "BLOCK_COMPILATION",
            "warning_policy": "RECORD",
            "info_policy": "RECORD",
            "inference": "RDFS",
            "automatic_repair": "FORBIDDEN",
        },
        "owl_consistency": {
            "required": True,
            "unknown_policy": "FAIL",
            "not_run_policy": "FAIL",
        },
        "graph_separation": {
            "business_abox": True,
            "modeling_provenance": True,
            "review_audit": True,
        },
    }
    for field, expected in expected_scalars.items():
        if policy.get(field) != expected:
            raise CompilerPolicyError(f"{field} policy mismatch")
    for section, expected in expected_sections.items():
        actual = policy.get(section)
        if actual != expected:
            raise CompilerPolicyError(f"{section} policy mismatch")


@lru_cache(maxsize=1)
def load_compiler_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = _read(path)
    validate_compiler_policy(value)
    return value


def compiler_policy_hash(policy: Mapping[str, Any] | None = None) -> str:
    return semantic_hash(policy if policy is not None else load_compiler_policy())


def load_shacl_profiles(path: Path = SHACL_PROFILE_PATH) -> dict[str, Any]:
    value = _read(path)
    profiles = value.get("profiles")
    if not isinstance(profiles, dict) or "foundation-instance" not in profiles:
        raise CompilerPolicyError("foundation-instance SHACL profile is missing")
    return value


def profile_files(
    profile_id: str = "foundation-instance",
    *,
    root: Path = ROOT,
    profiles: Mapping[str, Any] | None = None,
) -> list[Path]:
    repository_root = root.resolve()
    configuration = (
        dict(profiles)
        if profiles is not None
        else load_shacl_profiles(
            repository_root / "config" / "compilation" / SHACL_PROFILE_PATH.name
        )
    )
    profile = configuration.get("profiles", {}).get(profile_id)
    if not isinstance(profile, Mapping):
        raise CompilerPolicyError(f"unknown SHACL profile: {profile_id}")
    files = profile.get("files")
    if not isinstance(files, list) or not files:
        raise CompilerPolicyError(f"SHACL profile has no files: {profile_id}")
    result: list[Path] = []
    seen: set[Path] = set()
    for item in files:
        if not isinstance(item, str) or not item:
            raise CompilerPolicyError(f"SHACL profile file must be a relative path: {item!r}")
        relative = PurePosixPath(item)
        windows = PureWindowsPath(item)
        if (
            "\\" in item
            or relative.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in relative.parts
            or item != relative.as_posix()
        ):
            raise CompilerPolicyError(f"unsafe SHACL profile path: {item}")
        path = repository_root.joinpath(*relative.parts)
        resolved = path.resolve()
        if resolved != repository_root and repository_root not in resolved.parents:
            raise CompilerPolicyError(f"SHACL profile path escapes repository root: {item}")
        if resolved in seen:
            raise CompilerPolicyError(f"duplicate SHACL profile file: {item}")
        seen.add(resolved)
        try:
            is_regular = resolved.is_file() and stat.S_ISREG(resolved.stat().st_mode)
        except OSError:
            is_regular = False
        if not is_regular:
            raise CompilerPolicyError(f"SHACL profile file missing or not regular: {item}")
        result.append(resolved)
    return result
