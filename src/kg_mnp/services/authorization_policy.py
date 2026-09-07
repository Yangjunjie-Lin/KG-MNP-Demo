from __future__ import annotations

from .errors import ServiceBoundaryError
from .models import OperationDefinition, OperationRequest, PrincipalReference

_CLIENT_IDENTITY_FIELDS = {"__principal", "reviewer_id", "reviewer_roles", "reviewer_role", "role", "is_admin", "explicit_human_action", "approved", "quorum_satisfied", "system_actor"}


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
    if operation.project_scope_required and not request.project_id:
        raise ServiceBoundaryError("PROJECT_REQUIRED", "project scope is required", status_code=422)
    # Object membership/ownership is resolved by ApplicationService after
    # this permission check. An empty set is never a global grant.
    if principal.principal_type == "SERVICE" and any(permission in {"scope:approve", "review:decide", "release:review", "environment:review", "integration:review"} for permission in operation.required_permissions):
        raise ServiceBoundaryError("HUMAN_APPROVAL_REQUIRED", "service accounts cannot perform human approvals", status_code=403)
