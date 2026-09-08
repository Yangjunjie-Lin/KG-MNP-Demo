import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,object,rows,str,type Document} from './api';
import {DataTable,Field} from './components';
import {useWorkspace} from './shell';

export function FieldMappingPreview({prepared}:{prepared:Document}){
  const {state,prefix}=useWorkspace();
  const [selected,setSelected]=useState(''),[search,setSearch]=useState('');
  const mappings=rows(object(prepared.mappings).mappings);
  const terms=rows(object(prepared.terminology).terms),alignments=rows(object(prepared.alignments).alignments);
  const described:Document[]=mappings.map(mapping=>{
    const ids=new Set(terms.filter(term=>term.lexical_form===mapping.source_field_name).map(term=>term.term_id));
    const alternatives=new Set(alignments.filter(alignment=>ids.has(alignment.source_term_id)&&alignment.target_iri).map(alignment=>str(alignment.target_iri)));
    return {...mapping,alignment_state:!mapping.target_property_iri?'无明确建议，需要人工映射':alternatives.size>1?'存在多个对齐候选，需要人工消歧':'已有建议，仍需逐项审核'};
  });
  const visible=described.filter(mapping=>(str(mapping.source_field_name)+' '+str(mapping.target_property_iri)+' '+str(mapping.field_mapping_id)).toLowerCase().includes(search.toLowerCase()));
  const mapping=described.find(row=>row.field_mapping_id===selected);
  const datasetIds=object(prepared.mappings).kg_ir_dataset_ids;
  const run=state.results.find(row=>row.operation==='ingestion.run'&&Array.isArray(datasetIds)&&datasetIds.includes(row.result.dataset_id));
  const runId=str(object(run?.result.run).run_id);
  const sample=useQuery({queryKey:['mapping-sample',state.project.project_id,runId,mapping?.source_item_id],
    queryFn:({signal})=>api<{evidence:Document[]}>(prefix+'/evidence?run_id='+encodeURIComponent(runId)+'&item_id='+encodeURIComponent(str(mapping?.source_item_id)),{signal}),enabled:!!mapping&&!!runId});
  return <><DataTable data={described} fields={[["source_field_name","源字段"],["source_datatype","KG-IR 类型"],["target_property_iri","建议目标属性"],["alignment_state","歧义与审核状态"],["conversion_policy","转换策略"],["null_policy","空值策略"],["evidence_refs","证据"]]}/>
    <p>空值 OMIT 表示不生成该值，不表示资料完整。缺列、缺失标识与引用由锁定的解析／映射规则检验，失败不会伪造默认值。</p>
    <Field label="查找映射字段"><input value={search} onChange={event=>setSearch(event.target.value)}/></Field>
    <Field label="选择映射查看原始样本"><select value={selected} onChange={event=>setSelected(event.target.value)}><option value="">请选择</option>{visible.slice(0,200).map(row=><option key={str(row.field_mapping_id)} value={str(row.field_mapping_id)}>{str(row.source_field_name)} → {str(row.target_property_iri)||'待映射'} · {str(row.field_mapping_id)}</option>)}</select></Field>
    {visible.length>200&&<p>选择器最多显示 200 项；请搜索缩小范围。完整映射仍可在上方表格分页查看。</p>}
    {mapping&&(!runId?<p role="alert" className="error">无法绑定该映射所属的已验证解析运行。</p>:sample.error?<p role="alert" className="error">样本与证据读取失败：{String(sample.error)}</p>:sample.isFetching?<p role="status">正在按 KG-IR Item 核验样本来源…</p>:sample.data&&<section aria-label="映射原始样本"><h3>映射原始样本</h3><p>源字段：{str(mapping.source_field_name)}；KG-IR 类型：{str(mapping.source_datatype)}；目标：{str(mapping.target_property_iri)||'尚未对齐'}</p><DataTable data={sample.data.evidence} fields={[["observed_value","原始观察值"],["locator","来源定位"],["source_id","Source ID"],["evidence_id","Evidence ID"]]}/>{[...new Set(sample.data.evidence.map(row=>str(row.source_id)))].map(id=><p key={id}><a href={'/api/v1'+prefix+'/sources/'+encodeURIComponent(id)+'/content'}>下载映射样本来源 {id}</a></p>)}</section>)}
  </>;
}
