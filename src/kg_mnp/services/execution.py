"""Publish isolated core workspaces through the existing project authority.

Core libraries execute unchanged in a private full workspace copy. A single
atomic catalog replacement publishes the new handle AND commit receipt. The
existing JobStore writer transaction, credential metadata lock and project
metadata lock serialize that replacement with lease claims/revocation/CAS.
This is intentionally local, copy-on-write and not an external exactly-once
executor. Old generations are runtime recovery material, never source assets.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash

from .authorization_policy import authorize
from .coordination import metadata_lock
from .errors import ServiceBoundaryError
from .projects import (
    _safe_handle,
    get_project,
    inspect_project,
    load_catalog,
    require_access,
    save_catalog,
)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ServiceBoundaryError("WORKSPACE_LINK_REJECTED", "workspace contains a filesystem link", status_code=409)
        if relative.parts[0] == "tmp":
            continue
        if path.is_file():
            digest.update(relative.as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


@dataclass(frozen=True)
class ExecutionContext:
    project_id: str
    operation_id: str
    job_id: str
    attempt: int
    principal_id: str
    grant_reference: str
    request_digest: str
    input_tree_digest: str
    fencing_token: int
    expected_authority_revision: int


def committed_result(service, job):
    receipt = load_catalog(service.root).get("commits", {}).get(job.job_id)
    if receipt is None:
        return None
    identity = service.jobs.parameters(job.job_id).get("__principal", {})
    context = receipt["context"]
    if (context["project_id"] != job.project_id or context["operation_id"] != job.operation_id
            or context["request_digest"] != job.request_digest
            or context["principal_id"] != identity.get("principal_id")
            or receipt["receipt_digest"] != semantic_hash({k: v for k, v in receipt.items() if k != "receipt_digest"})):
        raise ServiceBoundaryError("COMMIT_RECEIPT_INVALID", "core commit receipt does not match job", status_code=409)
    # Verify bytes, not a cached validation verdict, including after restart.
    current = get_project(service.root, job.project_id)
    generation = Path(receipt["root"])
    if (not generation.resolve().is_relative_to((service.root / "projects").resolve())
            or tree_digest(generation) != receipt["output_tree_digest"]
            or current.authority_revision < receipt["authority_revision"]):
        raise ServiceBoundaryError("COMMIT_RECEIPT_INVALID", "committed workspace is not intact", status_code=409)
    return receipt["result"]


def execute_fenced(service, job, request, principal, action):
    replay = committed_result(service, job)
    if replay is not None:
        return replay
    project = get_project(service.root, job.project_id)
    require_access(principal, project)
    if inspect_project(project, service.configuration.domain_packs_root).status != "VALID":
        raise ServiceBoundaryError("WORKSPACE_INVALID", "workspace validation failed", status_code=409)
    original = Path(project.root)
    input_digest = tree_digest(original)
    context = ExecutionContext(project.project_id, request.operation_id, job.job_id, job.attempt,
                               principal.principal_id, principal.token_id, job.request_digest,
                               input_digest, job.fencing_token, project.authority_revision)
    generations = service.root / "projects" / "generations" / project.project_id.rsplit(":", 1)[-1]
    _safe_handle(service.root, {**asdict(project), "root": str(generations)})
    generations.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{job.job_id}-{job.attempt}-", dir=generations))
    published = False
    try:
        shutil.copytree(original, staging, dirs_exist_ok=True,
                        ignore=lambda parent, names: ["tmp"] if Path(parent) == original and "tmp" in names else [])
        (staging / "tmp").mkdir(exist_ok=True)
        if tree_digest(staging) != input_digest:
            raise ServiceBoundaryError("AUTHORITY_CONFLICT", "workspace changed while taking snapshot", status_code=409)
        staged_project = replace(project, root=str(staging), authority_revision=project.authority_revision + 1)
        result = action(staged_project)
        output_digest = tree_digest(staging)
        if inspect_project(staged_project, service.configuration.domain_packs_root).status != "VALID":
            raise ServiceBoundaryError("WORKSPACE_INVALID", "computed workspace validation failed", status_code=409)
        # One lock ordering throughout: credential -> job -> project. No lease
        # or permission is cached from before computation.
        with metadata_lock(service.tokens.path.with_suffix(".lock.sqlite3")):  # noqa: SIM117 - explicit global lock order
            with service.jobs.commit_lease(job):
                with metadata_lock(service.root / "service-data" / "projects-lock.sqlite3"):
                    current_principal = service.tokens.resolve(principal.token_id)
                    if current_principal.principal_id != principal.principal_id:
                        raise ServiceBoundaryError("AUTH_INVALID", "credential identity changed before commit", status_code=401)
                    authorize(current_principal, service.catalog[request.operation_id], request)
                    current = get_project(service.root, job.project_id)
                    require_access(current_principal, current)
                    if (current.root != project.root or current.authority_revision != project.authority_revision
                            or tree_digest(Path(current.root)) != input_digest):
                        raise ServiceBoundaryError("AUTHORITY_CONFLICT", "project authority revision changed", status_code=409)
                    catalog = load_catalog(service.root)
                    receipt = {"context": asdict(context), "root": str(staging), "output_tree_digest": output_digest,
                               "authority_revision": staged_project.authority_revision, "result": result}
                    receipt["receipt_digest"] = semantic_hash(receipt)
                    catalog["projects"][project.project_id] = asdict(staged_project)
                    catalog.setdefault("commits", {})[job.job_id] = receipt
                    service.jobs.require_lease(job)
                    service.tokens.resolve(principal.token_id)
                    save_catalog(service.root, catalog)
                    published = True
        return result
    finally:
        # A thrown/lost response after os.replace may still mean committed.
        # Never remove a generation referenced by the authoritative catalog.
        if not published:
            referenced = load_catalog(service.root).get("commits", {}).get(job.job_id, {}).get("root")
            if referenced != str(staging) and staging.resolve().parent == generations.resolve():
                shutil.rmtree(staging)
