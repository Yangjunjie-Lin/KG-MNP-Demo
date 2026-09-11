from __future__ import annotations

from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import (
    OperationRequest,
    OperationResult,
    PrincipalReference,
)


class LocalClient:
    """Trusted local caller; still goes through the same service catalog."""

    def __init__(self, service: ApplicationService, principal: PrincipalReference):
        self.service = service
        self.principal = principal

    def execute(self, request: OperationRequest) -> OperationResult:
        return self.service.execute(request, self.principal)

    def recover_job(self, job_id: str, *, mode: str, expected_attempt: int) -> dict:
        return self.service.request_job_recovery(job_id,self.principal,mode=mode,expected_attempt=expected_attempt)

    async def upload_source(self, project_id: str, chunks, *, filename: str, media_type: str,
                            idempotency_key: str) -> dict:
        from zhigou_toolchain.services.uploads import receive_upload
        result = await receive_upload(self.service, project_id, self.principal, chunks, filename=filename,
                                      media_type=media_type, idempotency_key=idempotency_key)
        return result.payload
