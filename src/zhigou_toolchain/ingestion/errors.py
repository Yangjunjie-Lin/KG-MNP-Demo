"""Ingestion and source-store errors with stable public categories."""


class IngestionError(RuntimeError):
    """Base ingestion error."""


class SourceError(IngestionError):
    """Source registration, integrity or locator error."""


class SourceTamperedError(SourceError):
    """Stored source content no longer matches its record."""


class IngestionPlanError(IngestionError):
    """An ingestion plan is invalid or unresolved."""


class QualityGateError(IngestionError):
    """The structural quality gate does not permit commit."""


class ArtifactTamperedError(IngestionError):
    """An existing artifact differs from deterministic expected content."""


class WorkspaceOperationLockedError(IngestionError):
    """Another writer holds the conservative workspace operation lock."""
