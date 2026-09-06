from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import LifecycleError
from .registry.events import append_event
from .registry.manifest import load_manifest
from .security import readonly_query
from .store import bind_identity, list_records, save

FOLDER="records/consumers"
def register_consumer(workspace: Path | str, *, consumer_name: str, consumer_type: str = "APPLICATION", ontology_iri: str, owner_label: str = "owner", criticality: str = "NORMAL", required_term_iris: list[str] | None = None, query_contracts: list[dict[str,Any]] | None = None, **extra: Any) -> dict[str,Any]:
    root=Path(workspace); m=load_manifest(root); rows=list_records(root,FOLDER)
    query_contracts = query_contracts or []
    for query in query_contracts:
        readonly_query(query.get("query_text", ""), query.get("resource_limits", {"max_query_characters": 100000, "max_query_path_depth": 16}))
    value={"manifest_kind":"KG_MNP_CONSUMER_MANIFEST","schema_version":"1.0.0","registry_id":m["registry_id"],"consumer_name":consumer_name,"consumer_type":consumer_type,"owner_label":owner_label,"criticality":criticality,"ontology_iri":ontology_iri,"package_constraints":extra.pop("package_constraints",{"package_names":[],"minimum_version":None,"maximum_version_exclusive":None,"package_ids":[]}),"required_term_iris":sorted(set(required_term_iris or [])),"required_graph_roles":extra.pop("required_graph_roles",[]),"required_mapping_ids":extra.pop("required_mapping_ids",[]),"required_cq_ids":extra.pop("required_cq_ids",[]),"query_contracts":query_contracts,"environment_refs":extra.pop("environment_refs",[]),"dependency_behavior":extra.pop("dependency_behavior","REQUIRE_EXPLICIT_COMPATIBILITY"),"status":"ACTIVE","supersedes_consumer_id":None,**extra}
    bind_identity(value, "consumer_id", "consumer-manifest")
    if any(r.get("consumer_name")==consumer_name and r.get("status")=="ACTIVE" for r in rows): raise LifecycleError("LIFECYCLE_CONFLICT","active consumer name already registered")
    save(root,f"{FOLDER}/{value['consumer_id'].rsplit(':',1)[1]}.json",value); append_event(root,"ConsumerRegistered",{"subject_id":value["consumer_id"]}); return value
def list_consumers(workspace): return list_records(workspace,FOLDER)
def inspect_consumer(workspace: Path | str, consumer_id: str) -> dict[str, Any]:
    for row in list_consumers(workspace):
        if row.get("consumer_id") == consumer_id:
            return row
    raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "consumer manifest not found")

def verify_consumer(value):
    if value.get("status") not in {"ACTIVE","SUPERSEDED","DISABLED"}: raise LifecycleError("LIFECYCLE_ARTIFACT_INVALID","invalid consumer status")
    return {"status":"VALID","consumer_id":value.get("consumer_id")}
