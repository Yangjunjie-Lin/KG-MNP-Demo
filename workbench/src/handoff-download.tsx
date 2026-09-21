import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,object,post,queryClient,rows,str,type Document} from './api';
import {useWorkspace} from './shell';

export function HandoffDownload({packageId}:{packageId:string}) {
  const {state,principal,prefix,busy}=useWorkspace();
  const [open,setOpen]=useState(false),[license,setLicense]=useState(''),[basis,setBasis]=useState(''),[recipient,setRecipient]=useState('');
  const [classification,setClassification]=useState('SYNTHETIC'),[error,setError]=useState(''),[pending,setPending]=useState(false);
  const [requestedJob,setRequestedJob]=useState('');
  const allowed=['package:export','source:read','source:export','acceptance:export'].every(p=>principal.permissions.includes('*')||principal.permissions.includes(p));
  const options=useQuery({queryKey:['handoff-options',state.project.project_id,state.project.authority_revision],queryFn:()=>api<Document>(`${prefix}/modeling/handoff-options`),enabled:open&&allowed});
  const ids=new Set(state.jobs.map(j=>j.job_id));
  const exported=state.results.filter(r=>r.operation==='modeling.handoff.export'&&r.result.package_id===packageId&&ids.has(r.job_id)).at(-1);
  const modeled=state.results.filter(r=>r.operation==='compile.build'&&r.result.package_id===packageId&&ids.has(r.job_id)).at(-1);
  const task=state.jobs.find(j=>j.job_id===requestedJob);
  const negative=state.results.filter(r=>r.operation==='modeling.handoff.check'&&r.result.package_id===packageId&&r.result.session_revision===options.data?.expected_revision).at(-1);
  const canCheck=principal.permissions.includes('*')||principal.permissions.includes('acceptance:run');
  async function checkNegatives(){
    setPending(true);setError('');
    try{const accepted=await post<Document>('/operations/modeling.handoff.check',{project_id:state.project.project_id,package_id:packageId,expected_revision:options.data?.expected_revision});
      setRequestedJob(str(accepted.job_id));await queryClient.invalidateQueries({queryKey:['state']});
    }catch(e){setError(String(e));}finally{setPending(false);}
  }
  async function prepare(){
    setPending(true);setError('');
    try{const accepted=await post<Document>('/operations/modeling.handoff.export',{project_id:state.project.project_id,package_id:packageId,
      expected_revision:options.data?.expected_revision,source_grants:rows(options.data?.sources).map(s=>({source_id:s.source_id,sha256:s.sha256,license,permission_basis:basis})),recipient,data_classification:classification,
      ...(options.data?.negative_plan_required?{negative_report_id:negative?.result.report_id}:{})});
      setRequestedJob(str(accepted.job_id));
      await queryClient.invalidateQueries({queryKey:['state']});
    }catch(e){setError(String(e));}finally{setPending(false);}
  }
  return <div className="package-export">
    <button disabled={!allowed||busy} onClick={()=>setOpen(!open)}>本体交接包</button>
    {open&&<div><p className="muted">包含来源与独立验收答案，仅交授权接收人；不授予发布权。</p>
      <label>接收人<input value={recipient} onChange={e=>setRecipient(e.target.value)}/></label>
      <label>来源许可<input value={license} onChange={e=>setLicense(e.target.value)}/></label>
      <label>导出授权依据<input value={basis} onChange={e=>setBasis(e.target.value)}/></label>
      <label>数据性质<select value={classification} onChange={e=>setClassification(e.target.value)}><option value="SYNTHETIC">合成工程数据</option><option value="AUTHORIZED_DATA">已授权数据</option></select></label>
      <p>{rows(options.data?.sources).map(s=>str(s.name)).join('、')}</p>
      {options.data?.negative_plan_required===true&&<p>冻结负例验收：{str(negative?.result.status)||'NOT_RUN'} <button disabled={busy||pending||!canCheck} onClick={checkNegatives}>执行冻结负例</button></p>}
      <button disabled={busy||pending||!license.trim()||!basis.trim()||!recipient.trim()||options.data?.status!=='READY'||(options.data?.negative_plan_required===true&&!negative?.result.report_id)} onClick={prepare}>确认授权并生成交接包</button>
      {(error||options.error)&&<p role="alert">{error||String(options.error)}</p>}
    </div>}
    {task&&<p role={task.status==='FAILED'?'alert':'status'}>本次导出：{task.status} {task.error?.code}{task.status==='FAILED'&&exported?'；下方是之前已生成的快照。':''}</p>}
    {exported&&<p><a download href={`/api/v1${prefix}/handoffs/${encodeURIComponent(exported.job_id)}/archive`}>下载本体交接包</a> · 已导出，未确认接收</p>}
    {modeled&&<EvolutionDownload jobId={modeled.job_id}/>}
  </div>;
}

export function EvolutionDownload({jobId}:{jobId:string}) {
  const {state,principal,prefix,busy}=useWorkspace();
  const [error,setError]=useState(''),[pending,setPending]=useState(false);
  const [requestedJob,setRequestedJob]=useState('');
  const allowed=['package:export','source:read','trace:export'].every(p=>principal.permissions.includes('*')||principal.permissions.includes(p));
  const exported=state.results.filter(r=>r.operation==='modeling.evolution.export'&&object(r.result).source_job_id===jobId).at(-1);
  const task=state.jobs.find(j=>j.job_id===requestedJob);
  async function prepare(profile:string){
    setPending(true);setError('');
    try{const accepted=await post<Document>('/operations/modeling.evolution.export',{project_id:state.project.project_id,job_id:jobId,batch_id:`batch-${jobId.replace(/[^A-Za-z0-9._-]/g,'-')}`,profile});
      setRequestedJob(str(accepted.job_id));
      await queryClient.invalidateQueries({queryKey:['state']});
    }catch(e){setError(String(e));}finally{setPending(false);}
  }
  if(!allowed)return <TrajectoryReview jobId={jobId}/>;
  return <div className="actions"><button disabled={busy||pending} onClick={()=>prepare('strict-v2')}>演进数据包</button>
    <button disabled={busy||pending} onClick={()=>prepare('local')}>本地轨迹诊断</button>
    {error&&<p role="alert">{error}；未启用录制或协议不兼容时不生成严格 v2 包。</p>}
    {task&&<p role={task.status==='FAILED'?'alert':'status'}>本次导出：{task.status} {task.error?.code}{task.status==='FAILED'?'；可尝试本地轨迹诊断。':''}</p>}
    {exported&&<a download href={`/api/v1${prefix}/handoffs/${encodeURIComponent(exported.job_id)}/archive`}>下载{str(exported.result.status)==='LOCAL_DIAGNOSTIC_EXPORTED'?'本地诊断（非 v2）':'演进数据包（未接收）'}</a>}
    <TrajectoryReview jobId={jobId}/>
  </div>;
}

export function TrajectoryReview({jobId}:{jobId?:string}) {
  const {state,principal,busy}=useWorkspace();
  const [historical,setHistorical]=useState(!jobId);
  const [verdict,setVerdict]=useState('pass'),[annotations,setAnnotations]=useState(''),[violations,setViolations]=useState(''),[correction,setCorrection]=useState('');
  const [execId,setExecId]=useState(''),[exportId,setExportId]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(false),[requested,setRequested]=useState('');
  const allowed=['trace:review','source:read'].every(p=>principal.permissions.includes('*')||principal.permissions.includes(p));
  const task=state.jobs.find(j=>j.job_id===requested);
  if(!allowed)return null;
  async function submit(){
    setError('');setPending(true);
    try{
      const payload:Document={project_id:state.project.project_id,verdict,...(!historical&&jobId?{job_id:jobId}:{exec_id:execId,execution_export_job_id:exportId})};
      if(annotations.trim())payload.annotations=JSON.parse(annotations);
      if(verdict==='fail'&&!annotations.trim())throw new Error('fail 必须填写 annotations 数组。');
      if(violations.trim())payload.violations=JSON.parse(violations);
      if(correction.trim())payload.corrected_answer=JSON.parse(correction);
      const accepted=await post<Document>('/operations/modeling.evolution.review',payload);
      setRequested(str(accepted.job_id));await queryClient.invalidateQueries({queryKey:['state']});
    }catch(e){setError(String(e));}finally{setPending(false);}
  }
  return <details><summary>16 运行人工评价</summary><p>审核人由服务端认证身份确定；开发身份仅记合成测试，不作为正式评价交付。</p>
    {jobId&&<label>评价对象<select value={historical?'historical':'selected'} onChange={e=>setHistorical(e.target.value==='historical')}><option value="selected">当前运行</option><option value="historical">此前批次运行</option></select></label>}
    {historical&&<><label>历史运行 exec_id<input value={execId} onChange={e=>setExecId(e.target.value)}/></label><label>可信执行导出任务 ID<input value={exportId} onChange={e=>setExportId(e.target.value)}/></label></>}
    <label>运行评价结论<select value={verdict} onChange={e=>setVerdict(e.target.value)}><option value="pass">pass</option><option value="fail">fail</option></select></label>
    <label>annotations（fail 必填，JSON 数组）<textarea value={annotations} onChange={e=>setAnnotations(e.target.value)} placeholder='[{"aspect":"完整性","severity":"minor","comment":"人工意见"}]'/></label>
    <label>violations（可选 JSON 数组）<textarea value={violations} onChange={e=>setViolations(e.target.value)} placeholder='[{"code":"人工提供的代码","evidence":"依据","suggestion":"建议"}]'/></label>
    <label>corrected_answer（可选 JSON）<textarea value={correction} onChange={e=>setCorrection(e.target.value)}/></label>
    <button disabled={busy||pending||(historical&&(!execId||!exportId))||(verdict==='fail'&&!annotations.trim())} onClick={submit}>以当前身份提交运行评价</button>
    {error&&<p role="alert">{error}</p>}{task&&<p role={task.status==='FAILED'?'alert':'status'}>评价任务：{task.status} {task.error?.code}；不代表对方已接收。</p>}
  </details>;
}

export function EvolutionBatchDownload(){
  const {state,principal,prefix,busy}=useWorkspace();
  const [batch,setBatch]=useState(''),[reviews,setReviews]=useState(''),[exports,setExports]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(false),[requested,setRequested]=useState('');
  const allowed=['package:export','source:read','trace:export'].every(p=>principal.permissions.includes('*')||principal.permissions.includes(p));
  const task=state.jobs.find(j=>j.job_id===requested),result=state.results.find(r=>r.job_id===requested);
  async function prepare(){
    setError('');setPending(true);
    try{const accepted=await post<Document>('/operations/modeling.evolution.export',{project_id:state.project.project_id,batch_id:batch,review_ids:reviews.split(/\s+/).filter(Boolean),known_run_export_job_ids:exports.split(/\s+/).filter(Boolean)});
      setRequested(str(accepted.job_id));await queryClient.invalidateQueries({queryKey:['state']});
    }catch(e){setError(String(e));}finally{setPending(false);}
  }
  return <details><summary>17 空批次或仅评价批次</summary><p>主动不选择运行；不会将受阻运行改为空成功。历史引用仅为本地预检，接收状态 NOT_CONTACTED。</p>
    <label>演进批次编号<input value={batch} onChange={e=>setBatch(e.target.value)}/></label><label>评价 ID（空白分隔，可留空）<textarea value={reviews} onChange={e=>setReviews(e.target.value)}/></label>
    <label>历史执行导出任务 ID（空白分隔，可选）<textarea value={exports} onChange={e=>setExports(e.target.value)}/></label>
    <button disabled={!allowed||busy||pending||!batch.trim()} onClick={prepare}>生成所选演进批次</button>
    {error&&<p role="alert">{error}</p>}{task&&<p role={task.status==='FAILED'?'alert':'status'}>批次任务：{task.status} {task.error?.code}</p>}
    {task?.status==='SUCCEEDED'&&result&&<a download href={`/api/v1${prefix}/handoffs/${encodeURIComponent(requested)}/archive`}>下载批次快照（未接收）</a>}
  </details>;
}

export function DeliveryChecklist(){
  return <details><summary>01–17 交付清单</summary>
    <p className="muted">参考版本：2026-09-18 精简版（名称更新版，经用户确认）。参考包是说明与上游样例，不是已生成成果；详细字段以项目交接契约为准。</p>
    <details><summary>01–08 上游输入</summary><p>01 表格数据 records.json（有记录）；02 文本片段 text_blocks.json（有文本）；03 来源、定位与快照 source_locator.json / sources；04 上游质量结果 quality_report.json；05 目标与领域规则 goal_and_rules.json（业务方）；06 可复用本体与依赖 baseline.ttl / imports.lock.json / assets（复用时）；07 独立验收材料 acceptance_private 与负例计划（生成前固定，仅验收）；08 输入批次清单 manifest.json（每批）。提供方职责不由 Agent 代替，生成只读白名单。</p></details>
    <details><summary>09–14 本体成果</summary><p>09 本体、实例、约束三图；10 实际映射与来源证据；11 验证与本体审核；12 查询、独立正负例；13 本体清单；14 实际依赖与原生 .kgop。来自同次确认与编译，格式、验收、审核、导出、接收、发布分别记账。</p></details>
    <details><summary>15–17 演进数据</summary><p>15 执行记录 executions/run-&lt;id&gt;.jsonl；16 运行人工评价 reviews/*.jsonl；17 推荐的演进批次清单 upstream_manifest.json。context 是可选关联附件，逐步审计不是六类事件。无真人评价不造 reviews；程序 turn 未定义时下载本地诊断，不伪造严格 v2。</p></details>
  </details>;
}
