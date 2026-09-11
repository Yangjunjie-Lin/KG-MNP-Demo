from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from zhigou_toolchain.api.openapi import export_openapi
from zhigou_toolchain.contracts.cli import emit_json
from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.environment import get_setting
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.service_runtime.configuration import load_configuration

from .facade import ApplicationService


def _arg(args: list[str], name: str, default: str | None = None) -> str | None:
    if name not in args:
        return default
    index = args.index(name)
    return args[index + 1] if index + 1 < len(args) else default


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    action = args[0] if args else "doctor"
    if action in {"--help", "-h", "help"}:
        print("usage: zhigou-toolchain service {doctor|openapi|token|serve|worker|call|upload|recover} [options]")
        return 0
    if action in {"call", "upload", "recover"}:
        from zhigou_toolchain.sdk.http import HTTPClient
        from zhigou_toolchain.services.models import OperationRequest
        token = get_setting("TOKEN", "")
        client = HTTPClient(_arg(args, "--url", "http://127.0.0.1:8765") or "", token, timeout=120)
        try:
            project_id = _arg(args, "--project-id")
            key = _arg(args, "--idempotency-key")
            if action == "recover":
                job_id, attempt = _arg(args,"--job-id"), _arg(args,"--expected-attempt")
                if not job_id or not attempt:
                    raise ValueError("recovery requires --job-id and --expected-attempt")
                result=client.recover_job(job_id,mode="RETRY_LOCAL" if "--retry-local" in args else "RECOVER_COMMITTED",expected_attempt=int(attempt))
            elif action == "upload":
                source_name = _arg(args, "--file")
                if not project_id or not key or not source_name:
                    raise ValueError("upload requires --project-id, --file and --idempotency-key")
                source = Path(source_name)
                with source.open("rb") as stream:
                    result = client.upload_source(project_id, iter(lambda: stream.read(64 * 1024), b""),
                        filename=source.name, media_type=_arg(args, "--media-type", "application/octet-stream") or "application/octet-stream", idempotency_key=key)
            else:
                operation = _arg(args, "--operation")
                if not operation:
                    raise ValueError("call requires --operation")
                request_file = _arg(args, "--request")
                parameters = read_document(Path(request_file)) if request_file else {}
                result = asdict(client.execute(OperationRequest(operation, project_id, parameters, key)))
            emit_json(result)
            return 0
        finally:
            client.close()
    config = load_configuration(_arg(args, "--workspace", ".") or ".")
    service = ApplicationService(config)
    if action == "doctor":
        emit_json(service.runtime_check())
        return 0
    if action == "openapi":
        destination = export_openapi(service, _arg(args, "--output", "openapi.json") or "openapi.json")
        emit_json({"status": "EXPORTED", "path": str(destination)})
        return 0
    if action == "token":
        subaction = args[1] if len(args) > 1 else "create"
        if subaction == "create":
            principal_id = _arg(args, "--principal-id")
            created_by = _arg(args, "--created-by")
            if not principal_id or not created_by:
                emit_json({"status": "FAIL", "message": "--principal-id and --created-by are required"})
                return 2
            token, principal = service.tokens.create(principal_id=principal_id, principal_type=_arg(args, "--principal-type", "HUMAN") or "HUMAN", permissions=set((_arg(args, "--permissions", "project:read") or "").split(",")), project_ids=set(filter(None, (_arg(args, "--project-ids", "") or "").split(","))), created_by=created_by)
            emit_json({"token": token, "principal": principal.to_dict()})
            return 0
        if subaction == "revoke":
            token_id = _arg(args, "--token-id")
            if not token_id:
                return 2
            service.tokens.revoke(token_id)
            return 0
    if action == "serve":
        import uvicorn

        from zhigou_toolchain.api.app import create_app
        uvicorn.run(create_app(service), host=config.host, port=config.port)
        return 0
    if action == "worker":
        worker = JobWorker(service.jobs, service)
        if "--once" not in args:
            try:
                worker.run_forever(_arg(args, "--worker-id", "worker") or "worker")
            except KeyboardInterrupt:
                pass
            return 0
        result = worker.run_once(_arg(args, "--worker-id", "worker") or "worker")
        emit_json({"status": "IDLE" if result is None else result.status})
        return 0
    emit_json({"status": "FAIL", "message": "unknown service command"})
    return 2
