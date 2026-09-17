"""Versioned observations of native authority, not a replacement state store."""
from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5

from zhigou_toolchain.contracts.canonical import semantic_hash

from .evolution import HARNESS_KEYS, parse_jsonl, validate_events
from .exchange_io import digest, json_bytes, require

TARGET_KEYS = ("project_id", "session_id", "session_revision", "input_run_id", "input_snapshot",
               "confirmed_package_id", "compilation_plan_id", "compiler_snapshot_id", "package_id", "native_archive_sha256")


def artifact_identity(bindings, native_sha256):
    return {k: (native_sha256 if k == "native_archive_sha256" else
                semantic_hash(bindings["dataset"]) if k == "input_snapshot" else bindings[k]) for k in TARGET_KEYS}


def require_target(actual, expected):
    require(isinstance(actual, dict) and all(actual.get(k) == expected[k] for k in TARGET_KEYS), "DELIVERY_TARGET_MISMATCH")


def require_handoff_head(session, package_id, revision):
    from zhigou_toolchain.services.modeling_sessions import current
    require(session is not None and session["revision"] == revision, "HANDOFF_SESSION_REVISION_STALE")
    built = current(session, "compile.build")
    require(built and built["identifier"] == package_id, "HANDOFF_PACKAGE_STALE")


def verify_provenance_refs(statements, sources, evidence):
    for row in statements:
        require(set(row["source_asset_refs"]).issubset(sources) and set(row["evidence_record_refs"]).issubset(evidence), "HANDOFF_PROVENANCE_OPEN")


def verify_ancestor(observation, session):
    matches = [o for o in session["outputs"] if o["job_id"] == observation["job_id"] and o["status"] == "CURRENT"]
    require(len(matches) == 1, "DELIVERY_ANCESTOR_NOT_CURRENT")
    output = matches[0]
    require(output == observation["session_output"], "DELIVERY_ANCESTOR_OUTPUT_MISMATCH")
    require(output["dependency_digest"] == observation["frozen_dependency_sha256"], "DELIVERY_ANCESTOR_DEPENDENCY_MISMATCH")
    expected_parts = dependency_parts(session["frozen"])
    relevant = set(expected_parts) - ({"configuration"} if output["stage"] == 1 else set())
    require(all(observation["dependency_parts"].get(k) == expected_parts[k] for k in relevant), "DELIVERY_ANCESTOR_DEPENDENCY_MISMATCH")
    require(observation["session_id"] == session["session_id"] and observation["operation_id"] == output["operation"], "DELIVERY_ANCESTOR_ID_MISMATCH")
    # A legitimate earlier stage need not have the final revision.
    require(type(observation["session_revision"]) is int and 1 <= observation["session_revision"] <= session["revision"], "DELIVERY_ANCESTOR_REVISION_INVALID")


def dependency_parts(frozen):
    return {k: semantic_hash(frozen.get(k)) for k in ("run_id", "dataset_digest", "business_rules", "acceptance", "negative_case_plan", "configuration")}


def validate_harness(harness, start):
    require(set(harness["resources"]) == set(HARNESS_KEYS), "HARNESS_RESOURCE_KEYS")
    hashes = {k: digest(json_bytes(harness["resources"][k])) for k in HARNESS_KEYS}
    require(hashes == harness["hashes"] == start["harness"], "HARNESS_START_MISMATCH")
    require(harness["algorithm"] == "SHA256_UTF8_SORTED_KEYS_COMPACT_JSON_WITH_LF_V1", "HARNESS_ALGORITHM_UNSUPPORTED")


def validate_trace_context(trace, *, strict=False):
    bound, events = trace["bindings"], trace["events"]
    native_id = bound["native_agent_run_id"]
    require(bound["transport_run_id"] == uuid5(NAMESPACE_URL, "zhigou:" + native_id).hex, "TRANSPORT_NATIVE_ID_MISMATCH")
    require(events and events[0]["event"] == "task_start" and events[-1]["event"] == "task_end", "TRACE_TERMINAL_REQUIRED")
    require(all(e["run_id"] == bound["transport_run_id"] for e in events) and events[0]["task_id"] == bound["task_id"], "TRACE_CONTEXT_ID_MISMATCH")
    validate_harness(trace["harness_manifest"], events[0])
    report = validate_events(events, bound["transport_run_id"], producer=True)
    if strict:
        require(bound.get("execution_mode") == "LIVE", "NON_LIVE_TRACE_NOT_COLLECTIBLE")
        require(trace.get("capture_status") == "COMPLETE" and not report["errors"], "STRICT_TRACE_INCOMPATIBLE")
    return report


def associate_trace(trace, downstream):
    validate_trace_context(trace)
    bound = trace["bindings"]
    b = json.loads(downstream["dependencies/run_bindings.json"])
    require(b.get("session_snapshot") is not None, "ANCESTRY_REQUIRES_HANDOFF_1_1")
    target = artifact_identity(b, digest(downstream["native/ontology.kgop"]))
    require_target(bound.get("delivery_target"), target)
    observations = [r for r in b["agent_runs"] if r["job_id"] == bound.get("job_id") and r["native_agent_run_id"] == bound["native_agent_run_id"]]
    require(len(observations) == 1, "DELIVERY_RUN_REFERENCE_MISSING")
    observed = observations[0]
    verify_ancestor(observed, b["session_snapshot"])
    require(bound["session_revision"] == observed["session_revision"] and bound["input_snapshot"] == target["input_snapshot"], "DELIVERY_TRACE_VERSION_MISMATCH")
    require(bound.get("output_artifacts") == [observed["session_output"]], "DELIVERY_OUTPUT_REFERENCE_MISMATCH")
    require(trace["events"][-1]["answer"].get("output_sha256") == observed["result_digest"], "DELIVERY_RESULT_DIGEST_MISMATCH")
    require(bound.get("committed_result_digest") == observed["result_digest"], "DELIVERY_COMMIT_DIGEST_MISMATCH")
    resources = trace["harness_manifest"]["resources"]
    require(resources["knowledge"].get("dataset_digest") == target["input_snapshot"]
        and resources["knowledge"].get("input_run_id") == target["input_run_id"], "DELIVERY_HARNESS_INPUT_MISMATCH")
    require(resources["tasks"].get("session_id") == bound["session_id"]
        and resources["tasks"].get("operation") == observed["operation_id"], "DELIVERY_HARNESS_TASK_MISMATCH")
    require(resources["ontology"]["initial_project_lock"]["lock_id"] == b["scope"]["project_lock_id"], "DELIVERY_HARNESS_BASELINE_MISMATCH")
    return {"job_id": bound["job_id"], "native_agent_run_id": bound["native_agent_run_id"],
            "relationship": "CURRENT_NATIVE_DEPENDENCY_ANCESTOR", "target": target}


def context_traces(files):
    bound = json.loads(files["context/run_bindings.json"])
    harnesses = json.loads(files["context/harness_manifest.json"])
    require(len(bound) == len(harnesses) and len({b["transport_run_id"] for b in bound}) == len(bound), "CONTEXT_RUN_SET_INVALID")
    traces = []
    expected = set()
    for b, h in zip(bound, harnesses, strict=True):
        name = "executions/run-" + b["transport_run_id"] + ".jsonl"
        expected.add(name)
        require(name in files, "CONTEXT_EXECUTION_MISSING")
        trace = {"bindings": b, "harness_manifest": h, "events": parse_jsonl(files[name]), "capture_status": "COMPLETE"}
        validate_trace_context(trace, strict=True)
        traces.append(trace)
    require(expected == {n for n in files if n.startswith("executions/")}, "CONTEXT_EXECUTION_SET_MISMATCH")
    return traces
