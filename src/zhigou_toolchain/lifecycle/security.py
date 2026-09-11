"""Offline safety and registry path confinement."""
from __future__ import annotations

import re
import stat
from pathlib import Path, PurePosixPath

from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.semantic_kernel.security import assert_read_only_query

from .errors import LifecycleError

ID_RE = re.compile(r"^urn:kg-mnp:[a-z0-9-]+:[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXEC_RE = re.compile(r"(?i)(?:rdf|turtle|sparql|python|shell|powershell|subprocess|exec\(|eval\(|os\.system|json\s*patch|insert\s+data|delete\s+where)")
def storage_key(identifier):
    if not isinstance(identifier,str) or not ID_RE.fullmatch(identifier): raise LifecycleError("LIFECYCLE_CONTRACT_INVALID","invalid content-addressed identifier")
    return identifier.rsplit(":",1)[1]
def safe_name(value):
    if not isinstance(value,str) or not NAME_RE.fullmatch(value): raise LifecycleError("LIFECYCLE_CONTRACT_INVALID","unsafe lifecycle name")
    return value
def safe_relative(value):
    if not isinstance(value,str) or not value or "\\" in value or PurePosixPath(value).is_absolute() or ":" in value or any(x in {"", ".", ".."} for x in value.split("/")): raise LifecycleError("LIFECYCLE_PATH_INVALID","unsafe relative path")
    return value
def assert_no_links(path: Path):
    for p in [path,*path.parents]:
        try: info=p.lstat()
        except FileNotFoundError: continue
        if stat.S_ISLNK(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1): raise LifecycleError("LIFECYCLE_PATH_INVALID","symlink or hard-link authority rejected")
def child(root: Path, relative: str):
    safe_relative(relative); assert_no_links(root); p=root.joinpath(*relative.split("/")); assert_no_links(p)
    if root.resolve() not in p.resolve().parents: raise LifecycleError("LIFECYCLE_PATH_INVALID","storage path escapes registry")
    return p
def document(path: Path, max_bytes=16777216):
    try:
        assert_no_links(path); value=read_document(path,max_bytes=max_bytes)
        if not isinstance(value,dict): raise TypeError("object required")
        return value
    except Exception as exc: raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED","invalid authority document") from exc
def inert_intent(values):
    if any(EXEC_RE.search(str(v)) for v in values): raise LifecycleError("LIFECYCLE_CONTRACT_INVALID","executable change intent rejected")
def readonly_query(query, limits):
    try: return assert_read_only_query(query,max_characters=limits["max_query_characters"],max_path_depth=limits["max_query_path_depth"])
    except Exception as exc: raise LifecycleError("CONSUMER_MANIFEST_INVALID","unsafe read-only query") from exc
def human(reviewer_id, reviewer_type="HUMAN", explicit=True):
    if reviewer_type != "HUMAN" or explicit is not True or re.search(r"(?i)(agent|provider|system|bot|auto)", reviewer_id): raise LifecycleError("LIFECYCLE_REVIEW_INVALID","explicit human reviewer required")
