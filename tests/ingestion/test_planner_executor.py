from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from prompt03_support import docx_bytes, pdf_bytes, png_bytes, wav_bytes, xlsx_bytes

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.ingestion.errors import (
    ArtifactTamperedError,
    IngestionError,
    IngestionPlanError,
    QualityGateError,
    WorkspaceOperationLockedError,
)
from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.limits import DEFAULT_LIMITS
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.ingestion.transaction import WorkspaceOperationLock
from kg_mnp.plugins.errors import PluginError
from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]


def _prepare(workspace: Path, source: Path):
    store = SourceStore(workspace)
    registered = store.add_file(source).source
    batch = store.create_batch([registered["source_id"]])
    plan = create_ingestion_plan(workspace, batch_id=batch["batch_id"])
    return store, registered, batch, plan


@pytest.mark.parametrize(
    ("name", "content", "expected_status", "item_kind"),
    [
        ("sample.txt", b"alpha\nbeta\n", "SUCCEEDED", "text-block"),
        ("sample.md", b"# Heading\nparagraph\n", "SUCCEEDED", "text-block"),
        ("sample.json", b'{"value":1.2300}', "SUCCEEDED", "scalar-field"),
        ("sample.csv", b"name,value\nalpha,1\n", "SUCCEEDED", "table-cell"),
        ("sample.xlsx", xlsx_bytes(), "REVIEW_REQUIRED", "table-cell"),
        ("sample.docx", docx_bytes(), "SUCCEEDED", "text-block"),
        ("sample.pdf", pdf_bytes(), "REVIEW_REQUIRED", "text-block"),
        ("sample.png", png_bytes(), "REVIEW_REQUIRED", "image-metadata"),
        ("sample.wav", wav_bytes(), "REVIEW_REQUIRED", "audio-metadata"),
    ],
    ids=["txt", "markdown", "json", "csv", "xlsx", "docx", "pdf", "png", "wav"],
)
def test_supported_format_end_to_end(
    prompt03_workspace: Path,
    tmp_path: Path,
    name: str,
    content: bytes,
    expected_status: str,
    item_kind: str,
) -> None:
    source = tmp_path / name
    source.write_bytes(content)
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    assert planned.plan["status"] == "READY"
    assert planned.plan["planner"]["planner_kind"] == "DETERMINISTIC_CORE"
    assert all(
        step["plugin_snapshot_id"]
        in {snapshot["snapshot_id"] for snapshot in planned.plan["plugin_snapshots"]}
        for step in planned.plan["steps"]
    )
    result = execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    assert result.run["status"] == expected_status
    assert result.quality_report["gate_status"] == (
        "REVIEW_REQUIRED" if expected_status == "REVIEW_REQUIRED" else "PASS"
    )
    assert any(item["item_kind"] == item_kind for item in result.dataset["items"])
    assert all(item["evidence_refs"] for item in result.dataset["items"])
    assert not any((prompt03_workspace / "artifacts" / "confirmed").iterdir())
    assert not any((prompt03_workspace / "artifacts" / "packages").iterdir())


def test_plan_id_binds_finite_limits_and_selection_reason(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("alpha", encoding="utf-8")
    store = SourceStore(prompt03_workspace)
    registered = store.add_file(source).source
    batch = store.create_batch([registered["source_id"]])
    first = create_ingestion_plan(prompt03_workspace, batch_id=batch["batch_id"])
    second = create_ingestion_plan(
        prompt03_workspace,
        batch_id=batch["batch_id"],
        limits=replace(DEFAULT_LIMITS, max_extracted_characters=1024),
    )
    assert first.plan["plan_id"] != second.plan["plan_id"]
    parse_step = next(step for step in first.plan["steps"] if step["operation"] == "parse")
    assert parse_step["configuration"]["selection_reason"]
    assert first.plan["fallback_policy"]["settings"]["max_attempts"] == 1


@pytest.mark.parametrize(
    ("name", "content", "issue"),
    [
        ("clip.mp4", b"\x00\x00\x00\x18ftypmp42\xff", "MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER"),
        ("audio.mp3", b"\xff\xfb\x90\x64\x00", "MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER"),
        ("unknown.bin", b"\x00\xff\x80", "MISSING_PROVIDER"),
    ],
)
def test_unsupported_media_is_unresolved_without_fabricated_output(
    prompt03_workspace: Path, tmp_path: Path, name: str, content: bytes, issue: str
) -> None:
    source = tmp_path / name
    source.write_bytes(content)
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    assert planned.plan["status"] == "UNRESOLVED"
    assert issue in {item["code"] for item in planned.plan["issues"]}
    assert not any(step["operation"] == "parse" for step in planned.plan["steps"])
    with pytest.raises(IngestionPlanError, match="UNRESOLVED"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])


def test_media_conflict_is_unresolved_and_recorded(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "disguised.pdf"
    source.write_text("plain text", encoding="utf-8")
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    assert planned.plan["status"] == "UNRESOLVED"
    assert "MEDIA_TYPE_CONFLICT" in {item["code"] for item in planned.plan["issues"]}


def test_existing_valid_run_reuses_and_tampered_artifact_fails_closed(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("alpha\n", encoding="utf-8")
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    first = execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    second = execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    assert second == first
    run_hash = first.run["run_id"].rsplit(":", 1)[-1]
    evidence = prompt03_workspace / "artifacts" / "evidence" / run_hash / "evidence-records.json"
    evidence.write_bytes(evidence.read_bytes() + b" ")
    with pytest.raises(ArtifactTamperedError, match="hash mismatch"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])


def test_parser_quality_and_artifact_writer_failures_leave_no_formal_run(
    prompt03_workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("alpha\n", encoding="utf-8")
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    run_hash = stable_urn(
        "ingestion-run",
        {
            "project_lock_id": planned.plan["project_lock_id"],
            "source_batch_id": planned.plan["source_batch_id"],
            "ingestion_plan_id": planned.plan["plan_id"],
            "plugin_snapshot_ids": sorted(
                item["snapshot_id"] for item in planned.plan["plugin_snapshots"]
            ),
            "execution_profile": "KG-MNP Deterministic Ingestion Execution v1",
        },
    ).rsplit(":", 1)[-1]
    formal = (
        prompt03_workspace / "artifacts" / "builds" / "ingestion" / run_hash,
        prompt03_workspace / "artifacts" / "evidence" / run_hash,
        prompt03_workspace / "artifacts" / "ir" / run_hash,
        prompt03_workspace / "artifacts" / "validation" / "ingestion" / run_hash,
    )
    monkeypatch.setattr(
        "kg_mnp.plugins.builtin.text_parser.PlainTextParser.parse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PluginError("PARSE_FAILURE")),
    )
    with pytest.raises(PluginError, match="PARSE_FAILURE"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    assert not any(path.exists() for path in formal)
    monkeypatch.undo()

    from kg_mnp.ingestion import executor

    original_quality = executor.build_quality_report

    def failed_quality(**kwargs):
        value = original_quality(**kwargs)
        return {**value, "gate_status": "FAIL"}

    monkeypatch.setattr(executor, "build_quality_report", failed_quality)
    with pytest.raises(QualityGateError):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    assert not any(path.exists() for path in formal)
    monkeypatch.undo()

    original_write = executor.atomic_write_json

    def fail_staging_write(path, value):
        if "tmp" in Path(path).parts and "ingestion" in Path(path).parts:
            raise OSError("simulated artifact writer failure")
        return original_write(path, value)

    monkeypatch.setattr(executor, "atomic_write_json", fail_staging_write)
    with pytest.raises(OSError, match="artifact writer"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    assert not any(path.exists() for path in formal)
    assert not (prompt03_workspace / "tmp" / "ingestion" / run_hash).exists()


def test_concurrent_writer_lock_and_authority_directories_fail_closed(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("alpha", encoding="utf-8")
    _store, _registered, _batch, planned = _prepare(prompt03_workspace, source)
    with (
        WorkspaceOperationLock(prompt03_workspace, "ingestion"),
        pytest.raises(WorkspaceOperationLockedError),
    ):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    confirmed = prompt03_workspace / "artifacts" / "confirmed" / "forbidden.json"
    confirmed.write_text("{}", encoding="utf-8")
    with pytest.raises(IngestionError, match="confirmed"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])


def test_equivalent_absolute_workspaces_produce_identical_formal_json(
    tmp_path: Path,
) -> None:
    workspaces = []
    for directory in (tmp_path / "left", tmp_path / "right"):
        initialize_workspace(
            directory,
            project_id="determinism-project",
            project_version="0.3.0",
            display_name="Determinism Project",
            domain_pack="minimal",
            domain_pack_version="0.1.0",
            domain_packs_root=ROOT / "domain_packs",
        )
        input_path = directory.parent / f"input-{directory.name}" / "sample.json"
        input_path.parent.mkdir()
        input_path.write_bytes(b'{"alpha":1.2300,"beta":true}')
        store, source, batch, plan = _prepare(directory, input_path)
        result = execute_ingestion_plan(directory, plan.plan["plan_id"])
        record_path = store.records_root / f"{source['source_id'].rsplit(':', 1)[-1]}.json"
        workspaces.append((directory, source, batch, plan.plan, result, record_path.read_bytes()))
    left, right = workspaces
    assert left[1]["source_id"] == right[1]["source_id"]
    assert left[2] == right[2]
    assert left[3] == right[3]
    assert left[4].run == right[4].run
    assert left[4].dataset == right[4].dataset
    assert left[4].quality_report == right[4].quality_report
    assert left[5] == right[5]
    for relative in (
        "ingestion-plan.json",
        "ingestion-run.json",
        "plugin-snapshots.json",
        "artifact-manifest.json",
    ):
        run_hash = left[4].run["run_id"].rsplit(":", 1)[-1]
        left_bytes = (
            left[0] / "artifacts" / "builds" / "ingestion" / run_hash / relative
        ).read_bytes()
        right_bytes = (
            right[0] / "artifacts" / "builds" / "ingestion" / run_hash / relative
        ).read_bytes()
        assert left_bytes == right_bytes
