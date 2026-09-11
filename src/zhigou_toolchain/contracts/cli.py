"""Public `kg-mnp contracts` command."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from .catalog import ContractCatalog, verify_catalog_lock
from .document_io import read_document
from .errors import ContractCatalogError, DocumentError
from .registry import get_contract_schema, validate_contract

SUCCESS = 0
USAGE_ERROR = 2
CONTRACT_INVALID = 3
PATH_OR_SECURITY_VIOLATION = 4
LOCK_MISMATCH = 5
DEPENDENCY_RESOLUTION_ERROR = 6
WORKSPACE_INVALID = 7
INTERNAL_ERROR = 8


def command_result(
    command: str,
    *,
    status: str,
    code: int,
    subject: str,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    result: Any = None,
) -> dict[str, Any]:
    return {
        "command": command,
        "status": status,
        "code": code,
        "subject": subject,
        "errors": errors or [],
        "warnings": warnings or [],
        "result": result,
    }


def emit_json(value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    try:
        text.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
    except (LookupError, UnicodeEncodeError):
        # Escape code points, never replace/drop them or partially print JSON.
        text = json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
    print(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp contracts")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="operation", required=True)
    listing = commands.add_parser("list", help="list authoritative public contracts")
    listing.add_argument("--json", action="store_true")
    showing = commands.add_parser("show", help="show one packaged JSON Schema")
    showing.add_argument("contract_name")
    showing.add_argument("--json", action="store_true")
    validating = commands.add_parser("validate", help="validate a JSON/YAML document")
    validating.add_argument("contract_name", nargs="?")
    validating.add_argument("document", nargs="?", type=Path)
    validating.add_argument("--contract", dest="legacy_contract")
    validating.add_argument("--input", dest="legacy_document", type=Path)
    validating.add_argument("--json", action="store_true")
    verifying = commands.add_parser("verify-catalog", help="verify catalog and lock")
    verifying.add_argument("--json", action="store_true")
    return parser


def _validation_error(exc: ValidationError) -> dict[str, Any]:
    return {
        "code": "CONTRACT_INVALID",
        "path": "$" + "".join(f"/{item}" for item in exc.absolute_path),
        "message": exc.message,
    }


def _document_subject(arguments: argparse.Namespace) -> str:
    path = getattr(arguments, "document", None) or getattr(arguments, "legacy_document", None)
    return path.name if isinstance(path, Path) else arguments.operation


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    command = f"contracts {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    try:
        if arguments.operation == "list":
            specs = [spec.to_dict() for spec in ContractCatalog.load().specs]
            payload = command_result(
                command, status="SUCCESS", code=SUCCESS, subject="public-contract-catalog", result=specs
            )
            if use_json:
                emit_json(payload)
            else:
                for spec in specs:
                    print(f"{spec['name']} {spec['version']} {spec['scope']} {spec['stability']}")
            return SUCCESS
        if arguments.operation == "show":
            schema = get_contract_schema(arguments.contract_name)
            payload = command_result(
                command, status="SUCCESS", code=SUCCESS, subject=arguments.contract_name, result=schema
            )
            emit_json(payload if use_json else schema)
            return SUCCESS
        if arguments.operation == "validate":
            contract_name = arguments.contract_name or arguments.legacy_contract
            document_path = arguments.document or arguments.legacy_document
            if contract_name is None or document_path is None:
                parser.error("validate requires a contract name and document")
            document = read_document(document_path)
            validate_contract(contract_name, document)
            payload = command_result(
                command,
                status="VALID",
                code=SUCCESS,
                subject=document_path.name,
                result={"contract_name": contract_name},
            )
            if use_json:
                emit_json(payload)
            else:
                print(f"VALID {contract_name} {document_path.name}")
            return SUCCESS
        lock = verify_catalog_lock()
        payload = command_result(
            command,
            status="VALID",
            code=SUCCESS,
            subject="public-contract-catalog",
            result={"lock_id": lock["lock_id"], "content_digest": lock["content_digest"]},
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"VALID {lock['lock_id']}")
        return SUCCESS
    except ValidationError as exc:
        payload = command_result(
            command,
            status="INVALID",
            code=CONTRACT_INVALID,
            subject=_document_subject(arguments),
            errors=[_validation_error(exc)],
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"CONTRACT_INVALID: {exc.message}", file=sys.stderr)
        return CONTRACT_INVALID
    except DocumentError as exc:
        payload = command_result(
            command,
            status="INVALID",
            code=PATH_OR_SECURITY_VIOLATION,
            subject=_document_subject(arguments),
            errors=[{"code": "DOCUMENT_SECURITY", "path": "$", "message": str(exc)}],
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"DOCUMENT_SECURITY: {exc}", file=sys.stderr)
        return PATH_OR_SECURITY_VIOLATION
    except ContractCatalogError as exc:
        code = LOCK_MISMATCH if "lock" in str(exc).casefold() else CONTRACT_INVALID
        payload = command_result(
            command,
            status="INVALID",
            code=code,
            subject="public-contract-catalog",
            errors=[{"code": "CATALOG_INVALID", "path": "$", "message": str(exc)}],
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"CATALOG_INVALID: {exc}", file=sys.stderr)
        return code
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - final CLI boundary
        if arguments.debug:
            traceback.print_exc()
        elif use_json:
            emit_json(
                command_result(
                    command,
                    status="ERROR",
                    code=INTERNAL_ERROR,
                    subject=arguments.operation,
                    errors=[{"code": "INTERNAL_ERROR", "path": "$", "message": str(exc)}],
                )
            )
        else:
            print(f"INTERNAL_ERROR: {exc}", file=sys.stderr)
        return INTERNAL_ERROR
