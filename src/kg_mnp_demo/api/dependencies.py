"""API dependency wiring — app-instance state only (no global singleton)."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.ontology_service import OntologyService
from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database


@dataclass
class AppState:
    assessment_service: AssessmentService = field(default_factory=AssessmentService)
    ontology_service: OntologyService = field(default_factory=OntologyService)
    query_service: QueryService = field(default_factory=QueryService)
    db: Database = field(default_factory=Database)
    repository: AssessmentRepository | None = None
    artifacts: ArtifactRepository = field(default_factory=ArtifactRepository)

    def __post_init__(self) -> None:
        if self.repository is None:
            self.repository = AssessmentRepository(self.db)


def get_state(request: Request) -> AppState:
    """Resolve AppState bound to this FastAPI application instance."""
    state = getattr(request.app.state, "kg_mnp", None)
    if state is None:
        raise RuntimeError("Application state not initialized (kg_mnp missing on app.state)")
    return state
