from __future__ import annotations

import pytest

from kg_mnp_demo.modeling.transformations import (
    TransformationError,
    transform_value,
)


def test_string_and_code_transforms_are_finite_and_deterministic() -> None:
    assert transform_value("IDENTITY", " value ") == " value "
    assert transform_value("STRING_TRIM", " value ") == "value"
    assert transform_value("STRING_NORMALIZE", "  Full\u3000 Width  ") == "Full Width"
    assert transform_value("CODE_NORMALIZE", " active-status ") == "ACTIVE_STATUS"


def test_strict_scalar_transforms_do_not_invent_defaults() -> None:
    assert transform_value("BOOLEAN_STRICT", "false") is False
    assert transform_value("INTEGER_STRICT", "-12") == -12
    assert transform_value("DECIMAL_STRICT", "12.3400") == "12.34"
    for transform, value in (
        ("BOOLEAN_STRICT", "maybe"),
        ("INTEGER_STRICT", "1.2"),
        ("DECIMAL_STRICT", "unknown"),
    ):
        with pytest.raises(TransformationError):
            transform_value(transform, value)


def test_datetime_to_utc_preserves_available_precision() -> None:
    assert transform_value(
        "DATETIME_TO_UTC", "2026-08-01T08:00:00.123456+08:00"
    ) == "2026-08-01T00:00:00.123456Z"
    with pytest.raises(TransformationError):
        transform_value("DATETIME_TO_UTC", "2026-08-01T00:00:00")


def test_stable_entity_iri_depends_on_class_and_source_identifier() -> None:
    first = transform_value(
        "IRI_FROM_STABLE_ID",
        "ENTITY-1",
        context={"target_term_iri": "https://example.test/ClassA"},
    )
    second = transform_value(
        "IRI_FROM_STABLE_ID",
        "ENTITY-1",
        context={"target_term_iri": "https://example.test/ClassA"},
    )
    changed = transform_value(
        "IRI_FROM_STABLE_ID",
        "ENTITY-1",
        context={"target_term_iri": "https://example.test/ClassB"},
    )
    assert first == second
    assert first != changed
    assert first.startswith(
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/"
    )


def test_unknown_transform_fails_closed() -> None:
    with pytest.raises(TransformationError, match="unknown transformation_id"):
        transform_value("EXECUTE_TEXT", "anything")

