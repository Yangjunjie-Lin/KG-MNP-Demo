from __future__ import annotations

import json

from kg_mnp.api.openapi import export_openapi
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.service_runtime.configuration import load_configuration

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
        print("usage: kg-mnp service {doctor|openapi|token|serve|worker} [options]")
        return 0
    config = load_configuration(_arg(args, "--workspace", ".") or ".")
    service = ApplicationService(config)
    if action == "doctor":
        print(json.dumps(service.runtime_check(), sort_keys=True))
        return 0
    if action == "openapi":
        destination = export_openapi(service, _arg(args, "--output", "openapi.json") or "openapi.json")
        print(json.dumps({"status": "EXPORTED", "path": str(destination)}, sort_keys=True))
        return 0
    if action == "token":
        subaction = args[1] if len(args) > 1 else "create"
        if subaction == "create":
            principal_id = _arg(args, "--principal-id")
            created_by = _arg(args, "--created-by")
            if not principal_id or not created_by:
                print(json.dumps({"status": "FAIL", "message": "--principal-id and --created-by are required"}))
                return 2
            token, principal = service.tokens.create(principal_id=principal_id, principal_type=_arg(args, "--principal-type", "HUMAN") or "HUMAN", permissions=set((_arg(args, "--permissions", "project:read") or "").split(",")), project_ids=set(filter(None, (_arg(args, "--project-ids", "") or "").split(","))), created_by=created_by)
            print(json.dumps({"token": token, "principal": principal.to_dict()}, sort_keys=True))
            return 0
        if subaction == "revoke":
            token_id = _arg(args, "--token-id")
            if not token_id:
                return 2
            service.tokens.revoke(token_id)
            return 0
    if action == "serve":
        import uvicorn

        from kg_mnp.api.app import create_app
        uvicorn.run(create_app(service), host=config.host, port=config.port)
        return 0
    if action == "worker":
        worker = JobWorker(service.jobs, service)
        result = worker.run_once(_arg(args, "--worker-id", "worker") or "worker")
        print(json.dumps({"status": "IDLE" if result is None else result.status}, sort_keys=True))
        return 0
    print(json.dumps({"status": "FAIL", "message": "unknown service command"}))
    return 2
