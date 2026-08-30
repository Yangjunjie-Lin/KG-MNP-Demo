"""Public `kg-mnp workspace` command."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from kg_mnp.contracts.cli import (
    DEPENDENCY_RESOLUTION_ERROR,
    INTERNAL_ERROR,
    LOCK_MISMATCH,
    PATH_OR_SECURITY_VIOLATION,
    SUCCESS,
    WORKSPACE_INVALID,
    command_result,
    emit_json,
)
from kg_mnp.contracts.errors import ContractError, PathSecurityError
from kg_mnp.domain_packs.registry import DomainPackRegistry, DomainPackRegistryError

from .locking import ProjectLockError, generate_project_lock
from .service import (
    WorkspaceError,
    initialize_workspace,
    load_project_manifest,
    open_workspace,
)
from .validation import validate_workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp workspace")
    parser.add_argument("--debug", action="store_true")
    operations = parser.add_subparsers(dest="operation", required=True)
    initializing = operations.add_parser("init")
    initializing.add_argument("workspace_path", type=Path)
    initializing.add_argument("--project-id", required=True)
    initializing.add_argument("--project-version", required=True)
    initializing.add_argument("--display-name", required=True)
    initializing.add_argument("--domain-pack", required=True)
    initializing.add_argument("--domain-pack-version", required=True)
    initializing.add_argument("--domain-packs-root", type=Path)
    initializing.add_argument("--json", action="store_true")
    for name in ("validate", "status", "inspect"):
        command = operations.add_parser(name)
        command.add_argument("workspace_path", type=Path)
        command.add_argument("--domain-packs-root", type=Path)
        command.add_argument("--json", action="store_true")
    locking = operations.add_parser("lock")
    locking.add_argument("workspace_path", type=Path)
    locking.add_argument("--domain-packs-root", type=Path)
    locking.add_argument("--check", action="store_true")
    locking.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    command = f"workspace {arguments.operation}"
    use_json = bool(arguments.json)
    error_message = "unknown Workspace error"
    try:
        if arguments.operation == "init":
            workspace = initialize_workspace(
                arguments.workspace_path,
                project_id=arguments.project_id,
                project_version=arguments.project_version,
                display_name=arguments.display_name,
                domain_pack=arguments.domain_pack,
                domain_pack_version=arguments.domain_pack_version,
                domain_packs_root=arguments.domain_packs_root,
            )
            result = {
                "project_id": workspace.manifest.project_id,
                "project_version": workspace.manifest.project_version,
                "lock_id": workspace.lock.lock_id,
                "status": "VALID",
            }
            payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=workspace.root.name, result=result)
            if use_json:
                emit_json(payload)
            else:
                print(f"INITIALIZED {workspace.root} {workspace.lock.lock_id}")
            return SUCCESS
        if arguments.operation in {"validate", "status"}:
            validation = validate_workspace(
                arguments.workspace_path,
                domain_packs_root=arguments.domain_packs_root,
            )
            report_codes = {item["code"] for item in validation.report["checks"]}
            if validation.valid:
                code = SUCCESS
            elif "WORKSPACE_SECURITY_VIOLATION" in report_codes:
                code = PATH_OR_SECURITY_VIOLATION
            elif validation.status == "MISSING_DOMAIN_PACK":
                code = DEPENDENCY_RESOLUTION_ERROR
            elif validation.status in {
                "STALE_PROJECT_LOCK",
                "STALE_DOMAIN_PACK_LOCK",
                "CONTRACT_CATALOG_MISMATCH",
            }:
                code = LOCK_MISMATCH
            else:
                code = WORKSPACE_INVALID
            payload = command_result(
                command,
                status=validation.status,
                code=code,
                subject=arguments.workspace_path.name,
                errors=validation.report["checks"],
                result=validation.report,
            )
            if use_json:
                emit_json(payload)
            else:
                print(validation.status)
                if not validation.valid:
                    for item in validation.report["checks"]:
                        print(f"{item['code']}: {item['message']}", file=sys.stderr)
            return code
        if arguments.operation == "inspect":
            workspace = open_workspace(arguments.workspace_path)
            result = {"manifest": workspace.manifest.document, "lock": workspace.lock.document}
            payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=workspace.root.name, result=result)
            if use_json:
                emit_json(payload)
            else:
                print(f"{workspace.manifest.project_id} {workspace.manifest.project_version} {workspace.lock.lock_id}")
            return SUCCESS
        manifest = load_project_manifest(arguments.workspace_path)
        registry = DomainPackRegistry(arguments.domain_packs_root)
        lock = generate_project_lock(manifest, registry, check=arguments.check)
        payload = command_result(
            command,
            status="VALID",
            code=SUCCESS,
            subject=manifest.project_id,
            result={"lock_id": lock.lock_id, "content_digest": lock.document["content_digest"]},
        )
        if use_json:
            emit_json(payload)
        else:
            print(f"VALID {lock.lock_id}")
        return SUCCESS
    except ProjectLockError as caught:
        code = LOCK_MISMATCH
        error_message = str(caught)
    except (OSError, PathSecurityError) as caught:
        code = PATH_OR_SECURITY_VIOLATION
        error_message = str(caught)
    except DomainPackRegistryError as caught:
        code = DEPENDENCY_RESOLUTION_ERROR
        error_message = str(caught)
    except (WorkspaceError, ContractError) as caught:
        code = WORKSPACE_INVALID
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
        subject=arguments.workspace_path.name,
        errors=[{"code": "WORKSPACE_ERROR", "path": "$", "message": error_message}],
    )
    if use_json:
        emit_json(payload)
    else:
        print(f"WORKSPACE_ERROR: {error_message}", file=sys.stderr)
    return code
