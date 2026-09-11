"""Bounded project-owned streaming uploads, independent of HTTP transport."""
from __future__ import annotations

import hashlib
import os
import tempfile

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import atomic_write_json

from .authorization_policy import authorize
from .coordination import metadata_lock
from .errors import ServiceBoundaryError
from .models import OperationRequest
from .projects import require_access
from .sources import upload_root


async def receive_upload(service, project_id, principal, chunks, *, filename, media_type, idempotency_key):
    principal = service._current(principal)
    request = OperationRequest("source.register", project_id, {}, idempotency_key)
    authorize(principal, service.catalog["source.register"], request)
    project = service._project(request)
    require_access(principal, project)
    if not idempotency_key or len(idempotency_key) > 200:
        raise ServiceBoundaryError("IDEMPOTENCY_REQUIRED", "bounded Idempotency-Key required", status_code=428)
    if (not filename or len(filename) > 200 or any(ord(char) < 32 for char in filename)
            or any(char in filename for char in "\\/:")):
        raise ServiceBoundaryError("FILENAME_INVALID", "filename is display text, not a path", status_code=422)
    if len(media_type) > 200:
        raise ServiceBoundaryError("MEDIA_TYPE_INVALID", "media type is too long", status_code=422)
    root = upload_root(service, project_id)
    if root.is_symlink() or root.resolve() != root.absolute():
        raise ServiceBoundaryError("UPLOAD_ROOT_INVALID", "upload root is unsafe", status_code=409)
    root.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="incoming-", suffix=".part", dir=root)
    from pathlib import Path
    temporary = Path(temporary_name)
    digest, size = hashlib.sha256(), 0
    try:
        with os.fdopen(descriptor, "wb") as stream:
            async for chunk in chunks:
                size += len(chunk)
                if size > service.configuration.max_upload_bytes:
                    raise ServiceBoundaryError("UPLOAD_TOO_LARGE", "upload byte limit exceeded", status_code=413)
                digest.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if not size:
            raise ServiceBoundaryError("UPLOAD_EMPTY", "upload is empty", status_code=422)
        record = {"project_id": project_id, "principal_id": principal.principal_id, "filename": filename,
                  "media_type": media_type, "sha256": digest.hexdigest(), "size_bytes": size}
        upload_id = semantic_hash(record)
        # Revalidate after receiving bytes; HTTP disconnect never cancels a
        # previously accepted durable job. Incomplete .part files are removed.
        principal = service._current(principal)
        require_access(principal, service._project(request))
        authorize(principal, service.catalog["source.register"], request)
        with metadata_lock(root / "uploads-lock.sqlite3"):
            blob, metadata = root / (upload_id + ".blob"), root / (upload_id + ".json")
            created = not blob.exists()
            if created:
                temporary.replace(blob)
                atomic_write_json(metadata, record)
            try:
                result = service.execute(OperationRequest("source.register", project_id, {"upload_id": upload_id}, idempotency_key), principal)
            except BaseException:
                if created:
                    blob.unlink(missing_ok=True)
                    metadata.unlink(missing_ok=True)
                raise
        return result
    finally:
        temporary.unlink(missing_ok=True)
