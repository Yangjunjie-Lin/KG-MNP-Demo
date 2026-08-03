"""API dependency wiring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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


_STATE: AppState | None = None


def set_state(state: AppState) -> None:
    global _STATE
    _STATE = state


def get_state() -> AppState:
    global _STATE
    if _STATE is None:
        _STATE = AppState()
    return _STATE
