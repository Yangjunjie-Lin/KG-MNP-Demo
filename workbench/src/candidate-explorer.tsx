import {useState} from 'react';
import {Background,Controls,ReactFlow} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {DataTable,Field} from './components';
import {boundedCandidateGraph} from './graph';
import {object,str,type Document} from './api';

export function CandidateExplorer({candidates,edit}:{candidates:Document[];edit:(candidate:Document)=>void}){
  const [search,setSearch]=useState(''),[selected,setSelected]=useState(''),[neighbors,setNeighbors]=useState(false);
  const current=candidates.find(c=>c.candidate_id===selected);
  const dependencies=(candidate:Document)=>Array.isArray(candidate.dependency_candidate_refs)?candidate.dependency_candidate_refs:[];
  const visible=candidates.filter(candidate=>{
    const matches=(str(candidate.candidate_id)+' '+str(candidate.body)+' '+str(candidate.candidate_kind)).toLowerCase().includes(search.toLowerCase());
    return matches&&(!neighbors||!current||candidate===current||dependencies(candidate).includes(selected)||dependencies(current).includes(candidate.candidate_id));
  });
  const graph=boundedCandidateGraph(visible);
  return <>
    <p>Proposed 候选视图：不是 Confirmed 或 Released。正式版本在“验证与发布”中按固定 Package / Release 读取。</p>
    <Field label="搜索候选概念与关系"><input value={search} onChange={event=>setSearch(event.target.value)}/></Field>
    <Field label="选择候选（键盘替代图选择）"><select value={selected} onChange={event=>setSelected(event.target.value)}>
      <option value="">未选择</option>{candidates.map(c=><option key={str(c.candidate_id)} value={str(c.candidate_id)}>{str(c.candidate_kind)} · {str(object(c.body).label||object(c.body).candidate_type)} · {str(c.candidate_id)}</option>)}
    </select></Field>
    <Field label="只看所选项与直接依赖邻居"><input type="checkbox" checked={neighbors} onChange={event=>setNeighbors(event.target.checked)}/></Field>
    {current&&<div className="record"><code>{selected}</code><p>证据：{str(current.evidence_refs)}</p><button onClick={()=>edit(current)}>修改所选候选</button></div>}
    <details><summary>概念与依赖图（布局拖动不修改语义）</summary>
      <div className="graph"><ReactFlow nodes={graph.nodes} edges={graph.edges} onNodeClick={(_event,node)=>setSelected(node.id)} fitView nodesConnectable={false}><Background/><Controls/></ReactFlow></div>
      <p>箭头从被依赖项指向依赖它的候选。{graph.truncated?'结果已截断。':''}最多显示 200 节点 / 400 边；搜索和邻居筛选同时作用于图与下方表格。</p>
    </details>
    <DataTable data={visible} fields={[["candidate_id","候选 ID"],["candidate_kind","分类"],["body","语义内容"],["evidence_refs","证据"],["dependency_candidate_refs","依赖"]]}/>
  </>;
}
