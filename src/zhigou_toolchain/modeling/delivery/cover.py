"""Optional project cover binding separate downstream and receiver-root formats."""
from __future__ import annotations

import json

from .bindings import associate_trace, context_traces, validate_trace_context
from .evolution import validate_batch
from .exchange_io import file_rows, json_bytes, require, verify_rows
from .handoff import verify_handoff


def compose(*, downstream=None, evolution=None, diagnostic=None, known_run_ids=()):
    require(bool(downstream) or bool(evolution) or bool(diagnostic), "HANDOFF_CONTENT_REQUIRED")
    files, statuses = {}, {}
    if downstream:
        statuses["downstream"] = verify_handoff(downstream)
        files.update({"downstream/" + n: raw for n, raw in downstream.items()})
    if evolution:
        statuses["evolution"] = validate_batch(evolution, producer=True, known_run_ids=known_run_ids)
        require(statuses["evolution"]["status"] == "LOCAL_PROTOCOL_VALID", "EVOLUTION_PROTOCOL_BLOCKED")
        traces = context_traces(evolution)
        if downstream:
            statuses["evolution"]["associations"] = [associate_trace(t, downstream) for t in traces]
            statuses["evolution"]["association_status"] = "VERIFIED" if traces else "NOT_PROVEN_NO_CONTEXT"
        files.update({"evolution/" + n: raw for n, raw in evolution.items()})
    if diagnostic:
        require("local-trace.json" in diagnostic, "LOCAL_TRACE_REQUIRED")
        trace = json.loads(diagnostic["local-trace.json"])
        protocol = validate_trace_context(trace)
        require(json.loads(diagnostic["protocol-diagnostic.json"]) == protocol, "LOCAL_PROTOCOL_REPORT_MISMATCH")
        if "journal.jsonl" in diagnostic:
            require(diagnostic["journal.jsonl"] == b"".join(json_bytes(r) for r in trace["events"]), "LOCAL_JOURNAL_MISMATCH")
        if downstream:
            statuses["diagnostic_association"] = associate_trace(trace, downstream)
        files.update({"diagnostics/" + n: raw for n, raw in diagnostic.items()})
        statuses["local_diagnostics"] = "NOT_AN_EVOLUTION_V2_BATCH"
    if not evolution:
        statuses["evolution"] = {"status": "BLOCKED" if diagnostic else "NOT_INCLUDED", "reason": "LOCAL_DIAGNOSTIC_NOT_COLLECTIBLE_V2" if diagnostic else "NO_COMPATIBLE_EXECUTION_SUPPLIED"}
    files["handoff_manifest.json"] = json_bytes({"format": "zhigou-handoff-cover/1.1.0", "outputs": statuses,
        "receiver_status": "NOT_CONTACTED", "evaluation": "NOT_CONFIRMED", "files": file_rows(files)})
    return files


def verify_cover(files, *, known_run_ids=()):
    manifest = json.loads(files["handoff_manifest.json"])
    require(manifest["format"] in {"zhigou-handoff-cover/1.0.0", "zhigou-handoff-cover/1.1.0"}, "COVER_FORMAT_INVALID")
    require(verify_rows(files, manifest["files"]) == {n.casefold() for n in files if n != "handoff_manifest.json"}, "COVER_FILE_SET_MISMATCH")
    parts = {key: {n[len(directory_prefix):]: raw for n, raw in files.items() if n.startswith(directory_prefix)} for key, directory_prefix in (
        ("downstream", "downstream/"), ("evolution", "evolution/"), ("diagnostic", "diagnostics/"))}
    if manifest["format"] == "zhigou-handoff-cover/1.0.0":
        if parts["downstream"]:
            verify_handoff(parts["downstream"])
        return {"status": "LEGACY_FORMAT_CHECKED", "association": "NOT_ATTESTED", "receiver_status": "NOT_CONTACTED"}
    rebuilt = compose(**parts, known_run_ids=known_run_ids)
    # Old 1.1 covers omitted these additive diagnostic fields. Re-run every
    # check; only compare using their original report projection, not new truth.
    expected = json.loads(rebuilt["handoff_manifest.json"])
    saved_evolution = manifest["outputs"].get("evolution", {})
    projected = expected["outputs"].get("evolution", {})
    for key in ("reference_check", "association_status"):
        if key not in saved_evolution:
            projected.pop(key, None)
    for name, report in projected.get("files", {}).items():
        old_report = saved_evolution.get("files", {}).get(name, {})
        for key in ("accepted", "quarantined"):
            if key not in old_report:
                report.pop(key, None)
    rebuilt["handoff_manifest.json"] = json_bytes(expected)
    require(rebuilt == files, "COVER_BINDINGS_CHANGED")
    return {"status": "VERIFIED", "receiver_status": "NOT_CONTACTED"}
