"""Product resource CLI: one authenticated application boundary, no role flags."""
from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from pathlib import Path

from kg_mnp.contracts.cli import emit_json
from kg_mnp.contracts.document_io import read_document
from kg_mnp.contracts.errors import ContractError
from kg_mnp.sdk.errors import SDKError
from kg_mnp.sdk.http import HTTPClient

from .authorization_policy import reject_client_identity_claims
from .errors import ServiceBoundaryError
from .models import OperationRequest
from .requests import validate_parameters

ROUTES = {
    "project": {"list":"project.list", "create":"project.create", "open":"project.open", "validate":"project.validate"},
    "model": {"scope":"modeling.scope", "approve-scope":"modeling.scope.approve", "prepare":"modeling.prepare", "propose":"modeling.proposal"},
    "review": {"decide":"review.action", "status":"review.replay", "replay":"review.replay", "finalize":"review.finalize"},
    "registry": {"import":"registry.import", "verify":"registry.verify"},
    "change": {"diff":"change.diff", "impact":"change.impact", "regression":"change.regression", "evaluate":"change.evaluate"},
    "release": {"candidate":"release.candidate", "review":"release.review", "publish":"release.publish", "inspect":"release.inspect"},
    "environment": {"create":"environment.create", "propose":"environment.propose", "review":"environment.review", "inspect":"environment.inspect", "activate":"environment.activate", "rollback":"environment.rollback"},
    "consumer": {"register":"consumer.register"},
    "feedback": {"add":"feedback.add"},
}


def main(namespace: str, argv: list[str] | None = None) -> int:
    arguments = list(argv or [])
    parser = argparse.ArgumentParser(prog=f"kg-mnp {namespace}", description="Authenticated application resources; credential is read from KG_MNP_TOKEN")
    if namespace == "lifecycle":
        parser.add_argument("resource", choices=["registry","change","release","environment","consumer","feedback"])
        parser.add_argument("action")
    else:
        parser.add_argument("action", choices=sorted(ROUTES[namespace]))
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--project-id")
    parser.add_argument("--request", type=Path, help="local JSON request file matching the resource DTO")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--json", action="store_true")
    parsed, unknown = parser.parse_known_args(arguments)
    if unknown:
        emit_json({"status":"ERROR","code":"CLI_OPTION_FORBIDDEN","message":"unsupported options; request identity and policy cannot be overridden"})
        return 42
    group = parsed.resource if namespace == "lifecycle" else namespace
    operation = ROUTES[group].get(parsed.action)
    if operation is None:
        emit_json({"status":"ERROR","code":"CLI_OPERATION_UNKNOWN"})
        return 2
    try:
        parameters = read_document(parsed.request) if parsed.request else {}
        if not isinstance(parameters, dict):
            raise TypeError("resource request must be an object")
        reject_client_identity_claims(parameters)
        request = OperationRequest(operation,parsed.project_id,parameters,parsed.idempotency_key)
        validate_parameters(request)
        client = HTTPClient(parsed.url,os.environ.get("KG_MNP_TOKEN",""),timeout=180)
        try:
            result = client.execute(request)
            emit_json(asdict(result))
        finally:
            client.close()
        return 0
    except (SDKError, ServiceBoundaryError) as exc:
        emit_json({"status":"ERROR","code":exc.code,"message":str(exc)})
        return 2
    except (OSError, ValueError, TypeError, ContractError) as exc:
        emit_json({"status":"ERROR","code":"CLI_REQUEST_INVALID","message":type(exc).__name__})
        return 2
