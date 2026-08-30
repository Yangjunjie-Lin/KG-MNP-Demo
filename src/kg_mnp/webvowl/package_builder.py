from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .._path_security import UnsafePathError, safe_artifact_path, validated_directory
from ..compilation.artifacts import write_artifact_set
from ..compilation.manifest import json_bytes
from ..modeling.dependencies import ROOT
from .coverage import build_coverage_report, build_representation_loss
from .manifest import build_visualization_manifest
from .normalizer import normalize_vowl_json, normalized_vowl_bytes
from .policy import load_webvowl_policy
from .source import build_visualization_source
from .verifier import scan_vowl_leakage, tbox_equivalence


class WebVOWLPackageError(ValueError):
    pass


def _audited_converter_output(*, root: Path, policy: Mapping[str, Any]) -> bytes:
    try:
        directory = validated_directory(Path(root), label="WebVOWL authority root")
        path = safe_artifact_path(
            directory,
            str(policy["conversion"]["audited_raw_fixture"]),
            label="audited OWL2VOWL fixture",
        )
        data = path.read_bytes()
    except (OSError, UnsafePathError) as exc:
        raise WebVOWLPackageError(
            f"audited OWL2VOWL fixture is unavailable: {exc}"
        ) from exc
    actual = hashlib.sha256(data).hexdigest()
    if actual != policy["conversion"]["audited_raw_sha256"]:
        raise WebVOWLPackageError("audited OWL2VOWL raw fixture hash mismatch")
    return data


def _raw_bytes(value: Mapping[str, Any] | bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return json_bytes(value)


def _validated_upstream_lock(root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    """Read the optional fetched lock only as an attestation of policy values."""
    expected = {
        "webvowl": {
            "commit_sha": str(policy["webvowl"]["commit_sha"]),
            "tree_sha": str(policy["source_tree_hashes"]["webvowl"]),
        },
        "owl2vowl": {
            "commit_sha": str(policy["owl2vowl"]["commit_sha"]),
            "tree_sha": str(policy["source_tree_hashes"]["owl2vowl"]),
        },
        "license": dict(policy["license"]),
    }
    source_root = Path(root) / "upstream-source"
    lock_path = source_root / "upstream-lock.json"
    if not lock_path.exists():
        return expected
    if (
        source_root.is_symlink()
        or bool(getattr(source_root, "is_junction", lambda: False)())
        or lock_path.is_symlink()
        or bool(getattr(lock_path, "is_junction", lambda: False)())
    ):
        raise WebVOWLPackageError("exact upstream lock path is unsafe")
    try:

        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise WebVOWLPackageError("duplicate upstream lock key")
                value[key] = item
            return value

        actual = json.loads(
            lock_path.read_text(encoding="utf-8"), object_pairs_hook=unique
        )
    except Exception as exc:
        raise WebVOWLPackageError(f"invalid exact upstream lock: {exc}") from exc
    if actual != expected:
        raise WebVOWLPackageError("exact upstream lock does not match frozen policy")
    return expected


def _files(
    source,
    raw,
    raw_run_2,
    normalized,
    normalized_run_2,
    manifest,
    coverage,
    loss,
    leakage,
    *,
    policy,
    graphdb_tbox_semantic_hash=None,
    compilation_manifest=None,
    graphdb_manifest=None,
    root=ROOT,
):
    def b(value):
        return json_bytes(value) if isinstance(value, Mapping) else value

    upstream_lock = {
        "contract_version": "1.0",
        "webvowl": policy["webvowl"],
        "owl2vowl": policy["owl2vowl"],
        "images": policy["images"],
        "build_dependencies": policy["build_dependencies"],
        "conversion": policy["conversion"],
        "license": policy["license"],
        "retrieval": policy["retrieval"],
        "source_tree_hashes": policy.get("source_tree_hashes", {}),
    }
    validated_lock = _validated_upstream_lock(Path(root), policy)
    upstream_lock["source_tree_hashes"] = {
        name: validated_lock[name]["tree_sha"] for name in ("webvowl", "owl2vowl")
    }
    raw_1_hash = __import__("hashlib").sha256(raw).hexdigest()
    raw_2_hash = __import__("hashlib").sha256(raw_run_2).hexdigest()
    normalized_1_bytes = normalized_vowl_bytes(normalized)
    normalized_2_bytes = normalized_vowl_bytes(normalized_run_2)
    differences = []
    if raw != raw_run_2:
        differences.append("raw_vowl")
    if normalized_1_bytes != normalized_2_bytes:
        differences.append("normalized_vowl")
    if differences:
        raise WebVOWLPackageError(
            "independent conversion runs are not deterministic: "
            + ", ".join(differences)
        )
    files = {
        "visualization/kg-mnp.webvowl.json": normalized_1_bytes,
        "visualization/visualization-manifest.json": b(manifest),
        "verification/ontology-visualization-coverage.json": b(coverage),
        "verification/representation-loss.json": b(loss),
        "source/webvowl-runtime-policy.yaml": policy["_path"].read_bytes(),
        "source/upstream-lock.json": b(upstream_lock),
        "verification/determinism-report.json": b(
            {
                "contract_version": "1.0",
                "raw_run_1_sha256": raw_1_hash,
                "raw_run_2_sha256": raw_2_hash,
                "normalized_run_1_sha256": __import__("hashlib")
                .sha256(normalized_1_bytes)
                .hexdigest(),
                "normalized_run_2_sha256": __import__("hashlib")
                .sha256(normalized_2_bytes)
                .hexdigest(),
                "sha256_differences": differences,
            }
        ),
        "verification/abox-leakage-scan.json": b(leakage),
        "verification/normalization-exclusions.json": b(
            {
                "contract_version": "1.0",
                "status": "PASS",
                "exclusions": [
                    {
                        **policy["normalization_exclusion_policy"]["class_individuals"],
                        "removed_value_count": sum(
                            len(item.get("individuals", []))
                            for item in json.loads(raw.decode("utf-8")).get(
                                "classAttribute", []
                            )
                            if isinstance(item, Mapping)
                        ),
                    }
                ],
            }
        ),
    }
    graphdb_hash = graphdb_tbox_semantic_hash
    files["verification/tbox-equivalence.json"] = b(
        {
            "status": "PASS"
            if graphdb_hash == source["tbox_semantic_hash"]
            else "UNVERIFIED"
            if graphdb_hash is None
            else "FAILED",
            "stage03_tbox_semantic_hash": source["tbox_semantic_hash"],
            "graphdb_tbox_semantic_hash": graphdb_hash,
            "equal": graphdb_hash == source["tbox_semantic_hash"]
            if graphdb_hash is not None
            else None,
        }
    )
    if compilation_manifest is not None:
        files["source/compilation-manifest.json"] = b(compilation_manifest)
    if graphdb_manifest is not None:
        files["source/graphdb-import-manifest.json"] = b(graphdb_manifest)
    return files


def build_webvowl_visualization_package(
    *,
    ontology_baseline: Mapping[str, Any] | None = None,
    output_dir: Path | None = None,
    force: bool = False,
    root: Path = ROOT,
    graphdb_tbox_semantic_hash: str | None = None,
    compilation_manifest: Mapping[str, Any] | None = None,
    graphdb_manifest: Mapping[str, Any] | None = None,
    raw_converter_runs: tuple[
        Mapping[str, Any] | bytes | str, Mapping[str, Any] | bytes | str
    ]
    | None = None,
    **_: Any,
) -> dict[str, Any]:
    policy = load_webvowl_policy(root / "config/webvowl/webvowl-runtime-1.0.0.yaml")
    policy["_path"] = root / "config/webvowl/webvowl-runtime-1.0.0.yaml"
    source = build_visualization_source(root=root, baseline=ontology_baseline)
    if (
        source["tbox_semantic_hash"]
        != policy["conversion"]["audited_source_tbox_sha256"]
    ):
        raise WebVOWLPackageError(
            "Stage 03 TBox differs from the source audited for this OWL2VOWL projection"
        )
    if graphdb_tbox_semantic_hash is not None:
        tbox_equivalence(
            stage03_semantic_hash=source["tbox_semantic_hash"],
            graphdb_semantic_hash=graphdb_tbox_semantic_hash,
        )
    if raw_converter_runs is None:
        audited = _audited_converter_output(root=root, policy=policy)
        raw_values = (audited, audited)
    else:
        raw_values = raw_converter_runs
    raw, raw_2 = (_raw_bytes(value) for value in raw_values)
    expected_raw_hash = policy["conversion"]["audited_raw_sha256"]
    if any(
        hashlib.sha256(value).hexdigest() != expected_raw_hash for value in (raw, raw_2)
    ):
        raise WebVOWLPackageError(
            "OWL2VOWL output differs from the audited exact-source conversion"
        )
    exclusion_policy = policy["normalization_exclusion_policy"]
    normalized = normalize_vowl_json(raw, exclusion_policy=exclusion_policy)
    normalized_2 = normalize_vowl_json(raw_2, exclusion_policy=exclusion_policy)
    nb = normalized_vowl_bytes(normalized)
    if (
        hashlib.sha256(nb).hexdigest()
        != policy["conversion"]["audited_normalized_sha256"]
    ):
        raise WebVOWLPackageError("normalized OWL2VOWL fixture hash mismatch")
    coverage = build_coverage_report(normalized, source=source, root=root)
    loss = build_representation_loss(normalized, source=source, root=root)
    leakage = scan_vowl_leakage(normalized)
    manifest = build_visualization_manifest(
        policy=policy,
        source=source,
        normalized_vowl=normalized,
        raw_bytes=raw,
        normalized_bytes=nb,
        coverage=coverage,
        loss=loss,
        tbox_verified=(graphdb_tbox_semantic_hash == source["tbox_semantic_hash"]),
    )
    if leakage["status"] != "PASS":
        raise WebVOWLPackageError(
            "VOWL leakage scan failed: " + ", ".join(leakage["hits"])
        )
    if coverage["status"] != "PASS":
        raise WebVOWLPackageError("visualization coverage failed")
    if loss["status"] != "PASS":
        raise WebVOWLPackageError("visualization representation analysis failed")
    files = _files(
        source,
        raw,
        raw_2,
        normalized,
        normalized_2,
        manifest,
        coverage,
        loss,
        leakage,
        policy=policy,
        graphdb_tbox_semantic_hash=graphdb_tbox_semantic_hash,
        compilation_manifest=compilation_manifest,
        graphdb_manifest=graphdb_manifest,
        root=root,
    )
    files["source/ontology-baseline.json"] = json_bytes(source["baseline"])
    if output_dir is not None:
        write_artifact_set(Path(output_dir), files, force=force)
    return {
        "manifest": manifest,
        "files": files,
        "source": source,
        "normalized_vowl": normalized,
        "raw_vowl": json.loads(raw),
        "coverage": coverage,
        "representation_loss": loss,
    }
