from __future__ import annotations

from pathlib import Path

import yaml

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn

from ..errors import LifecycleError
from ..security import assert_no_links, safe_name
from ._common import read, write


def registry_id(registry_name, project_id, policy_digest): return stable_urn("ontology-registry", {"registry_name":registry_name,"project_id":project_id,"registry_scope":"PROJECT_LOCAL","policy_digest":policy_digest})
def _policy(root):
    source=Path(__file__).resolve().parents[1]/"resources/registry-policy-1.0.0.yaml"; data=yaml.safe_load(source.read_text(encoding="utf-8")); core={k:v for k,v in data.items() if k not in {"policy_id","content_digest"}}; digest=semantic_hash(core); data["content_digest"]=digest; data["policy_id"]=stable_urn("ontology-registry-policy",{"content_digest":digest}); return data
def init_registry(workspace: Path|str, *, registry_name="local", project_id="project", accepted_ontology_iris=(), accepted_package_names=(), created_by="operator"):
    requested=Path(workspace); assert_no_links(requested); root=requested.resolve(); assert_no_links(root)
    if not str(project_id).startswith("urn:kg-mnp:"):
        project_id = stable_urn("project", {"name": str(project_id)})
    if root.exists() and any(root.iterdir()): raise LifecycleError("LIFECYCLE_REGISTRY_INVALID","registry directory must be empty")
    root.mkdir(parents=True,exist_ok=True); policy=_policy(root); pd=policy["content_digest"]; safe_name(registry_name)
    manifest_core={"manifest_kind":"KG_MNP_ONTOLOGY_REGISTRY","schema_version":"1.0.0","registry_format_version":"1.0.0","registry_name":registry_name,"project_id":project_id,"registry_scope":"PROJECT_LOCAL","policy_id":policy["policy_id"],"policy_digest":pd,"accepted_package_format_versions":["1.0.0"],"accepted_ontology_iris":sorted(accepted_ontology_iris),"accepted_package_names":sorted(accepted_package_names),"storage_profile":"CONTENT_ADDRESSED_LOCAL","created_by":created_by}
    manifest={**manifest_core,"content_digest":semantic_hash(manifest_core),"registry_id":registry_id(registry_name,project_id,pd)}
    for d in ("events","state","objects/sha256","records/packages","records/feedback","records/changes","records/change-evaluations","records/diffs","records/impacts","records/regressions","records/version-compatibility","records/release-candidates","records/release-reviews","records/releases","records/attestations","records/consumers","records/environments","records/activation-proposals","records/activation-reviews","records/activation-receipts","indexes","packages"):
        (root/d).mkdir(parents=True,exist_ok=True)
    write(root,"registry-manifest.json",manifest); write(root,"policy/registry-policy.json",policy)
    snap={"manifest_kind":"KG_MNP_REGISTRY_SNAPSHOT","schema_version":"1.0.0","registry_id":manifest["registry_id"],"registry_manifest_digest":manifest["content_digest"],"policy_digest":pd,"package_records":[],"feedback_records":[],"change_proposals":[],"consumer_manifests":[],"release_candidates":[],"release_reviews":[],"releases":[],"environments":[],"activation_proposals":[],"authority_records":[],"event_count":0,"head_event_hash":None}; snap["content_digest"]=semantic_hash(snap); snap["snapshot_id"]=stable_urn("registry-snapshot",{"content_digest":snap["content_digest"]}); write(root,"state/registry-snapshot.json",snap)
    head_core={"manifest_kind":"KG_MNP_REGISTRY_HEAD","schema_version":"1.0.0","registry_id":manifest["registry_id"],"generation":0,"event_count":0,"head_event_id":None,"head_event_hash":None,"snapshot_id":snap["snapshot_id"],"snapshot_semantic_hash":snap["content_digest"]}
    head_digest=semantic_hash(head_core); head={**head_core,"head_id":stable_urn("registry-head",{"content_digest":head_digest}),"content_digest":head_digest,"head_hash":semantic_hash({"registry_id":manifest["registry_id"],"generation":0,"event_count":0,"head_event_hash":None})}; write(root,"state/registry-head.json",head)
    return manifest
def load_manifest(workspace):
    root=Path(workspace).resolve(); value=read(root,"registry-manifest.json")
    if value.get("manifest_kind")!="KG_MNP_ONTOLOGY_REGISTRY": raise LifecycleError("LIFECYCLE_REGISTRY_INVALID","registry manifest invalid")
    return value
