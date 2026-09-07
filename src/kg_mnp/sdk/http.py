from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from kg_mnp.services.models import OperationRequest, OperationResult

from .errors import SDKError


class HTTPClient:
    def __init__(self, base_url: str, bearer_token: str, *, timeout: float = 30.0, client: httpx.Client | None = None):
        if not bearer_token.startswith("kgmnp_"):
            raise ValueError("HTTP SDK requires a server-issued bearer credential")
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def execute(self, request: OperationRequest) -> OperationResult:
        response = self._client.post(f"/api/v1/operations/{request.operation_id}", headers={"Authorization": f"Bearer {self.bearer_token}", "Idempotency-Key": request.idempotency_key or "", "X-Request-ID": request.request_id}, json={"project_id": request.project_id, **request.parameters})
        if response.status_code >= 400:
            try:
                payload = response.json().get("error", {})
            except ValueError:
                payload = {}
            raise SDKError(payload.get("code", "HTTP_ERROR"), payload.get("message", response.text), response.status_code)
        payload: dict[str, Any] = response.json()
        return OperationResult(payload["operation_id"], payload["status"], payload["payload"], payload["request_id"], payload.get("job_id"), payload.get("audit_id"))

    def close(self) -> None:
        self._client.close()

    def upload_source(self, project_id: str, content, *, filename: str, media_type: str,
                      idempotency_key: str) -> dict:
        response = self._client.post(f"/api/v1/projects/{project_id}/sources", content=content,
                                     headers={"Authorization": f"Bearer {self.bearer_token}",
                                              "X-Filename": quote(filename, safe=""), "Content-Type": media_type,
                                              "Idempotency-Key": idempotency_key})
        if response.status_code >= 400:
            error = response.json().get("error", {})
            raise SDKError(error.get("code", "HTTP_ERROR"), error.get("message", "upload failed"), response.status_code)
        return response.json()
