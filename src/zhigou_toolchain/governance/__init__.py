"""Human-governed, non-authoritative diagnostic amendment requests."""

from .authority_binding import GovernanceAuthority, load_production_phase03_authority
from .errors import GovernanceError, GovernanceErrorCode
from .validator import validate_governance_workspace_against_authorities
from .workspace import GovernanceWorkspace

__all__ = [
    "GovernanceAuthority",
    "GovernanceError",
    "GovernanceErrorCode",
    "GovernanceWorkspace",
    "load_production_phase03_authority",
    "validate_governance_workspace_against_authorities",
]
