import copy

import pytest

from kg_mnp_demo.compilation.contracts import CompilationContractError, validate_compilation_contract
from kg_mnp_demo.compilation.policy import (
    CompilerPolicyError,
    compiler_policy_hash,
    load_compiler_policy,
    profile_files,
    validate_compiler_policy,
)


def test_frozen_policy_is_closed_and_hashed():
    policy = load_compiler_policy()
    validate_compiler_policy(policy)
    assert policy["compiler_policy_id"] == "kg-mnp-stage06-formal-compiler"
    assert policy["candidate_compilation"]["MAPPING_ASSERTION"].startswith("FORBIDDEN")
    assert len(compiler_policy_hash(policy)) == 64


def test_policy_unknown_field_rejected():
    policy = load_compiler_policy()
    validate_compilation_contract("compiler-policy", policy)
    forged = copy.deepcopy(policy)
    forged["unknown_policy_entry"] = "must fail"
    with pytest.raises(CompilationContractError):
        validate_compilation_contract("compiler-policy", forged)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("serialization", "authoritative_abox"), "TURTLE"),
        (("serialization", "line_endings"), "CRLF"),
        (("serialization", "encoding"), "ASCII"),
        (("shacl", "warning_policy"), "IGNORE"),
        (("shacl", "info_policy"), "IGNORE"),
        (("shacl", "inference"), "NONE"),
        (("shacl", "automatic_repair"), "ALLOW"),
        (("owl_consistency", "not_run_policy"), "RECORD"),
        (("graph_separation", "review_audit"), False),
    ],
)
def test_policy_declared_behavior_must_match(path, value):
    policy = copy.deepcopy(load_compiler_policy())
    policy[path[0]][path[1]] = value
    with pytest.raises((CompilerPolicyError, CompilationContractError)):
        validate_compiler_policy(policy)


def test_policy_requires_warning_and_info_recording():
    for field in ("warning_policy", "info_policy"):
        policy = copy.deepcopy(load_compiler_policy())
        policy["shacl"].pop(field)
        with pytest.raises((CompilerPolicyError, CompilationContractError)):
            validate_compiler_policy(policy)


def test_profile_path_escape_rejected(tmp_path):
    profile = {"profiles": {"test": {"files": ["../outside.ttl"]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=profile)
    profile = {"profiles": {"test": {"files": [str(tmp_path / "outside.ttl")]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=profile)


def test_profile_missing_duplicate_and_symlink_escape_are_rejected(tmp_path, monkeypatch):
    (tmp_path / "shapes").mkdir()
    target = tmp_path / "shapes" / "shape.ttl"
    target.write_text("@prefix sh: <http://www.w3.org/ns/shacl#> .\n", encoding="utf-8")
    duplicate = {"profiles": {"test": {"files": ["shapes/shape.ttl", "shapes/shape.ttl"]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=duplicate)

    missing = {"profiles": {"test": {"files": ["shapes/missing.ttl"]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=missing)
    directory = {"profiles": {"test": {"files": ["shapes"]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=directory)

    outside = tmp_path.parent / "outside-shacl.ttl"
    outside.write_text("outside\n", encoding="utf-8")
    original_resolve = type(tmp_path).resolve

    def resolve_with_escape(path, *args, **kwargs):
        if path.name == "escape.ttl":
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "resolve", resolve_with_escape)
    escaped = {"profiles": {"test": {"files": ["shapes/escape.ttl"]}}}
    with pytest.raises(CompilerPolicyError):
        profile_files("test", root=tmp_path, profiles=escaped)
