"""Validate and normalize external JSON case inputs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from kg_mnp_demo.loader import project_root


SCHEMA_PATH = project_root() / "schemas" / "mnp_case_input.schema.json"


class InputValidationError(ValueError):
    """Raised when JSON input fails schema or normalization checks."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class EvidenceInput:
    source_system: str
    generated_at: datetime
    valid_until: datetime
    status: str


@dataclass(frozen=True)
class IdentityEvidence(EvidenceInput):
    matched: bool


@dataclass(frozen=True)
class NumberStatusEvidence(EvidenceInput):
    status_code: str


@dataclass(frozen=True)
class BillingEvidence(EvidenceInput):
    outstanding_amount: Decimal
    currency: str
    has_payment_arrangement: bool


@dataclass(frozen=True)
class ContractEvidence(EvidenceInput):
    contract_status: str
    contract_end_time: datetime | None


@dataclass(frozen=True)
class PortingEvidence(EvidenceInput):
    days_since_last_port: int


@dataclass(frozen=True)
class NormalizedCaseInput:
    schema_version: str
    case_id: str
    assessment_time: datetime
    subscriber_id: str
    masked_number: str
    account_id: str
    identity: IdentityEvidence
    number_status: NumberStatusEvidence
    billing: BillingEvidence
    contract: ContractEvidence
    porting_history: PortingEvidence

    def to_dict(self) -> dict[str, Any]:
        def _ser(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(obj, Decimal):
                return format(obj, "f")
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _ser(v) for k, v in asdict(obj).items()}
            return obj

        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "assessment_time": _ser(self.assessment_time),
            "subscriber": {"subscriber_id": self.subscriber_id},
            "phone_number": {"masked_number": self.masked_number},
            "account": {"account_id": self.account_id},
            "evidence": {
                "identity": _ser(self.identity),
                "number_status": _ser(self.number_status),
                "billing": _ser(self.billing),
                "contract": _ser(self.contract),
                "porting_history": _ser(self.porting_history),
            },
        }


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _format_path(path: list[Any]) -> str:
    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts:
                parts.append(f".{item}")
            else:
                parts.append(str(item))
    return "".join(parts) or "(root)"


def _schema_errors(data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(load_schema(), format_checker=FormatChecker())
    errors: list[str] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = _format_path(list(err.path))
        msg = err.message
        # Prefer required-field phrasing
        if err.validator == "required":
            missing = err.message.split("'")[1] if "'" in err.message else err.message
            field = f"{path}.{missing}" if path != "(root)" else missing
            errors.append(f"{field} is required")
        elif err.validator == "format" and err.validator_value == "date-time":
            errors.append(f"{path} must be date-time")
        else:
            errors.append(f"{path}: {msg}")
    return errors


def parse_utc_datetime(value: str, field: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise InputValidationError([f"{field} must be date-time"]) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise InputValidationError([f"{field} must be a decimal number"]) from exc


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    cleaned = cleaned.strip("-_")
    if not cleaned:
        raise InputValidationError(["identifier contains no safe characters"])
    return cleaned


def normalize_case_input(data: dict[str, Any]) -> NormalizedCaseInput:
    schema_errors = _schema_errors(data)
    if schema_errors:
        raise InputValidationError(schema_errors)

    ev = data["evidence"]
    case_id = _safe_id(data["case_id"])
    return NormalizedCaseInput(
        schema_version=str(data["schema_version"]),
        case_id=case_id,
        assessment_time=parse_utc_datetime(data["assessment_time"], "assessment_time"),
        subscriber_id=_safe_id(data["subscriber"]["subscriber_id"]),
        masked_number=str(data["phone_number"]["masked_number"]),
        account_id=_safe_id(data["account"]["account_id"]),
        identity=IdentityEvidence(
            matched=bool(ev["identity"]["matched"]),
            source_system=str(ev["identity"]["source_system"]),
            generated_at=parse_utc_datetime(
                ev["identity"]["generated_at"], "evidence.identity.generated_at"
            ),
            valid_until=parse_utc_datetime(
                ev["identity"]["valid_until"], "evidence.identity.valid_until"
            ),
            status=str(ev["identity"]["status"]),
        ),
        number_status=NumberStatusEvidence(
            status_code=str(ev["number_status"]["status_code"]),
            source_system=str(ev["number_status"]["source_system"]),
            generated_at=parse_utc_datetime(
                ev["number_status"]["generated_at"],
                "evidence.number_status.generated_at",
            ),
            valid_until=parse_utc_datetime(
                ev["number_status"]["valid_until"],
                "evidence.number_status.valid_until",
            ),
            status=str(ev["number_status"]["status"]),
        ),
        billing=BillingEvidence(
            outstanding_amount=_parse_decimal(
                ev["billing"]["outstanding_amount"],
                "evidence.billing.outstanding_amount",
            ),
            currency=str(ev["billing"]["currency"]),
            has_payment_arrangement=bool(ev["billing"]["has_payment_arrangement"]),
            source_system=str(ev["billing"]["source_system"]),
            generated_at=parse_utc_datetime(
                ev["billing"]["generated_at"], "evidence.billing.generated_at"
            ),
            valid_until=parse_utc_datetime(
                ev["billing"]["valid_until"], "evidence.billing.valid_until"
            ),
            status=str(ev["billing"]["status"]),
        ),
        contract=ContractEvidence(
            contract_status=str(ev["contract"]["contract_status"]),
            contract_end_time=(
                parse_utc_datetime(
                    ev["contract"]["contract_end_time"],
                    "evidence.contract.contract_end_time",
                )
                if ev["contract"].get("contract_end_time")
                else None
            ),
            source_system=str(ev["contract"]["source_system"]),
            generated_at=parse_utc_datetime(
                ev["contract"]["generated_at"], "evidence.contract.generated_at"
            ),
            valid_until=parse_utc_datetime(
                ev["contract"]["valid_until"], "evidence.contract.valid_until"
            ),
            status=str(ev["contract"]["status"]),
        ),
        porting_history=PortingEvidence(
            days_since_last_port=int(ev["porting_history"]["days_since_last_port"]),
            source_system=str(ev["porting_history"]["source_system"]),
            generated_at=parse_utc_datetime(
                ev["porting_history"]["generated_at"],
                "evidence.porting_history.generated_at",
            ),
            valid_until=parse_utc_datetime(
                ev["porting_history"]["valid_until"],
                "evidence.porting_history.valid_until",
            ),
            status=str(ev["porting_history"]["status"]),
        ),
    )


def load_and_normalize(path: Path | str) -> NormalizedCaseInput:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise InputValidationError(["(root) must be a JSON object"])
    return normalize_case_input(raw)
