from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.policy import GraphRole
from kg_mnp_demo.application.publication_binding import (
    PUBLICATION_SCENARIOS,
    PublicationBinding,
)

from ._phase01_helpers import ROOT, publication_attestation_report


def test_binding_cannot_be_constructed_without_official_verification() -> None:
    with pytest.raises(TypeError, match=r"must be created by verify\(\)"):
        PublicationBinding(publication_scenario="full-confirmation")


@pytest.mark.parametrize("scenario", sorted(PUBLICATION_SCENARIOS))
def test_binding_reconstructs_each_controlled_stage08_scenario(
    tmp_path: Path, scenario: str
):
    package = ROOT / f"examples/publication/expected/{scenario}"
    attestation = publication_attestation_report(tmp_path / "report", scenario)

    binding = PublicationBinding.verify(
        package,
        attestation,
        publication_scenario=scenario,
    )

    assert binding.publication_scenario == scenario
    assert binding.publication_authority_reconstruction == {
        "status": "PASS",
        "scenario": scenario,
        "publication_id": binding.publication_id,
        "deterministic_reconstruction_match": True,
    }
    with pytest.raises(TypeError):
        binding.graphs[GraphRole.BUSINESS_ABOX] = binding.graphs[
            GraphRole.REVIEW_AUDIT
        ]


def test_binding_rejects_a_wrong_controlled_scenario(tmp_path: Path):
    scenario = "full-confirmation"
    package = ROOT / f"examples/publication/expected/{scenario}"
    attestation = publication_attestation_report(tmp_path / "report", scenario)

    with pytest.raises(ApplicationError) as caught:
        PublicationBinding.verify(
            package,
            attestation,
            publication_scenario="modified-confirmation",
        )

    assert caught.value.code == ErrorCode.FOUNDATION_NOT_VERIFIED


def test_binding_requires_an_explicit_controlled_scenario(tmp_path: Path):
    scenario = "full-confirmation"
    package = ROOT / f"examples/publication/expected/{scenario}"
    attestation = publication_attestation_report(tmp_path / "report", scenario)

    with pytest.raises(ApplicationError) as caught:
        PublicationBinding.verify(package, attestation)

    assert caught.value.code == ErrorCode.FOUNDATION_NOT_VERIFIED
