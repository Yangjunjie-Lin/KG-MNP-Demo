"""Public `kg-mnp domain-pack` command."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from zhigou_toolchain.contracts.cli import (
    CONTRACT_INVALID,
    DEPENDENCY_RESOLUTION_ERROR,
    INTERNAL_ERROR,
    LOCK_MISMATCH,
    PATH_OR_SECURITY_VIOLATION,
    SUCCESS,
    command_result,
    emit_json,
)
from zhigou_toolchain.contracts.errors import ContractError, PathSecurityError

from .locking import (
    DomainPackLockError,
    generate_pack_lock,
    load_pack_lock,
    verify_pack_lock,
)
from .registry import DomainPackRegistry, DomainPackRegistryError
from .resolver import resolve_dependency_closure
from .validation import load_domain_pack_manifest, validate_domain_pack


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp domain-pack")
    parser.add_argument("--debug", action="store_true")
    operations = parser.add_subparsers(dest="operation", required=True)
    listing = operations.add_parser("list")
    listing.add_argument("--domain-packs-root", type=Path)
    listing.add_argument("--json", action="store_true")
    for name in ("inspect", "validate", "verify-lock"):
        command = operations.add_parser(name)
        command.add_argument("pack")
        command.add_argument("--domain-packs-root", type=Path)
        command.add_argument("--json", action="store_true")
    locking = operations.add_parser("lock")
    locking.add_argument("pack")
    locking.add_argument("--domain-packs-root", type=Path)
    locking.add_argument("--check", action="store_true")
    locking.add_argument("--json", action="store_true")
    return parser


def _pack_path(arguments: argparse.Namespace) -> Path:
    candidate = Path(arguments.pack)
    if candidate.exists():
        return candidate.resolve(strict=True)
    return DomainPackRegistry(arguments.domain_packs_root).resolve_path_or_id(arguments.pack)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    command = f"domain-pack {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    error_message = "unknown Domain Pack error"
    try:
        if arguments.operation == "list":
            registry = DomainPackRegistry(arguments.domain_packs_root)
            result = [
                {"pack_id": pack_id, "pack_version": version, "path": path.name}
                for pack_id, version, path in registry.list()
            ]
            payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=registry.root.name, result=result)
            if use_json:
                emit_json(payload)
            else:
                for item in result:
                    print(f"{item['pack_id']} {item['pack_version']}")
            return SUCCESS
        path = _pack_path(arguments)
        if arguments.operation == "inspect":
            manifest = load_domain_pack_manifest(path)
            lock = load_pack_lock(path)
            result = {"manifest": manifest.document, "lock": lock.document}
            payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=manifest.pack_id, result=result)
            if use_json:
                emit_json(payload)
            else:
                print(f"{manifest.pack_id} {manifest.pack_version} {manifest.document['lifecycle']} {lock.lock_id}")
            return SUCCESS
        if arguments.operation == "validate":
            validation = validate_domain_pack(path)
            codes = {item["code"] for item in validation.report["checks"]}
            if validation.valid and validation.manifest is not None:
                try:
                    registry = DomainPackRegistry(arguments.domain_packs_root or path.parent)
                    resolve_dependency_closure(
                        registry,
                        ((validation.manifest.pack_id, validation.manifest.pack_version),),
                    )
                except DomainPackRegistryError as exc:
                    validation.report["checks"].append(
                        {
                            "code": "DEPENDENCY_RESOLUTION_ERROR",
                            "severity": "ERROR",
                            "path": "$/dependencies",
                            "message": str(exc),
                            "contract_name": "domain-pack-manifest",
                        }
                    )
                    validation.report["status"] = "INVALID"
                    validation.report["summary"]["error_count"] += 1
                    codes.add("DEPENDENCY_RESOLUTION_ERROR")
            if validation.valid:
                code = SUCCESS
            elif "DEPENDENCY_RESOLUTION_ERROR" in codes:
                code = DEPENDENCY_RESOLUTION_ERROR
            elif "DOMAIN_PACK_LOCK_MISMATCH" in codes:
                code = LOCK_MISMATCH
            elif codes & {
                "ASSET_SECURITY_VIOLATION",
                "PACK_FILESYSTEM_VIOLATION",
                "MANIFEST_UNREADABLE",
            }:
                code = PATH_OR_SECURITY_VIOLATION
            else:
                code = CONTRACT_INVALID
            payload = command_result(
                command,
                status=validation.report["status"],
                code=code,
                subject=path.name,
                errors=[item for item in validation.report["checks"] if item["severity"] == "ERROR"],
                warnings=[item for item in validation.report["checks"] if item["severity"] == "WARNING"],
                result=validation.report,
            )
            if use_json:
                emit_json(payload)
            elif validation.valid:
                print(f"VALID {path.name}")
            else:
                for item in payload["errors"]:
                    print(f"{item['code']}: {item['message']}", file=sys.stderr)
            return code
        manifest = load_domain_pack_manifest(path)
        if arguments.operation == "lock":
            validation = validate_domain_pack(path, verify_lock=False)
            if not validation.valid:
                payload = command_result(
                    command,
                    status="INVALID",
                    code=CONTRACT_INVALID,
                    subject=manifest.pack_id,
                    errors=validation.report["checks"],
                )
                if use_json:
                    emit_json(payload)
                else:
                    print("Domain Pack validation failed; lock was not written", file=sys.stderr)
                return CONTRACT_INVALID
            lock = generate_pack_lock(manifest, check=arguments.check)
        else:
            lock = verify_pack_lock(manifest)
        payload = command_result(
            command,
            status="VALID",
            code=SUCCESS,
            subject=manifest.pack_id,
            result={"lock_id": lock.lock_id, "content_digest": lock.content_digest},
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"VALID {lock.lock_id}")
        return SUCCESS
    except DomainPackLockError as caught:
        code = LOCK_MISMATCH
        error_message = str(caught)
    except (OSError, PathSecurityError) as caught:
        code = PATH_OR_SECURITY_VIOLATION
        error_message = str(caught)
    except (DomainPackRegistryError, ContractError) as caught:
        code = DEPENDENCY_RESOLUTION_ERROR if isinstance(caught, DomainPackRegistryError) else CONTRACT_INVALID
        error_message = str(caught)
    except Exception as caught:  # noqa: BLE001  # pragma: no cover - final CLI boundary
        code = INTERNAL_ERROR
        error_message = str(caught)
        if arguments.debug:
            traceback.print_exc()
    payload = command_result(
        command,
        status="INVALID" if code != INTERNAL_ERROR else "ERROR",
        code=code,
        subject=getattr(arguments, "pack", "domain-packs"),
        errors=[{"code": "DOMAIN_PACK_ERROR", "path": "$", "message": error_message}],
    )
    if use_json:
        emit_json(payload)
    else:
        print(f"DOMAIN_PACK_ERROR: {error_message}", file=sys.stderr)
    return code
