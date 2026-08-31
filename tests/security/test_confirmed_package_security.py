from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from kg_mnp.modeling.control_plane.confirmation import verify_confirmed_package
from kg_mnp.modeling.control_plane.errors import (
    ConfirmedPackageError,
    ModelingControlError,
)


@pytest.mark.parametrize(
    "text",
    [
        "C:\\Users\\someone\\secret.json",
        "/etc/passwd",
        "sk-abcdefghijklmnop",
        "SPARQL UPDATE INSERT DATA",
        "```shell\nrm something",
        "graphdb://server/repository",
    ],
)
def test_package_rejects_path_secret_rdf_execution_and_graphdb_payloads(
    prompt04_case: dict, text: str
) -> None:
    package = copy.deepcopy(prompt04_case["package"])
    package["confirmed_tbox"][0]["rationale"] = text
    with pytest.raises((ModelingControlError, ValueError)):
        verify_confirmed_package(package)


def test_package_manifest_rehash_is_detected(prompt04_case: dict) -> None:
    package = copy.deepcopy(prompt04_case["package"])
    package["artifact_manifest"]["artifact_sha256"] = "f" * 64
    with pytest.raises((ConfirmedPackageError, ModelingControlError, ValidationError)):
        verify_confirmed_package(package)
