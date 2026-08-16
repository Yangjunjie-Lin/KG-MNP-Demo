"""Production-only construction for the Phase 06 local control plane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient

from .authority_binding import load_production_phase06_authority
from .execution import ActivationController, ReadOnlyGraphDBTargetVerifier
from .persistence import ActivationStateStore
from .resolver import ActivePublicationResolver


@dataclass(frozen=True, slots=True)
class ActivationRuntimeConfig:
    """Startup configuration; none of these paths enter deterministic identities."""

    publication_package_directory: Path
    publication_attestation_path: Path
    phase01_artifact_directory: Path
    phase02_artifact_directory: Path
    phase03_artifact_directory: Path
    phase04_artifact_directory: Path
    phase05_artifact_directory: Path
    expected_commit_sha: str
    state_directory: Path = Path("runtime_outputs/activation")
    publication_scenario: str = "full-confirmation"
    graphdb_url: str = "http://127.0.0.1:7200"

    def authority_arguments(self) -> dict[str, object]:
        return {
            "publication_package_directory": self.publication_package_directory,
            "publication_attestation_path": self.publication_attestation_path,
            "phase01_artifact_directory": self.phase01_artifact_directory,
            "phase02_artifact_directory": self.phase02_artifact_directory,
            "phase03_artifact_directory": self.phase03_artifact_directory,
            "phase04_artifact_directory": self.phase04_artifact_directory,
            "phase05_artifact_directory": self.phase05_artifact_directory,
            "expected_commit_sha": self.expected_commit_sha,
            "publication_scenario": self.publication_scenario,
        }


def _production_parts(
    config: ActivationRuntimeConfig,
) -> tuple[ActivationStateStore, ReadOnlyGraphDBTargetVerifier]:
    def current_authority():
        return load_production_phase06_authority(**config.authority_arguments())

    # Validate every physical trust root before returning a production boundary.
    current_authority()
    store = ActivationStateStore(config.state_directory, current_authority)
    verifier = ReadOnlyGraphDBTargetVerifier(
        ReadOnlyGraphDBClient(config.graphdb_url),
        publication_scenario=config.publication_scenario,
    )
    return store, verifier


def create_production_activation_controller(
    config: ActivationRuntimeConfig,
) -> ActivationController:
    """Build a controller without accepting an injected authority or target."""

    store, verifier = _production_parts(config)
    return ActivationController(store, verifier)


def create_production_active_resolver(
    config: ActivationRuntimeConfig,
    *,
    trusted_registry_hash: str | None = None,
    trusted_head_event_hash: str | None = None,
) -> ActivePublicationResolver:
    """Build the read-only current-head resolver from exact physical authority."""

    store, verifier = _production_parts(config)
    return ActivePublicationResolver(
        store,
        verifier,
        trusted_registry_hash=trusted_registry_hash,
        trusted_head_event_hash=trusted_head_event_hash,
    )
