"""Publish path-redacted historical views while preserving exact original bytes.

This is a one-time mechanical publication transform, not a verification rerun.
Default is read-only verification. Never overwrite an existing original archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = "docs/research/historical-evidence-originals-20260929.zip"
FILES = (
    "docs/research/benchmark-selection-2026-09-14-evidence.json",
    "docs/research/formal-call-parameters-2026-09-14-evidence.json",
    "docs/research/full-experiment-activation-2026-09-14-evidence.json",
    "docs/research/ontology-io-2026-09-13/execution-evidence.json",
    "docs/upgrade/ontology-kernel-v1-evidence.json",
)


def redact(value):
    if isinstance(value, dict):
        return {redact(k): redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    # Keep relative report locations; do not reinterpret commands as newly run.
    value = re.sub(r"[A-Za-z]:[\\/][^\r\n]*?KG-MNP-Demo[\\/]", "<REPOSITORY>/", value)
    if "<REPOSITORY>/" in value:
        value = value.replace("\\", "/")
    value = re.sub(r"[A-Za-z]:[\\/]Users[\\/][^\r\n]*?python\.exe", "<PYTHON_EXECUTABLE>", value, flags=re.IGNORECASE)
    value = re.sub(r"/home/[^/\s]+/", "<USER_HOME>/", value)
    return value


def published_view(path, raw):
    view = redact(json.loads(raw))
    assert "publication_provenance" not in view, "Cannot redact an already transformed view"
    view["publication_provenance"] = {
        "kind": "PATH_REDACTED_HISTORICAL_VIEW_NOT_ORIGINAL_BYTES",
        "original_archive": ARCHIVE, "original_member": path,
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "transformation": "Local repository, interpreter and home paths replaced with explicit placeholders; historical outcomes unchanged.",
        "current_source_validation": "NOT_CLAIMED_BY_HISTORICAL_EVIDENCE",
    }
    return view


def verify(root=ROOT):
    with zipfile.ZipFile(root / ARCHIVE) as archive:
        assert set(archive.namelist()) == set(FILES), "Original archive member mismatch"
        for path in FILES:
            expected = published_view(path, archive.read(path))
            assert json.loads((root / path).read_bytes()) == expected, f"Historical view changed beyond documented path redaction: {path}"
    return len(FILES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="One-time transform; refuses existing archives")
    args = parser.parse_args()
    if args.write:
        originals = {path: (ROOT / path).read_bytes() for path in FILES}
        for path, raw in originals.items():
            committed = subprocess.check_output(["git", "show", "HEAD:" + path], cwd=ROOT)
            # Git checkout may apply CRLF; the archive still preserves actual
            # pre-transform working-tree bytes, not a reconstructed Git blob.
            assert raw.replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n"), f"Refusing to alter pre-existing user edits: {path}"
            published_view(path, raw)
        with zipfile.ZipFile(ROOT / ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, raw in originals.items():
                info = zipfile.ZipInfo(path, date_time=(2026, 9, 29, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
        # Bulk mechanical rewrite only after the exact originals are preserved.
        for path, raw in originals.items():
            (ROOT / path).write_text(json.dumps(published_view(path, raw), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_historical_views": verify(), "original_archive": ARCHIVE,
                      "current_tests": "NOT_CLAIMED"}))


if __name__ == "__main__":
    main()
