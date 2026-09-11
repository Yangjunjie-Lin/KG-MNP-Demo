"""Closed named-graph role vocabulary."""

GRAPH_ROLES = (
    "ontology-module",
    "effective-tbox",
    "abox",
    "compiled-shapes",
    "effective-shapes",
    "mapping-provenance",
    "statement-provenance",
    "evidence-lineage",
    "review-audit",
    "compilation-activity",
)


def validate_graph_role(role: str) -> str:
    if role not in GRAPH_ROLES:
        raise ValueError(f"unsupported named graph role: {role}")
    return role
