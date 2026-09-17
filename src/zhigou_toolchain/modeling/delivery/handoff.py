"""Project handoff view of one verified native package and its frozen authorities.

This is not ontology-delivery v3. Original graphs, review and declarative mapping
semantics remain intact. Additional bindings come from the service generation.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from zhigou_toolchain.contracts.document_io import deterministic_json_bytes
from zhigou_toolchain.modeling.five_stage.exact_answers import ExactAnswer, assertions
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes

from .bindings import artifact_identity, verify_ancestor, verify_provenance_refs
from .exchange_io import MAX_BYTES, digest, file_rows, json_bytes, require, verify_rows
from .native import GRAPH_PATHS, capture_native
from .negative_plan import plan_digest

FORMAT = "zhigou-ontology-handoff/1.0.0"
STAGE_FORMAT = "zhigou-ontology-handoff/1.1.0"


def handoff_files(native_raw, native_files, bindings, dependencies):
    confirmed = json.loads(native_files["source/confirmed-modeling-package.json"])
    native_manifest = json.loads(native_files["ontology-package.json"])
    plan = json.loads(native_files["source/semantic-compilation-plan.json"])
    cq_plan = json.loads(native_files["validation/competency-question-test-plan.json"])
    require(bindings["package_id"] == native_manifest["package_id"] and bindings["confirmed_package_id"] == confirmed["package_id"], "HANDOFF_NATIVE_BINDING_MISMATCH")
    require(bindings["scope"]["scope_id"] == confirmed["scope_id"] and bindings["scope_approval"]["approval_id"] == confirmed["scope_approval_id"], "HANDOFF_SCOPE_BINDING_MISMATCH")
    require(bindings["proposal"]["proposal_id"] == confirmed["source_proposal_id"], "HANDOFF_PROPOSAL_BINDING_MISMATCH")
    require(bindings["dataset"]["dataset_id"] in confirmed["kg_ir_dataset_ids"], "HANDOFF_DATASET_BINDING_MISMATCH")
    require(bindings["compilation_plan_id"] == plan["plan_id"], "HANDOFF_PLAN_BINDING_MISMATCH")
    files = {role + ".ttl": native_files[name] for role, name in GRAPH_PATHS.items()}
    files.update({"dependencies/" + name: raw for name, raw in dependencies.items()})
    files["dependencies/run_bindings.json"] = json_bytes(bindings)
    files["native/ontology.kgop"] = native_raw
    mapping = json.loads(native_files["mappings/mapping-plan.json"])
    files["mapping.json"] = json_bytes({"native_mapping_plan": mapping,
        "native_execution_policy": mapping["execution_policy"],
        "candidate_construction": bindings["mapping_execution"],
        "proposal_id": confirmed["source_proposal_id"], "confirmed_package_id": confirmed["package_id"],
        "note": "Candidate construction is distinct from executing the declarative compiled MappingPlan."})
    provenance = json.loads(native_files["provenance/statement-provenance-manifest.json"])
    files["provenance.jsonl"] = b"".join(json_bytes(row) for row in provenance["statements"])
    files["review.json"] = json_bytes({"status": "NATIVE_REVIEW_CONFIRMED", "nature": bindings["review_nature"],
        "review_decision_log": json.loads(native_files["source/review-decision-log.json"]),
        "scope_approval": bindings["scope_approval"], "confirmed_package_id": confirmed["package_id"],
        "review_semantic_hash": confirmed["review_semantic_hash"], "release_status": "NOT_GRANTED_BY_EXPORT"})
    reports = {name: json.loads(raw) for name, raw in native_files.items() if name.startswith("validation/") and name.endswith("report.json")}
    files["validation.json"] = json_bytes({"execution": "COMPILED_AND_NATIVE_VERIFIED", "native_reports": reports,
        "graph_bytes": file_rows({k: v for k, v in files.items() if k.endswith(".ttl") and "/" not in k}),
        "new_validation_run": False, "release_status": "NOT_GRANTED_BY_EXPORT"})
    answers = {a["query_asset_id"]: a["expected"] for a in bindings["independent_acceptance"]}
    require(len(answers) == len(bindings["independent_acceptance"]), "DUPLICATE_ACCEPTANCE_QUERY")
    require(set(answers) == {t["query_artifact_ref"] for t in cq_plan["tests"]}, "INDEPENDENT_ACCEPTANCE_REQUIRED")
    for index, test in enumerate(cq_plan["tests"], 1):
        answer = ExactAnswer.model_validate(answers[test["query_artifact_ref"]])
        require(assertions(answer) == test["assertions"], "ACCEPTANCE_NATIVE_ASSERTION_MISMATCH")
        matches = [raw for name, raw in native_files.items() if name.endswith(".rq") and digest(raw) == test["query_sha256"]]
        require(bool(matches), "FROZEN_QUERY_MISSING")
        name = f"cq_{index:02d}"
        files["queries/" + name + ".rq"] = matches[0]
        files["tests/" + name + ".json"] = json_bytes({"native_test": test, "expected": answer.model_dump(mode="json"),
            "independence": "SESSION_FROZEN_BEFORE_PROPOSAL", "query": "queries/" + name + ".rq"})
    current = "session_snapshot" in bindings
    negative_plan = bindings.get("negative_case_plan")
    negative_report = bindings.get("negative_case_results")
    acceptance = {"negative_status": negative_report["status"] if negative_report else "NOT_RUN",
        "plan_sha256": plan_digest(negative_plan) if negative_plan else None,
        "report_sha256": digest(json_bytes(negative_report)) if negative_report else None}
    files["tests/negative_cases.json"] = json_bytes({"format": "zhigou-negative-acceptance/1.0.0", "status": acceptance["negative_status"],
        "plan": negative_plan, "report": negative_report,
        "reason": None if negative_report else "PLAN_NOT_EXECUTED" if negative_plan else "NO_INDEPENDENT_PLAN"} if current else {
        "status": "NOT_RUN", "cases": [], "reason": "No independently supplied per-run negative-case plan; repository security regressions are separate evidence."})
    files["manifest.json"] = json_bytes({"format": STAGE_FORMAT if current else FORMAT, "schema_version": "1.1.0" if current else "1.0.0", "package_kind": "NATIVE_BOUND_EXCHANGE_VIEW",
        "native_package_id": native_manifest["package_id"], "native_archive_sha256": digest(native_raw),
        "session_id": bindings["session_id"], "session_revision": bindings["session_revision"],
        "input_run_id": bindings["input_run_id"], "project_id": bindings["project_id"],
        "execution_mode": bindings["execution_mode"], "data_classification": bindings["data_classification"],
        "validation_status": native_manifest["package_status"], "review_status": "NATIVE_REVIEW_CONFIRMED",
        "review_nature": bindings["review_nature"], "release_status": "NOT_GRANTED_BY_EXPORT",
        "default_query_graph": "instances.ttl", "generation_access": "FORBIDDEN_CONTAINS_INDEPENDENT_ACCEPTANCE",
        "files": file_rows(files), **({"stage_acceptance": acceptance} if current else {})})
    return files


def verify_handoff(files, *, trusted_receipt=None):
    manifest = json.loads(files["manifest.json"])
    require(manifest["format"] in {FORMAT, STAGE_FORMAT}, "HANDOFF_FORMAT_UNSUPPORTED")
    schema = json.loads(Path(__file__).with_name("handoff-1.1.schema.json" if manifest["format"] == STAGE_FORMAT else "handoff.schema.json").read_bytes())
    Draft202012Validator(schema).validate(manifest)
    listed = verify_rows(files, manifest["files"])
    require(listed == {n.casefold() for n in files if n != "manifest.json"}, "HANDOFF_UNDECLARED_FILE")
    native_raw = files["native/ontology.kgop"]
    require(digest(native_raw) == manifest["native_archive_sha256"], "HANDOFF_NATIVE_DIGEST")
    with tempfile.TemporaryDirectory(prefix="zhigou-handoff-verify-") as directory:
        path = Path(directory) / "native.kgop"
        path.write_bytes(native_raw)
        _, native, verified = capture_native(path)
    require(verified["package_id"] == manifest["native_package_id"], "HANDOFF_NATIVE_ID")
    bindings = json.loads(files["dependencies/run_bindings.json"])
    attested = {a["artifact_id"]: a for a in json.loads(native["source/compiler-input-attestation.json"])["resolved_artifacts"]}
    for key, id_key in (("scope", "scope_id"), ("scope_approval", "approval_id"), ("proposal", "proposal_id"), ("dataset", "dataset_id")):
        doc = bindings[key]
        row = attested.get(doc[id_key])
        require(row and digest(deterministic_json_bytes(doc)) == row["byte_sha256"], "HANDOFF_ATTESTED_AUTHORITY_CHANGED")
    dependencies = {n[len("dependencies/"):]: raw for n, raw in files.items() if n.startswith("dependencies/") and n != "dependencies/run_bindings.json"}
    reconstructed = handoff_files(native_raw, native, bindings, dependencies)
    require(reconstructed == files, "HANDOFF_VIEW_NOT_REPRODUCIBLE")
    dataset = bindings["dataset"]
    sources = {s["source_id"]: s for s in bindings["sources"]}
    evidence = {e["evidence_id"] for e in dataset["evidence_records"]}
    for source_id, source in sources.items():
        raw = dependencies[source["delivery_path"]]
        require(digest(raw) == source["content_sha256"], "HANDOFF_SOURCE_DIGEST")
        grant = next((g for g in bindings["source_grants"] if g["source_id"] == source_id), None)
        require(grant and grant["sha256"] == digest(raw) and grant["license"] and grant["permission_basis"], "SOURCE_EXPORT_NOT_AUTHORIZED")
        require(digest(deterministic_json_bytes(source["native_document"])) == attested[source_id]["byte_sha256"], "HANDOFF_SOURCE_AUTHORITY_CHANGED")
    from zhigou_toolchain.ingestion.evidence import verify_evidence_closure
    from zhigou_toolchain.ingestion.limits import DEFAULT_LIMITS
    verify_evidence_closure(records=tuple(dataset["evidence_records"]), transformations=tuple(dataset["transformation_records"]),
        snapshots=tuple(dataset["plugin_snapshots"]), sources={i: (s["native_document"], dependencies[s["delivery_path"]]) for i, s in sources.items()}, limits=DEFAULT_LIMITS)
    verify_provenance_refs(json.loads(native["provenance/statement-provenance-manifest.json"])["statements"], sources, evidence)
    negative_status = "NOT_RUN"
    if manifest["format"] == STAGE_FORMAT:
        from zhigou_toolchain.contracts.canonical import semantic_hash

        from .negative import verify_negative_report
        session = bindings["session_snapshot"]
        require(session["session_id"] == bindings["session_id"] and session["revision"] == bindings["session_revision"]
            and session["frozen"]["dataset_digest"] == semantic_hash(dataset)
            and session["frozen"]["run_id"] == bindings["input_run_id"], "HANDOFF_SESSION_BINDING_MISMATCH")
        from zhigou_toolchain.services.modeling_sessions import (
            current as session_current,
        )
        confirmed = json.loads(native["source/confirmed-modeling-package.json"])
        native_plan = json.loads(native["source/semantic-compilation-plan.json"])
        selected = {"compile.build": (verified["package_id"], json.loads(native["ontology-package.json"])),
            "compile.plan.exact": (native_plan["plan_id"], native_plan), "review.finalize": (confirmed["package_id"], confirmed),
            "modeling.scope": (bindings["scope"]["scope_id"], bindings["scope"]),
            "modeling.proposal": (bindings["proposal"]["proposal_id"], bindings["proposal"])}
        for operation, (identifier, document) in selected.items():
            selected_output = session_current(session, operation)
            require(selected_output and selected_output["identifier"] == identifier and selected_output["digest"] == semantic_hash(document), "HANDOFF_NATIVE_DEPENDENCY_MISMATCH")
        require(any(o["operation_id"] == "compile.build" for o in bindings["agent_runs"]), "DELIVERY_BUILD_RUN_REQUIRED")
        require(bindings.get("negative_case_plan") == session["frozen"].get("negative_case_plan"), "NEGATIVE_FREEZE_MISMATCH")
        for observed in bindings["agent_runs"]:
            verify_ancestor(observed, session)
        if bindings.get("negative_case_results"):
            require(bindings["acceptance_freeze"]["negative_plan_sha256"] == plan_digest(bindings["negative_case_plan"]), "NEGATIVE_ORIGIN_MISMATCH")
            negative_status = verify_negative_report(bindings["negative_case_plan"], bindings["negative_case_results"],
                artifact_identity(bindings, digest(native_raw)), dependencies)
    if trusted_receipt is not None:
        receipt = trusted_receipt.get("result", trusted_receipt)
        require(receipt["sha256"] == digest(archive_mapping_bytes(files)) and receipt["package_id"] == verified["package_id"], "TRUSTED_EXPORT_RECEIPT_MISMATCH")
    return {"status": "VERIFIED", "format": manifest["format"], "native_package_id": verified["package_id"],
            "negative_acceptance": negative_status, "authority": "TRUSTED_EXPORT_RECEIPT_MATCHED" if trusted_receipt else "CONSISTENCY_ONLY_REQUIRE_OUT_OF_BAND_RECEIPT",
            "stage_acceptance": "PASS" if trusted_receipt and negative_status == "PASS" else "NOT_ATTESTED" if negative_status == "PASS" else negative_status,
            "native_archive_sha256": digest(native_raw), "graphs": "ORIGINAL_BYTES", "receiver_status": "NOT_CONTACTED",
            "release_status": "NOT_GRANTED_BY_EXPORT"}


def handoff_bytes(files):
    require(sum(map(len, files.values())) <= MAX_BYTES, "HANDOFF_EXPANSION_LIMIT")
    verify_handoff(files)
    return archive_mapping_bytes(files)
