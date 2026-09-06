from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.document_io import atomic_write_json

from ..contracts import canonicalize
from ..errors import LifecycleError
from ._common import lock, read, write


def read_events(root):
    root=Path(root); rows=[]
    for path in sorted((root/"events").glob("*.json")):
        rows.append(json.loads(path.read_bytes()))
    return rows
def _event(root,event_type,payload,observed_at=None):
    manifest=read(root,"registry-manifest.json"); head=read(root,"state/registry-head.json"); seq=head["event_count"]+1; observed_at=observed_at or datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00","Z")
    core={"manifest_kind":"KG_MNP_REGISTRY_EVENT","schema_version":"1.0.0","registry_id":manifest["registry_id"],"sequence":seq,"event_type":event_type,"previous_event_hash":head["head_event_hash"],"previous_semantic_event_hash":None,"payload":payload,"observed_at":observed_at}
    semantic=semantic_hash({k:v for k,v in core.items() if k not in {"observed_at","previous_event_hash","previous_semantic_event_hash"}})
    event={**core,"content_digest":semantic,"semantic_event_hash":semantic,"event_id":stable_urn("registry-event",{"semantic_event_hash":semantic})}
    event["event_hash"]=semantic_hash(event)
    return event
def append_event(root,event_type,payload,*,observed_at=None):
    root=Path(root)
    with lock(root):
        event=_event(root,event_type,canonicalize(payload),observed_at); head=read(root,"state/registry-head.json"); expected=root/"events"/f"{event['sequence']:012d}-{event['event_id'].rsplit(':',1)[1]}.json"
        if expected.exists(): raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED","event replay collision")
        atomic_write_json(expected,event); new={**head,"generation":head["generation"]+1,"event_count":event["sequence"],"head_event_id":event["event_id"],"head_event_hash":event["event_hash"],"head_hash":semantic_hash({"registry_id":head["registry_id"],"generation":head["generation"]+1,"event_count":event["sequence"],"head_event_hash":event["event_hash"]})}; new["content_digest"]=semantic_hash({k:v for k,v in new.items() if k not in {"content_digest","head_hash","head_id"}}); new["head_id"]=stable_urn("registry-head",{"content_digest":new["content_digest"]}); write(root,"state/registry-head.json",new); return event
