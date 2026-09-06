from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import LifecycleError
from .registry.events import append_event
from .security import inert_intent
from .store import bind_identity, list_records, save

FOLDER="records/feedback"

def add_feedback(workspace: Path | str, *, feedback_type: str, target_package_id: str, observations: list[str] | None = None, severity: str = "INFO", source_type: str = "HUMAN", reported_by: str = "operator", **extra: Any) -> dict[str, Any]:
    root=Path(workspace); observations=observations or []
    inert_intent(observations)
    if not target_package_id.startswith("urn:kg-mnp:"): raise LifecycleError("LIFECYCLE_IDENTITY_INVALID", "target_package_id must be a KG-MNP URN")
    value={"manifest_kind":"KG_MNP_FEEDBACK_RECORD","schema_version":"1.0.0","registry_id":__import__("kg_mnp.lifecycle.registry.manifest",fromlist=["load_manifest"]).load_manifest(root)["registry_id"],"feedback_type":feedback_type,"severity":severity,"source_type":source_type,"target_package_id":target_package_id,"target_release_id":None,"target_environment_id":None,"observations":sorted(set(observations)),"metric_records":extra.pop("metric_records",[]),"artifact_refs":extra.pop("artifact_refs",[]),"evidence_refs":extra.pop("evidence_refs",[]),"reported_by":reported_by,"status":"OPEN",**extra}
    bind_identity(value, "feedback_id", "feedback-record"); save(root, f"{FOLDER}/{value['feedback_id'].rsplit(':',1)[1]}.json", value); append_event(root,"FeedbackRecorded",{"subject_id":value["feedback_id"],"target_package_id":target_package_id}); return value

def list_feedback(workspace: Path | str) -> list[dict[str, Any]]: return list_records(workspace,FOLDER)
def inspect_feedback(workspace: Path | str, feedback_id: str) -> dict[str, Any]:
    for row in list_feedback(workspace):
        if row.get("feedback_id")==feedback_id:return row
    raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "feedback record not found")
