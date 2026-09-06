from __future__ import annotations

import json
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash, stable_urn

from ..contracts import verify
from ..errors import LifecycleError
from ._common import read
from .events import read_events


def replay(root):
    root=Path(root); manifest=read(root,"registry-manifest.json"); head=read(root,"state/registry-head.json"); events=read_events(root); previous=None; seen=set(); state={"packages":{},"feedback":{},"changes":{},"consumers":{},"candidates":{},"reviews":{},"releases":{},"environments":{},"proposals":{}}
    for expected,event in enumerate(events,1):
        if event.get("registry_id")!=manifest["registry_id"] or event.get("sequence")!=expected or event.get("previous_event_hash")!=previous or event.get("event_id") in seen: raise LifecycleError("REGISTRY_EVENT_CHAIN_INVALID","event chain is not contiguous")
        if semantic_hash({k:v for k,v in event.items() if k not in {"event_hash"}})!=event.get("event_hash"): raise LifecycleError("REGISTRY_EVENT_CHAIN_INVALID","event hash mismatch")
        if event.get("content_digest") != event.get("semantic_event_hash") or event.get("event_id") != stable_urn("registry-event", {"semantic_event_hash": event.get("semantic_event_hash")}):
            raise LifecycleError("REGISTRY_EVENT_CHAIN_INVALID", "event semantic identity mismatch")
        previous=event["event_hash"]; seen.add(event["event_id"]); p=event.get("payload",{}); subject=p.get("subject_id")
        typ=event["event_type"]
        bucket={"PackageImported":"packages","FeedbackRecorded":"feedback","ChangeProposalCreated":"changes","ConsumerRegistered":"consumers","ReleaseCandidateCreated":"candidates","ReleaseReviewInitialized":"reviews","ReleasePublished":"releases","EnvironmentCreated":"environments","ActivationProposed":"proposals"}.get(typ)
        if bucket and subject:
            projection = p
            folders = {"packages": "records/packages", "feedback": "records/feedback", "changes": "records/changes", "consumers": "records/consumers", "candidates": "records/release-candidates", "reviews": "records/release-reviews", "releases": "records/releases", "environments": "records/environments"}
            folder = root / folders.get(bucket, "")
            for candidate in sorted(folder.glob("*.json")) if folder.is_dir() else ():
                try:
                    loaded = json.loads(candidate.read_bytes())
                except (OSError, json.JSONDecodeError):
                    continue
                identity_key = {"packages":"record_id","feedback":"feedback_id","changes":"change_proposal_id","consumers":"consumer_id","candidates":"release_candidate_id","reviews":"review_id","releases":"release_id","environments":"environment_id"}.get(bucket, "")
                if loaded.get(identity_key) == subject:
                    projection = loaded
                    break
            state[bucket][subject] = projection
    if head["event_count"]!=len(events) or head["head_event_hash"]!=previous: raise LifecycleError("REGISTRY_EVENT_CHAIN_INVALID","registry head does not match events")
    return {k:sorted(v.values(),key=lambda x:json.dumps(x,sort_keys=True)) for k,v in state.items()}
def _verify_head(head: dict) -> None:
    core = {k: head.get(k) for k in ("manifest_kind", "schema_version", "registry_id", "generation", "event_count", "head_event_id", "head_event_hash", "snapshot_id", "snapshot_semantic_hash")}
    digest = semantic_hash(core)
    if head.get("content_digest") != digest or head.get("head_id") != stable_urn("registry-head", {"content_digest": digest}):
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "registry head identity mismatch")
    expected_head_hash = semantic_hash({"registry_id": head.get("registry_id"), "generation": head.get("generation"), "event_count": head.get("event_count"), "head_event_hash": head.get("head_event_hash")})
    if head.get("head_hash") != expected_head_hash:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "registry head hash mismatch")


def _verify_snapshot(snap: dict) -> None:
    digest = semantic_hash({k: v for k, v in snap.items() if k not in {"content_digest", "snapshot_id"}})
    if snap.get("content_digest") != digest or snap.get("snapshot_id") != stable_urn("registry-snapshot", {"content_digest": digest}):
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "registry snapshot identity mismatch")


def verify_registry(root):
    root=Path(root); state=replay(root); manifest=read(root,"registry-manifest.json"); head=read(root,"state/registry-head.json"); snap=read(root,"state/registry-snapshot.json")
    verify(manifest, contract="ontology-registry-manifest", registry_id=manifest.get("registry_id"))
    _verify_head(head); _verify_snapshot(snap)
    if head.get("snapshot_id") is not None and head.get("snapshot_id") != snap.get("snapshot_id"):
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "head does not point at snapshot")
    folders = {
        "packages": "records/packages", "feedback": "records/feedback", "changes": "records/changes",
        "consumers": "records/consumers", "candidates": "records/release-candidates", "reviews": "records/release-reviews",
        "releases": "records/releases", "environments": "records/environments",
    }
    for bucket in folders:
        for row in state.get(bucket, []):
            try: verify(row, contract={"packages":"registered-package-record", "feedback":"feedback-record", "changes":"change-proposal", "consumers":"consumer-manifest", "candidates":"release-candidate", "reviews":"release-review-decision-log", "releases":"release-manifest", "environments":"environment-manifest"}[bucket], registry_id=manifest.get("registry_id"))
            except LifecycleError as exc: raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"invalid {bucket} record") from exc
    from .index import verify_indexes
    verify_indexes(root)
    return {"status":"VALID","registry_id":head["registry_id"],"event_count":head["event_count"],"snapshot_id":snap.get("snapshot_id"),"state":state}
