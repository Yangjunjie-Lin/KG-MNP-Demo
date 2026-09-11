"""Statement-provenance closure gate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..contracts import finalize_artifact


def validate_provenance_closure(
    manifest: dict[str, Any],
    *,
    known_artifact_ids: set[str],
    project_artifact_ids: set[str],
    candidates: Mapping[str, dict[str, Any]],
    resolved_artifacts: Mapping[str, dict[str, Any]],
    packaged_baseline_paths: set[str],
) -> dict[str, Any]:
    missing = []
    closed = 0
    for row in manifest["statements"]:
        problems: list[tuple[str, str]] = []
        if row["provenance_class"] == "BASELINE_REUSED":
            required = [row["compiler_snapshot_id"]]
            if row["confirmed_item_id"] is None:
                if any(row[field] is not None for field in ("source_candidate_id", "review_decision_id", "review_semantic_hash")):
                    problems.append(("BASELINE_AUTHORITY", "partial baseline reuse authority"))
            else:
                required.extend(
                    [
                        row["confirmed_item_id"],
                        row["source_candidate_id"],
                        row["review_decision_id"],
                        *row["provider_snapshot_refs"],
                        *row["kg_ir_item_refs"],
                        *row["evidence_record_refs"],
                        *row["source_asset_refs"],
                    ]
                )
                if row["confirmed_item_id"] not in candidates:
                    problems.append(("CONFIRMED_ITEM", str(row["confirmed_item_id"])))
            if not row["domain_pack_asset_refs"]:
                problems.append(("BASELINE_ASSET", "baseline asset and Pack Lock references are required"))
            for path in row["domain_pack_asset_refs"]:
                if path not in packaged_baseline_paths:
                    problems.append(("BASELINE_ASSET", path))
        else:
            required = [
                row["confirmed_item_id"],
                row["source_candidate_id"],
                row["review_decision_id"],
                row["compiler_snapshot_id"],
                *row["provider_snapshot_refs"],
                *row["kg_ir_item_refs"],
                *row["evidence_record_refs"],
                *row["source_asset_refs"],
            ]
            candidate = candidates.get(row["confirmed_item_id"])
            if candidate is None:
                problems.append(("CONFIRMED_ITEM", str(row["confirmed_item_id"])))
            else:
                if candidate["candidate_kind"] == "ABOX" and (not row["kg_ir_item_refs"] or not row["evidence_record_refs"]):
                    problems.append(("ABOX_EVIDENCE", candidate["candidate_id"]))
                if candidate["candidate_kind"] in {"TBOX", "SHACL"} and not (
                    candidate["competency_question_refs"]
                    or candidate["domain_asset_refs"]
                    or candidate["evidence_refs"]
                ):
                    problems.append(("MODELING_BASIS", candidate["candidate_id"]))
                required.extend(candidate["model_invocation_refs"])
            for evidence_id in row["evidence_record_refs"]:
                evidence = resolved_artifacts.get(evidence_id)
                if evidence is None:
                    problems.append(("EVIDENCE_RECORD", evidence_id))
                    continue
                source_id = evidence.get("source_id")
                source = resolved_artifacts.get(source_id) if isinstance(source_id, str) else None
                if source is None or not isinstance(source.get("content_sha256"), str):
                    problems.append(("SOURCE_BLOB", str(source_id)))
                plugin = evidence.get("plugin_snapshot_id")
                if not isinstance(plugin, str) or plugin not in known_artifact_ids:
                    problems.append(("PARSER_SNAPSHOT", str(plugin)))
                for transformation in evidence.get("transformation_ids", []):
                    if transformation not in known_artifact_ids:
                        problems.append(("TRANSFORMATION", transformation))
        absent = sorted(set(required) - known_artifact_ids)
        cross_project = sorted(set(required) - project_artifact_ids)
        for ref in sorted({*absent, *cross_project}):
            problems.append(("AUTHORITY_REFERENCE", str(ref)))
        for relation, ref in sorted(set(problems)):
            missing.append({"statement_id": row["statement_id"], "relation": relation, "missing_ref": ref[:256]})
        if not problems and not absent and not cross_project:
            closed += 1
    required_count = len(manifest["statements"])
    coverage = 10000 if required_count == 0 else closed * 10000 // required_count
    referenced_candidates = {row["confirmed_item_id"] for row in manifest["statements"] if row["confirmed_item_id"] is not None}
    orphan_records = sorted(set(candidates) - referenced_candidates)
    status = "PASSED" if coverage == 10000 and not orphan_records else "FAILED"
    core = {"manifest_kind": "KG_MNP_PROVENANCE_CLOSURE_REPORT", "schema_version": "1.0.0", "required_statement_count": required_count, "closed_statement_count": closed, "coverage_basis_points": coverage, "missing_links": missing, "orphan_records": orphan_records, "status": status}
    return finalize_artifact(core, id_field="report_id", urn_kind="provenance-closure-report", contract="provenance-closure-report")
