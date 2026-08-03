"""Request body size limiting middleware."""

from __future__ import annotations

import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode


def max_request_bytes() -> int:
    raw = os.environ.get("KG_MNP_MAX_REQUEST_BYTES", str(1024 * 1024))
    try:
        return max(1024, int(raw))
    except ValueError:
        return 1024 * 1024


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int | None = None) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes if max_bytes is not None else max_request_bytes()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return self._too_large()
            except ValueError:
                pass

        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > self.max_bytes:
                return self._too_large()

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, receive)

        return await call_next(request)

    def _too_large(self) -> JSONResponse:
        err = ApplicationError(
            ErrorCode.REQUEST_TOO_LARGE,
            details=[f"max_bytes={self.max_bytes}"],
        )
        return JSONResponse(status_code=413, content=err.to_dict())
