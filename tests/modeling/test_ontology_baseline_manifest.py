"""The Stage 04 ontology baseline is a frozen view of Stage 03."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

from kg_mnp_demo.modeling.dependencies import (
    ROOT,
    build_ontology_baseline_manifest,
    load_ontology_baseline,
    normalize_lf_bytes,
    normalized_file_hash,
    verify_ontology_baseline_manifest,
)
from kg_mnp_demo.modeling.registry import validate_contract


def _copy_baseline_sources(destination: Path) -> None:
    (destination / "config").mkdir(parents=True)
    shutil.copy2(
        ROOT / "config" / "ontology_modules.yaml",
        destination / "config" / "ontology_modules.yaml",
    )
    shutil.copytree(ROOT / "ontology", destination / "ontology")
    (destination / "docs" / "ontology").mkdir(parents=True)
    for name in ("reasoner-attestation.json", "term-inventory.csv"):
        shutil.copy2(
            ROOT / "docs" / "ontology" / name,
            destination / "docs" / "ontology" / name,
        )


def test_tracked_manifest_exactly_matches_current_stage03_assets():
    manifest = load_ontology_baseline()
    validate_contract("ontology-baseline-manifest", manifest)
    expected = build_ontology_baseline_manifest()
    assert manifest == expected
    assert verify_ontology_baseline_manifest(manifest) == []


def test_manifest_reuses_release_and_semantic_hashes_from_stage03():
    import importlib.util

    path = ROOT / "scripts" / "run_reasoner.py"
    spec = importlib.util.spec_from_file_location("baseline_test_reasoner", path)
    assert spec is not None and spec.loader is not None
    reasoner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reasoner)

    manifest = load_ontology_baseline()
    attestation = json.loads(
        (ROOT / "docs" / "ontology" / "reasoner-attestation.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["release_source_hash"] == reasoner.ontology_release_source_hash(
        ROOT,
        include_alignments=False,
    )
    assert manifest["reasoner_input_semantic_hash"] == (
        reasoner.reasoner_input_semantic_hash(reasoner.asserted_reasoner_graph(ROOT))
    )
    assert manifest["release_source_hash"] == attestation["release_source_hash"]
    assert manifest["reasoner_input_semantic_hash"] == attestation[
        "reasoner_input_semantic_hash"
    ]


def test_manifest_fingerprints_attestation_inventory_and_module_config():
    manifest = load_ontology_baseline()
    assert manifest["reasoner_attestation_hash"] == normalized_file_hash(
        ROOT / "docs" / "ontology" / "reasoner-attestation.json"
    )
    assert manifest["term_inventory_hash"] == normalized_file_hash(
        ROOT / "docs" / "ontology" / "term-inventory.csv"
    )
    assert manifest["ontology_module_config_hash"] == normalized_file_hash(
        ROOT / "config" / "ontology_modules.yaml"
    )


def test_optional_alignment_is_explicitly_excluded_from_reasoner_input():
    manifest = load_ontology_baseline()
    assert manifest["release_source_includes_optional_alignments"] is False
    assert [entry["code"] for entry in manifest["optional_modules"]] == [
        "ALIGNMENTS"
    ]
    assert all(
        entry["included_in_reasoner_input"] is False
        for entry in manifest["optional_modules"]
    )
    assert all(
        entry["included_in_reasoner_input"] is True
        for entry in manifest["runtime_modules"]
    )


def test_manifest_build_is_deterministic():
    first = build_ontology_baseline_manifest()
    second = build_ontology_baseline_manifest()
    render = lambda value: (  # noqa: E731 - compact byte-level assertion helper
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    assert render(first) == render(second)


def test_builder_writes_identical_lf_json_bytes(tmp_path: Path):
    script = ROOT / "scripts" / "build_ontology_baseline_manifest.py"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for output in (first, second):
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(ROOT), "--output", str(output)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    assert b"\r" not in first.read_bytes()
    assert first.read_bytes().endswith(b"\n")


def test_builder_refuses_to_write_inside_ontology_directory(tmp_path: Path):
    root = tmp_path / "checkout"
    (root / "ontology").mkdir(parents=True)
    output = root / "ontology" / "forbidden.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_ontology_baseline_manifest.py"),
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1
    assert "never writes under ontology" in result.stderr
    assert not output.exists()


def test_lf_normalized_hash_is_portable(tmp_path: Path):
    windows = tmp_path / "windows.txt"
    unix = tmp_path / "unix.txt"
    windows.write_bytes(b"first\r\nsecond\r\nthird\r")
    unix.write_bytes(b"first\nsecond\nthird\n")
    assert normalize_lf_bytes(windows.read_bytes()) == unix.read_bytes()
    assert normalized_file_hash(windows) == normalized_file_hash(unix)


def test_runtime_ontology_change_invalidates_manifest(tmp_path: Path):
    _copy_baseline_sources(tmp_path)
    frozen = copy.deepcopy(load_ontology_baseline())
    changed = tmp_path / "ontology" / "mnp-core.ttl"
    changed.write_bytes(changed.read_bytes() + b"\n# changed in verification fixture\n")
    errors = verify_ontology_baseline_manifest(frozen, root=tmp_path)
    assert errors
    assert any(
        "attestation" in error.casefold() or "release" in error.casefold()
        for error in errors
    )


def test_optional_ontology_change_also_invalidates_manifest(tmp_path: Path):
    _copy_baseline_sources(tmp_path)
    frozen = copy.deepcopy(load_ontology_baseline())
    changed = tmp_path / "ontology" / "mnp-alignments.ttl"
    changed.write_bytes(changed.read_bytes() + b"\n# optional source changed\n")
    errors = verify_ontology_baseline_manifest(frozen, root=tmp_path)
    assert errors
    assert any(
        field in errors
        for field in (
            "generated_from does not match current Stage 03 assets",
            "optional_modules does not match current Stage 03 assets",
        )
    )
