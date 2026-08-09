from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.query_registry import QueryRegistry


def test_registry_is_closed_versioned_and_covers_all_categories():
    registry = QueryRegistry.load()
    definitions = registry.list()
    assert len(definitions) == 12
    assert {item.category.value for item in definitions} == {
        "FOUNDATION_METADATA", "ONTOLOGY", "BUSINESS_FACT", "PROVENANCE",
        "REVIEW_TRACE", "SOURCE_TRACE", "EVIDENCE_TRACE", "CROSS_TRACE",
    }
    assert all(item.allowed_named_graphs for item in definitions)
    assert all(item.maximum_result_count <= 1000 for item in definitions)
    assert all(item.timeout_seconds <= 10 for item in definitions)


def test_unknown_query_id_fails_closed():
    with pytest.raises(ApplicationError) as caught:
        QueryRegistry.load().get("arbitrary.sparql")
    assert caught.value.code == ErrorCode.INVALID_QUERY_ID


def test_registry_collision_and_template_tamper_fail_closed(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    raw = yaml.safe_load((root / "config/application/query-registry-1.0.0.yaml").read_text(encoding="utf-8"))
    raw["queries"].append(dict(raw["queries"][0], query_id=raw["queries"][0]["query_id"].upper()))
    config = tmp_path / "registry.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(ApplicationError):
        QueryRegistry.load(config, root=root)

    query = root / raw["queries"][0]["template"]
    original = query.read_text(encoding="utf-8")
    raw = yaml.safe_load((root / "config/application/query-registry-1.0.0.yaml").read_text(encoding="utf-8"))
    raw["queries"][0]["template_sha256"] = "0" * 64
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    assert original
    with pytest.raises(ApplicationError):
        QueryRegistry.load(config, root=root)
