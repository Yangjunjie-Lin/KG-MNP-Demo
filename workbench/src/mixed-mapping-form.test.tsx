// Synthetic component projections only; the separate mixed browser flow is real.
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {ExtractionReport,MixedMappingForm} from './mixed-mapping-form';

afterEach(cleanup);
const prepared={bundle:{modeling_input_bundle_id:'bundle'},baseline:{elements:[{element_id:'class',element_kind:'CLASS',iri:'urn:Entity'},{element_id:'label',element_kind:'DATA_PROPERTY',iri:'urn:label'}]},
 input_inventory:{tables:[{source_id:'source',locator:{locator_kind:'document-table-cell',table_index:1,sheet:null},headers:[{name:'id'},{name:'label'}],item_ids:['cell']}],text_items:[{item_id:'text',source_ids:['source'],text:'实体 T001 的标签为 Alpha。'}],data_item_ids:['text','cell']}};

it('submits exact Word table selectors, typed mappings and explicit alias rationale',()=>{
 const submit=vi.fn().mockResolvedValue(undefined);
 render(<MixedMappingForm prepared={prepared} sources={[{source_id:'source',original_name:'facts.docx'}]} busy={false} submit={submit}/>);
 expect(screen.getByRole('button',{name:'生成混合资料候选'})).toBeDisabled();
 fireEvent.click(screen.getByLabelText('纳入表格 1'));
 fireEvent.change(screen.getByLabelText('对象类型'),{target:{value:'urn:Entity'}});
 fireEvent.click(screen.getByRole('button',{name:'添加数据属性'}));
 fireEvent.change(screen.getByLabelText('数据字段 1'),{target:{value:'label'}});
 fireEvent.change(screen.getByLabelText('数据属性 1'),{target:{value:'urn:label'}});
 fireEvent.change(screen.getByLabelText('数据类型 1'),{target:{value:'decimal'}});
 fireEvent.click(screen.getByRole('button',{name:'声明身份别名'}));
 fireEvent.change(screen.getByLabelText('原始主键 1'),{target:{value:'legacy'}});
 fireEvent.change(screen.getByLabelText('统一主键 1'),{target:{value:'T001'}});
 fireEvent.change(screen.getByLabelText('身份合并依据 1'),{target:{value:'explicit source reference'}});
 fireEvent.submit(screen.getByRole('button',{name:'生成混合资料候选'}).closest('form')!);
 const payload=submit.mock.calls[0][1];
 expect(payload.providers).toEqual(['manual-candidate-provider']);
 expect(payload.record_mapping.tables[0]).toMatchObject({source_id:'source',locator:{locator_kind:'document-table-cell',table_index:1},identity_space:'entities',literals:{label:{predicate_iri:'urn:label',datatype:'decimal'}},identity_aliases:[{value:'legacy',canonical:'T001',rationale:'explicit source reference'}]});
});

it('allows evidence span annotation without asking users to edit candidate JSON',()=>{
 render(<MixedMappingForm prepared={prepared} sources={[]} busy={false} submit={vi.fn()}/>);
 fireEvent.click(screen.getByRole('button',{name:'添加原文记录'}));
 const panel=within(screen.getByRole('group',{name:'原文记录 1'}));
 fireEvent.change(panel.getByLabelText('标注原文条目'),{target:{value:'text'}});
 const text=panel.getByLabelText('证据文本（选中要绑定的文字）') as HTMLTextAreaElement;
 text.setSelectionRange(3,7);
 fireEvent.select(text);
 fireEvent.change(panel.getByLabelText('标注字段名'),{target:{value:'id'}});
 fireEvent.click(panel.getByRole('button',{name:'添加此原文片段'}));
 expect(panel.getByText('id：T001（3–7）')).toBeInTheDocument();
});

it('displays unmodeled input as a confirmation blocker, not semantic success',()=>{
 render(<ExtractionReport report={{mapping_digest:'digest',unmapped_item_ids:['missing-item'],identities:[{iri:'urn:item',occurrences:3,item_ids:['one','two','three']}],text_spans:[]}}/>);
 expect(screen.getByRole('status')).toHaveTextContent('不能确认');
 expect(screen.getByText('missing-item')).toBeInTheDocument();
 expect(screen.getByText('urn:item')).toBeInTheDocument();
});
