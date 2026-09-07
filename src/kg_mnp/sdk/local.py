from __future__ import annotations

from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, OperationResult, PrincipalReference


class LocalClient:
    """Trusted local caller; still goes through the same service catalog."""

    def __init__(self, service: ApplicationService, principal: PrincipalReference):
        self.service = service
        self.principal = principal

    def execute(self, request: OperationRequest) -> OperationResult:
        return self.service.execute(request, self.principal)

    async def upload_source(self, project_id: str, chunks, *, filename: str, media_type: str,
                            idempotency_key: str) -> dict:
        from kg_mnp.services.uploads import receive_upload
        result = await receive_upload(self.service, project_id, self.principal, chunks, filename=filename,
                                      media_type=media_type, idempotency_key=idempotency_key)
        return result.payload
