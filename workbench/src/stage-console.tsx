import {useState} from 'react';
import {Link, useSearchParams} from 'react-router-dom';
import {object, outputs, rows, str, type Document} from './api';
import {Field, Panel, SelectDocument, Status} from './components';
import {useWorkspace} from './shell';
import {ModelingOperations} from './modeling';
import {Releases} from './releases';
import {ArtifactViewer, EvidenceDrawer, ValidationSummary} from './modeling-components';
import {ExactCompilationForm} from './modeling-exact-form';
import {StageRunControls} from './stage-run-controls';
import {ScopeSuggestion} from './scope-suggestion';
import {ManualDrafts} from './manual-drafts';
import {ModelAssistance} from './model-assistance';

export const stages = [
  ['输入核验与范围确认','核验资料与来源，冻结本轮规则及独立验收预期。','规则化记录与原文','确认范围、规则与验收要求'],
  ['本体复用与结构设计','保留基线语义与身份，形成可追溯的结构和约束候选。','业务范围与已有定义','类、属性、关系及约束'],
  ['数据映射与事实构建','将记录与文本映射为统一对象，保留多源证据和冲突。','分散的记录与文本','统一对象和候选事实'],
  ['联合校验与人工审核','对同一候选版本执行语义检查，再由授权身份逐项审核。','候选、规则与问题','检查结果与人工确认包'],
  ['语义编译与交付验收','确定性编译确认内容，对照冻结答案验收实际文件。','已确认的冻结建模结果','语义文件、查询结果与交付包'],
];
const operationStage:Record<string,number>={'modeling.profile':1,'modeling.scope':1,'modeling.scope.approve':1,'modeling.prepare':2,'modeling.proposal':3,'modeling.semantic.check':4,'review.action':4,'review.finalize':4,'compile.plan.exact':5,'compile.plan':5,'compile.build':5,'package.export':5};
function label(value:unknown){const text=str(value);return text.includes('#')?text.split('#').at(-1)!:text.includes('/')?text.split('/').at(-1)!:text.startsWith('urn:')?text.split(':').at(-1)!:text.length>80?text.slice(0,65)+'…':text;}
const kindNames:Record<string,string>={CLASS:'对象类型',DATA_PROPERTY:'数据属性',OBJECT_PROPERTY:'对象关系',INDIVIDUAL:'对象标识',CLASS_ASSERTION:'对象类型',DATA_PROPERTY_ASSERTION:'属性值',OBJECT_PROPERTY_ASSERTION:'对象关系',NODE_SHAPE:'对象约束',PROPERTY_SHAPE:'属性约束'};
export function summarize(value:unknown,terms:Record<string,string>={}):Document[]{
  const d=object(value);
  if(d.proposal)return summarize(d.proposal,terms);
  if(d.confirmed_package)return summarize({abox_candidates:object(d.confirmed_package).confirmed_abox},terms);
  if(d.manifest){const main=['ontology/module.ttl','data/abox.ttl','shapes/compiled-shapes.ttl','mappings/mapping-plan.json','provenance/statements.ttl'];return rows(object(d.manifest).artifacts).sort((a,b)=>(main.includes(str(a.path))?main.indexOf(str(a.path)):-1+100)-(main.includes(str(b.path))?main.indexOf(str(b.path)):-1+100)).map(f=>({name:str(f.path),change:'实际交付文件',value:`${f.size_bytes} 字节`,detail:f}));}
  if(d.five_stage){const artifacts=rows(object(d.five_stage).artifacts);const profile=artifacts.find(a=>object(a.ref).step_id==='1.2');if(profile)return summarize(profile.content);return artifacts.filter(a=>object(a.ref).step_id!=='3.6').map(a=>({name:object(a.ref).step_id==='4.1'?'依赖与来源检查':'联合语义检查',change:object(a.content).status,value:object(a.content).approval||'检查不授予审批',detail:a}));}
  if(d.fields)return rows(d.fields).map(f=>({name:str(f.field).split(':').at(-1),change:`${f.sample_count} 个值，空值 ${f.isna_count}`,value:Array.isArray(f.examples)?f.examples.join('、'):'',detail:f})).concat(rows(d.texts).map(t=>({name:'原文',change:`${t.code_point_length} 个字符`,value:str(t.text),detail:t})));
  if(d.scope)return (Array.isArray(object(d.scope).target_object_families)?object(d.scope).target_object_families as string[]:[]).map(name=>({name,change:'范围已登记',value:'等待明确审核',detail:object(d.scope)}));
  if(d.baseline)return rows(object(d.baseline).elements).map(t=>({name:terms[str(t.iri)]||label(t.iri||t.element_iri),change:kindNames[str(t.element_kind)]||t.element_kind||'基线复用候选',value:t.definition||'保留锁定语义',detail:t}));
  const candidates=['tbox_candidates','abox_candidates','mapping_candidates','shacl_candidates'].flatMap(k=>rows(d[k]));
  if(candidates.length)return candidates.map(c=>{const b=object(c.body),literal=object(b.literal),iri=str(b.object_iri);return {name:b.label||label(b.subject_iri||b.target_iri||b.iri||c.candidate_kind),change:terms[str(b.predicate_iri)]||label(b.predicate_iri)||kindNames[str(b.candidate_type)]||b.candidate_type,value:Object.hasOwn(literal,'lexical_value')?(str(literal.lexical_value)||'空字符串'):terms[iri]||label(iri)||({SUPPORTED:'有来源支持'} as Record<string,string>)[str(c.support_status)]||c.support_status,source:`${rows(c.evidence_refs).length} 项依据`,detail:c};});
  if(Array.isArray(value))return value.map(v=>({name:label(object(v).name||object(v).field||object(v).iri||object(v).item_id||'记录'),change:label(object(v).status||object(v).kind||''),value:label(object(v).value||object(v).sample_values||object(v).text||''),detail:object(v)}));
  return Object.entries(d).filter(([,v])=>v!==null&&v!==undefined).map(([k,v])=>({name:({scope:'建模范围',approval:'范围审核',bundle:'结构输入',baseline:'基线快照',questions:'验收问题',proposal:'事实候选',prevalidation:'完整性检查',five_stage:'阶段执行收据',confirmed_package:'人工确认包',manifest:'语义文件清单',reports:'磁盘验收报告',run:'规则化批次',quality:'质量报告',extraction:'映射核账',plan:'确定性编译计划'} as Record<string,string>)[k]||k,change:label(object(v).status||object(v).decision||'已产生工件'),value:Array.isArray(v)?`${v.length} 条`:typeof v==='object'?`${Object.keys(object(v)).length} 项字段`:label(v),detail:object(v)}));
}
function inputRows(dataset:Document):Document[]{return rows(dataset.items).filter(item=>!(item.item_kind==='table-cell'&&object(item.payload).row===1)).map(item=>{const p=object(item.payload);return {name:item.item_kind==='text-block'?'原文片段':`记录 ${p.row??''} · 字段 ${p.column??p.field_name??''}`,change:'保留来源定位',value:p.text||object(p.value).normalized_lexical_value||object(p.value).original_lexical_value||'',detail:item};});}
export function ComparisonTable({data,onDetail}:{data:Document[];onDetail:(d:Document)=>void}){
  const [expanded,setExpanded]=useState(false);const visible=expanded?data:data.slice(0,5);
  return <><div className="table-scroll" tabIndex={0} role="region" aria-label="阶段数据对比"><table><thead><tr><th>业务内容</th><th>处理变化</th><th>当前结果</th></tr></thead><tbody>{visible.map((r,i)=><tr key={i}><td><button className="text-button" onClick={()=>onDetail(object(r.detail))}>{str(r.name)}</button></td><td>{str(r.change)}</td><td>{str(r.value)}</td></tr>)}</tbody></table></div>{!data.length&&<p className="empty">尚未产生本轮结果。执行后显示真实内容。</p>}<p className="muted">显示 {visible.length} / 总共 {data.length} 条 {data.length>5&&<button onClick={()=>setExpanded(!expanded)}>{expanded?'收起':'展开全部（含问题项）'}</button>}</p></>;
}
export function FiveStageModeling(){
  const {state,prefix,submit,busy}=useWorkspace();const [params,setParams]=useSearchParams();
  const stage=Math.min(5,Math.max(1,Number(params.get('stage')||params.get('step')?.split('.')[0]||1)||1));
  const [detail,setDetail]=useState<Document|null>(null),[error,setError]=useState('');
  const session=object(state.modeling_session), run=params.get('run')||str(object(session.frozen).run_id);
  const selected=state.results.filter(r=>!session.session_id||rows(session.outputs).some(o=>o.job_id===r.job_id&&o.status==='CURRENT'));
  const before=selected.filter(r=>operationStage[r.operation]<stage).at(-1);
  const assisted=selected.filter(r=>r.operation==='modeling.proposal'&&r.result.model_assistance).at(-1);
  const explicitAfter=selected.filter(r=>operationStage[r.operation]===stage).at(-1);
  const after=stage===2&&assisted?{...assisted,result:{tbox_candidates:object(assisted.result.proposal).tbox_candidates,shacl_candidates:object(assisted.result.proposal).shacl_candidates}}:
    stage===4&&!explicitAfter&&assisted&&object(assisted.result.automatic_validation).five_stage?{...assisted,result:object(assisted.result.automatic_validation)}:explicitAfter;
  const title=stages[stage-1];
  const profile=state.results.filter(r=>r.operation==='modeling.profile'&&(!run||object(r.result.five_stage).source_run_id===run)).at(-1);
  const input=object(rows(object(profile?.result.five_stage).artifacts).find(a=>object(a.ref).step_id==='0.0')?.content);
  const prepared=selected.filter(r=>r.operation==='modeling.prepare').at(-1)?.result;
  const terms=Object.fromEntries(rows(object(prepared?.baseline).elements).map(t=>[str(t.iri),str(rows(t.labels).find(l=>l.language==='zh')?.value||rows(t.labels)[0]?.value||label(t.iri))]));
  const proposed=selected.filter(r=>r.operation==='modeling.proposal').at(-1)?.result;
  const beforeRows=stage===1||stage===3?inputRows(input):stage===4?summarize({abox_candidates:object(proposed?.proposal).abox_candidates},terms):summarize(before?.result||{},terms);
  const afterRows=stage===3?summarize({abox_candidates:object(after?.result.proposal).abox_candidates},terms):summarize(after?.result||{},terms);
  const latestJob=state.jobs.find(j=>operationStage[j.operation_id]===stage);
  const attemptStatus=latestJob&&latestJob.status!=='SUCCEEDED'?latestJob.status:after?'已产生结果，详见检查与审核':'NOT_RUN';
  const openDetail=(value:Document)=>{const refs=Array.isArray(value.evidence_refs)?value.evidence_refs:[];setDetail({...value,linked_evidence:rows(input.evidence_records).filter(e=>refs.includes(e.evidence_id))});};
  const navigate=(n:number)=>setParams({...Object.fromEntries(params),stage:String(n)});
  return <div className="five-stage-workbench stage-console"><header className="modeling-heading"><div><span className="eyebrow">ZhiGou Toolchain · 本体内部流程</span><h1>本体建模工作台</h1><p className="muted">同一批次，五个阶段。校验、审核、交付与发布分别记账。</p></div><div className="actions"><button onClick={()=>setParams({...Object.fromEntries(params),focus:params.get('focus')==='1'?'0':'1'})}>{params.get('focus')==='1'?'退出专注':'专注模式'}</button><button onClick={()=>setDetail({session, jobs:state.jobs})}>运行记录</button></div></header>
  <nav className="modeling-stepper" aria-label="本体建模五阶段">{stages.map((s,i)=><button key={s[0]} aria-current={stage===i+1?'step':undefined} onClick={()=>navigate(i+1)}><span>0{i+1}</span><strong>{s[0]}</strong><small>{selected.some(r=>operationStage[r.operation]===i+1)?'有真实产物':'尚未运行'}</small></button>)}</nav>
  <section className="stage-panel"><header className="panel-heading"><div><h2>{title[0]}</h2><p>{title[1]}</p></div><Status value={attemptStatus}/></header><div className="compare-grid"><section aria-label="处理前"><h3>处理前 · {title[2]}</h3><ComparisonTable data={beforeRows} onDetail={openDetail}/></section><section aria-label="处理后"><h3>处理后 · {title[3]}</h3><ComparisonTable data={afterRows} onDetail={openDetail}/></section></div><div className="stage-delta"><strong>本次变化</strong><p>{after?`本阶段已提交 ${selected.filter(r=>operationStage[r.operation]===stage).length} 个真实操作结果，最新结果包含 ${afterRows.length} 项可查看内容。点击表格追溯实际产物。`:'本阶段尚无已提交产物，不预填成功结果。'}</p></div><footer className="handoff-band">下一步接收：{stage<5?stages[stage][2]:'同一个已验证交付包，交给本体服务与版本管理。'} {stage<5?<button onClick={()=>navigate(stage+1)}>查看下一阶段</button>:<Link to={`${prefix}/releases`}>交接服务与版本管理</Link>}</footer></section>
  {latestJob&&['FAILED','RECOVERY_REQUIRED','CANCELLED'].includes(latestJob.status)&&<p role="alert" className="error">本次任务 {latestJob.status}：{latestJob.error?.code||'未完成'}。上方保留的历史产物不代表本次重跑成功。</p>}<StageRunControls stage={stage} runId={run} navigate={navigate}/>
  {!session.session_id&&<p className="notice">当前展示兼容工作区。开始新版构建前，请在第一阶段冻结输入、规则与答案，启用后台失效和必需检查门。</p>}
  {stage===1&&<Panel title="本轮批次与验收基线"><SelectDocument label="规则化运行" items={outputs(state,'ingestion.run','run')} idKey="run_id" value={run} onChange={id=>setParams({...Object.fromEntries(params),run:id})}/><button disabled={busy||!run} onClick={()=>submit('/modeling/profiles',{run_id:run})}>核验输入并生成画像</button><details><summary>冻结或变更本轮规则与独立答案</summary><form onSubmit={e=>{e.preventDefault();setError('');const f=new FormData(e.currentTarget);try{submit('/toolchain/modeling.session.open',{run_id:run,business_rules:String(f.get('rules')).split('\n').filter(Boolean),acceptance:JSON.parse(String(f.get('acceptance'))),configuration:{},expected_revision:session.revision??null});}catch{setError('独立答案必须为有效 JSON。');}}}><Field label="确认的业务规则（每行一项）"><textarea name="rules" required/></Field><Field label="构建前独立答案（查询资产及类型化预期）"><textarea name="acceptance" required placeholder='[{"query_asset_id":"…","expected":{"query_type":"SELECT","comparison":"MULTISET","variables":[],"rows":[]}}]'/></Field><button disabled={busy||!run}>冻结本轮输入与验收基线</button>{error&&<p role="alert">{error}</p>}</form></details></Panel>}
  {stage===1&&<ScopeSuggestion runId={run}/>}
  {(stage===2||stage===3)&&<ManualDrafts/>}
  {(stage===2||stage===3)&&<ModelAssistance/>}
  {stage===4&&<ModelAssistance repair/>}
  <details className="stage-operations" open><summary>本阶段操作</summary>{stage===1&&<ModelingOperations step="1.3"/>}{stage<5?<ModelingOperations step={['1.4','2.1','3.1','4.2'][stage-1]}/>:<><ExactCompilationForm/><Releases deliveryOnly/></>}</details>
  {stage===4&&<><ValidationSummary checks={rows(session.checks)}/><p className="notice">修复请返回映射阶段提交新候选，再执行检查和逐项审核。新版会话禁止修改后直接接受。</p></>}
  <details><summary>技术产物与来源详情</summary>{after&&<ArtifactViewer value={after.result}/>}</details><EvidenceDrawer value={detail} onClose={()=>setDetail(null)}/></div>;
}
