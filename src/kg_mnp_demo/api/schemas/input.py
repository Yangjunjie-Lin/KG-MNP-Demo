"""Pydantic input models aligned with schemas/mnp_case_input.schema.json."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kg_mnp_demo.api.schemas.common import AuthorizationCodeStatus, EvidenceStatus


class SubscriberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_id: str = Field(min_length=1)


class PhoneNumberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    masked_number: str = Field(min_length=1)


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)


class EvidenceBaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(min_length=1)
    generated_at: datetime
    valid_until: datetime
    status: EvidenceStatus


class IdentityEvidenceInput(EvidenceBaseInput):
    matched: bool


class NumberStatusEvidenceInput(EvidenceBaseInput):
    status_code: str = Field(min_length=1)


class BillingEvidenceInput(EvidenceBaseInput):
    outstanding_amount: Decimal | float | int | str
    currency: str = Field(min_length=1)
    has_payment_arrangement: bool


class ContractEvidenceInput(EvidenceBaseInput):
    contract_status: str = Field(min_length=1)
    contract_end_time: datetime | None = None


class PortingHistoryEvidenceInput(EvidenceBaseInput):
    days_since_last_port: int = Field(ge=0)


class EvidenceBundleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: IdentityEvidenceInput
    number_status: NumberStatusEvidenceInput
    billing: BillingEvidenceInput
    contract: ContractEvidenceInput
    porting_history: PortingHistoryEvidenceInput


class AuthorizationCodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AuthorizationCodeStatus | None = None
    issued_at: datetime | None = None
    valid_until: datetime | None = None
    masked_value: str | None = None


class TerminationAgreementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signed_at: datetime | None = None
    effective_at: datetime | None = None
    status: str | None = None


class ProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: str | None = None
    authorization_code: AuthorizationCodeInput | None = None
    termination_agreement: TerminationAgreementInput | None = None


class MNPCaseInput(BaseModel):
    """API request body for a case assessment (mirrors JSON Schema contract)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    case_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    assessment_time: datetime
    subscriber: SubscriberInput
    phone_number: PhoneNumberInput
    account: AccountInput
    evidence: EvidenceBundleInput
    process: ProcessInput | None = None

    def to_pipeline_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict for AssessmentService / JSON Schema path."""
        # Omit null optionals so JSON Schema (process as object, not null) still accepts.
        return self.model_dump(mode="json", exclude_none=True)
