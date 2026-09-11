"""Project-scoped, commit-fenced temporary candidate validation."""
from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService
from zhigou_toolchain.modeling.five_stage.contracts import artifact, bind_job, receipt
from zhigou_toolchain.modeling.five_stage.semantic_check import check_graphs, integrity
from zhigou_toolchain.semantic_kernel.baseline import load_baseline_closure

from .errors import ServiceBoundaryError


def execute(app, project, request, principal):
    from importlib.metadata import version

    from .modeling import _datasets

    modeling = ModelingWorkspaceService(project.root)
    queue = modeling.find_artifact(request.parameters["review_id"])
    proposal = modeling.find_artifact(queue["proposal_id"])
    scope = modeling.find_artifact(proposal["scope_id"])
    ids = set(request.parameters["candidate_ids"])
    all_candidates = [c for key in ("tbox_candidates", "abox_candidates", "mapping_candidates", "shacl_candidates") for c in proposal[key]]
    candidates = [c for c in all_candidates if c["candidate_id"] in ids]
    if len(candidates) != len(ids) or not ids:
        raise ServiceBoundaryError("CANDIDATE_SELECTION_INVALID", "select candidates from this review queue", status_code=422)
    if proposal["conflicts"]:
        raise ServiceBoundaryError("UNRESOLVED_ALTERNATIVES", "Resolve mutually exclusive proposal alternatives before semantic checks", status_code=422)
    datasets = _datasets(modeling, scope)
    session = stable_urn("modeling-session", {"project_id": project.project_id, "scope_id": scope["scope_id"]})
    def make(value, step, kind="REPORT"):
        return artifact(value, project_id=project.project_id, session_id=session, step_id=step, produced_by=request.operation_id, data_kind=kind)
    source = make(candidates, "3.6", "MODELING_CANDIDATE")
    try:
        checked = make(integrity(candidates, {e["evidence_id"] for d in datasets for e in d["evidence_records"]}), "4.1")
    except ImportError:
        raise ServiceBoundaryError("SEMANTIC_DEPENDENCY_MISSING", "Explicitly install modeling-analysis for task dependency checks", status_code=422) from None
    r1 = receipt("4.1", [source], [checked], configuration={"selection": sorted(ids)}, tools={"networkx": version("networkx")}, scope="Explicit selected candidate construction dependencies and evidence closure.")
    r1["validation_status"] = checked["content"]["status"]
    artifacts, receipts = [source, checked], [r1]
    if checked["content"]["status"] == "PASS":
        baseline = load_baseline_closure(modeling.project_lock, domain_packs_root=DomainPackRegistry(app.configuration.domain_packs_root).root)
        try:
            result = check_graphs(candidates, baseline=baseline, namespace=scope["namespace_policy"]["default_namespace"], reasoner_jar=app.configuration.reasoner_jar)
        except (ValueError, OSError) as exc:
            raise ServiceBoundaryError("SEMANTIC_CHECK_BLOCKED", "Candidate conversion, dependency or semantic tool failed", status_code=422) from exc
        output = make(result, "4.2")
        artifacts.append(output)
        r2 = receipt("4.2", [source, checked], [output], configuration={"inference": "RDFS", "owl": "DL", "metadata_in_owl": False},
                     tools={"rdflib": version("rdflib"), "pyshacl": version("pyshacl")}, scope="Selected candidate graphs compiled using the same production TBox/ABox/SHACL functions; no approval or final artifact issued.")
        r2["validation_status"] = result["status"]
        receipts.append(r2)
    result = {"schema_version": "1.0.0", "session_id": session, "step_runs": bind_job(receipts, request.idempotency_key), "artifacts": artifacts, "authority": "OBSERVATION_ONLY"}
    identifier = stable_urn("semantic-check", {"artifacts": [a["ref"] for a in artifacts], "job_id": request.idempotency_key})
    modeling.write_build(identifier, {"semantic-check.json": result})
    return {"five_stage": result}
