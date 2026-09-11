"""Bounded resource limits that participate in Modeling Run identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelingLimits:
    max_kgir_datasets: int = 32
    max_kgir_items: int = 100_000
    max_terms: int = 100_000
    max_alignment_candidates_per_term: int = 64
    max_total_candidates: int = 100_000
    max_candidate_dependencies: int = 128
    max_conflicts: int = 100_000
    max_definition_characters: int = 16_384
    max_rationale_characters: int = 16_384
    max_model_response_bytes: int = 4 * 1024 * 1024
    max_model_json_depth: int = 64
    max_review_actions: int = 100_000
    max_baseline_triples: int = 1_000_000
    max_baseline_import_depth: int = 16

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"modeling limit {name} must be a positive finite integer")
            if value > 1_000_000_000:
                raise ValueError(f"modeling limit {name} exceeds the hard maximum")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)
