"""Closed, independently readable multi-case stage archive; no embedded code runs."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes

from .bindings import associate_trace, context_traces
from .evolution import validate_batch
from .exchange_io import (
    atomic_file,
    digest,
    file_rows,
    json_bytes,
    read_archive,
    read_bounded,
    require,
    verify_rows,
)
from .handoff import verify_handoff
from .negative import execute_negative_plan

FORMAT = "zhigou-ontology-stage-handoff/1.0.0"


def compose_stage(cases, evidence, snapshot_id, readme):
    require(set(cases) == {"hr", "forestry"}, "STAGE_TWO_CASES_REQUIRED")
    files = {"README.md": readme, **{"evidence/" + n: raw for n, raw in evidence.items()}}
    records = []
    for name, case_files in sorted(cases.items()):
        require("ontology-handoff.zip" in case_files and "verification.json" in case_files, "STAGE_CASE_FILES_REQUIRED")
        files.update({name + "/" + n: raw for n, raw in case_files.items()})
        included_diagnostic = any(n.startswith("diagnostics/") for n in case_files)
        included_evolution = any(n.startswith("evolution/") for n in case_files)
        records.append({"case_id": name, "ontology": {"status": "INCLUDED", "path": name + "/ontology-handoff.zip"},
            "verification": name + "/verification.json", "diagnostics": {"status": "INCLUDED" if included_diagnostic else "NOT_INCLUDED", "reason": "RECORDED_LOCAL_JOURNAL" if included_diagnostic else "NO_AUTHORIZED_JOURNAL"},
            "evolution": {"status": "INCLUDED" if included_evolution else "BLOCKED", "reason": "STRICT_V2_REPRESENTABLE" if included_evolution else "PROGRAM_OR_RECORDED_TRACE_NOT_STRICT_V2"}})
    rows = file_rows(files)
    for row in rows:
        row.update(purpose="ONTOLOGY_CASE" if row["path"].split("/")[0] in cases else "VERIFICATION_EVIDENCE",
                   access="AUTHORIZED_ACCEPTANCE_ONLY", case_id=row["path"].split("/")[0] if row["path"].split("/")[0] in cases else None)
    files["stage_manifest.json"] = json_bytes({"format": FORMAT, "snapshot_id": snapshot_id, "cases": records,
        "files": rows, "external_receiver": "NOT_CONTACTED", "production_release": "NOT_PERFORMED",
        "generation_access": "FORBIDDEN_INDEPENDENT_ACCEPTANCE_INCLUDED"})
    return files


def verify_stage_files(files, *, externally_pinned=False, replay_negatives=False):
    from .snapshot import validate_snapshot
    manifest = json.loads(files["stage_manifest.json"])
    require(manifest["format"] == FORMAT, "STAGE_FORMAT_INVALID")
    require(verify_rows(files, manifest["files"]) == {n.casefold() for n in files if n != "stage_manifest.json"}, "STAGE_FILE_SET_MISMATCH")
    require(all(r.get("access") == "AUTHORIZED_ACCEPTANCE_ONLY" and r.get("purpose") in {"ONTOLOGY_CASE", "VERIFICATION_EVIDENCE"} for r in manifest["files"]), "STAGE_ACCESS_METADATA_MISSING")
    require({c["case_id"] for c in manifest["cases"]} == {"hr", "forestry"} and len(manifest["cases"]) == 2, "STAGE_CASE_SET_MISMATCH")
    snapshot = json.loads(files["evidence/source-snapshot.json"])
    validate_snapshot(snapshot)
    require(snapshot["snapshot_id"] == manifest["snapshot_id"], "STAGE_SNAPSHOT_MISMATCH")
    stage = json.loads(files["evidence/stage-verification.json"])
    full = json.loads(files["evidence/full-regression-summary.json"])
    require(stage["snapshot_id"] == manifest["snapshot_id"] and stage["source_before"] == stage["source_after"] == manifest["snapshot_id"]
            and stage["source_unchanged"] is True, "STAGE_SOURCE_NOT_FROZEN")
    require(full["source_unchanged"] is True and full["collection"]["complete"] is True, "FULL_REGRESSION_NOT_FROZEN_OR_COMPLETE")
    require(stage["full_repository_status"] == full["raw_status"], "STAGE_REGRESSION_STATUS_MISMATCH")
    for check in stage["checks"]:
        name = "evidence/relevant-test-receipts/" + check["log"]
        require(name in files and digest(files[name]) == check["log_sha256"], "STAGE_TEST_RECEIPT_MISSING")
    results = {}
    for record in manifest["cases"]:
        name = record["case_id"]
        require(record["ontology"] == {"status": "INCLUDED", "path": name + "/ontology-handoff.zip"} and record["verification"] == name + "/verification.json", "STAGE_CASE_PATH_INVALID")
        raw = files[name + "/ontology-handoff.zip"]
        case_receipt = json.loads(files[name + "/verification.json"])
        receipt = case_receipt["export_receipt"]
        require(digest(raw) == receipt["sha256"] and len(raw) == receipt["size_bytes"], "STAGE_SERVICE_EXPORT_MISMATCH")
        inner = read_archive(raw)
        verified = verify_handoff(inner, trusted_receipt=receipt)
        require(verified["format"] == "zhigou-ontology-handoff/1.1.0", "STAGE_REQUIRES_HANDOFF_1_1")
        from .negative_plan import RECIPES
        acceptance = json.loads(inner["tests/negative_cases.json"])
        require(acceptance.get("plan") and set(RECIPES).issubset({c["mutation"] for c in acceptance["plan"]["cases"]}), "STAGE_NEGATIVE_COVERAGE_INCOMPLETE")
        bindings = json.loads(inner["dependencies/run_bindings.json"])
        native = read_archive(inner["native/ontology.kgop"])
        expected_pack = "hr" if name == "hr" else "forestry-workorders"
        locks = [json.loads(raw) for path, raw in native.items() if path.startswith("baseline/domain-pack-locks/") and path.endswith(".json")]
        require(any(lock.get("pack_id") == expected_pack for lock in locks), "STAGE_DOMAIN_CASE_MISMATCH")
        require(bindings["configuration"].get("stage_source_snapshot") == manifest["snapshot_id"], "STAGE_CASE_SOURCE_MISMATCH")
        results[name] = {"package_id": verified["native_package_id"], "native_sha256": verified["native_archive_sha256"],
                         "negative_acceptance": verified["negative_acceptance"], "format": "VERIFIED"}
        diagnostic = {n[len(name + "/diagnostics/"):]: v for n, v in files.items() if n.startswith(name + "/diagnostics/")}
        if record["diagnostics"]["status"] == "INCLUDED":
            require(diagnostic and "local-trace.json" in diagnostic and "journal.jsonl" in diagnostic, "STAGE_DIAGNOSTIC_MISSING")
            trace = json.loads(diagnostic["local-trace.json"])
            require(diagnostic["journal.jsonl"] == b"".join(json_bytes(e) for e in trace["events"]), "STAGE_JOURNAL_MISMATCH")
            results[name]["diagnostic"] = associate_trace(trace, inner)
            source = trace["harness_manifest"]["provenance"]["source"]
            require(source["commit"] == snapshot["git_head"], "STAGE_TRACE_SOURCE_COMMIT_MISMATCH")
            for path, sha in source["fingerprint"]["files"].items():
                frozen_file = snapshot["files"].get(path)
                require(frozen_file and (frozen_file.get("sha256") == sha or sha == "DELETED" and frozen_file.get("status") == "DELETED"), "STAGE_TRACE_SOURCE_BYTES_MISMATCH")
        else:
            require(not diagnostic and record["diagnostics"]["status"] == "NOT_INCLUDED", "STAGE_DIAGNOSTIC_STATUS_MISMATCH")
        evolution = {n[len(name + "/evolution/"):]: v for n, v in files.items() if n.startswith(name + "/evolution/")}
        if record["evolution"]["status"] == "INCLUDED":
            require(evolution and validate_batch(evolution, producer=True)["status"] == "LOCAL_PROTOCOL_VALID", "STAGE_EVOLUTION_INVALID")
            for trace in context_traces(evolution):
                associate_trace(trace, inner)
        else:
            require(not evolution and record["evolution"]["status"] in {"BLOCKED", "NOT_INCLUDED"} and record["evolution"]["reason"], "STAGE_EVOLUTION_STATUS_MISMATCH")
        if replay_negatives:
            negative = json.loads(inner["tests/negative_cases.json"])
            native = read_archive(inner["native/ontology.kgop"])
            with tempfile.TemporaryDirectory(prefix="zhigou-stage-replay-") as directory:
                replay, _ = execute_negative_plan(negative["plan"], inner, native, output=Path(directory) / "results")
            require([(r["case_id"], r["status"], r["observed"].get("code")) for r in replay["cases"]] ==
                [(r["case_id"], r["status"], r["observed"].get("code")) for r in negative["report"]["cases"]], "STAGE_NEGATIVE_REPLAY_MISMATCH")
            results[name]["negative_replay"] = replay["status"]
    required_checks = {"focused", "new-stage", "ruff", "types", "ontology", "services", "frontend-lint", "frontend-types", "frontend-tests", "frontend-build", "browser"}
    indexed = {c["name"]: c for c in stage["checks"]}
    require(required_checks.issubset(indexed), "STAGE_REQUIRED_CHECK_MISSING")
    actual_module = all(indexed[n]["exit_code"] == 0 and indexed[n].get("skipped", 0) == 0 for n in required_checks) and all(r["negative_acceptance"] == "PASS" for r in results.values())
    require(stage["module_acceptance"] == ("PASS" if actual_module else "FAIL"), "STAGE_FALSE_MODULE_PASS")
    module_pass = actual_module
    return {"format": FORMAT, "status": "VERIFIED", "snapshot_id": manifest["snapshot_id"], "cases": results,
        "module_acceptance": "PASS" if module_pass and externally_pinned else "UNATTESTED" if module_pass else "FAIL",
        "authority": "EXTERNAL_ARCHIVE_SHA256_PINNED" if externally_pinned else "CONSISTENCY_ONLY_NOT_AN_AUTHORIZATION",
        "full_repository_status": full["raw_status"], "new_regressions": full["new_regressions_status"],
        "receiver_status": "NOT_CONTACTED", "production_release": "NOT_PERFORMED"}


def verify_stage_archive(path, *, expected_sha256=None, replay_negatives=False):
    raw = read_bounded(path)
    if expected_sha256 is not None:
        require(digest(raw) == expected_sha256, "TRUSTED_STAGE_ARCHIVE_MISMATCH")
    result = verify_stage_files(read_archive(raw), externally_pinned=expected_sha256 is not None, replay_negatives=replay_negatives)
    return {**result, "archive_sha256": digest(raw), "size_bytes": len(raw)}


def export_stage(output, files):
    raw = archive_mapping_bytes(files)
    atomic_file(output, raw)
    # Validate the on-disk ZIP, not only the precompression dictionary.
    return verify_stage_archive(output, expected_sha256=digest(raw))
