"""TEST-ONLY Phase04 diagnostics for governance behavior and security probes.

This module is deliberately an integration fixture below ``scripts/``. A
controlled fixture is not a verified Phase03 artifact and does not carry a
Phase03 attestation. The only conversion to ``GovernanceAuthority`` is the
explicitly named test-harness adapter at the bottom of this file.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.diagnostics.authority_binding import AuthorityBindings
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.diagnostics.issue import diagnostic_semantic_basis
from kg_mnp_demo.diagnostics.policy import diagnostic_policy_hash
from kg_mnp_demo.governance.authority_binding import GovernanceAuthority
from kg_mnp_demo.modeling.canonical_json import semantic_hash

FIXTURE_NAMESPACE = "urn:kg-mnp:test-fixture:phase04:"
FIXTURE_TYPE = "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE"
FIXTURE_STATUS = "CONTROLLED_DIAGNOSTIC_FIXTURE"


def _fixture_hash(label: str) -> str:
    return semantic_hash({"phase": "Application Phase04", "test_fixture": label})


def _fixture_bindings() -> AuthorityBindings:
    publication_hash = _fixture_hash("publication")
    return AuthorityBindings(
        # Phase03's frozen schema requires this structural publication-ID shape
        # during this private reconstruction step. It is never exposed: the
        # fixture projection below rewrites it into the Phase04 test namespace.
        publication_id=f"urn:kg-mnp:test-fixture:{publication_hash}",
        publication_semantic_hash=publication_hash,
        phase01_attestation_hash=_fixture_hash("not-a-phase01-attestation"),
        phase02_attestation_hash=_fixture_hash("not-a-phase02-attestation"),
        query_registry_hash=_fixture_hash("query-registry"),
        repository_semantic_hash=_fixture_hash("repository"),
        diagnostic_policy_hash=diagnostic_policy_hash(),
    )


def _controlled_snapshot(bindings: AuthorityBindings) -> dict[str, Any]:
    """Return synthetic inputs, never an authority snapshot trusted by production."""

    def iri(value: str) -> str:
        return f"{FIXTURE_NAMESPACE}{value}"

    def requirement(name: str, *, maximum: int | None = 1) -> dict[str, Any]:
        focus = iri(f"focus:{name}")
        if name == "missing":
            focus += ":<img src=x onerror=window.__xss=1>"
        constraint = iri(f"constraint:{name}")
        return {
            "focus_node": focus,
            "path": iri("property:controlled"),
            "requirement_type": "CONTROLLED_SHACL_MIN_MAX_COUNT",
            "authority_iri": constraint,
            "shape_iri": iri(f"shape:{name}"),
            "constraint_iri": constraint,
            "module": "phase04-controlled-test-fixture",
            "publication_id": bindings.publication_id,
            "min_count": 1,
            "max_count": maximum,
        }

    conflict_focus = iri("focus:conflict")
    rejected_focus = iri("focus:rejected")
    predicate = iri("property:controlled")
    return {
        "authority_bindings": bindings.to_dict(),
        "requirements": [
            requirement("missing"),
            requirement("rejected"),
            requirement("conflict"),
        ],
        "facts": [
            {
                "subject": conflict_focus,
                "predicate": predicate,
                "object": "confirmed-a",
                "assertion_ref": iri("assertion:confirmed-a"),
            },
            {
                "subject": conflict_focus,
                "predicate": predicate,
                "object": "confirmed-b",
                "assertion_ref": iri("assertion:confirmed-b"),
            },
        ],
        "constraint_results": [],
        "candidates": [
            {
                "focus_node": rejected_focus,
                "path": predicate,
                "value": "rejected-value",
                "outcome": "REJECT",
                "candidate_ref": iri("candidate:rejected"),
                "review_decision_ref": iri("decision:rejected"),
                "evidence_refs": [],
                "source_refs": [],
            }
        ],
        "conflict_rules": [],
    }


def _assert_fixture_namespace(snapshot: Mapping[str, Any]) -> None:
    """Keep every caller-minted IRI in the unmistakable test namespace."""

    iri_fields = {
        "publication_id",
        "focus_node",
        "path",
        "authority_iri",
        "shape_iri",
        "constraint_iri",
        "assertion_ref",
        "candidate_ref",
        "review_decision_ref",
    }

    def visit(value: Any, field: str | None = None) -> None:
        if (
            field in iri_fields
            and value is not None
            and (
                not isinstance(value, str)
                or not value.startswith(FIXTURE_NAMESPACE)
            )
        ):
            raise ValueError(
                f"controlled fixture IRI escaped test namespace: {field}"
            )
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(child, str(key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, field)

    visit(snapshot)


def _as_controlled_fixture_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Re-namespace engine output so it cannot pass as a Phase03 package."""

    value = deepcopy(dict(package))
    original_publication_id = value["authority_bindings"]["publication_id"]
    fixture_publication_id = (
        f"{FIXTURE_NAMESPACE}publication:"
        f"{value['authority_bindings']['publication_semantic_hash']}"
    )
    value["authority_bindings"]["publication_id"] = fixture_publication_id
    for issue in value["issues"]:
        issue["publication_id"] = fixture_publication_id
        for basis in issue["authority_basis"]:
            if basis.get("publication_id") == original_publication_id:
                basis["publication_id"] = fixture_publication_id
        basis_hash = semantic_hash(diagnostic_semantic_basis(issue))
        issue["diagnostic_basis_hash"] = basis_hash
        issue["diagnostic_id"] = f"{FIXTURE_NAMESPACE}diagnostic:{basis_hash}"
    value["manifest"]["issue_ids"] = [
        issue["diagnostic_id"] for issue in value["issues"]
    ]
    value["manifest"].pop("package_id", None)
    value["manifest"].pop("package_semantic_hash", None)
    value["manifest"]["status"] = FIXTURE_STATUS
    value["status"] = FIXTURE_STATUS
    fixture_package_hash = semantic_hash(value)
    value["manifest"]["fixture_package_id"] = (
        f"{FIXTURE_NAMESPACE}diagnostic-package:{fixture_package_hash}"
    )
    value["manifest"]["controlled_fixture_diagnostic_package_hash"] = (
        fixture_package_hash
    )
    return value


@dataclass(frozen=True)
class ControlledDiagnosticFixture:
    """Synthetic diagnostic evidence carrying non-production identity markers."""

    _authority_snapshot: Mapping[str, Any]
    _diagnostic_package: Mapping[str, Any]

    @classmethod
    def create(cls) -> ControlledDiagnosticFixture:
        snapshot = _controlled_snapshot(_fixture_bindings())
        package = _as_controlled_fixture_package(
            reconstruct_diagnostics(snapshot).to_dict()
        )
        fixture_publication_id = package["authority_bindings"]["publication_id"]
        snapshot["authority_bindings"]["publication_id"] = fixture_publication_id
        for collection in ("requirements", "conflict_rules"):
            for row in snapshot[collection]:
                row["publication_id"] = fixture_publication_id
        _assert_fixture_namespace(snapshot)
        return cls(
            _authority_snapshot=deepcopy(snapshot),
            _diagnostic_package=deepcopy(package),
        )

    @property
    def fixture_type(self) -> str:
        return FIXTURE_TYPE

    @property
    def status(self) -> str:
        return FIXTURE_STATUS

    @property
    def production_authority(self) -> bool:
        return False

    @property
    def test_only(self) -> bool:
        return True

    @property
    def authority_snapshot(self) -> dict[str, Any]:
        return deepcopy(dict(self._authority_snapshot))

    @property
    def diagnostic_package(self) -> dict[str, Any]:
        return deepcopy(dict(self._diagnostic_package))

    @property
    def controlled_fixture_diagnostic_package_hash(self) -> str:
        return str(
            self._diagnostic_package["manifest"][
                "controlled_fixture_diagnostic_package_hash"
            ]
        )

    def _semantic_content(self) -> dict[str, Any]:
        return {
            "contract_version": "1.0",
            "fixture_type": self.fixture_type,
            "status": self.status,
            "production_authority": self.production_authority,
            "test_only": self.test_only,
            "authority_snapshot": self.authority_snapshot,
            "diagnostic_package": self.diagnostic_package,
            "controlled_fixture_diagnostic_package_hash": (
                self.controlled_fixture_diagnostic_package_hash
            ),
        }

    @property
    def controlled_fixture_hash(self) -> str:
        return semantic_hash(self._semantic_content())

    @property
    def fixture_id(self) -> str:
        return f"{FIXTURE_NAMESPACE}fixture:{self.controlled_fixture_hash}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._semantic_content(),
            "fixture_id": self.fixture_id,
            "controlled_fixture_hash": self.controlled_fixture_hash,
        }


def controlled_governance_authority_for_test_harness(
    fixture: ControlledDiagnosticFixture,
) -> GovernanceAuthority:
    """Adapt a marked fixture solely for Phase04 behavioral tests.

    No Phase03 attestation is built or claimed.  The placeholder physical hash
    is derived from the marked fixture and is meaningful only inside this test
    harness.
    """

    if (
        fixture.fixture_type != FIXTURE_TYPE
        or fixture.status != FIXTURE_STATUS
        or fixture.production_authority
        or not fixture.test_only
    ):
        raise ValueError("unmarked controlled fixture")
    package = fixture.diagnostic_package
    bindings = package["authority_bindings"]
    issues: dict[str, dict[str, Any]] = {}
    for fixture_issue in package["issues"]:
        issue = deepcopy(fixture_issue)
        diagnostic_id = f"urn:kg-mnp:diagnostic:{issue['diagnostic_basis_hash']}"
        issue["diagnostic_id"] = diagnostic_id
        issues[diagnostic_id] = issue
    return GovernanceAuthority(
        authority_type="CONTROLLED_TEST_HARNESS",
        publication_id=bindings["publication_id"],
        publication_semantic_hash=bindings["publication_semantic_hash"],
        repository_semantic_hash=bindings["repository_semantic_hash"],
        upstream_phase03_attestation_sha256=semantic_hash(
            {
                "test_only": True,
                "controlled_fixture_hash": fixture.controlled_fixture_hash,
                "status": FIXTURE_STATUS,
            }
        ),
        upstream_phase03_diagnostic_package_hash=(
            fixture.controlled_fixture_diagnostic_package_hash
        ),
        issues=issues,
    )
