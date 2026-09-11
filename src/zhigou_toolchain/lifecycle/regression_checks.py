"""Actual package-contained dependency, mapping and provenance closure checks.

These checks resolve portable package bytes. They do not claim that the original
source content is factually true, or rerun a missing external data provider.
"""
import hashlib
import json
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.identifiers import pack_lock_urn
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.semantic_kernel.contracts import verify_artifact


def document(root: Path, name: str):
    return json.loads((root / name).read_bytes())


def dependencies(root: Path) -> bool:
    manifest = document(root, "ontology-package.json")
    locks = [json.loads(path.read_bytes()) for path in (root / "baseline/domain-pack-locks").glob("*.json")]
    ids = {(lock["pack_id"], lock["pack_version"]) for lock in locks}
    locked_paths = {}
    for lock in locks:
        validate_contract("domain-pack-lock", lock)
        digest = semantic_hash({k: v for k, v in lock.items() if k not in {"content_digest", "lock_id"}})
        if lock["content_digest"] != digest or lock["lock_id"] != pack_lock_urn({"content_digest": digest}):
            return False
        if any((d["pack_id"], d["pack_version"]) not in ids for d in lock["dependencies"]):
            return False
        for asset in lock["assets"]:
            # Package closed-set verification runs before this check. Still
            # confine embedded asset paths explicitly before resolving them.
            relative = f"baseline/assets/{lock['pack_id']}/{asset['path']}"
            path = (root / relative).resolve(strict=True)
            if not path.is_relative_to(root.resolve()):
                return False
            data = path.read_bytes()
            if len(data) != asset["size_bytes"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
                return False
            locked_paths[relative] = lock["lock_id"]
    return bool(locks) and all(locked_paths.get(a["asset_path"]) == a["pack_lock_id"] for a in manifest["baseline_dependencies"])


def mappings(root: Path, required_id: str | None = None) -> bool:
    plan = document(root, "mappings/mapping-plan.json")
    confirmed = document(root, "source/confirmed-modeling-package.json")
    source = document(root, "source/semantic-compilation-plan.json")
    verify_artifact(plan, id_field="mapping_plan_id", urn_kind="mapping-plan", contract="mapping-plan")
    candidates = {c["candidate_id"] for c in confirmed["confirmed_mapping"]}
    actual = {row["source_confirmed_item_id"] for row in plan["mappings"]}
    return (plan["mapping_count"] == len(plan["mappings"]) and actual == candidates
        and plan["source_plan_id"] == source["plan_id"]
        and (required_id is None or required_id in {r["compiled_mapping_id"] for r in plan["mappings"]})
        and all(r["review_decision_ref"] == confirmed["review_decision_log_id"] for r in plan["mappings"]))


def provenance(root: Path) -> bool:
    manifest = document(root, "provenance/statement-provenance-manifest.json")
    verify_artifact(manifest, id_field="provenance_manifest_id", urn_kind="statement-provenance-manifest", contract="statement-provenance-manifest")
    confirmed = document(root, "source/confirmed-modeling-package.json")
    index = document(root, "source/authority-index.json")
    snapshot = document(root, "source/semantic-compiler-snapshot.json")
    plan = document(root, "source/semantic-compilation-plan.json")
    if index["content_digest"] != semantic_hash({"artifact_ids": index["artifact_ids"]}):
        return False
    candidates = {c["candidate_id"]: c for field in ("confirmed_tbox", "confirmed_abox", "confirmed_shacl", "confirmed_mapping") for c in confirmed[field]}
    known = set(index["artifact_ids"]) | set(confirmed["artifact_manifest"]["artifact_ids"]) | set(candidates) | {snapshot["snapshot_id"], plan["plan_id"], confirmed["review_decision_log_id"]}
    linked = set()
    if manifest["plan_id"] != plan["plan_id"] or manifest["statement_count"] != len(manifest["statements"]):
        return False
    for row in manifest["statements"]:
        if row["compiler_snapshot_id"] != snapshot["snapshot_id"]:
            return False
        refs = [r for r in (row["source_candidate_id"], row["confirmed_item_id"], row["review_decision_id"]) if r]
        refs += [r for field in ("provider_snapshot_refs", "kg_ir_item_refs", "evidence_record_refs", "source_asset_refs") for r in row[field]]
        if not set(refs).issubset(known):
            return False
        item = row["confirmed_item_id"]
        if item:
            linked.add(item)
            if item not in candidates or row["review_semantic_hash"] != confirmed["review_semantic_hash"]:
                return False
            if candidates[item]["candidate_kind"] == "ABOX" and (not row["kg_ir_item_refs"] or not row["evidence_record_refs"] or not row["source_asset_refs"]):
                return False
        if row["provenance_class"] == "BASELINE_REUSED":
            if not row["domain_pack_asset_refs"]:
                return False
            for relative in row["domain_pack_asset_refs"]:
                target = (root / relative).resolve(strict=True)
                if not target.is_relative_to(root.resolve()) or not target.is_file():
                    return False
        elif not item:
            return False
    return linked == set(candidates)
