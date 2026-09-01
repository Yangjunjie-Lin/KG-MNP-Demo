from __future__ import annotations

import copy
from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.input_attestation import attest_compiler_input

ROOT = Path(__file__).resolve().parents[2]


def test_current_confirmed_package_attestation_is_valid_and_deterministic(prompt05_case: dict) -> None:
    compiler = prompt05_case["compiler"]
    package_id = prompt05_case["prompt04"]["package"]["package_id"]
    first = compiler.attest(package_id)
    second = compiler.attest(package_id)
    assert first == second == prompt05_case["attestation"]
    assert first["status"] == "VALID"
    assert first["closure_results"] == {"evidence_basis_points": 10000, "dependency_basis_points": 10000}
    assert first["partition_counts"] == {"TBOX": 2, "MAPPING": 1, "ABOX": 6, "SHACL": 0}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("package_status", "STALE"),
        ("contract_catalog_digest", "0" * 64),
        ("review_semantic_hash", "0" * 64),
    ],
)
def test_attestation_rejects_tampered_or_stale_confirmed_authority(prompt05_case: dict, field: str, value: str) -> None:
    package = copy.deepcopy(prompt05_case["prompt04"]["package"])
    package[field] = value
    with pytest.raises(ValueError):
        attest_compiler_input(
            prompt05_case["workspace"],
            package,
            supported_types=set(prompt05_case["compiler"].policy["supported_candidate_types"]),
            domain_packs_root=ROOT / "domain_packs",
        )


def test_attestation_rejects_candidate_identity_tamper(prompt05_case: dict) -> None:
    package = copy.deepcopy(prompt05_case["prompt04"]["package"])
    package["confirmed_tbox"][0]["body"]["label"] = "tampered"
    with pytest.raises(ValueError):
        attest_compiler_input(
            prompt05_case["workspace"],
            package,
            supported_types=set(prompt05_case["compiler"].policy["supported_candidate_types"]),
            domain_packs_root=ROOT / "domain_packs",
        )
