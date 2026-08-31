"""Workspace artifact orchestration for Prompt 4 modeling and review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kg_mnp.contracts.document_io import atomic_write_bytes, deterministic_json_bytes
from kg_mnp.ingestion.transaction import WorkspaceOperationLock
from kg_mnp.workspace.service import open_workspace

from .artifacts import (
    artifact_manifest,
    read_json,
    transactional_write_directory,
    transactional_write_files,
)
from .errors import ModelingControlError
from .review.actions import verify_action_chain
from .security import assert_safe_json

_PRIMARY_ID_BY_KIND = {
    "KG_MNP_ONTOLOGY_SCOPE": "scope_id",
    "KG_MNP_ONTOLOGY_SCOPE_APPROVAL": "approval_id",
    "KG_MNP_COMPETENCY_QUESTION_SET": "question_set_id",
    "KG_MNP_COMPETENCY_QUESTION_COVERAGE_REPORT": "coverage_report_id",
    "KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT": "baseline_snapshot_id",
    "KG_MNP_TERMINOLOGY_CATALOG": "terminology_catalog_id",
    "KG_MNP_TERM_ALIGNMENT_SET": "term_alignment_set_id",
    "KG_MNP_FIELD_MAPPING_CANDIDATE_SET": "field_mapping_candidate_set_id",
    "KG_MNP_MODELING_INPUT_BUNDLE": "modeling_input_bundle_id",
    "KG_MNP_MODELING_PROVIDER_REQUEST": "request_id",
    "KG_MNP_MODELING_PROVIDER_RESPONSE": "response_id",
    "KG_MNP_MODEL_INVOCATION_RECORD": "invocation_id",
    "KG_MNP_ONTOLOGY_CANDIDATE_SET": "candidate_set_id",
    "KG_MNP_ONTOLOGY_MODELING_PROPOSAL": "proposal_id",
    "KG_MNP_FORMAL_PREVALIDATION_REPORT": "formal_prevalidation_report_id",
    "KG_MNP_ONTOLOGY_REVIEW_POLICY": "policy_id",
    "KG_MNP_ONTOLOGY_REVIEW_QUEUE": "review_queue_id",
    "KG_MNP_ONTOLOGY_REVIEW_DECISION_LOG": "review_decision_log_id",
    "KG_MNP_ONTOLOGY_CONFIRMED_MODELING_PACKAGE": "package_id",
    "KG_MNP_ONTOLOGY_MODELING_RUN": "modeling_run_id",
    "KG_MNP_KG_IR_DATASET": "dataset_id",
}


def _tail(artifact_id: str) -> str:
    tail = artifact_id.rsplit(":", 1)[-1]
    if len(tail) != 64 or any(character not in "0123456789abcdef" for character in tail):
        raise ModelingControlError("artifact ID has no canonical SHA-256 suffix")
    return tail


class ModelingWorkspaceService:
    def __init__(self, workspace: Path | str) -> None:
        opened = open_workspace(workspace)
        self.root = opened.root
        self.project = opened.manifest.document
        self.project_lock = opened.lock.document

    def find_artifact(self, artifact_id: str) -> dict[str, Any]:
        artifacts = self.root / "artifacts"
        for path in sorted(artifacts.rglob("*.json"), key=lambda item: item.as_posix()):
            if path.is_symlink() or "packages" in path.relative_to(artifacts).parts:
                continue
            try:
                value = read_json(path, enforce_safe_json=False)
            except ModelingControlError:
                continue
            id_field = _PRIMARY_ID_BY_KIND.get(value.get("manifest_kind"))
            if id_field is not None and value.get(id_field) == artifact_id:
                return value
        raise ModelingControlError(f"artifact not found: {artifact_id}")

    def latest_artifact(self, manifest_kind: str) -> dict[str, Any]:
        matches: list[dict[str, Any]] = []
        for path in sorted((self.root / "artifacts").rglob("*.json")):
            if path.is_symlink() or "packages" in path.relative_to(self.root / "artifacts").parts:
                continue
            try:
                value = read_json(path, enforce_safe_json=False)
            except ModelingControlError:
                continue
            if value.get("manifest_kind") == manifest_kind:
                matches.append(value)
        if not matches:
            raise ModelingControlError(f"no artifact of kind {manifest_kind}")
        return max(matches, key=lambda value: deterministic_json_bytes(value))

    def find_candidate(self, candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for path in sorted((self.root / "artifacts" / "proposals" / "modeling").rglob(
            "ontology-modeling-proposal.json"
        )):
            proposal = read_json(path)
            for candidate in [
                *proposal["tbox_candidates"],
                *proposal["mapping_candidates"],
                *proposal["abox_candidates"],
                *proposal["shacl_candidates"],
            ]:
                if candidate["candidate_id"] == candidate_id:
                    return candidate, proposal
        raise ModelingControlError(f"candidate not found: {candidate_id}")

    def write_build(self, run_id: str, documents: dict[str, Any]) -> Path:
        return transactional_write_directory(
            self.root,
            operation="scope-write",
            relative_destination=f"artifacts/builds/modeling/{_tail(run_id)}",
            documents=documents,
        )

    def build_directory(self, run_id: str) -> Path:
        path = (
            self.root / "artifacts" / "builds" / "modeling" / _tail(run_id)
        ).resolve(strict=True)
        builds = (self.root / "artifacts" / "builds" / "modeling").resolve(strict=True)
        if path.is_symlink() or builds not in path.parents:
            raise ModelingControlError("unsafe modeling build directory")
        return path

    def update_build(self, run_id: str, documents: dict[str, Any]) -> None:
        directory = self.build_directory(run_id)
        with WorkspaceOperationLock(self.root, "scope-write"):
            for name, value in documents.items():
                if "/" in name or "\\" in name:
                    raise ModelingControlError("modeling build filenames must be direct children")
                atomic_write_bytes(directory / name, deterministic_json_bytes(value))
            self._rewrite_review_manifest(directory)

    def update_modeling_run(self, document: dict[str, Any]) -> None:
        """Atomically replace the single mutable state record for a semantic run."""

        from .run import verify_modeling_run

        verify_modeling_run(document)
        matches = [
            path
            for path in (self.root / "artifacts" / "builds" / "modeling").rglob(
                "modeling-run.json"
            )
            if not path.is_symlink()
            and read_json(path).get("modeling_run_id") == document["modeling_run_id"]
        ]
        if len(matches) != 1:
            raise ModelingControlError("modeling run artifact is absent or ambiguous")
        directory = matches[0].parent
        with WorkspaceOperationLock(self.root, "scope-write"):
            atomic_write_bytes(matches[0], deterministic_json_bytes(document))
            self._rewrite_review_manifest(directory)

    def write_proposal(self, proposal_id: str, documents: dict[str, Any]) -> Path:
        return transactional_write_directory(
            self.root,
            operation="proposal-write",
            relative_destination=f"artifacts/proposals/modeling/{_tail(proposal_id)}",
            documents=documents,
        )

    def proposal_directory(self, proposal_id: str) -> Path:
        path = (
            self.root / "artifacts" / "proposals" / "modeling" / _tail(proposal_id)
        ).resolve(strict=True)
        proposals = (
            self.root / "artifacts" / "proposals" / "modeling"
        ).resolve(strict=True)
        if path.is_symlink() or proposals not in path.parents:
            raise ModelingControlError("unsafe modeling proposal directory")
        return path

    def update_proposal(self, proposal_id: str, documents: dict[str, Any]) -> None:
        directory = self.proposal_directory(proposal_id)
        with WorkspaceOperationLock(self.root, "proposal-write"):
            for name, value in documents.items():
                if "/" in name or "\\" in name:
                    raise ModelingControlError("proposal filenames must be direct children")
                atomic_write_bytes(directory / name, deterministic_json_bytes(value))
            self._rewrite_review_manifest(directory)

    def write_review(self, review_id: str, documents: dict[str, Any]) -> Path:
        files = {name: deterministic_json_bytes(value) for name, value in documents.items()}
        files["review-actions.jsonl"] = b""
        return transactional_write_files(
            self.root,
            operation="review-write",
            relative_destination=f"artifacts/reviews/modeling/{_tail(review_id)}",
            files=files,
        )

    def review_directory(self, review_id: str) -> Path:
        path = (
            self.root / "artifacts" / "reviews" / "modeling" / _tail(review_id)
        ).resolve(strict=True)
        reviews = (self.root / "artifacts" / "reviews" / "modeling").resolve(strict=True)
        if path.is_symlink() or reviews not in path.parents:
            raise ModelingControlError("unsafe review artifact directory")
        return path

    def load_actions(self, review_id: str) -> list[dict[str, Any]]:
        path = self.review_directory(review_id) / "review-actions.jsonl"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            raise ModelingControlError("unsafe or oversized review action log")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ModelingControlError("invalid UTF-8 review action JSONL") from exc
        actions: list[dict[str, Any]] = []
        decoder = json.JSONDecoder()
        cursor = 0
        while cursor < len(text):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text):
                break
            try:
                value, cursor = decoder.raw_decode(text, cursor)
            except json.JSONDecodeError as exc:
                raise ModelingControlError("invalid review action JSONL") from exc
            if not isinstance(value, dict):
                raise ModelingControlError("review action JSONL entries must be objects")
            assert_safe_json(value)
            actions.append(value)
        verify_action_chain(actions)
        return actions

    def _rewrite_review_manifest(self, directory: Path) -> None:
        files = {
            item.name: item.read_bytes()
            for item in directory.iterdir()
            if item.is_file()
            and not item.is_symlink()
            and item.name != "artifact-manifest.json"
        }
        atomic_write_bytes(
            directory / "artifact-manifest.json",
            deterministic_json_bytes(artifact_manifest(files)),
        )

    def append_action(self, review_id: str, action: dict[str, Any]) -> None:
        directory = self.review_directory(review_id)
        with WorkspaceOperationLock(self.root, "review-write"):
            actions = self.load_actions(review_id)
            verify_action_chain([*actions, action])
            path = directory / "review-actions.jsonl"
            content = b"".join(
                json.dumps(
                    item,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
                for item in [*actions, action]
            )
            atomic_write_bytes(path, content)
            self._rewrite_review_manifest(directory)

    def write_review_final(
        self,
        review_id: str,
        *,
        decision_log: dict[str, Any],
        coverage_report: dict[str, Any],
    ) -> None:
        directory = self.review_directory(review_id)
        with WorkspaceOperationLock(self.root, "review-write"):
            atomic_write_bytes(
                directory / "review-decision-log.json",
                deterministic_json_bytes(decision_log),
            )
            atomic_write_bytes(
                directory / "competency-question-coverage-report.json",
                deterministic_json_bytes(coverage_report),
            )
            self._rewrite_review_manifest(directory)

    def write_confirmed(self, package_id: str, package: dict[str, Any]) -> Path:
        return transactional_write_directory(
            self.root,
            operation="confirmation-write",
            relative_destination=f"artifacts/confirmed/modeling/{_tail(package_id)}",
            documents={"ontology-confirmed-modeling-package.json": package},
        )

    def trace_candidate(self, candidate_id: str) -> dict[str, Any]:
        candidate, proposal = self.find_candidate(candidate_id)
        datasets = [self.find_artifact(dataset_id) for dataset_id in self.latest_artifact(
            "KG_MNP_MODELING_INPUT_BUNDLE"
        )["kg_ir_dataset_ids"]]
        item_index = {
            item["item_id"]: item for dataset in datasets for item in dataset["items"]
        }
        evidence_index = {
            record["evidence_id"]: record
            for dataset in datasets
            for record in dataset["evidence_records"]
        }
        evidence = [evidence_index[value] for value in candidate["evidence_refs"]]
        source_bindings = sorted(
            {
                (record["source_id"], record["source_content_sha256"])
                for record in evidence
            }
        )
        source_asset_ids = sorted(
            {
                record.get("source_asset_id")
                for record in evidence
                if record.get("source_asset_id") is not None
            }
        )
        source_blob_ids = sorted(
            {
                record.get("source_blob_id")
                for record in evidence
                if record.get("source_blob_id") is not None
            }
        )
        return {
            "candidate_id": candidate_id,
            "proposal_id": proposal["proposal_id"],
            "kg_ir_items": [item_index[value] for value in candidate["kg_ir_item_refs"]],
            "evidence_records": evidence,
            "sources": [
                {"source_id": source_id, "source_content_sha256": content_sha256}
                for source_id, content_sha256 in source_bindings
            ],
            "source_ids": [source_id for source_id, _digest in source_bindings],
            "source_content_sha256s": [
                digest for _source_id, digest in source_bindings
            ],
            "source_asset_ids": source_asset_ids,
            "source_blob_ids": source_blob_ids,
        }
