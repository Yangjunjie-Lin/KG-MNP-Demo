"""Optional project cover binding separate downstream and receiver-root formats."""
from __future__ import annotations

import json

from .evolution import validate_batch
from .exchange_io import file_rows, json_bytes, require, verify_rows
from .handoff import verify_handoff


def compose(*, downstream=None, evolution=None, diagnostic=None):
    require(bool(downstream) or bool(evolution) or bool(diagnostic), "HANDOFF_CONTENT_REQUIRED")
    files, statuses = {}, {}
    if downstream:
        statuses["downstream"] = verify_handoff(downstream)
        files.update({"downstream/" + n: raw for n, raw in downstream.items()})
    if evolution:
        statuses["evolution"] = validate_batch(evolution, producer=True)
        require(statuses["evolution"]["status"] == "LOCAL_PROTOCOL_VALID", "EVOLUTION_PROTOCOL_BLOCKED")
        if downstream:
            manifest = json.loads(downstream["manifest.json"])
            bindings = json.loads(evolution["context/run_bindings.json"])
            require(all(b.get("project_id") == manifest["project_id"] and b.get("session_id") == manifest["session_id"] for b in bindings), "COVER_RUN_BINDING_MISMATCH")
        files.update({"evolution/" + n: raw for n, raw in evolution.items()})
    if diagnostic:
        files.update({"diagnostics/" + n: raw for n, raw in diagnostic.items()})
        statuses["local_diagnostics"] = "NOT_AN_EVOLUTION_V2_BATCH"
    files["handoff_manifest.json"] = json_bytes({"format": "zhigou-handoff-cover/1.0.0", "outputs": statuses,
        "receiver_status": "NOT_CONTACTED", "evaluation": "NOT_CONFIRMED", "files": file_rows(files)})
    return files


def verify_cover(files):
    manifest = json.loads(files["handoff_manifest.json"])
    require(manifest["format"] == "zhigou-handoff-cover/1.0.0", "COVER_FORMAT_INVALID")
    require(verify_rows(files, manifest["files"]) == {n.casefold() for n in files if n != "handoff_manifest.json"}, "COVER_FILE_SET_MISMATCH")
    parts = {key: {n[len(directory_prefix):]: raw for n, raw in files.items() if n.startswith(directory_prefix)} for key, directory_prefix in (
        ("downstream", "downstream/"), ("evolution", "evolution/"), ("diagnostic", "diagnostics/"))}
    require(compose(**parts) == files, "COVER_BINDINGS_CHANGED")
    return {"status": "VERIFIED", "receiver_status": "NOT_CONTACTED"}
