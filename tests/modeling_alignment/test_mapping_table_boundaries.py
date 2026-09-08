"""Actual ingestion keeps field headers scoped to Source and sheet evidence."""
from copy import deepcopy

import pytest

from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.mappings import build_field_mapping_candidates
from kg_mnp.modeling.control_plane.providers.record_mapping import record_mapping_drafts


def ingest(workspace, files):
    store=SourceStore(workspace)
    sources=[store.add_file(file).source for file in files]
    batch=store.create_batch([source['source_id'] for source in sources])
    plan=create_ingestion_plan(workspace,batch_id=batch['batch_id'])
    return execute_ingestion_plan(workspace,plan.plan['plan_id']).dataset,sources


def mappings(dataset):
    return build_field_mapping_candidates(kg_ir_datasets=[dataset],alignments={'alignments':[]},terminology={'terms':[]})['mappings']


def test_two_csv_headers_never_cross_source_boundaries(prompt03_workspace,tmp_path):
    left,right=tmp_path/'left.csv',tmp_path/'right.csv'
    left.write_text('left_field,common\nleft-value,a\n',encoding='utf-8')
    right.write_text('right_field,common\nright-value,b\n',encoding='utf-8')
    dataset,sources=ingest(prompt03_workspace,[left,right])
    expected={sources[0]['source_id']:'left_field',sources[1]['source_id']:'right_field'}
    items={item['item_id']:item for item in dataset['items']}
    result=mappings(dataset)
    assert len(result)==4
    for row in result:
        item=items[row['source_item_id']]
        assert row['source_field_name']==(expected[item['source_ids'][0]] if item['payload']['column']==1 else 'common')


@pytest.fixture
def sheets(prompt03_workspace,tmp_path):
    from openpyxl import Workbook
    book=Workbook()
    book.active.title='Left'
    book.active.append(['left_field'])
    book.active.append(['left-value'])
    right=book.create_sheet('Right')
    right.append(['right_field'])
    right.append(['right-value'])
    source=tmp_path/'two-sheets.xlsx'
    book.save(source)
    return ingest(prompt03_workspace,[source])


def test_spreadsheet_headers_are_bound_to_evidence_sheet(sheets):
    dataset,_=sheets
    items={item['item_id']:item for item in dataset['items']}
    evidence={row['evidence_id']:row for row in dataset['evidence_records']}
    result=mappings(dataset)
    assert len(result)==2
    for row in result:
        sheet=evidence[items[row['source_item_id']]['evidence_refs'][0]]['locator']['sheet']
        assert row['source_field_name']=={'Left':'left_field','Right':'right_field'}[sheet]


def test_conflicting_headers_in_one_table_are_not_last_writer_wins(sheets):
    dataset,_=sheets
    dataset=deepcopy(dataset)
    header=next(item for item in dataset['items'] if item['item_kind']=='table-cell' and item['payload']['row']==1)
    duplicate=deepcopy(header)
    duplicate['item_id']='urn:kg-mnp:kg-ir-item:'+'f'*64
    duplicate['payload']['value']['normalized_lexical_value']='conflicting-header'
    dataset['items'].append(duplicate)
    with pytest.raises(ModelingControlError,match='ambiguous table header'):
        mappings(dataset)


def test_closed_record_profile_refuses_ambiguous_multisheet_source(sheets):
    dataset,sources=sheets
    with pytest.raises(ModelingControlError,match='MAPPING_TABLE_AMBIGUOUS'):
        record_mapping_drafts(rules={'profile':'evidence-record-mapping-v1','tables':[{'table_id':'rows','source_name':'two-sheets.xlsx','class_iri':'urn:Thing','id_field':'left_field','literals':{},'references':[]}]},
            datasets=[dataset],source_names={sources[0]['source_id']:'two-sheets.xlsx'},namespace='urn:test:',
            baseline={'elements':[{'iri':'urn:Thing','element_kind':'CLASS','element_id':'urn:baseline:thing'}]},question_ids=[],asset_id=None)
