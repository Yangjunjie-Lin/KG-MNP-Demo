"""Data-only record mappings to evidence-bound proposal drafts, never RDF writes."""
from __future__ import annotations

import re

from ..errors import ModelingControlError
from .models import candidate_body, candidate_draft


def record_mapping_drafts(*,rules:dict,datasets:list[dict],source_names:dict[str,str],namespace:str,baseline:dict,question_ids:list[str],asset_id:str|None)->list[dict]:
    if set(rules)!={"profile","tables"} or rules["profile"]!="evidence-record-mapping-v1":
        raise ModelingControlError("unsupported declarative record mapping")
    elements={e["iri"]:e for e in baseline["elements"]}
    cells={}
    for dataset in datasets:
        for item in dataset["items"]:
            if item["item_kind"]=="table-cell":
                for source in item["source_ids"]:
                    cells.setdefault(source,[]).append(item)
    records={}; tables={}; drafts=[]
    for table in rules["tables"]:
        if set(table)!={"table_id","source_name","class_iri","id_field","literals","references"}:
            raise ModelingControlError("closed record mapping fields required")
        key=table["table_id"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,50}",key) or key in tables:
            raise ModelingControlError("invalid or duplicate mapping table")
        if table["class_iri"] not in elements or elements[table["class_iri"]]["element_kind"]!="CLASS":
            raise ModelingControlError("mapping class is not a locked baseline class")
        tables[key]=table
        matched=[source for source,name in source_names.items() if name==table["source_name"]]
        if len(matched)!=1:raise ModelingControlError("mapped source must be present exactly once")
        by_row={}
        for item in cells.get(matched[0],[]):
            by_row.setdefault(item["payload"]["row"],{})[item["payload"]["column"]]=item
        headers={column:cell["payload"]["value"]["normalized_lexical_value"] for column,cell in by_row.get(1,{}).items()}
        if len(set(headers.values()))!=len(headers):raise ModelingControlError("duplicate CSV header")
        for ordinal,row in sorted(by_row.items()):
            if ordinal==1:continue
            fields={headers[column]:item for column,item in row.items() if column in headers}
            identifier=fields.get(table["id_field"],{}).get("payload",{}).get("value",{}).get("normalized_lexical_value")
            if not isinstance(identifier,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}",identifier):
                raise ModelingControlError("MAPPING_IDENTIFIER_REQUIRED: portable nonempty identifier required")
            if (key,identifier) in records:raise ModelingControlError("MAPPING_IDENTITY_CONFLICT: duplicate record identifier")
            records[key,identifier]={"fields":fields,"iri":namespace+key+"-"+identifier,"ref":"record-"+key+"-"+identifier,"id_cell":fields[table["id_field"]]}
    def draft(record,ref,kind,body,cell,dependencies=(),baseline_refs=()):
        return candidate_draft(draft_ref=ref,draft_kind=kind,candidate_action="ALIGN_TO_EXISTING" if kind=="MAPPING" else "ASSERT",
            body=body,rationale="Explicit declarative record mapping proposal; evidence-bound and review-required",
            kg_ir_item_refs=[cell["item_id"]],evidence_refs=cell["evidence_refs"],domain_asset_refs=[asset_id] if asset_id else [],
            competency_question_refs=question_ids,baseline_element_refs=baseline_refs,dependency_draft_refs=dependencies)
    for (key,identifier),record in sorted(records.items()):
        table=tables[key]; cell=record["id_cell"]; ref=record["ref"]
        drafts.append(draft(record,ref,"ABOX",candidate_body(candidate_type="INDIVIDUAL",subject_iri=record["iri"]),cell))
        drafts.append(draft(record,ref+"-class","ABOX",candidate_body(candidate_type="CLASS_ASSERTION",subject_iri=record["iri"],object_iri=table["class_iri"]),cell,[ref],[elements[table["class_iri"]]["element_id"]]))
        for field,predicate in sorted(table["literals"].items()):
            element=elements.get(predicate)
            if not element or element["element_kind"]!="DATA_PROPERTY":raise ModelingControlError("literal mapping requires baseline data property")
            field_cell=record["fields"].get(field)
            if field_cell is None:raise ModelingControlError("MAPPING_FIELD_MISSING: declared field absent")
            mapping_ref=ref+"-mapping-"+field
            drafts.append(draft(record,mapping_ref,"MAPPING",candidate_body(candidate_type="FIELD_TO_DATA_PROPERTY",source_field=field,target_iri=predicate,conversion_policy="IDENTITY",null_policy="OMIT"),field_cell,baseline_refs=[element["element_id"]]))
            value=field_cell["payload"]["value"]["normalized_lexical_value"]
            if value is not None:
                drafts.append(draft(record,ref+"-value-"+field,"ABOX",candidate_body(candidate_type="DATA_PROPERTY_ASSERTION",subject_iri=record["iri"],predicate_iri=predicate,literal={"lexical_value":value,"datatype_iri":"http://www.w3.org/2001/XMLSchema#string","language":None}),field_cell,[ref,mapping_ref],[element["element_id"]]))
        for link in table["references"]:
            if set(link)!={"field","target_table","predicate_iri"}:raise ModelingControlError("closed reference mapping fields required")
            field_cell=record["fields"].get(link["field"])
            value=field_cell.get("payload",{}).get("value",{}).get("normalized_lexical_value") if field_cell else None
            target=records.get((link["target_table"],value))
            if target is None:raise ModelingControlError("MAPPING_REFERENCE_INVALID: referenced record does not exist")
            element=elements.get(link["predicate_iri"])
            if not element or element["element_kind"]!="OBJECT_PROPERTY":raise ModelingControlError("reference requires baseline object property")
            drafts.append(draft(record,ref+"-link-"+link["field"],"ABOX",candidate_body(candidate_type="OBJECT_PROPERTY_ASSERTION",subject_iri=record["iri"],predicate_iri=link["predicate_iri"],object_iri=target["iri"]),field_cell,[ref,target["ref"]],[element["element_id"]]))
    return drafts
