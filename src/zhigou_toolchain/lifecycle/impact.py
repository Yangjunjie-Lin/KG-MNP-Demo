from __future__ import annotations

from pathlib import Path

from .registry.manifest import load_manifest
from .store import bind_identity, list_records, next_id, save


def build_dependency_graph(workspace: Path | str) -> dict:
    root=Path(workspace); consumers=list_records(root,"records/consumers"); nodes=[]; edges=[]
    for c in consumers:
        nodes.append({"node_id":c["consumer_id"],"node_type":"CONSUMER","artifact_ref":c["consumer_id"]})
        for package in c.get("package_constraints",{}).get("package_ids",[]): edges.append({"source":c["consumer_id"],"target":package,"edge_type":"REQUIRES_PACKAGE"})
        for term in c.get("required_term_iris",[]): nodes.append({"node_id":term,"node_type":"ONTOLOGY_TERM","artifact_ref":term}); edges.append({"source":c["consumer_id"],"target":term,"edge_type":"REQUIRES_TERM"})
    core={"registry_id":load_manifest(root)["registry_id"],"registry_head_hash":"", "consumer_manifest_ids":sorted(c["consumer_id"] for c in consumers),"nodes":sorted(nodes,key=lambda x:x["node_id"]),"edges":sorted(edges,key=lambda x:(x["source"],x["target"])),"dangling_nodes":[],"illegal_cycles":[],"completeness_scope":"REGISTRY_LOCAL"}
    core["snapshot_id"]=next_id("dependency-graph-snapshot",core); save(root,f"state/dependency-graph-{core['snapshot_id'].rsplit(':',1)[1]}.json",{"manifest_kind":"KG_MNP_DEPENDENCY_GRAPH_SNAPSHOT","schema_version":"1.0.0",**core}); return core

def analyze_impact(workspace: Path | str, *, semantic_diff: dict, graph: dict | None = None) -> dict:
    root=Path(workspace); graph=graph or build_dependency_graph(root); affected_terms=set(semantic_diff.get("affected_iris",[])); consumers=[]
    for n in graph.get("nodes",[]):
        if n.get("node_type")=="CONSUMER" and any(e["source"]==n["node_id"] and e["target"] in affected_terms for e in graph.get("edges",[])): consumers.append(n["node_id"])
    classification=semantic_diff.get("overall_classification","UNKNOWN_REQUIRES_REVIEW"); risk="HIGH" if classification in {"BREAKING","POTENTIALLY_BREAKING"} else "LOW"
    value={"manifest_kind":"KG_MNP_IMPACT_ANALYSIS_REPORT","schema_version":"1.0.0","registry_id":load_manifest(root)["registry_id"],"semantic_diff_id":semantic_diff.get("diff_id",""),"dependency_graph_snapshot_id":graph.get("snapshot_id",""),"affected_packages":[],"affected_releases":[],"affected_consumers":sorted(consumers),"affected_environments":[],"affected_terms":sorted(affected_terms),"affected_mappings":[],"affected_competency_questions":[],"migration_requirements":[],"regression_requirements":[],"unknown_impacts":[],"risk_summary":{"overall":risk,"reasons":["semantic-diff-classification"]},"completeness_scope":"REGISTRY_LOCAL","status":"COMPLETE"}
    bind_identity(value, "impact_id", "impact-analysis-report"); save(root,f"records/impacts/{value['impact_id'].rsplit(':',1)[1]}.json",value); return value
