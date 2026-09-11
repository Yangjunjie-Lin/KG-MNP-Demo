from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn

from ._common import read, write
from .replay import replay


def rebuild_snapshot(root):
    root=Path(root); manifest=read(root,"registry-manifest.json"); policy=read(root,"policy/registry-policy.json"); state=replay(root); head=read(root,"state/registry-head.json")
    snap={"manifest_kind":"KG_MNP_REGISTRY_SNAPSHOT","schema_version":"1.0.0","registry_id":manifest["registry_id"],"registry_manifest_digest":manifest["content_digest"],"policy_digest":policy["content_digest"],"package_records":state["packages"],"feedback_records":state["feedback"],"change_proposals":state["changes"],"consumer_manifests":state["consumers"],"release_candidates":state["candidates"],"release_reviews":state["reviews"],"releases":state["releases"],"environments":state["environments"],"activation_proposals":state["proposals"],"authority_records":[],"event_count":head["event_count"],"head_event_hash":head["head_event_hash"]}; snap["content_digest"]=semantic_hash(snap); snap["snapshot_id"]=stable_urn("registry-snapshot",{"content_digest":snap["content_digest"]}); write(root,"state/registry-snapshot.json",snap)
    linked={**head,"snapshot_id":snap["snapshot_id"],"snapshot_semantic_hash":snap["content_digest"]}
    linked["content_digest"]=semantic_hash({k:v for k,v in linked.items() if k not in {"content_digest","head_hash","head_id"}})
    linked["head_id"]=stable_urn("registry-head",{"content_digest":linked["content_digest"]})
    linked["head_hash"]=semantic_hash({"registry_id":linked["registry_id"],"generation":linked["generation"],"event_count":linked["event_count"],"head_event_hash":linked["head_event_hash"]})
    write(root,"state/registry-head.json",linked)
    return snap
