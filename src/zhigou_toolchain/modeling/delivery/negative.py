"""Execute fixed negative recipes on disposable copies; never edit native archives."""
from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from rdflib import RDF, SH, XSD, Graph, Literal, URIRef

from zhigou_toolchain import __version__
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes

from .bindings import (
    artifact_identity,
    require_handoff_head,
    require_target,
    verify_ancestor,
    verify_provenance_refs,
)
from .exchange_io import (
    atomic_file,
    digest,
    json_bytes,
    read_bounded,
    require,
    verify_rows,
)
from .negative_plan import normalize_plan, plan_digest
from .v3 import read_zip
from .validation import shacl_check


def negative_status(cases):
    if not cases:
        return "NOT_RUN"
    if any(c["status"] in {"FAIL", "ERROR", "TIMEOUT"} for c in cases):
        return "FAIL"
    return "PASS" if all(c["status"] == "PASS" for c in cases) else "INCOMPLETE"


def _shacl(case, files, native, directory):
    graphs = {role: Graph().parse(data=files[role + ".ttl"], format="turtle") for role in ("ontology", "instances", "shapes")}
    basis, target = case["rule_basis"], case["target"]
    locked = [raw for name, raw in native.items() if name.startswith("baseline/") and name.endswith(".ttl") and digest(raw) == basis["asset_sha256"]]
    if not locked:
        return {"status": "NOT_APPLICABLE", "reason": "NO_MATCHING_FROZEN_SHAPE_ASSET"}, json_bytes(case)
    shape = Graph().parse(data=locked[0], format="turtle")
    cls, prop, node = URIRef(target["class_iri"]), URIRef(target["predicate_iri"]), URIRef(basis["shape_iri"])
    properties = [p for p in shape.objects(node, SH.property) if (p, SH.path, prop) in shape]
    supported = (node, SH.targetClass, cls) in shape and any(
        (case["mutation"] == "REMOVE_REQUIRED" and any(int(str(v)) >= 1 for v in shape.objects(p, SH.minCount)))
        or (case["mutation"] == "WRONG_DATATYPE" and (p, SH.datatype, XSD.string) in shape) for p in properties)
    if not supported:
        return {"status": "NOT_APPLICABLE", "reason": "NO_INDEPENDENT_APPLICABLE_RULE"}, json_bytes(case)
    subjects = sorted(set(graphs["instances"].subjects(RDF.type, cls)), key=str)
    if not subjects:
        return {"status": "NOT_APPLICABLE", "reason": "NO_TARGET_INSTANCE"}, json_bytes(case)
    subject = subjects[0]
    if not list(graphs["instances"].objects(subject, prop)):
        return {"status": "ERROR", "reason": "BASELINE_REQUIRED_FACT_MISSING"}, json_bytes(case)
    baseline = shacl_check(graphs)
    if baseline["status"] != "PASS":
        return {"status": "ERROR", "reason": "BASELINE_NOT_CONFORMANT", "baseline": baseline}, json_bytes(case)
    graphs["instances"].remove((subject, prop, None))
    if case["mutation"] == "WRONG_DATATYPE":
        graphs["instances"].add((subject, prop, Literal(42, datatype=XSD.integer)))
    raw = graphs["instances"].serialize(format="turtle", encoding="utf-8")
    atomic_file(directory / "mutated-instances.ttl", raw)
    graphs["instances"] = Graph().parse(data=read_bounded(directory / "mutated-instances.ttl"), format="turtle")
    observed = shacl_check(graphs)
    detected = observed["status"] == "FAIL" and any(v["component"] == str(SH) + case["expected"]["code"]
        and v["focus"] == str(subject) and v["path"] == str(prop) for v in observed.get("violations", []))
    return {"status": "DETECTED" if detected else "TIMEOUT" if observed["status"] == "TIMEOUT" else
            "ERROR" if observed["status"] == "ENGINE_ERROR" else "NOT_DETECTED", "checker": observed,
            "validator": "pyshacl.validate", "version": version("pyshacl"), "selected_subject": str(subject),
            "code": case["expected"]["code"] if detected else None}, raw


def _guard(case, files, bound, target, directory):
    mutation = case["mutation"]
    working = dict(files)
    input_value = {"mutation": mutation, "target": target}
    def check():
        return None
    validator = ""
    if mutation in {"TAMPER_BYTES", "MISSING_FILE", "WRONG_SIZE"}:
        manifest = json.loads(working["manifest.json"])
        if mutation == "TAMPER_BYTES":
            working["ontology.ttl"] += b"# negative-byte-change\n"
        elif mutation == "MISSING_FILE":
            del working["ontology.ttl"]
        else:
            next(r for r in manifest["files"] if r["path"] == "ontology.ttl")["size_bytes"] += 1
            working["manifest.json"] = json_bytes(manifest)
        raw = archive_mapping_bytes(working)
        atomic_file(directory / "mutated.zip", raw)
        working = read_zip(read_bounded(directory / "mutated.zip"))
        def check():
            verify_rows(working, json.loads(working["manifest.json"])["files"])
        validator = "exchange_io.verify_rows"
    elif mutation == "BROKEN_EVIDENCE":
        statements = [json.loads(line) for line in working["provenance.jsonl"].decode().splitlines()]
        require(bool(statements), "NEGATIVE_PROVENANCE_TARGET_MISSING")
        statements[0]["evidence_record_refs"].append("urn:kg-mnp:evidence:" + "0" * 64)
        raw = b"".join(json_bytes(r) for r in statements)
        atomic_file(directory / "mutated-provenance.jsonl", raw)
        statements = [json.loads(line) for line in read_bounded(directory / "mutated-provenance.jsonl").decode().splitlines()]
        def check():
            verify_provenance_refs(statements, {s["source_id"] for s in bound["sources"]}, {e["evidence_id"] for e in bound["dataset"]["evidence_records"]})
        validator = "bindings.verify_provenance_refs"
    elif mutation in {"STALE_REVIEW", "WRONG_COMPILATION", "STALE_REVISION"}:
        from zhigou_toolchain.services.modeling_sessions import (
            before,
            current,
            invalidate,
            save,
        )
        from zhigou_toolchain.services.models import OperationRequest
        session = deepcopy(bound["session_snapshot"])
        if mutation == "STALE_REVIEW":
            proposal = current(session, "modeling.proposal")
            if proposal is None:
                raise ValueError("NEGATIVE_REVIEW_TARGET_MISSING")
            request = OperationRequest("review.finalize", parameters={"review_id": proposal["review_id"]})
            invalidate(session, 3, "Isolated predeclared negative mutation")
        elif mutation == "WRONG_COMPILATION":
            request = OperationRequest("compile.build", parameters={"plan_id": "urn:kg-mnp:semantic-compilation-plan:" + "0" * 64})
        else:
            request = OperationRequest("modeling.handoff.export", parameters={"package_id": target["package_id"], "expected_revision": session["revision"] - 1})
        save(directory, session)
        raw = json_bytes({"session": session, "request": request.to_dict()})
        def check():
            if mutation == "STALE_REVISION":
                require_handoff_head(session, target["package_id"], request.parameters["expected_revision"])
            else:
                before(directory, request)
        validator = "modeling_sessions.before" if mutation != "STALE_REVISION" else "bindings.require_handoff_head"
    elif mutation == "DENIED_EXPORT":
        from zhigou_toolchain.services.authorization_policy import authorize
        from zhigou_toolchain.services.models import (
            OperationRequest,
            PrincipalReference,
        )
        from zhigou_toolchain.services.operations import build_operation_catalog
        principal = PrincipalReference("synthetic-negative-readonly", permissions=frozenset({"project:read"}))
        operation = build_operation_catalog()["modeling.handoff.export"]
        raw = json_bytes({"permissions": sorted(principal.permissions), "operation": operation.operation_id, "project_id": target["project_id"]})
        def check():
            authorize(principal, operation, OperationRequest(operation.operation_id, target["project_id"]))
        validator = "authorization_policy.authorize"
    else:
        altered = deepcopy(target)
        key = {"WRONG_PACKAGE": "package_id", "WRONG_ARCHIVE": "native_archive_sha256", "WRONG_INPUT": "input_run_id"}.get(mutation)
        if key:
            altered[key] = "0" * 64
            input_value["altered"] = altered
            def check():
                require_target(altered, target)
            validator = "bindings.require_target"
        elif mutation == "STALE_ANCESTOR":
            session = deepcopy(bound["session_snapshot"])
            observed = deepcopy(next(r for r in bound["agent_runs"] if r["operation_id"] == "compile.build"))
            next(o for o in session["outputs"] if o["job_id"] == observed["job_id"])["status"] = "STALE"
            input_value.update(session=session, observation=observed)
            def check():
                verify_ancestor(observed, session)
            validator = "bindings.verify_ancestor"
        else:
            raise ValueError("NEGATIVE_MUTATION_UNSUPPORTED")
        raw = json_bytes(input_value)
    atomic_file(directory / "input-digest-object.bin", raw)
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    try:
        check()
    except (ValueError, ServiceBoundaryError) as exc:
        code = exc.code if isinstance(exc, ServiceBoundaryError) else str(exc)
        return {"status": "DETECTED" if code == case["expected"]["code"] else "UNEXPECTED_REJECTION",
                "code": code, "validator": validator, "version": __version__}, raw
    return {"status": "NOT_DETECTED", "code": None, "validator": validator, "version": __version__}, raw


def execute_negative_plan(plan, files, native, *, output):
    plan = normalize_plan(plan)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    bound = json.loads(files["dependencies/run_bindings.json"])
    target = artifact_identity(bound, digest(files["native/ontology.kgop"]))
    sha = plan_digest(plan)
    cases, logs = [], {}
    original_sha = target["native_archive_sha256"]
    for case in plan["cases"]:
        started, clock = datetime.now(UTC).isoformat(), perf_counter()
        with tempfile.TemporaryDirectory(prefix="zhigou-negative-") as temporary:
            directory = Path(temporary)
            try:
                observed, raw = _shacl(case, files, native, directory) if case["category"] == "SHACL" else _guard(case, files, bound, target, directory)
            except Exception as exc:  # noqa: BLE001 - a checker crash is evidence, never a successful rejection
                observed, raw = {"status": "ERROR", "exception_type": type(exc).__name__}, json_bytes(case)
        status = "PASS" if observed["status"] == "DETECTED" else "NOT_APPLICABLE" if observed["status"] == "NOT_APPLICABLE" else "TIMEOUT" if observed["status"] == "TIMEOUT" else "ERROR" if observed["status"] == "ERROR" else "FAIL"
        name = "negative-logs/" + case["case_id"] + ".json"
        log = {"case": case, "observed": observed, "mutated_input_sha256": digest(raw), "input_digest_scope": "EXACT_BYTES_OF_ISOLATED_MUTATED_INPUT"}
        logs[name] = json_bytes(log)
        input_name = "negative-logs/" + case["case_id"] + ".input.bin"
        logs[input_name] = raw
        atomic_file(output / input_name, raw)
        atomic_file(output / name, logs[name])
        cases.append({"case_id": case["case_id"], "category": case["category"], "plan_version": plan["version"], "plan_sha256": sha,
            "case_sha256": digest(json_bytes(case)), "tested_native_archive_sha256": original_sha, "mutated_input_sha256": digest(raw),
            "expected": case["expected"], "observed": observed, "status": status, "expected_rejection_detected": status == "PASS",
            "started_at": started, "duration_ms": (perf_counter() - clock) * 1000, "log": name, "log_sha256": digest(logs[name]), "input_artifact": input_name})
    require(digest(files["native/ontology.kgop"]) == original_sha, "NEGATIVE_CHANGED_NATIVE_ARCHIVE")
    report = {"format": "zhigou-negative-case-results/1.0.0", "plan_sha256": sha, "target": target,
              "status": negative_status(cases), "cases": cases, "native_bytes_unchanged": True,
              "semantics": "PASS_MEANS_PREDECLARED_REJECTION_DETECTED_NOT_BAD_INPUT_ACCEPTED"}
    atomic_file(output / "report.json", json_bytes(report))
    return report, logs


def verify_negative_report(plan, report, target, logs):
    plan = normalize_plan(plan)
    sha = plan_digest(plan)
    require(report["format"] == "zhigou-negative-case-results/1.0.0" and report["plan_sha256"] == sha, "NEGATIVE_PLAN_BINDING_MISMATCH")
    require_target(report["target"], target)
    require(len(report["cases"]) == len(plan["cases"]), "NEGATIVE_CASE_SET_MISMATCH")
    require(report["native_bytes_unchanged"] is True, "NEGATIVE_NATIVE_CHANGED")
    for case, result in zip(plan["cases"], report["cases"], strict=True):
        require(result["case_id"] == case["case_id"] and result["category"] == case["category"] and result["plan_version"] == plan["version"]
                and result["case_sha256"] == digest(json_bytes(case)) and result["plan_sha256"] == sha
                and result["expected"] == case["expected"] and result["tested_native_archive_sha256"] == target["native_archive_sha256"], "NEGATIVE_CASE_BINDING_MISMATCH")
        require(result["log"] in logs and digest(logs[result["log"]]) == result["log_sha256"], "NEGATIVE_LOG_MISMATCH")
        require(result["input_artifact"] in logs and digest(logs[result["input_artifact"]]) == result["mutated_input_sha256"], "NEGATIVE_MUTATED_INPUT_MISMATCH")
        log = json.loads(logs[result["log"]])
        require(log["case"] == case and log["observed"] == result["observed"] and log["mutated_input_sha256"] == result["mutated_input_sha256"], "NEGATIVE_LOG_CONTENT_MISMATCH")
        observed = result["observed"]
        status = "PASS" if observed["status"] == "DETECTED" else "NOT_APPLICABLE" if observed["status"] == "NOT_APPLICABLE" else "TIMEOUT" if observed["status"] == "TIMEOUT" else "ERROR" if observed["status"] == "ERROR" else "FAIL"
        require(result["status"] == status and result["expected_rejection_detected"] == (status == "PASS"), "NEGATIVE_FALSE_PASS")
        if status == "PASS":
            require(observed.get("code") == case["expected"]["code"] and observed.get("validator") and observed.get("version"), "NEGATIVE_DETECTION_NOT_ATTESTED")
    require(report["status"] == negative_status(report["cases"]), "NEGATIVE_SUMMARY_MISMATCH")
    return report["status"]
