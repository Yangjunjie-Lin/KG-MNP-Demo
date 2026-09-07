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
