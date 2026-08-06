"""Frozen Stage 06 compiler policy and offline profile loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..modeling.canonical_json import semantic_hash
from ..modeling.dependencies import ROOT

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
    required = (
        "contract_version", "compiler_policy_id", "compiler_policy_version",
        "compiler_version", "input_package_status", "blocked_package_policy",
        "schema_delta_policy", "candidate_compilation", "asserted_graph_policy",
        "serialization", "shacl", "owl_consistency", "graph_separation",
    )
    missing = [field for field in required if field not in policy]
    if missing:
        raise CompilerPolicyError("compiler policy missing: " + ", ".join(missing))
    if policy.get("contract_version") != "1.0":
        raise CompilerPolicyError("compiler policy contract_version must be 1.0")
    if policy.get("input_package_status") != "READY_FOR_COMPILATION":
        raise CompilerPolicyError("input_package_status must be READY_FOR_COMPILATION")
    if policy.get("blocked_package_policy") != "REJECT":
        raise CompilerPolicyError("blocked_package_policy must be REJECT")
    if policy.get("schema_delta_policy") != "FORBIDDEN":
        raise CompilerPolicyError("schema_delta_policy must be FORBIDDEN")
    mapping = policy.get("candidate_compilation", {})
    expected = {
        "ENTITY": "RDF_TYPE_ASSERTION",
        "CLASS_ASSERTION": "RDF_TYPE_ASSERTION",
        "OBJECT_PROPERTY_ASSERTION": "OBJECT_PROPERTY_TRIPLE",
        "DATA_PROPERTY_ASSERTION": "TYPED_LITERAL_TRIPLE",
        "MAPPING_ASSERTION": "FORBIDDEN_UNTIL_TYPED_OBJECT_CONTRACT",
    }
    for key, value in expected.items():
        if mapping.get(key) != value:
            raise CompilerPolicyError(f"candidate_compilation.{key} policy mismatch")
    if policy.get("asserted_graph_policy", {}).get("blank_nodes") != "FORBIDDEN":
        raise CompilerPolicyError("blank nodes must be forbidden")
    if policy.get("asserted_graph_policy", {}).get("inference_materialization") != "FORBIDDEN":
        raise CompilerPolicyError("inference materialization must be forbidden")
    shacl = policy.get("shacl", {})
    if shacl.get("violation_policy") != "BLOCK_COMPILATION":
        raise CompilerPolicyError("SHACL violations must block compilation")
    owl = policy.get("owl_consistency", {})
    if owl.get("required") is not True or owl.get("unknown_policy") != "FAIL":
        raise CompilerPolicyError("OWL consistency must be required and fail closed")


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


def profile_files(profile_id: str = "foundation-instance", *, root: Path = ROOT) -> list[Path]:
    profile = load_shacl_profiles().get("profiles", {}).get(profile_id)
    if not isinstance(profile, Mapping):
        raise CompilerPolicyError(f"unknown SHACL profile: {profile_id}")
    files = profile.get("files")
    if not isinstance(files, list) or not files:
        raise CompilerPolicyError(f"SHACL profile has no files: {profile_id}")
    result = [root / str(item) for item in files]
    missing = [path.as_posix() for path in result if not path.is_file()]
    if missing:
        raise CompilerPolicyError("SHACL profile file missing: " + missing[0])
    return result
