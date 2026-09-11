import {useEffect, useRef, type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {object, str, type Document} from './api';
import {DataTable, Panel, Status} from './components';

export type Method = {method_id:string;stage:number;title:string;full_name:string;roles:string[];source_definition:string;guard:string;source_implementation:{name:string;use:string;how:string}[];required_output:string;tutorial_file:string;tutorial_inputs:string[]};
export type MethodRegistry = {schema_version:string;stages:{id:number;title:string;summary:string}[];methods:Method[];branches:Record<string,string[]>};
const roleNames:Record<string,string>={ai:'AI',program:'程序',review:'人工审核'};

export function Stepper({registry,step,href,progress={}}:{registry:MethodRegistry;step:Method;href:(id:string)=>string;progress?:Record<string,string>}) {
  return <nav aria-label="本体建模五阶段" className="modeling-stepper">{registry.stages.map(stage=><Link key={stage.id} aria-current={stage.id===step.stage?'step':undefined} to={href(`${stage.id}.1`)}><strong><span>{stage.id.toString().padStart(2,'0')}</span>{stage.title}</strong><small>{progress[String(stage.id)]||'尚未核定执行进度'}</small><p>{stage.summary}</p></Link>)}</nav>;
}

export function StepDetail({method,view,onView,children}:{method:Method;view:string;onView:(v:string)=>void;children:ReactNode}) {
  const views=[['operation','当前操作'],['input','本步输入'],['output','本步产物'],['method','方法说明']];
  return <section className="step-detail" aria-label={`${method.method_id} ${method.title}`}><header><span className="eyebrow">方法 {method.method_id} · {method.roles.map(r=>roleNames[r]).join('＋')}</span><h2>{method.title}</h2><p className="muted">{method.source_definition}</p></header><div className="step-tabs" role="tablist" aria-label="步骤视图" onKeyDown={e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const index=views.findIndex(([v])=>v===view);const next=e.key==='Home'?0:e.key==='End'?3:(index+(e.key==='ArrowRight'?1:3))%4;onView(views[next][0]);(e.currentTarget.children[next] as HTMLButtonElement).focus();}}>{views.map(([v,label])=><button id={`tab-${v}`} key={v} role="tab" aria-selected={v===view} aria-controls="step-panel" tabIndex={v===view?0:-1} onClick={()=>onView(v)}>{label}</button>)}</div><div id="step-panel" role="tabpanel" aria-labelledby={`tab-${view}`} tabIndex={0}>{view==='method'?<><h3>{method.full_name}</h3>{method.source_implementation.map(tool=><div className="method-tool" key={tool.name}><strong>{tool.name} · {tool.use}</strong><p>{tool.how}</p></div>)}<p className="notice">边界：{method.guard}</p><p>规定产物：{method.required_output}</p></>:children}</div></section>;
}

export function EvidenceDrawer({value,onClose}:{value:Document|null;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const node=dialog.current;if(value&&node&&!node.open)node.showModal();return()=>{if(node?.open)node.close();};},[value]);
  return <dialog className="evidence-drawer" ref={dialog} onCancel={e=>{e.preventDefault();onClose();}} aria-labelledby="evidence-title"><div className="actions"><h2 id="evidence-title">证据、原值与版本</h2><button autoFocus onClick={onClose} aria-label="关闭证据抽屉">关闭</button></div><p className="muted">字符位置采用 Unicode 码点左闭右开区间。引用匹配不等于语义批准。</p>{value&&<Readable value={value}/>}<details><summary>完整定位与版本 JSON</summary><pre>{JSON.stringify(value,null,2)}</pre></details></dialog>;
}

const labels:Record<string,string>={objects:'业务对象',facts:'事实',rules:'业务规则',evidence_refs:'支持证据',input_refs:'输入引用',conflicts:'冲突',identities:'统一身份',rows:'结果行',expected_rows:'独立预期行',actual_rows:'实际结果行',fields:'字段画像',texts:'文本画像',candidates:'候选',quarantined:'隔离项',usable:'可用项',status:'状态',state:'状态',actual_review:'实际审核',actual_execution_status:'实际执行',source_field:'来源字段',original_item:'原始输入项',source_ids:'来源引用'};
function display(value:unknown):string {
  if(Array.isArray(value))return value.map(display).join('；');
  if(value&&typeof value==='object') {const d=object(value);if(d.kind&&d.value)return `${d.kind==='iri'?'IRI':'字面值'}：${str(d.value)}${d.datatype?' · '+str(d.datatype):''}`;return Object.entries(d).map(([k,v])=>`${labels[k]||k}：${display(v)}`).join('；');}
  return str(value);
}
function Readable({value,depth=0}:{value:unknown;depth?:number}) {
  if(Array.isArray(value)) {
    if(!value.length)return <p className="muted">空集合（未登记条目）</p>;
    if(value.every(v=>v!==null&&typeof v==='object'&&!Array.isArray(v))){const keys=[...new Set(value.flatMap(v=>Object.keys(v)))].slice(0,8);return <DataTable data={value.map(v=>Object.fromEntries(keys.map(k=>[k,display(v[k])]))) as Document[]} fields={keys.map(k=>[k,labels[k]||k])}/>;}
    return <ul>{value.map((v,i)=><li key={i}>{display(v)}</li>)}</ul>;
  }
  if(value&&typeof value==='object')return <div className="readable-fields">{Object.entries(object(value)).map(([k,v])=><section key={k}><h4>{labels[k]||k}</h4>{depth<2&&v&&typeof v==='object'?<Readable value={v} depth={depth+1}/>:<p>{display(v)||'未提供'}</p>}</section>)}</div>;
  return <p>{display(value)||'未提供'}</p>;
}

export function ArtifactViewer({value,title='工件内容',download,onEvidence}:{value:unknown;title?:string;download?:string;onEvidence?:(v:Document)=>void}) {
  const d=object(value), facts=Array.isArray(d.facts)?d.facts as Document[]:null;
  return <Panel title={title}>{download&&<p><a href={download} download>下载此工件</a></p>}{facts&&onEvidence?<><DataTable data={facts.map(f=>({id:f.fact_id,subject:f.subject,predicate:f.predicate,object:display(f.object),supports:display(f.evidence_refs)}))} fields={[["id","事实"],["subject","对象"],["predicate","关系／属性"],["object","值／目标"],["supports","来源支持"]]}/><div className="fact-links" aria-label="事实证据">{facts.map(f=><button key={str(f.fact_id)} onClick={()=>onEvidence(f)}>查看 {str(f.fact_id)} 的证据</button>)}</div></>:<Readable value={value}/>}<details className="raw-artifact"><summary>完整 JSON／原始内容</summary><pre>{typeof value==='string'?value:JSON.stringify(value,null,2)}</pre></details></Panel>;
}

export function ValidationSummary({checks}:{checks:Document[]}) {
  return <div className="validation-summary">{checks.length?checks.map((c,i)=><div className="record" key={i}><strong>{str(c.name||c.check||c.method_id)}</strong><Status value={c.status||'NOT_RUN'}/><p>{str(c.reason||c.scope)}</p></div>):<p className="notice">NOT_RUN · 当前没有此检查的真实执行收据。</p>}</div>;
}
