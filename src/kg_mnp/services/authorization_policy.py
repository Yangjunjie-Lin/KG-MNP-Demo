from __future__ import annotations

from .errors import ServiceBoundaryError
from .models import OperationDefinition, OperationRequest, PrincipalReference

_CLIENT_IDENTITY_FIELDS = {"reviewer_id", "reviewer_roles", "role", "is_admin", "explicit_human_action", "approved", "quorum_satisfied", "system_actor"}


def reject_client_identity_claims(value: object) -> None:
    if isinstance(value, dict):
        conflict = _CLIENT_IDENTITY_FIELDS.intersection(value)
        if conflict:
            raise ServiceBoundaryError("AUTH_IDENTITY_CLAIM_REJECTED", "review identity is derived from the authenticated principal")
        for child in value.values():
            reject_client_identity_claims(child)
    elif isinstance(value, list):
        for child in value:
            reject_client_identity_claims(child)


def authorize(principal: PrincipalReference, operation: OperationDefinition, request: OperationRequest) -> None:
    reject_client_identity_claims(request.parameters)
    if operation.blocked_reason:
        raise ServiceBoundaryError("OPERATION_BLOCKED", operation.blocked_reason, status_code=501)
    for permission in operation.required_permissions:
        if not principal.can(permission):
            raise ServiceBoundaryError("FORBIDDEN", f"missing permission: {permission}", status_code=403)
    if operation.project_scope_required:
        if not request.project_id:
            raise ServiceBoundaryError("PROJECT_REQUIRED", "project scope is required", status_code=422)
        if principal.project_ids and request.project_id not in principal.project_ids and not principal.can("project:admin"):
            raise ServiceBoundaryError("PROJECT_FORBIDDEN", "principal is not authorized for this project", status_code=403)
    if principal.principal_type == "SERVICE" and any(permission in {"review:decide", "release:review", "environment:review", "integration:review"} for permission in operation.required_permissions):
        raise ServiceBoundaryError("HUMAN_APPROVAL_REQUIRED", "service accounts cannot perform human approvals", status_code=403)
