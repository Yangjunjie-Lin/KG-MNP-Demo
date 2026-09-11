"""Migrated exact offline artifact allowlist scanner; does not execute a historical deployment."""
import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
errors = []
forbidden_path_parts = {".docker", ".env", ".m2"}
forbidden_path_markers = (
    "authorization",
    "cookie",
    "credential",
    "docker-auth",
    "docker-config",
    "env.json",
    "environment-dump",
    "environment.json",
    "license-content",
    "maven-cache",
    "node_modules",
    "raw-env",
    "settings.xml",
)
expected_files = {
    "browser-smoke.json",
    "hash-summary.json",
    "ontology-visualization-coverage.json",
    "publication-attestation.json",
    "publication-manifest.json",
    "representation-loss.json",
    "tbox-equivalence.json",
    "upstream-lock.json",
    "visualization-manifest.json",
    "webvowl-runtime.json",
}
documents = {}
actual_files = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() or path.is_symlink()
}
if actual_files != expected_files:
    missing = sorted(expected_files - actual_files)
    unexpected = sorted(actual_files - expected_files)
    if missing:
        errors.append("missing required artifact files: " + ", ".join(missing))
    if unexpected:
        errors.append("unexpected artifact files: " + ", ".join(unexpected))
forbidden_key_markers = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "rawenv",
    "secret",
    "token",
)
forbidden_keys = {
    "auths",
    "clientsecret",
    "credhelpers",
    "credsstore",
    "dockerconfig",
    "environment",
    "env",
    "graphdblicenseb64",
    "graphdblicensecontent",
    "identitytoken",
    "licensecontent",
    "licensepath",
    "mavencache",
    "mavensettings",
    "m2repository",
    "privatekey",
}
forbidden_value_patterns = (
    re.compile(r"(?i)\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*[:=]"),
    re.compile(r"(?i)\bgraphdb_license_(?:content|b64)\s*="),
    re.compile(r"(?i)(?:^|[/\\])(?:\.docker|\.m2)(?:[/\\]|$)|settings\.xml|docker-credential-"),
    re.compile(r"(?im)(?:^|\n)\s*[A-Z_][A-Z0-9_]{1,63}=\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)

def reject_duplicate_keys(pairs):
    result = {}
    folded = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ValueError(f"duplicate JSON key: {key}")
        folded.add(marker)
        result[key] = value
    return result

def walk(value, location):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if normalized in forbidden_keys or any(
                marker in normalized for marker in forbidden_key_markers
            ):
                errors.append(f"{location}: sensitive JSON key {key!r}")
            walk(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, f"{location}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in forbidden_value_patterns):
        errors.append(f"{location}: sensitive string value")

for path in sorted(root.rglob("*")):
    relative = path.relative_to(root)
    lowered = relative.as_posix().casefold()
    if path.is_symlink():
        errors.append(f"{relative}: symlinks are forbidden")
        continue
    if not path.is_file():
        continue
    if (
        any(part.casefold() in forbidden_path_parts for part in relative.parts)
        or any(marker in lowered for marker in forbidden_path_markers)
    ):
        errors.append(f"{relative}: sensitive filename")
    if path.suffix.casefold() != ".json":
        errors.append(f"{relative}: non-JSON artifact file")
        continue
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{relative}: invalid JSON: {exc}")
        continue
    documents[relative.as_posix()] = payload
    walk(payload, relative.as_posix())

if not errors:
    try:
        from zhigou_toolchain.publication.contracts import (
            validate_publication_attestation_evidence,
            validate_publication_contract,
        )
        from zhigou_toolchain.webvowl.contracts import validate_webvowl_contract

        validate_publication_contract(
            "end-to-end-publication-manifest",
            documents["publication-manifest.json"],
        )
        validate_webvowl_contract(
            "visualization-manifest",
            documents["visualization-manifest.json"],
        )
        validate_webvowl_contract(
            "coverage-report",
            documents["ontology-visualization-coverage.json"],
        )
        validate_webvowl_contract(
            "representation-loss",
            documents["representation-loss.json"],
        )
        validate_publication_attestation_evidence(
            documents["publication-attestation.json"],
            publication_manifest=documents["publication-manifest.json"],
            visualization_manifest=documents["visualization-manifest.json"],
            coverage=documents["ontology-visualization-coverage.json"],
            representation_loss=documents["representation-loss.json"],
            tbox_equivalence=documents["tbox-equivalence.json"],
            upstream_lock=documents["upstream-lock.json"],
            browser_smoke=documents["browser-smoke.json"],
            webvowl_runtime=documents["webvowl-runtime.json"],
        )
        summary = documents["hash-summary.json"]
        expected_summary_files = expected_files - {"hash-summary.json"}
        if (
            summary.get("contract_version") != "1.0"
            or set(summary.get("sha256", {})) != expected_summary_files
        ):
            raise ValueError("hash summary artifact set mismatch")
        for name in sorted(expected_summary_files):
            actual_hash = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if summary["sha256"][name] != actual_hash:
                raise ValueError(f"hash summary mismatch: {name}")
    except Exception as exc:  # noqa: BLE001 - audit boundary must fail closed on any malformed historical artifact
        errors.append(f"semantic attestation validation failed: {exc}")

if errors:
    print("attestation artifact sensitive-data scan failed:", file=sys.stderr)
    print("\n".join(f"- {item}" for item in errors), file=sys.stderr)
    raise SystemExit(1)
print("attestation artifact sensitive-data scan: PASS")
