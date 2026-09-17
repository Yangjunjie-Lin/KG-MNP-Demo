import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,rows,str,type Document} from './api';
import {Status} from './components';
import {useWorkspace} from './shell';

export function AgentWorkbench({stage,navigate,titles}:{stage:number;navigate:(stage:number)=>void;titles:string[]}) {
  const {state,principal,prefix}=useWorkspace();
  const [showAll,setShowAll]=useState(false);
  const can=(p:string)=>principal.permissions.includes('*')||principal.permissions.includes(p);
  const index=useQuery({queryKey:['step-audits',state.project.project_id,state.project.authority_revision],
    queryFn:()=>api<Document>(`${prefix}/modeling/audits`),enabled:can('job:read'),refetchInterval:5000});
  const agents=rows(index.data?.agents||state.modeling_flow?.agent_packages);
  const records=rows(index.data?.records).filter(r=>showAll||(Array.isArray(r.stages)&&r.stages.includes(stage)));
  const downloadable=['trace:export','source:read','source:export','package:read'].every(can);
  return <section aria-label="双 Agent 与步骤审计" className="agent-workbench">
    <div className="agent-package-grid">{agents.map(agent=><section key={str(agent.agent_id)} className="agent-package" aria-label={str(agent.display_name)}>
      <span className="eyebrow">{str(agent.agent_id)}</span><h2>{str(agent.display_name)}</h2><p>{str(agent.responsibility)}</p>
      <div className="agent-stage-buttons">{(Array.isArray(agent.stages)?agent.stages as number[]:[]).map(n=><button key={n} aria-pressed={stage===n} onClick={()=>navigate(n)}>S{n} · {titles[n-1]}</button>)}</div>
    </section>)}</div>
    <details className="step-audit-panel"><summary>逐步审计文件 · 处理前 / 处理后</summary>
      <p>每个服务操作和实际 Agent 工具调用独立留痕；审批由授权人完成。成功执行、提交成功、验收通过和发布是不同状态。</p>
      <p className="muted">{index.data?.content_capture_enabled?'当前服务已启用受控内容快照；具体任务仍需录制权限。敏感字段会遮蔽。':'当前服务只记录摘要和版本引用；完整内容快照未启用，不能从旧摘要还原。'}</p>
      <label><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>显示全部阶段与历史尝试</label>
      {index.error&&<p role="alert">审计列表读取失败：{String(index.error)}</p>}
      <div className="table-scroll"><table><thead><tr><th>操作 / 执行主体</th><th>任务状态</th><th>审计内容</th><th>文件</th></tr></thead><tbody>{records.map(r=><tr key={`${r.job_id}-${r.attempt}`}>
        <td>{str(r.operation_id)}<br/><small>{str(r.actor)} · 尝试 {str(r.attempt)}</small></td>
        <td><Status value={str(r.job_status)}/><br/><small>{str(r.session_output_status)}</small></td>
        <td>{str(r.content_mode)}{r.event_count!==undefined&&<small> · {str(r.event_count)} 条前后记录</small>}</td>
        <td>{r.availability!=='AVAILABLE'?'未录制（历史内容不可补造）':!downloadable?'需要审计及来源导出权限':['SUCCEEDED','FAILED','CANCELLED','RECOVERY_REQUIRED','SUPERSEDED_ATTEMPT'].includes(str(r.job_status))?<a download href={`/api/v1${prefix}/modeling/audits/${encodeURIComponent(str(r.job_id))}/archive?attempt=${r.attempt}`}>下载前后审计 ZIP</a>:'执行中，保留已写入记录'}</td>
      </tr>)}</tbody></table></div>
      {!records.length&&<p className="empty">尚无可见的本阶段审计任务；不会预填成功记录。</p>}
    </details>
  </section>;
}
