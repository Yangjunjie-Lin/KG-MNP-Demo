"""Closed, non-executable, independently frozen negative acceptance recipes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .exchange_io import digest, json_bytes

# These are existing guards, not new domain rules. SHACL expectations must also
# be justified by the actual locked shape supplied in each case's rule basis.
RECIPES = {
    "REMOVE_REQUIRED": ("SHACL", "SHACL", "MinCountConstraintComponent"),
    "WRONG_DATATYPE": ("SHACL", "SHACL", "DatatypeConstraintComponent"),
    "BROKEN_EVIDENCE": ("PROVENANCE", "PROVENANCE", "HANDOFF_PROVENANCE_OPEN"),
    "TAMPER_BYTES": ("FILE_INTEGRITY", "MANIFEST", "MANIFEST_BYTES_MISMATCH"),
    "MISSING_FILE": ("FILE_INTEGRITY", "MANIFEST", "MANIFEST_FILE_MISSING"),
    "WRONG_SIZE": ("FILE_INTEGRITY", "MANIFEST", "MANIFEST_BYTES_MISMATCH"),
    "STALE_REVIEW": ("STATE_GATE", "REVIEW", "SESSION_REVIEW_STALE"),
    "STALE_REVISION": ("STATE_GATE", "EXPORT", "HANDOFF_SESSION_REVISION_STALE"),
    "WRONG_COMPILATION": ("STATE_GATE", "COMPILE", "SESSION_DEPENDENCY_STALE"),
    "DENIED_EXPORT": ("AUTHORIZATION", "AUTHORIZATION", "FORBIDDEN"),
    "WRONG_PACKAGE": ("DELIVERY_BINDING", "COVER", "DELIVERY_TARGET_MISMATCH"),
    "WRONG_ARCHIVE": ("DELIVERY_BINDING", "COVER", "DELIVERY_TARGET_MISMATCH"),
    "WRONG_INPUT": ("DELIVERY_BINDING", "COVER", "DELIVERY_TARGET_MISMATCH"),
    "STALE_ANCESTOR": ("DELIVERY_BINDING", "COVER", "DELIVERY_ANCESTOR_NOT_CURRENT"),
}


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RuleBasis(Closed):
    reference: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=100)
    asset_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    shape_iri: str | None = None


class NegativeTarget(Closed):
    selector: Literal["FIRST_TYPED_SUBJECT", "FROZEN_PACKAGE"]
    class_iri: str | None = None
    predicate_iri: str | None = None


class ExpectedRejection(Closed):
    stage: str
    code: str


class NegativeCase(Closed):
    case_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,100}$")
    category: str
    rule_basis: RuleBasis
    target: NegativeTarget
    mutation: str
    expected: ExpectedRejection

    @model_validator(mode="after")
    def fixed_expectation(self):
        if RECIPES.get(self.mutation) != (self.category, self.expected.stage, self.expected.code):
            raise ValueError("NEGATIVE_EXPECTATION_NOT_REGISTERED")
        if self.category == "SHACL":
            if (self.target.selector != "FIRST_TYPED_SUBJECT" or not self.target.class_iri or not self.target.predicate_iri
                    or not self.rule_basis.asset_sha256 or not self.rule_basis.shape_iri):
                raise ValueError("NEGATIVE_INDEPENDENT_SHAPE_REQUIRED")
        elif self.target.selector != "FROZEN_PACKAGE":
            raise ValueError("NEGATIVE_PACKAGE_TARGET_REQUIRED")
        return self


class NegativeCasePlan(Closed):
    format: Literal["zhigou-negative-case-plan/1.0.0"] = "zhigou-negative-case-plan/1.0.0"
    plan_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,100}$")
    version: str = Field(min_length=1, max_length=100)
    origin: Literal["INDEPENDENT_SYNTHETIC_ACCEPTANCE", "AUTHORIZED_INDEPENDENT_ACCEPTANCE"]
    cases: list[NegativeCase] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len({c.case_id for c in self.cases}) != len(self.cases):
            raise ValueError("DUPLICATE_NEGATIVE_CASE")
        return self


def normalize_plan(value):
    return NegativeCasePlan.model_validate(value).model_dump(mode="json")


def plan_digest(value):
    return digest(json_bytes(normalize_plan(value)))
