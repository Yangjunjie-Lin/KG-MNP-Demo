"""Finite semantic compilation limits."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SemanticLimits:
    max_confirmed_items: int = 100_000
    max_tbox_statements: int = 500_000
    max_abox_statements: int = 1_000_000
    max_shacl_statements: int = 500_000
    max_mapping_rules: int = 100_000
    max_provenance_statements: int = 5_000_000
    max_dataset_quads: int = 10_000_000
    max_rdf_bytes_per_file: int = 268_435_456
    max_package_files: int = 10_000
    max_package_uncompressed_bytes: int = 1_073_741_824
    max_archive_compression_ratio: int = 100
    max_reasoner_input_triples: int = 2_000_000
    max_reasoner_seconds: int = 180
    max_reasoner_output_bytes: int = 16_777_216
    max_shacl_results: int = 100_000
    max_shacl_seconds: int = 120
    max_cq_count: int = 10_000
    max_query_characters: int = 100_000
    max_query_results: int = 100_000
    max_query_seconds: int = 30
    max_query_path_depth: int = 8

    def __post_init__(self) -> None:
        if any(not isinstance(value, int) or value <= 0 for value in asdict(self).values()):
            raise ValueError("semantic compiler resource limits must be finite positive integers")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)
