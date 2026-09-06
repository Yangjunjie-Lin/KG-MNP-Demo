from __future__ import annotations

import hashlib
from pathlib import Path

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.document_io import atomic_write_json

from ..security import child


def aid(kind, core): return stable_urn(kind, {"content_digest": semantic_hash(core)})
def artifact(kind, core, ident=None):
    core={k:v for k,v in core.items() if k not in {"content_digest", "id"}}
    digest=semantic_hash(core); value={**core,"content_digest":digest}
    value["id" if ident is None else ident]=stable_urn(kind,{"content_digest":digest}); return value
def write(root: Path, rel: str, value: dict):
    path=child(root,rel); path.parent.mkdir(parents=True,exist_ok=True); atomic_write_json(path,value); return path
def read(root: Path, rel: str):
    from ..security import document
    return document(child(root,rel))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def lock(root):
    from ..transactions import registry_lock
    return registry_lock(root)
