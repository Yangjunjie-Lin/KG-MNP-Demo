import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api, object, str, type Document} from './api';
import {useWorkspace} from './shell';

export function PreparedPackageDownload({packageId}:{packageId:string}) {
  const {state,prefix,submit,busy,principal}=useWorkspace();
  const [requested,setRequested]=useState(false);
  const authorizedJobs=new Set(state.jobs.map(j=>j.job_id));
  const exported=state.results.filter(r=>r.operation==='package.export'&&r.result.package_id===packageId&&authorizedJobs.has(r.job_id)).at(-1);
  const job=useQuery({queryKey:['export-snapshot',state.project.project_id,exported?.job_id],
    queryFn:({signal})=>api<Document>(`/jobs/${encodeURIComponent(exported!.job_id)}`,{signal}),enabled:!!exported,
    refetchOnWindowFocus:false});
  const allowed=principal.permissions.includes('*')||principal.permissions.includes('package:export');
  if(!allowed)return <p className="muted">下载本体包需要 package:export 权限。</p>;
  const verified=job.data?.status==='SUCCEEDED'&&object(job.data.result).package_id===packageId;
  return <div className="package-export" style={{overflowWrap:'anywhere'}}><button disabled={busy} onClick={()=>{setRequested(true);submit(`/packages/${encodeURIComponent(packageId)}/exports`,{});}}>准备安全下载（后台任务）</button>
    <p className="muted">先通过现有导出器验证并生成固定 .kgop 快照，再下载同一任务的摘要绑定字节。关闭页面不等于取消任务。</p>
    {requested&&!exported&&<p role="status">等待导出任务提交回执；失败、取消或重试请查看任务中心。</p>}
    {job.error&&<p role="alert" className="error">导出快照复核失败：{String(job.error)}</p>}
    {exported&&job.isFetching&&<p role="status">正在核对导出任务与不可变版本…</p>}
    {verified&&<p><a download="ontology.kgop" href={`/api/v1${prefix}/exports/${encodeURIComponent(exported!.job_id)}/archive`}>下载已验证本体包（.kgop）</a><small> SHA-256：{str(object(job.data?.result).sha256)}</small></p>}
  </div>;
}
