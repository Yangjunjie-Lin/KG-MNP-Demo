from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.publication_binding import PublicationBinding

from ._phase01_helpers import ROOT


def test_missing_or_non_verified_attestation_fails_closed(tmp_path: Path):
    package = ROOT / "examples/publication/expected/full-confirmation"
    with pytest.raises(ApplicationError) as missing:
        PublicationBinding.verify(package, tmp_path / "publication-attestation.json")
    assert missing.value.code == ErrorCode.PUBLICATION_MISMATCH
    attestation = tmp_path / "publication-attestation.json"
    attestation.write_text(json.dumps({"status": "FAILED"}), encoding="utf-8")
    with pytest.raises(ApplicationError):
        PublicationBinding.verify(package, attestation)


def test_repository_mismatch_fails_before_runtime_queries(tmp_path: Path):
    package = ROOT / "examples/publication/expected/full-confirmation"
    attestation = tmp_path / "publication-attestation.json"
    attestation.write_text("{}", encoding="utf-8")
    with pytest.raises(ApplicationError):
        PublicationBinding.verify(package, attestation, expected_repository_id="kg-mnp-" + "0" * 20)
