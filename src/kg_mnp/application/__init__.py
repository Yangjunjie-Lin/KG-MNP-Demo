"""Public surface for the Application Phase 01 read-only projection layer.

Legacy eligibility examples remain importable from their explicit modules, but are
intentionally not exported as part of this application-layer authority surface.
"""

from kg_mnp.application.errors import ApplicationError, ErrorCode
from kg_mnp.application.publication_binding import PublicationBinding
from kg_mnp.application.query_registry import QueryRegistry
from kg_mnp.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp.application.service import ApplicationService

__all__ = [
    "ApplicationError",
    "ApplicationService",
    "ErrorCode",
    "PublicationBinding",
    "QueryRegistry",
    "ReadOnlyGraphDBClient",
]
