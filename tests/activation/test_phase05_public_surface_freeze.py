from __future__ import annotations

import inspect
from pathlib import Path

from kg_mnp import amendment
from kg_mnp.amendment.republication import complete_reentry, prepare_reentry

ROOT = Path(__file__).resolve().parents[2]


def test_generic_reentry_primitives_remain_internal() -> None:
    assert "prepare_reentry" not in amendment.__all__
    assert "complete_reentry" not in amendment.__all__
    assert not hasattr(amendment, "prepare_reentry")
    assert not hasattr(amendment, "complete_reentry")


def test_generic_reentry_signatures_are_frozen() -> None:
    prepare = inspect.signature(prepare_reentry).parameters
    assert tuple(prepare) == (
        "amendment_request",
        "intake_manifest",
        "base_cleaned_data",
        "revised_cleaned_data",
        "base_publication_id",
        "base_publication_semantic_hash",
        "dependencies",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in prepare.values()
    )
    complete = inspect.signature(complete_reentry).parameters
    assert tuple(complete) == (
        "prepared",
        "decision_log",
        "dependencies",
        "revised_cleaned_data",
        "publication_builder",
        "diagnostic_runner",
        "base_publication_bytes",
        "base_publication_bytes_after",
        "base_repository_hash_before",
        "base_repository_hash_after",
    )


def test_phase05_implementation_has_no_phase06_hook() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src/kg_mnp/amendment").glob("*.py"))
    ).casefold()
    assert "kg_mnp.activation" not in sources
