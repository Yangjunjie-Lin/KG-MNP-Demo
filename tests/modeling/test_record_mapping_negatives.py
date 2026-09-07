
import pytest

from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.providers.record_mapping import record_mapping_drafts


def cell(row,column,value):
    return {"item_kind":"table-cell","source_ids":["source"],"item_id":f"item-{row}-{column}","evidence_refs":[f"evidence-{row}-{column}"],
            "payload":{"row":row,"column":column,"value":{"normalized_lexical_value":value}}}


def fixture():
    rules={"profile":"evidence-record-mapping-v1","tables":[{"table_id":"records","source_name":"records.csv","class_iri":"urn:Class","id_field":"code","literals":{},"references":[]}]}
    dataset={"items":[cell(1,1,"code"),cell(2,1,"A")]}
    return {"rules":rules,"datasets":[dataset],"source_names":{"source":"records.csv"},"namespace":"urn:record:","baseline":{"elements":[{"iri":"urn:Class","element_id":"class","element_kind":"CLASS"}]},"question_ids":[],"asset_id":"mapping"}


@pytest.mark.parametrize("missing",["",None,"../path"])
def test_record_identifiers_must_be_nonempty_and_portable(missing):
    args=fixture();args["datasets"][0]["items"][1]["payload"]["value"]["normalized_lexical_value"]=missing
    with pytest.raises(ModelingControlError,match="IDENTIFIER_REQUIRED"):record_mapping_drafts(**args)


def test_duplicate_identity_is_not_silently_merged():
    args=fixture();args["datasets"][0]["items"].append(cell(3,1,"A"))
    with pytest.raises(ModelingControlError,match="IDENTITY_CONFLICT"):record_mapping_drafts(**args)


def test_missing_reference_target_is_not_invented():
    args=fixture();args["rules"]["tables"][0]["references"]=[{"field":"code","target_table":"absent","predicate_iri":"urn:link"}]
    with pytest.raises(ModelingControlError,match="REFERENCE_INVALID"):record_mapping_drafts(**args)
