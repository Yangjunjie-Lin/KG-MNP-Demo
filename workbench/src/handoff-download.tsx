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
  async function prepare(){
    setPending(true);setError('');
    try{const accepted=await post<Document>('/operations/modeling.handoff.export',{project_id:state.project.project_id,package_id:packageId,
      expected_revision:options.data?.expected_revision,source_grants:rows(options.data?.sources).map(s=>({source_id:s.source_id,sha256:s.sha256,license,permission_basis:basis})),recipient,data_classification:classification});
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
      <button disabled={busy||pending||!license.trim()||!basis.trim()||!recipient.trim()||options.data?.status!=='READY'} onClick={prepare}>确认授权并生成交接包</button>
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
  if(!allowed)return null;
  return <div className="actions"><button disabled={busy||pending} onClick={()=>prepare('strict-v2')}>演进数据包</button>
    <button disabled={busy||pending} onClick={()=>prepare('local')}>本地轨迹诊断</button>
    {error&&<p role="alert">{error}；未启用录制或协议不兼容时不生成严格 v2 包。</p>}
    {task&&<p role={task.status==='FAILED'?'alert':'status'}>本次导出：{task.status} {task.error?.code}{task.status==='FAILED'?'；可尝试本地轨迹诊断。':''}</p>}
    {exported&&<a download href={`/api/v1${prefix}/handoffs/${encodeURIComponent(exported.job_id)}/archive`}>下载{str(exported.result.status)==='LOCAL_DIAGNOSTIC_EXPORTED'?'本地诊断（非 v2）':'演进数据包（未接收）'}</a>}
  </div>;
}
