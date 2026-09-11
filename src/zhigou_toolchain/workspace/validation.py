"""Fail-closed Project Workspace validation and status classification."""

from __future__ import annotations

from pathlib import Path

from jsonschema import ValidationError

from zhigou_toolchain.contracts.catalog import (
    ContractCatalog,
    ContractCatalogError,
    verify_catalog_lock,
)
from zhigou_toolchain.contracts.document_io import DocumentError
from zhigou_toolchain.contracts.errors import ContractError, PathSecurityError
from zhigou_toolchain.contracts.validation import ValidationCheck, validation_report
from zhigou_toolchain.domain_packs.locking import DomainPackLockError
from zhigou_toolchain.domain_packs.registry import (
    DomainPackRegistry,
    DomainPackRegistryError,
)

from .layout import layout_errors
from .locking import ProjectLockError, load_project_lock, verify_project_lock
from .models import WorkspaceValidationResult
from .security import (
    confirmed_authority_files,
    validate_confirmed_authority,
    validate_workspace_tree,
)
from .service import WorkspaceError, load_project_manifest
from .status import (
    CONTRACT_CATALOG_MISMATCH,
    INVALID,
    MISSING_DOMAIN_PACK,
    STALE_DOMAIN_PACK_LOCK,
    STALE_PROJECT_LOCK,
    UNINITIALIZED,
    VALID,
)


def _check(code: str, path: str, message: str) -> ValidationCheck:
    return ValidationCheck(
        code=code,
        severity="ERROR",
        path=path,
        message=message,
        contract_name="project-manifest",
    )


def validate_workspace(
    workspace_root: Path | str,
    *,
    domain_packs_root: Path | str | None = None,
) -> WorkspaceValidationResult:
    root = Path(workspace_root)
    checks: list[ValidationCheck] = []
    status = INVALID
    if not root.is_dir() or not (root / "project.yaml").is_file():
        checks.append(_check("WORKSPACE_UNINITIALIZED", "$", "project.yaml is missing"))
        status = UNINITIALIZED
    else:
        try:
            validate_workspace_tree(root)
            for code, detail in layout_errors(root):
                checks.append(_check(code, detail, "Workspace v1 layout mismatch"))
            unexpected_confirmed = confirmed_authority_files(root)
            if unexpected_confirmed:
                try:
                    validate_confirmed_authority(root, domain_packs_root=domain_packs_root)
                except Exception:  # noqa: BLE001 - malformed authorities fail closed
                    checks.append(_check("UNEXPECTED_CONFIRMED_AUTHORITY", "artifacts/confirmed",
                                         "Confirmed authority closure or manifest is invalid"))
        except PathSecurityError as exc:
            checks.append(_check("WORKSPACE_SECURITY_VIOLATION", "$", str(exc)))
        try:
            manifest = load_project_manifest(root)
            registry = DomainPackRegistry(domain_packs_root)
            try:
                actual_lock = load_project_lock(root)
                verify_catalog_lock()
                if actual_lock.document["contract_catalog_digest"] != ContractCatalog.load().digest:
                    status = CONTRACT_CATALOG_MISMATCH
                    checks.append(_check("CONTRACT_CATALOG_MISMATCH", "project.lock.json", "Project Lock binds another Contract Catalog"))
                else:
                    verify_project_lock(manifest, registry)
                    if not checks:
                        status = VALID
            except DomainPackLockError as exc:
                status = STALE_DOMAIN_PACK_LOCK
                checks.append(_check("STALE_DOMAIN_PACK_LOCK", "project.lock.json", str(exc)))
            except DomainPackRegistryError as exc:
                status = MISSING_DOMAIN_PACK
                checks.append(_check("MISSING_DOMAIN_PACK", "project.yaml", str(exc)))
            except ContractCatalogError as exc:
                status = CONTRACT_CATALOG_MISMATCH
                checks.append(_check("CONTRACT_CATALOG_MISMATCH", "project.lock.json", str(exc)))
            except (ProjectLockError, ValidationError, DocumentError) as exc:
                status = STALE_PROJECT_LOCK
                checks.append(_check("STALE_PROJECT_LOCK", "project.lock.json", str(exc)))
            except ContractError as exc:
                status = INVALID
                checks.append(_check("DOMAIN_PACK_INVALID", "project.yaml", str(exc)))
        except (WorkspaceError, ValidationError, DocumentError, OSError) as exc:
            checks.append(_check("PROJECT_MANIFEST_INVALID", "project.yaml", str(exc)))
    report = validation_report(
        validator="kg-mnp-workspace",
        subject=root.name or "workspace",
        contract_name="project-manifest",
        checks=checks,
    )
    return WorkspaceValidationResult(report=report, status=status)
