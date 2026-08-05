#!/usr/bin/env python3
"""Verify the tracked Stage 03 attestation and its generated Markdown view."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from run_reasoner import (
    ATTESTATION_FIELDS,
    CONSISTENT,
    EXPECTED_RDFLIB_VERSION,
    EXPECTED_ROBOT_SHA256,
    PORTABLE_EXECUTION_COMMAND,
    PORTABLE_ROBOT_COMMAND,
    ROBOT_URL,
    ROBOT_VERSION,
    ROOT,
    STATUS_NOT_RUN,
    STATUS_PASS,
    UNKNOWN,
    _allowlist_hash,
    _load_module_config,
    find_portability_violations,
    java_major_version,
    load_equivalence_allowlist,
    ontology_release_source_hash,
    ontology_version,
    read_json,
    release_source_files,
    render_reasoner_markdown,
    validate_runtime_report,
)


def _contains_value(value: Any, forbidden: str) -> bool:
    if value == forbidden:
        return True
    if isinstance(value, dict):
        return any(_contains_value(item, forbidden) for item in value.values())
    if isinstance(value, list):
        return any(_contains_value(item, forbidden) for item in value)
    return False


def validate_attestation(
    attestation: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> list[str]:
    errors: list[str] = []
    required = {"attestation_schema_version", *ATTESTATION_FIELDS}
    missing = sorted(required - set(attestation))
    extra = sorted(set(attestation) - required)
    if missing:
        errors.append(f"attestation fields: missing {', '.join(missing)}")
    if extra:
        errors.append(f"attestation fields: unexpected {', '.join(extra)}")

    expected_scalars = {
        "attestation_schema_version": 1,
        "status": STATUS_PASS,
        "ontology_version": ontology_version(root),
        "root_ontology_iri": _load_module_config(root)["root"]["ontology_iri"],
        "release_source_hash": ontology_release_source_hash(root),
        "release_source_includes_optional_alignments": False,
        "reasoner_allowlist_hash": _allowlist_hash(root / "config" / "reasoner-allowlist.yaml"),
        "rdflib_version": EXPECTED_RDFLIB_VERSION,
        "robot_version": ROBOT_VERSION,
        "robot_sha256": EXPECTED_ROBOT_SHA256,
        "robot_download_url": ROBOT_URL,
        "reasoner": "HermiT",
        "consistency": CONSISTENT,
        "unsatisfiable_check": STATUS_PASS,
        "unexpected_equivalent_class_check": STATUS_PASS,
        "execution_command": PORTABLE_EXECUTION_COMMAND,
        "robot_command": PORTABLE_ROBOT_COMMAND,
    }
    for field, expected in expected_scalars.items():
        actual = attestation.get(field)
        if actual != expected:
            errors.append(f"{field}: expected {expected!r}, got {actual!r}")

    expected_sources = [
        path.relative_to(root).as_posix()
        for path in release_source_files(root, include_alignments=False)
    ]
    if attestation.get("release_source_files") != expected_sources:
        errors.append("release_source_files: does not match current formal release sources")

    if attestation.get("unsatisfiable_named_classes") != []:
        errors.append(
            "unsatisfiable_named_classes: expected [], "
            f"got {attestation.get('unsatisfiable_named_classes')!r}"
        )
    if attestation.get("unexpected_equivalent_classes") != []:
        errors.append(
            "unexpected_equivalent_classes: expected [], "
            f"got {attestation.get('unexpected_equivalent_classes')!r}"
        )

    allowed_pairs = {
        tuple(pair)
        for pair in attestation.get("allowed_inferred_equivalent_classes", [])
        if isinstance(pair, list) and len(pair) == 2
    }
    configured_allowlist = load_equivalence_allowlist(
        root / "config" / "reasoner-allowlist.yaml"
    )
    if not allowed_pairs <= configured_allowlist:
        errors.append(
            "allowed_inferred_equivalent_classes: contains a pair not present in the allowlist"
        )

    hermit_version = attestation.get("hermit_version")
    if not isinstance(hermit_version, str) or not hermit_version:
        errors.append("hermit_version: missing")
    # UNKNOWN is honest and permitted only for this dependency metadata field;
    # the current pinned JAR normally yields the exact embedded version.
    java = attestation.get("java_version")
    if not isinstance(java, str) or not java:
        errors.append("java_version: missing")
    else:
        major = java_major_version(java)
        if major is None or major < 17:
            errors.append(f"java_version: Java 17 or newer is required, got {java!r}")

    if _contains_value(attestation, STATUS_NOT_RUN):
        errors.append("attestation contains NOT_RUN")
    if attestation.get("consistency") == UNKNOWN:
        errors.append("consistency: UNKNOWN is not a passing result")

    proof_text = json.dumps(attestation, ensure_ascii=False)
    for violation in find_portability_violations(proof_text):
        errors.append(f"attestation portability: contains {violation}")

    # Java patch/vendor versions are intentionally not required to match the
    # release machine so that Java 17+ CI can reproduce a proof made on Java
    # 17 or newer. All logical inputs, pinned tools, and logical results match.
    cross_run_fields = set(ATTESTATION_FIELDS) - {"java_version"}
    for field in sorted(cross_run_fields):
        if field in attestation and attestation.get(field) != runtime.get(field):
            errors.append(
                f"{field}: attestation={attestation.get(field)!r} "
                f"runtime={runtime.get(field)!r}"
            )
    return errors


def validate_reasoner_proof_files(*, root: Path = ROOT) -> list[str]:
    attestation_path = root / "docs" / "ontology" / "reasoner-attestation.json"
    markdown_path = root / "docs" / "ontology" / "reasoner-report.md"
    runtime_path = root / "runtime_reports" / "ontology" / "reasoner-run.json"
    errors: list[str] = []
    for label, path in (
        ("attestation", attestation_path),
        ("Markdown report", markdown_path),
        ("runtime report", runtime_path),
    ):
        if not path.is_file():
            errors.append(f"{label}: missing {path.relative_to(root).as_posix()}")
    if errors:
        return errors

    try:
        runtime = read_json(runtime_path)
        errors.extend(validate_runtime_report(runtime, root=root))
    except Exception as exc:  # noqa: BLE001
        return [f"runtime report: cannot be verified: {exc}"]

    try:
        attestation = read_json(attestation_path)
        errors.extend(validate_attestation(attestation, runtime, root=root))
    except Exception as exc:  # noqa: BLE001
        return errors + [f"attestation: cannot be verified: {exc}"]

    markdown = markdown_path.read_text(encoding="utf-8")
    expected_markdown = render_reasoner_markdown(attestation)
    if markdown != expected_markdown:
        errors.append(
            "Markdown report: does not exactly match the deterministic JSON rendering"
        )
    for label, text in (
        ("attestation", attestation_path.read_text(encoding="utf-8")),
        ("Markdown report", markdown),
    ):
        for violation in find_portability_violations(text):
            errors.append(f"{label} portability: contains {violation}")
    return errors


def main() -> int:
    errors = validate_reasoner_proof_files()
    if errors:
        print("REASONER REPORT CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Reasoner attestation and Markdown report check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
