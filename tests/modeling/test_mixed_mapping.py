"""Data-only profile safety, typed conversions, exact evidence and references."""
from copy import deepcopy

import pytest

from kg_mnp.modeling.control_plane.errors import ModelingControlError
from kg_mnp.modeling.control_plane.providers.mixed_mapping import (
    input_inventory,
    match_template,
    mixed_mapping_drafts,
    template_slots,
    typed_value,
)
from tests.modeling_alignment.test_mapping_table_boundaries import ingest
from tests.services.test_mixed_source_workflow import MIN, mixed_files, profile


@pytest.fixture
def source_case(prompt03_workspace, tmp_path):
    files = []
    for filename, _, data in mixed_files():
        path = tmp_path / filename
        path.write_bytes(data)
        files.append(path)
    dataset, _ = ingest(prompt03_workspace, files)
    baseline = {'elements': [
        {'iri': MIN + 'Entity', 'element_kind': 'CLASS', 'element_id': 'urn:class'},
        {'iri': MIN + 'label', 'element_kind': 'DATA_PROPERTY', 'element_id': 'urn:label'},
        {'iri': 'urn:relates', 'element_kind': 'OBJECT_PROPERTY', 'element_id': 'urn:relates-element'}]}
    inventory = input_inventory([dataset])
    def generate(rules):
        return mixed_mapping_drafts(rules=rules, datasets=[dataset], baseline=baseline, namespace='urn:test:', question_ids=[])
    return inventory, generate


@pytest.mark.parametrize(('datatype', 'raw', 'expected'), [
    ('integer', '+002', '2'), ('decimal', '02.500', '2.5'), ('decimal', '-0.0', '0'),
    ('boolean', '1', 'true'), ('date', '2024-02-29', '2024-02-29'),
    ('dateTime', '2026-09-08T10:30:00Z', '2026-09-08T10:30:00Z'), ('string', '  原文  ', '  原文  ')])
def test_explicit_datatypes_canonicalize_without_guessing(datatype, raw, expected):
    assert typed_value(raw, datatype)['lexical_value'] == expected


@pytest.mark.parametrize(('datatype', 'raw'), [('integer', '1.0'), ('integer', '=1+1'), ('decimal', 'NaN'),
    ('decimal', '1e100000'), ('boolean', 'yes'), ('date', '2025-02-29'), ('dateTime', '2026-99-08T10:30:00Z')])
def test_invalid_typed_values_and_formulas_block(datatype, raw):
    with pytest.raises(ModelingControlError, match='MAPPING_DATATYPE_INVALID'):
        typed_value(raw, datatype)


def test_exact_prose_annotation_and_tampered_quote(source_case):
    inventory, generate = source_case
    rules = profile(inventory)
    rules['text_templates'] = []
    rules['text_records'] = []
    for index, item in enumerate(inventory['text_items']):
        slots = match_template(template_slots('实体 {id} 的标签为 {label}。'), item['text'])
        rules['text_records'].append({'record_id': f'annotation-{index}', 'class_iri': MIN+'Entity', 'identity_space': 'entities', 'id_field': 'id',
            'literals': {'label': {'predicate_iri': MIN+'label'}}, 'fields': [{**s, 'item_id': item['item_id']} for s in slots]})
    _, report = generate(rules)
    assert not report['unmapped_item_ids']
    rules['text_records'][0]['fields'][0]['quote'] = 'forged quote'
    with pytest.raises(ModelingControlError, match='MAPPING_EVIDENCE_INVALID'):
        generate(rules)


def test_missing_and_cross_dataset_evidence_rejected(source_case):
    inventory, generate = source_case
    rules = profile(inventory)
    rules['tables'][0]['source_id'] = 'urn:kg-mnp:source:' + 'f'*64
    with pytest.raises(ModelingControlError, match='MAPPING_TABLE_MISSING'):
        generate(rules)
    rules = profile(inventory)
    rules['exclusions'] = [{'item_id': 'urn:kg-mnp:kg-ir-item:' + 'f'*64, 'rationale': 'not actually in input'}]
    with pytest.raises(ModelingControlError, match='MAPPING_EXCLUSION_INVALID'):
        generate(rules)


def test_alias_cycles_multiple_classes_and_unknown_targets_block(source_case):
    inventory, generate = source_case
    rules = profile(inventory)
    rules['tables'][0]['identity_aliases'].append({'value': 'T001', 'canonical': 'legacy-A', 'rationale': 'bad cycle'})
    with pytest.raises(ModelingControlError, match='MAPPING_ALIAS_CONFLICT'):
        generate(rules)
    rules = profile(inventory)
    rules['tables'][0]['class_iri'] = 'urn:unknown-class'
    with pytest.raises(ModelingControlError, match='MAPPING_BASELINE_INVALID'):
        generate(rules)


def test_cross_source_reference_uses_canonical_keys_and_missing_target_blocks(source_case):
    inventory, generate = source_case
    rules = profile(inventory)
    rules['tables'][0]['references'] = [{'field': 'id', 'target_space': 'entities', 'predicate_iri': 'urn:relates'}]
    drafts, _ = generate(rules)
    links = [d for d in drafts if d['body']['candidate_type'] == 'OBJECT_PROPERTY_ASSERTION']
    assert links and links[0]['body']['subject_iri'] == links[0]['body']['object_iri']
    rules['tables'][0]['references'][0]['target_space'] = 'absent'
    with pytest.raises(ModelingControlError, match='MAPPING_REFERENCE_INVALID'):
        generate(rules)


def test_closed_profile_rejects_authority_and_exclusion_conflicts(source_case):
    inventory, generate = source_case
    rules = profile(inventory)
    malicious = deepcopy(rules)
    malicious['reviewer_roles'] = ['Administrator']
    with pytest.raises(ModelingControlError, match='MAPPING_PROFILE_INVALID'):
        generate(malicious)
    rules['exclusions'] = [{'item_id': inventory['text_items'][0]['item_id'], 'rationale': 'Cannot exclude evidence already mapped'}]
    with pytest.raises(ModelingControlError, match='MAPPING_EXCLUSION_INVALID'):
        generate(rules)


@pytest.mark.parametrize('template', ['{id}{label}', '{id} {id}', '(.*)', '{id} {nested.x}'])
def test_templates_are_not_regex_or_ambiguous_slot_programs(template):
    with pytest.raises(ModelingControlError, match='TEXT_TEMPLATE_INVALID'):
        template_slots(template)


def test_nonmatching_prose_is_not_claimed_as_understood():
    assert match_template(template_slots('实体 {id} 的标签为 {label}。'), '没有身份信息的任意说明段落') is None


def test_text_offsets_name_normalized_coordinates_and_retain_original_transform(prompt03_workspace, tmp_path):
    path = tmp_path / 'unicode.txt'
    path.write_text('实体 T001 的标签为 e\u0301。\n', encoding='utf-8')
    dataset, _ = ingest(prompt03_workspace, [path])
    inventory = input_inventory([dataset])
    item = inventory['text_items'][0]
    assert item['text'] == '实体 T001 的标签为 é。'
    original = next(e for e in dataset['evidence_records'] if e['evidence_id'] in item['evidence_refs'])
    assert original['observed_value'] == '实体 T001 的标签为 e\u0301。'
    _, report = mixed_mapping_drafts(rules=profile(inventory), datasets=[dataset], namespace='urn:test:', question_ids=[],
        baseline={'elements':[{'iri':MIN+'Entity','element_kind':'CLASS','element_id':'urn:class'},
                              {'iri':MIN+'label','element_kind':'DATA_PROPERTY','element_id':'urn:label'}]})
    span = next(s for s in report['text_spans'] if s['field'] == 'label')
    assert span['quote'] == 'é'
    assert span['end'] - span['start'] == 1
    assert span['coordinate_basis'] == 'KG_IR_NORMALIZED_TEXT_UNICODE_CODEPOINTS'
    assert span['transformation_refs'] == original['transformation_ids']


def test_native_excel_types_and_sparse_cells_are_not_string_guesses(prompt03_workspace, tmp_path):
    from datetime import datetime

    from openpyxl import Workbook
    book = Workbook()
    book.active.append(['id', 'flag', 'date', 'time', 'count'])
    book.active.append(['T001', True, datetime(2026, 9, 8), datetime(2026, 9, 8, 12, 30), 12.5])  # noqa: DTZ001 -- Excel explicitly stores timezone-naive dates.
    book.active.append(['T002', None, None, None, None])
    path = tmp_path/'types.xlsx'
    book.save(path)
    dataset, _ = ingest(prompt03_workspace, [path])
    table = input_inventory([dataset])['tables'][0]
    types = {'flag':'boolean', 'date':'date', 'time':'dateTime', 'count':'decimal'}
    rules = {'profile':'evidence-record-mapping-v2', 'tables':[{'record_id':'typed', 'class_iri':MIN+'Entity',
        'source_id':table['source_id'], 'locator':table['locator'], 'identity_space':'entities', 'id_field':'id',
        'literals':{field:{'predicate_iri':'urn:'+field, 'datatype':datatype} for field, datatype in types.items()}}]}
    baseline = {'elements':[{'iri':MIN+'Entity','element_kind':'CLASS','element_id':'urn:class'},
                           *[{'iri':'urn:'+field,'element_kind':'DATA_PROPERTY','element_id':'urn:property:'+field} for field in types]]}
    drafts, report = mixed_mapping_drafts(rules=rules, datasets=[dataset], namespace='urn:test:', baseline=baseline, question_ids=[])
    assert not report['unmapped_item_ids']
    assert len(report['identities']) == 2
    literals = {d['body']['predicate_iri']:d['body']['literal']['lexical_value'] for d in drafts if d['body']['candidate_type']=='DATA_PROPERTY_ASSERTION'}
    assert literals == {'urn:flag':'true', 'urn:date':'2026-09-08', 'urn:time':'2026-09-08T12:30:00', 'urn:count':'12.5'}
    assert not [d for d in drafts if d['body']['candidate_type']=='DATA_PROPERTY_ASSERTION' and d['body']['subject_iri'].endswith('T002')]
    with pytest.raises(ModelingControlError, match='MAPPING_DATATYPE_INVALID'):
        typed_value('2026-09-08 12:30:00', 'date', source_kind='spreadsheet-cell')
