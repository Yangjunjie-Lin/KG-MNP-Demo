"""Prompt 4 fail-closed error hierarchy."""


class ModelingControlError(ValueError):
    """Base error for a rejected modeling control-plane operation."""


class ScopeInvalidError(ModelingControlError):
    """An ontology scope is invalid or stale."""


class ScopeNotApprovedError(ModelingControlError):
    """A provider operation was attempted without a current approval."""


class ModelingProviderError(ModelingControlError):
    """A provider or recorded response crossed its proposal boundary."""


class ModelingProposalError(ModelingControlError):
    """A candidate set or proposal is invalid."""


class PrevalidationError(ModelingControlError):
    """Formal structural prevalidation failed."""


class ReviewIncompleteError(ModelingControlError):
    """Review cannot be finalized."""


class ReviewPolicyError(ModelingControlError):
    """A review action or quorum violates policy."""


class ConfirmedPackageError(ModelingControlError):
    """A confirmed modeling package is invalid or tampered."""


class StaleModelingArtifactError(ModelingControlError):
    """An artifact is correctly formed but bound to stale authorities."""


class ModelingConflictError(ModelingControlError):
    """An unresolved blocking conflict prevents finalization."""
