from __future__ import annotations

from fastapi import Header, Request

from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import PrincipalReference


def service_from_request(request: Request) -> ApplicationService:
    return request.app.state.service


def principal_from_request(request: Request, authorization: str | None = Header(default=None)) -> PrincipalReference:
    if not authorization:
        raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
    return service_from_request(request).authenticate(authorization)
