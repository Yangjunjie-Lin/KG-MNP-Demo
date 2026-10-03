import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,rows,str,type Document} from './api';
import {Status} from './components';
import {useWorkspace} from './shell';

export function AgentWorkbench({stage,navigate,titles}:{stage:number;navigate:(stage:number)=>void;titles:string[]}) {
  const {state,principal,prefix}=useWorkspace();
  const [showAll,setShowAll]=useState(false);
  const [selection,setSelection]=useState({session_id:'',package_id:'',job_id:'',attempt:''});
  const [selected,setSelected]=useState<Document|null>(null);
  const search=new URLSearchParams(Object.entries(selection).filter(([,v])=>v)).toString();
  const can=(p:string)=>principal.permissions.includes('*')||principal.permissions.includes(p);
  const index=useQuery({queryKey:['step-audits',state.project.project_id,state.project.authority_revision,search],
    queryFn:()=>api<Document>(`${prefix}/modeling/audits${search?'?'+search:''}`),enabled:can('job:read'),refetchInterval:5000});
  const agents=rows(index.data?.agents||state.modeling_flow?.agent_packages);
  const records=rows(index.data?.records).filter(r=>showAll||(Array.isArray(r.stages)&&r.stages.includes(stage)));
  const downloadable=['trace:export','source:read','source:export','package:read'].every(can);
  const detail=useQuery({queryKey:['step-audit-detail',state.project.project_id,selected?.job_id,selected?.attempt],
    queryFn:()=>api<Document>(`${prefix}/modeling/audits/${encodeURIComponent(str(selected?.job_id))}?attempt=${selected?.attempt}`),
    enabled:!!selected&&downloadable,retry:false});
  return <section aria-label="双 Agent 与步骤审计" className="agent-workbench">
    <div className="agent-package-grid">{agents.map(agent=><section key={str(agent.agent_id)} className="agent-package" aria-label={str(agent.display_name)}>
      <span className="eyebrow">{str(agent.agent_id)}</span><h2>{str(agent.display_name)}</h2><p>{str(agent.responsibility)}</p>
      <div className="agent-stage-buttons">{(Array.isArray(agent.stages)?agent.stages as number[]:[]).map(n=><button key={n} aria-pressed={stage===n} onClick={()=>navigate(n)}>S{n} · {titles[n-1]}</button>)}</div>
    </section>)}</div>
    <details className="step-audit-panel"><summary>逐步审计文件 · 处理前 / 处理后</summary>
      <p>每个服务操作和实际 Agent 工具调用独立留痕；审批由授权人完成。成功执行、提交成功、验收通过和发布是不同状态。</p>
      <p className="muted">{index.data?.content_capture_enabled?'当前服务已启用受控内容快照；具体任务仍需录制权限。敏感字段会遮蔽。':'当前服务只记录摘要和版本引用；完整内容快照未启用，不能从旧摘要还原。'}</p>
      <p>模型消息录制：{index.data?.model_trace_enabled?'已配置（仍须任务授权）':'未启用'}。开启步骤正文不等于保存了模型请求。</p>
      <div className="agent-audit-filters">{(['session_id','package_id','job_id','attempt'] as const).map(key=><label key={key}>{key}<input aria-label={`审计筛选 ${key}`} value={selection[key]} onChange={e=>setSelection({...selection,[key]:e.target.value})}/></label>)}</div>
      <label><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>显示全部阶段与历史尝试</label>
      {index.error&&<p role="alert">审计列表读取失败：{String(index.error)}</p>}
      <div className="table-scroll"><table><thead><tr><th>操作 / 执行主体</th><th>任务状态</th><th>审计内容</th><th>文件</th></tr></thead><tbody>{records.map(r=><tr key={`${r.job_id}-${r.attempt}`}>
        <td>{str(r.operation_id)}<br/><small>{str(r.actor)} · 尝试 {str(r.attempt)}</small></td>
        <td><Status value={str(r.job_status)}/><br/><small>{str(r.session_output_status)}</small></td>
        <td>{str(r.content_mode)}{r.event_count!==undefined&&<small> · {str(r.event_count)} 条前后记录</small>}<br/><small>{str(r.session_id)} / 修订 {str(r.session_revision)}</small><br/><small>物理请求 {str(r.physical_requests)}；方法 {Array.isArray(r.method_ids)?r.method_ids.join(', '):'历史未记录'}</small>{downloadable&&r.availability==='AVAILABLE'&&<button onClick={()=>setSelected(r)}>查看步骤与实际 Prompt</button>}</td>
        <td>{r.availability!=='AVAILABLE'?'未录制（历史内容不可补造）':!downloadable?'需要审计及来源导出权限':['SUCCEEDED','FAILED','CANCELLED','RECOVERY_REQUIRED','SUPERSEDED_ATTEMPT'].includes(str(r.job_status))?<a download href={`/api/v1${prefix}/modeling/audits/${encodeURIComponent(str(r.job_id))}/archive?attempt=${r.attempt}`}>下载前后审计 ZIP</a>:'执行中，保留已写入记录'}</td>
      </tr>)}</tbody></table></div>
      {!records.length&&<p className="empty">尚无可见的本阶段审计任务；不会预填成功记录。</p>}
      {selected&&<section aria-label="审计详情"><h3>{str(selected.job_id)} · 尝试 {str(selected.attempt)}</h3>
        {detail.error?<p role="alert">审计详情不可用或权限已撤销：{String(detail.error)}</p>:detail.data&&<>
          <p>已验证服务归档 SHA-256：{str(detail.data.archive_sha256)}</p>
          <details><summary>实际请求 Token（含失败/取消；未知不填零）</summary><pre>{JSON.stringify(detail.data.token_usage,null,2)}</pre></details>
          <details><summary>逐方法覆盖与四项交接结论</summary><pre>{JSON.stringify(detail.data.coverage,null,2)}</pre></details>
          <details><summary>本次实际发送快照 / 公开结果</summary>{(detail.data.coverage as {dimensions?:{prompts?:string}}|undefined)?.dimensions?.prompts==='NOT_APPLICABLE_NO_MODEL_CALL'?<p>本次没有模型调用，不生成空 Prompt；程序步骤仍保留前后记录。</p>:detail.data.actual_model_trace?<pre>{JSON.stringify(detail.data.actual_model_trace,null,2)}</pre>:<p>未录制或历史不可获得；不能使用当前模板补造本次消息。</p>}</details>
          <details><summary>当前源码模板（不是历史请求）</summary><pre>{JSON.stringify(detail.data.current_templates,null,2)}</pre></details>
          <details><summary>前后记录、输入输出及错误引用</summary><pre>{JSON.stringify(detail.data.events,null,2)}</pre></details>
        </>}
      </section>}
    </details>
  </section>;
}
