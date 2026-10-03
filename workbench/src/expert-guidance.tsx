import {useState} from 'react';
import {Link} from 'react-router-dom';
import {object, rows, str, type Document} from './api';
import {Field, Status} from './components';
import {useWorkspace} from './shell';

export function ExpertGuidance({stage}:{stage:number}) {
  const {state, principal, prefix, busy, submit} = useWorkspace();
  const session = object(state.modeling_session), expert = object(session.expert);
  const version = object(object(expert.stages)[String(stage)] || state.expert_defaults?.[String(stage)]);
  const configuration = object(version.configuration);
  const scenario = object(object(session.scenario).effective);
  const additions = object(object(object(scenario.stages)[`S${stage}`]).expert_additions);
  const can = (p:string) => principal.permissions.includes('*') || principal.permissions.includes(p);
  const editable = principal.principal_type === 'HUMAN' && can('model:propose') && can('source:read') && can(stage===1?'scope:approve':'review:decide');
  const loops = rows(expert.loops).filter(r=>rows(r.methods).some(m=>m.stage_id===stage));
  const latest = loops.at(-1);
  const [error,setError] = useState('');
  async function save(form:HTMLFormElement) {
    const data = new FormData(form); setError('');
    try {
      const next:Document = {...configuration, pre_guidance_prompt:String(data.get('pre')), post_review_prompt:String(data.get('post')),
        method_overrides:JSON.parse(String(data.get('overrides'))), criteria:JSON.parse(String(data.get('criteria'))),
        budget:JSON.parse(String(data.get('budget'))), coverage_confirmed:data.get('coverage')==='on'};
      await submit('/toolchain/modeling.expert.save',{expected_revision:session.revision,
        expected_configuration_digest:version.digest, configuration:next, confirm:true});
    } catch { setError('高级配置必须为有效 JSON；原版本未覆盖。'); }
  }
  return <details className="expert-guidance"><summary>专家指导 · S{stage} · {expert.enabled?str(version.status):'旧模式（尚未启用专家闭环）'}</summary>
    <p>默认模板待专家确认。确认 Prompt 不批准本次产物；AI PASS 不代替人工范围批准、逐项审核或冻结。</p>
    <p>配置版本 {str(version.version)} · {str(version.origin)} · 确认人 {str(version.confirmed_by)||'尚无'}。配置保存后下游旧审核失效。</p>
    {!!scenario.scenario_id&&<section aria-label={`S${stage} 已冻结场景 Prompt`}><p>场景模板：{str(scenario.scenario_id)} · v{str(scenario.scenario_version)}（与下方专家指导共同生效）</p><p>场景生成指导：{str(additions.pre_guidance)}</p><p>场景审核要求：{str(additions.post_review)}</p></section>}
    <form key={`${stage}-${version.digest}`} onSubmit={e=>{e.preventDefault();save(e.currentTarget);}}>
      <Field label="生成前专家指导"><textarea name="pre" defaultValue={str(configuration.pre_guidance_prompt)} required maxLength={12000} disabled={!editable}/></Field>
      <Field label="生成后审核要求"><textarea name="post" defaultValue={str(configuration.post_review_prompt)} required maxLength={12000} disabled={!editable}/></Field>
      <details><summary>高级：检查点、方法覆盖与有界预算</summary>
        <p>全部方法继承阶段默认，只有明确覆盖项单独保存；不能由模型删除必需检查点。网络重试与业务修订分别计数。</p>
        <Field label="结构化检查点 JSON"><textarea name="criteria" defaultValue={JSON.stringify(configuration.criteria,null,2)} disabled={!editable}/></Field>
        <Field label="方法覆盖 JSON"><textarea name="overrides" defaultValue={JSON.stringify(configuration.method_overrides||{},null,2)} disabled={!editable}/></Field>
        <Field label="循环预算 JSON"><textarea name="budget" defaultValue={JSON.stringify(configuration.budget,null,2)} disabled={!editable}/></Field>
      </details>
      <label><input name="coverage" type="checkbox" required disabled={!editable}/>我确认检查点覆盖当前两份文本；未覆盖要求不能按 PASS 放行。</label>
      <button disabled={busy||!editable||!session.session_id}>保存并确认指导（新版本）</button>
    </form>
    {error&&<p role="alert">{error}</p>}
    <p>开始/继续闭环：使用下方本阶段原运行按钮，已启用会话由服务强制检查与审核，直接 API 也适用。未配置或无模型权限时受阻。</p>
    {latest&&<section aria-label="专家闭环结果"><h3>当前闭环 <Status value={str(latest.status)}/></h3>
      <p>修订轮次 {str(latest.revision_round)}；停止原因 {str(latest.stop_reason)}；{latest.current?'当前结论':'旧结论已失效'}。</p>
      <p>真实请求 {str(object(latest.token_usage).physical_calls)}；Token 已知小计 {JSON.stringify(object(latest.token_usage).known_subtotal)}。总计未知字段保留 null：{JSON.stringify(object(latest.token_usage).totals)}。</p>
      <details><summary>候选摘要、逐方法问题、程序检查与前后差异</summary><pre>{JSON.stringify(latest.rounds,null,2)}</pre></details>
      <p>审核正文、问题说明与实际 Prompt 通过上方受权限控制的“步骤审计”查看；METADATA_ONLY 不能还原正文。</p>
      <form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const round=rows(latest.rounds).at(-1);submit('/toolchain/modeling.expert.reaudit',{
        expected_revision:session.revision,job_id:latest.reviewed_job_id||latest.job_id,candidate_digest:round?.candidate_digest,
        feedback:String(f.get('feedback'))||null});}}>
        <Field label="针对当前候选的具体意见（禁止粘贴独立验收答案）"><textarea name="feedback" maxLength={4000}/></Field>
        <button disabled={busy||!can('model:propose')||!can('trace:export')||!can('review:decide')}>补充意见并重审</button>
      </form>
    </section>}
    <Link to={`${prefix}/jobs`}>停止运行 / 查看取消与恢复状态（原任务中心权限）</Link>
  </details>;
}
