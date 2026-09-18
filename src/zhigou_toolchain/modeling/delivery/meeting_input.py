"""Thin meeting-v2 input adapter. No candidate, approval or ontology IDs invented."""
from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from .exchange_io import digest, file_rows, json_bytes, require, safe_name, verify_rows

PRIVATE_PARTS = {"acceptance_private", "tests", "references", "evidence", "scoring", "gold"}


def validate_input(files):
    manifest = json.loads(files["manifest.json"])
    require(manifest.get("package_kind") == "MEETING_INPUT_HANDOFF" and manifest.get("schema_version") == "2.0.0", "MEETING_INPUT_FORMAT_REQUIRED")
    listed = verify_rows(files, manifest["files"])
    require(listed == {n.casefold() for n in files if n != "manifest.json"}, "INPUT_UNDECLARED_FILE")
    allowlist = manifest["generation_allowlist"]
    require(len(allowlist) == len(set(allowlist)) and all(n in files for n in allowlist), "GENERATION_ALLOWLIST_INVALID")
    for name in allowlist:
        safe_name(name)
        require(not PRIVATE_PARTS.intersection(p.casefold() for p in Path(name).parts) and Path(name).suffix.lower() not in {".zip", ".docx", ".html"}, "GENERATION_PRIVATE_INPUT_FORBIDDEN")
    require(not set(allowlist).intersection(manifest.get("evaluator_only_files", [])), "GENERATION_PRIVATE_INPUT_FORBIDDEN")
    private = manifest.get("evaluator_only_files", [])
    require(isinstance(private, list) and len(private) == len(set(private)) and all(n in files for n in private), "EVALUATOR_FILE_LIST_INVALID")
    require(set(allowlist) | set(private) == set(files) - {"manifest.json"}, "INPUT_ACCESS_CLASSIFICATION_REQUIRED")
    require("baseline.ttl" not in files or "imports.lock.json" in files, "INPUT_BASELINE_LOCK_REQUIRED")
    locators = json.loads(files["source_locator.json"])
    sources = {s["source_id"]: s for s in locators["sources"]}
    evidence = {e["evidence_id"]: e for e in locators["evidence"]}
    require(len(sources) == len(locators["sources"]) and len(evidence) == len(locators["evidence"]), "INPUT_DUPLICATE_REFERENCE")
    records = json.loads(files.get("records.json", b'{"records":[]}'))
    texts = json.loads(files.get("text_blocks.json", b'{"text_blocks":[]}'))
    quality = json.loads(files["quality_report.json"])
    for doc in (records, texts, quality):
        require(doc.get("dataset_id", manifest["dataset_id"]) == manifest["dataset_id"] and doc.get("snapshot_version", manifest["snapshot_version"]) == manifest["snapshot_version"], "INPUT_VERSION_MISMATCH")
    require(not quality.get("quarantined_record_ids") and not any(i.get("severity") in {"ERROR", "CRITICAL", "error", "critical"} for i in quality.get("issues", [])), "INPUT_QUALITY_REVIEW_REQUIRED")
    for check in quality.get("checked_files", []):
        require(check["path"] in files and digest(files[check["path"]]) == check["sha256"], "QUALITY_REPORT_STALE")
    for source in sources.values():
        require(source["file"] in allowlist and digest(files[source["file"]]) == source["sha256"], "INPUT_SOURCE_DIGEST_MISMATCH")
        require(source.get("source_version") and source.get("access", {}).get("permission_basis"), "SOURCE_VERSION_AND_PERMISSION_REQUIRED")
    rows = {r["record_id"]: r for r in records["records"]}
    blocks = {t["text_id"]: t for t in texts["text_blocks"]}
    require(len(rows) == len(records["records"]) and len(blocks) == len(texts["text_blocks"]), "INPUT_DUPLICATE_RECORD")
    for row in [*rows.values(), *blocks.values()]:
        require(row["source_ref"] in sources and row["evidence_ref"] in evidence, "INPUT_REFERENCE_MISSING")
        require(evidence[row["evidence_ref"]]["source_ref"] == row["source_ref"], "INPUT_REFERENCE_MISMATCH")
        require(all(ref in evidence and evidence[ref]["source_ref"] == row["source_ref"] for ref in row.get("field_evidence_refs", {}).values()), "INPUT_FIELD_REFERENCE_MISSING")
    for item in evidence.values():
        require(item["source_ref"] in sources, "INPUT_EVIDENCE_SOURCE_MISSING")
        source = sources[item["source_ref"]]
        raw = files[source["file"]].decode("utf-8-sig")
        locator = item["locator"]
        if locator["kind"] in {"record", "record_field"}:
            row = rows[locator["record_id"]]
            require(row["source_ref"] == item["source_ref"] and row["collection"] == locator["collection"], "INPUT_RECORD_LOCATOR_MISMATCH")
            parsed = list(csv.DictReader(StringIO(raw)))
            matches = [r for r in parsed if all(r.get(k) == v for k, v in locator["primary_key"].items())]
            require(len(matches) == 1 and all(matches[0].get(k) == row.get(k) for k in matches[0]), "INPUT_RECORD_SNAPSHOT_MISMATCH")
            metadata = {"record_id", "collection", "source_ref", "evidence_ref", "field_evidence_refs"}
            require(set(row) - metadata == set(matches[0]), "INPUT_RECORD_FIELDS_NOT_IN_SOURCE")
            if locator["kind"] == "record_field":
                require(row.get("field_evidence_refs", {}).get(locator["field"]) == item["evidence_id"], "INPUT_FIELD_LOCATOR_MISMATCH")
        elif locator["kind"] == "char_range":
            block = blocks[locator["text_id"]]
            require(block["text_version"] == locator["text_version"] and block["source_ref"] == item["source_ref"], "INPUT_TEXT_VERSION_MISMATCH")
            require(digest(block["text"].encode("utf-8")) == block["content_sha256"], "INPUT_TEXT_DIGEST_MISMATCH")
            position = block["source_position"]
            require(position["kind"] == "char_range" and type(position["start"]) is int and type(position["end"]) is int
                    and 0 <= position["start"] < position["end"] <= len(raw)
                    and raw[position["start"]:position["end"]] == block["text"], "INPUT_TEXT_SNAPSHOT_MISMATCH")
            start, end = locator["start"], locator["end"]
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(raw), "INPUT_TEXT_LOCATOR_INVALID")
            require(raw[start:end] == item["quote"] and item["quote"] in block["text"], "INPUT_TEXT_QUOTE_MISMATCH")
        else:
            raise ValueError("INPUT_LOCATOR_PROFILE_UNSUPPORTED")
    if "imports.lock.json" in files:
        lock = json.loads(files["imports.lock.json"])
        require(not lock.get("imports") and not lock.get("missing_dependencies"), "INPUT_EXTERNAL_IMPORTS_UNSUPPORTED")
        for key in ("baseline", "companion_shapes"):
            dependency = lock.get(key)
            if dependency:
                require(dependency["file"] in allowlist and digest(files[dependency["file"]]) == dependency["sha256"], "INPUT_BASELINE_DIGEST_MISMATCH")
        require(lock.get("license", {}).get("expression") and lock["license"]["file"] in allowlist, "INPUT_BASELINE_LICENSE_REQUIRED")
    return {"manifest": manifest, "sources": sources, "evidence": evidence, "records": records, "texts": texts, "quality": quality,
            "goal_and_rules": json.loads(files["goal_and_rules.json"])}


def generation_files(files):
    parsed = validate_input(files)
    selected = {n: files[n] for n in parsed["manifest"]["generation_allowlist"]}
    selected["manifest.json"] = json_bytes({"format": "zhigou-generation-input/1.0.0", "source_manifest_sha256": digest(files["manifest.json"]),
        "files": file_rows(selected), "excluded": parsed["manifest"].get("evaluator_only_files", []), "os_isolation": "NOT_PROVIDED_BY_FILE_FILTER"})
    return selected
