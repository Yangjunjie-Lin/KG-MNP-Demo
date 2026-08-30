from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp.ingestion.contracts import finalize_document
from kg_mnp.ingestion.errors import IngestionError
from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.kgir import (
    PROHIBITED_ITEM_KINDS,
    build_dataset,
    validate_dataset_closure,
)
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore


def _json_dataset(workspace: Path, tmp_path: Path):
    source_path = tmp_path / "sample.json"
    source_path.write_bytes(b'{"name":"alpha","value":1.2300}')
    store = SourceStore(workspace)
    source = store.add_file(source_path).source
    batch = store.create_batch([source["source_id"]])
    plan = create_ingestion_plan(workspace, batch_id=batch["batch_id"])
    return execute_ingestion_plan(workspace, plan.plan["plan_id"])


def test_dataset_is_intermediate_evidence_bound_and_not_ontology(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    result = _json_dataset(prompt03_workspace, tmp_path)
    dataset = result.dataset
    validate_dataset_closure(dataset)
    assert {item["item_kind"] for item in dataset["items"]} == {"document", "scalar-field"}
    assert all(item["evidence_refs"] for item in dataset["items"])
    assert not ({item["item_kind"] for item in dataset["items"]} & PROHIBITED_ITEM_KINDS)
    serialized = json.dumps(dataset, sort_keys=True).casefold()
    for forbidden in ("ontology-class", "ontology-property", "business-object", "confirmed-fact"):
        assert forbidden not in serialized
    assert result.run["quality_report_id"] == dataset["quality_report_id"]


def test_item_and_dataset_ids_are_deterministic_and_tamper_evident(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    result = _json_dataset(prompt03_workspace, tmp_path)
    first = copy.deepcopy(result.dataset)
    validate_dataset_closure(first)
    tampered = copy.deepcopy(first)
    tampered["items"][0]["ordinal"] += 1
    with pytest.raises(ValueError, match="mismatch"):
        validate_dataset_closure(tampered)


def test_no_evidence_free_or_prohibited_item_can_be_finalized() -> None:
    base = {
        "manifest_kind": "KG_MNP_KG_IR_ITEM",
        "schema_version": "1.0.0",
        "item_kind": "document",
        "source_ids": ["urn:kg-mnp:source:" + "1" * 64],
        "parent_item_id": None,
        "ordinal": 0,
        "payload": {"media_type": "text/plain", "title": None},
        "evidence_refs": [],
        "transformation_refs": [],
        "quality_flags": [],
    }
    with pytest.raises(ValidationError):
        finalize_document(base, contract="kg-ir-item", id_field="item_id", urn_kind="kg-ir-item")
    base["evidence_refs"] = ["urn:kg-mnp:evidence:" + "2" * 64]
    base["item_kind"] = "ontology-class"
    with pytest.raises(ValidationError):
        finalize_document(base, contract="kg-ir-item", id_field="item_id", urn_kind="kg-ir-item")


def test_parent_and_evidence_closure_fail_closed(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    result = _json_dataset(prompt03_workspace, tmp_path)
    dataset = result.dataset
    child = next(item for item in dataset["items"] if item["parent_item_id"] is not None)
    invalid_child = finalize_document(
        {
            **{key: value for key, value in child.items() if key not in {"item_id", "content_digest"}},
            "parent_item_id": "urn:kg-mnp:kg-ir-item:" + "f" * 64,
        },
        contract="kg-ir-item",
        id_field="item_id",
        urn_kind="kg-ir-item",
    )
    items = tuple(invalid_child if item["item_id"] == child["item_id"] else item for item in dataset["items"])
    with pytest.raises(IngestionError, match="parent closure"):
        build_dataset(
            project_lock_id=dataset["project_lock_id"],
            source_batch_id=dataset["source_batch_id"],
            ingestion_plan_id=dataset["ingestion_plan_id"],
            items=items,
            evidence_records=tuple(dataset["evidence_records"]),
            transformation_records=tuple(dataset["transformation_records"]),
            plugin_snapshots=tuple(dataset["plugin_snapshots"]),
            artifact_manifest=dataset["artifact_manifest"],
            quality_report_id=dataset["quality_report_id"],
        )
    missing_evidence = copy.deepcopy(dataset)
    missing_evidence["evidence_records"] = []
    with pytest.raises(ValidationError, match="non-empty"):
        finalize_document(
            {
                key: value
                for key, value in missing_evidence.items()
                if key not in {"dataset_id", "content_digest"}
            },
            contract="kg-ir-dataset",
            id_field="dataset_id",
            urn_kind="kg-ir-dataset",
        )
