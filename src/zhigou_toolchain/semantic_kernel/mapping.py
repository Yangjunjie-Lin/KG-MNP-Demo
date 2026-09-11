"""Compile confirmed mapping candidates into inert declarative JSON."""

from __future__ import annotations

import re
from typing import Any

from rdflib import OWL, RDF, Graph, URIRef

from .contracts import finalize_artifact
from .identifiers import semantic_id

_PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
_DANGEROUS = re.compile(r"(?:\(|\)|\[|\]|\.|`|\$\(|__|;|\b(?:python|shell|select|insert|delete|update)\b)", re.IGNORECASE)


def _template(candidate: dict[str, Any]) -> str | None:
    body = candidate["body"]
    if body["candidate_type"] != "IRI_TEMPLATE":
        return None
    values = body.get("values", [])
    value = values[0] if values else body.get("target_iri")
    if not isinstance(value, str) or _DANGEROUS.search(value):
        raise ValueError("unsafe IRI template")
    residual = _PLACEHOLDER.sub("placeholder", value)
    if "{" in residual or "}" in residual:
        raise ValueError("unsafe IRI template placeholder")
    return value


def compile_mapping_plan(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    source_plan_id: str,
    review_decision_id: str,
    effective_tbox: Graph,
) -> dict[str, Any]:
    mappings = []
    for candidate in sorted(candidates, key=lambda item: item["candidate_id"]):
        body = candidate["body"]
        target = body.get("target_iri")
        required_type = {
            "RECORD_TO_CLASS": OWL.Class,
            "FIELD_TO_DATA_PROPERTY": OWL.DatatypeProperty,
            "REFERENCE_TO_OBJECT_PROPERTY": OWL.ObjectProperty,
        }.get(body["candidate_type"])
        if required_type is not None and (
            not isinstance(target, str)
            or (URIRef(target), RDF.type, required_type) not in effective_tbox
        ):
            raise ValueError("mapping target is missing or has the wrong semantic type")
        values = []
        if body["candidate_type"] == "VALUE_MAPPING":
            seen = set()
            for value in body.get("values", []):
                source, separator, target = value.partition("=")
                if not separator:
                    source = target = value
                if source in seen:
                    raise ValueError("duplicate value-mapping key")
                seen.add(source)
                values.append({"source": source, "target": target})
        mapping_basis = {"candidate_id": candidate["candidate_id"], "body": body}
        mapping_id = semantic_id("compiled-mapping", mapping_basis)
        mappings.append({
            "compiled_mapping_id": mapping_id,
            "source_confirmed_item_id": candidate["candidate_id"],
            "mapping_kind": body["candidate_type"],
            "source_kgir_item_refs": candidate["kg_ir_item_refs"],
            "source_evidence_refs": candidate["evidence_refs"],
            "target_class_iri": target if body["candidate_type"] == "RECORD_TO_CLASS" else None,
            "target_property_iri": target if body["candidate_type"] in {"FIELD_TO_DATA_PROPERTY", "REFERENCE_TO_OBJECT_PROPERTY"} else None,
            "conversion_policy": body["conversion_policy"],
            "null_policy": body["null_policy"],
            "value_map": values,
            "iri_template": _template(candidate),
            "dependencies": candidate["dependency_candidate_refs"],
            "review_decision_ref": review_decision_id,
            "provenance_ref": semantic_id("mapping-provenance", mapping_basis),
        })
    core = {"manifest_kind": "KG_MNP_MAPPING_PLAN", "schema_version": "1.0.0", "source_plan_id": source_plan_id, "execution_policy": "DECLARATIVE_NOT_EXECUTED", "mappings": mappings, "mapping_count": len(mappings)}
    return finalize_artifact(core, id_field="mapping_plan_id", urn_kind="mapping-plan", contract="mapping-plan")
