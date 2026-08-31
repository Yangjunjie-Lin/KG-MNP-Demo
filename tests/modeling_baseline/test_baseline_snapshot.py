from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kg_mnp.domain_packs.locking import generate_pack_lock
from kg_mnp.domain_packs.validation import load_domain_pack_manifest
from kg_mnp.modeling.control_plane.baseline import build_baseline_snapshot
from kg_mnp.modeling.control_plane.errors import ModelingControlError


def test_minimal_baseline_has_required_indexes_and_is_deterministic(prompt04_case: dict) -> None:
    baseline = prompt04_case["baseline"]
    assert baseline == build_baseline_snapshot(
        project_lock_id=baseline["project_lock_id"],
        pack_roots=[Path(__file__).resolve().parents[2] / "domain_packs/minimal"],
    )
    assert baseline["classes"] and baseline["data_properties"] and baseline["shapes"]
    assert set(baseline["indexes"]) == {
        "iri_index",
        "label_index",
        "normalized_label_index",
        "language_index",
        "property_type_index",
        "domain_range_index",
        "hierarchy_index",
        "source_asset_index",
    }


def test_baseline_is_byte_identical_across_absolute_pack_paths(
    prompt04_case: dict, tmp_path: Path
) -> None:
    source = Path(__file__).resolve().parents[2] / "domain_packs/minimal"
    copied = tmp_path / "elsewhere" / "minimal"
    shutil.copytree(source, copied)
    rebuilt = build_baseline_snapshot(
        project_lock_id=prompt04_case["project_lock"]["lock_id"], pack_roots=[copied]
    )
    assert rebuilt == prompt04_case["baseline"]


def test_baseline_tamper_fails_pack_lock(prompt04_case: dict, tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "domain_packs/minimal"
    copied = tmp_path / "minimal"
    shutil.copytree(source, copied)
    (copied / "ontology/minimal.ttl").write_text("tampered", encoding="utf-8")
    with pytest.raises(ModelingControlError, match="differs from pack lock"):
        build_baseline_snapshot(
            project_lock_id=prompt04_case["project_lock"]["lock_id"],
            pack_roots=[copied],
        )


def test_baseline_rejects_forged_pack_lock_and_locked_remote_import(
    prompt04_case: dict, tmp_path: Path
) -> None:
    source = Path(__file__).resolve().parents[2] / "domain_packs/minimal"

    forged = tmp_path / "forged" / "minimal"
    shutil.copytree(source, forged)
    lock_path = forged / "pack.lock.json"
    lock_text = lock_path.read_text(encoding="utf-8")
    lock_path.write_text(
        lock_text.replace(
            "urn:kg-mnp:domain-pack-lock:",
            "urn:kg-mnp:domain-pack-lock:" + "f" * 64 + "-",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelingControlError, match="lock is invalid|lock mismatch"):
        build_baseline_snapshot(
            project_lock_id=prompt04_case["project_lock"]["lock_id"],
            pack_roots=[forged],
        )

    remote = tmp_path / "remote" / "minimal"
    shutil.copytree(source, remote)
    ontology_path = remote / "ontology/minimal.ttl"
    ontology_path.write_text(
        ontology_path.read_text(encoding="utf-8")
        + "\n<https://yangjunjie-lin.github.io/KG-MNP-Demo/domain-packs/minimal/ontology> "
        + "<http://www.w3.org/2002/07/owl#imports> <https://example.invalid/remote.owl> .\n",
        encoding="utf-8",
    )
    generate_pack_lock(load_domain_pack_manifest(remote))
    with pytest.raises(ModelingControlError, match="remote or unlocked owl:imports"):
        build_baseline_snapshot(
            project_lock_id=prompt04_case["project_lock"]["lock_id"],
            pack_roots=[remote],
        )
