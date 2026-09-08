import {useQuery} from '@tanstack/react-query';
import {Link} from 'react-router-dom';
import {api,object,str,type Document,type ProjectState} from './api';
import {DataTable,Id,Panel,Status} from './components';
import {useWorkspace} from './shell';

export function projectArtifacts(state:ProjectState){
  const latest=(operation:string)=>state.results.filter(row=>row.operation===operation).at(-1)?.result;
  const batch=state.results.filter(row=>['source.register','source.batch'].includes(row.operation)).at(-1)?.result;
  return {
    batch:object(batch?.batch).batch_id,
    proposal:object(latest('modeling.proposal')?.proposal).proposal_id,
    review:object(latest('modeling.proposal')?.queue).review_queue_id,
    confirmed:object(latest('review.finalize')?.confirmed_package).package_id,
    compilation:latest('compile.build')?.package_id,
    release:object(latest('release.publish')?.release).release_id,
  };
}

export function ProjectOverview(){
  const {state,prefix}=useWorkspace();
  const artifacts=projectArtifacts(state);
  const review=useQuery({queryKey:['overview-review',state.project.project_id,artifacts.review,state.project.authority_revision],
    queryFn:({signal})=>api<{status:Document}>(`${prefix}/reviews/${encodeURIComponent(str(artifacts.review))}`,{signal}),enabled:!!artifacts.review});
  const blocked=state.jobs.filter(job=>['FAILED','RECOVERY_REQUIRED'].includes(job.status)).map(job=>({...job,error_code:job.error?.code??''}));
  return <><h1>项目概览</h1><Panel title="项目与权威版本"><dl>
    <dt>领域包</dt><dd>{state.project.domain_pack} · {state.project.domain_pack_version}</dd>
    <dt>Workspace 状态</dt><dd><Status value={state.project.status}/></dd>
    <dt>项目修订</dt><dd>{state.project.authority_revision}</dd>
    <dt>项目 ID</dt><dd><Id value={state.project.project_id}/></dd>
  </dl></Panel><Panel title="当前工件与审核状态"><dl>
    {([['最近数据批次',artifacts.batch,'sources'],['最近 Proposal',artifacts.proposal,'modeling'],['审核队列',artifacts.review,'modeling'],
      ['最近确认包',artifacts.confirmed,'modeling'],['最近成功编译 Package',artifacts.compilation,'releases'],['最近发布 Release',artifacts.release,'releases']] as const).map(([label,value,route])=>
      <div className="artifact-summary" key={label}><dt>{label}</dt><dd>{value?<Link to={`${prefix}/${route}`}><Id value={value}/></Link>:'尚未生成'}</dd></div>)}
  </dl>{!artifacts.review?<p>尚无审核队列。</p>:review.error?<p role="alert" className="error">审核状态读取失败：{String(review.error)}</p>:review.isPending?<p role="status">正在重放当前审核动作…</p>:review.data&&<p>
    待形成一致决定：{str(review.data.status.remaining_count)}；决定冲突：{Array.isArray(review.data.status.inconsistent_candidate_ids)?review.data.status.inconsistent_candidate_ids.length:0}；待补证：{Array.isArray(review.data.status.requested_evidence_candidate_ids)?review.data.status.requested_evidence_candidate_ids.length:0}。
    动作统计不代替角色、quorum 和最终确认校验。
  </p>}</Panel><Panel title="任务阻断与恢复">{blocked.length?<><p>以下是失败或待恢复任务，不将历史失败改写为当前版本验证结论。</p><DataTable data={blocked} fields={[["operation_id","操作"],["status","任务状态"],["error_code","阻断原因"],["job_id","任务 ID"]]}/><Link to={`${prefix}/jobs`}>查看失败详情与显式恢复</Link></>:<p>当前没有失败或待恢复任务。</p>}</Panel>
  <Panel title="工作流程"><ol className="workflow"><li><Link to={`${prefix}/sources`}>上传资料并运行解析计划</Link></li><li><Link to={`${prefix}/modeling`}>核验证据、定义范围与能力问题、逐项审核</Link></li><li><Link to={`${prefix}/releases`}>确认、编译、真实验证与发布</Link></li><li><Link to={`${prefix}/versions`}>比较版本与审核环境选择</Link></li></ol></Panel>
  <Panel title="最新任务"><DataTable data={state.jobs.slice(0,10)} fields={[["operation_id","操作"],["status","状态"],["job_id","任务 ID"]]}/></Panel></>;
}
