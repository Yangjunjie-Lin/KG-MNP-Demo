import {useEffect,useRef,useState} from 'react';
import {object, post, rows, str, type Document} from './api';
import {Field} from './components';
import {useWorkspace} from './shell';

export function ScenarioConfiguration({selection,onChange,runId,onPreview}:{selection:Document|null;onChange:(v:Document)=>void;runId:string;onPreview:(ready:boolean)=>void}) {
  const {state,prefix,principal,submit,busy}=useWorkspace();
  const [filter,setFilter]=useState(''),[preview,setPreview]=useState<Document|null>(null),[error,setError]=useState('');
  const session=object(state.modeling_session), active=object(object(session.scenario).effective);
  const can=principal.principal_type==='HUMAN'&&['scope:approve','model:propose','source:read'].every(p=>principal.permissions.includes('*')||principal.permissions.includes(p));
  const scenes=state.scenario_catalogue||[], chosen=scenes.find(s=>s.scenario_id===selection?.scenario_id&&s.scenario_version===selection?.scenario_version);
  const selectionKey=JSON.stringify({selection,runId,prefix}),latestKey=useRef(selectionKey);
  latestKey.current=selectionKey;
  useEffect(()=>{setPreview(null);onPreview(false);setError('');},[selectionKey,onPreview]);
  function change(value:Document){onChange(value);setPreview(null);onPreview(false);setError('');}
  async function inspect(){
    const key=selectionKey;
    try{
      setError('');
      const result=await post<Document>(`${prefix}/toolchain/modeling.scenario.preview`,{selection,run_id:runId||null});
      if(latestKey.current!==key)return;
      setPreview(result);onPreview(result.status==='AVAILABLE');
    }catch(e){if(latestKey.current===key){setError(String(e));onPreview(false);}}
  }
  const legacy=!!active.scenario_id&&active.scenario_version!=='2.0.0';
  return <details className="scenario-configuration" open={!active.scenario_id||legacy}><summary>领域场景与 Prompt 预设 · {str(active.scenario_id)||'尚未选择场景'}</summary>
    <p>选择场景，加载五个步骤的生成与审核 Prompt 预设。模板是待确认的工程草案，不是专家批准；原证据、硬检查和人工审批不变。</p>
    {legacy&&<p role="alert">当前是历史场景配置，不能继续运行。请选择当前模板并预检、保存，之后从 S1 重新确认、生成和审核；旧记录保留。</p>}
    <Field label="筛选领域或用途"><input value={filter} onChange={e=>setFilter(e.target.value)}/></Field>
    <div className="form-grid">{scenes.filter(s=>`${s.name} ${s.purpose}`.includes(filter)).map(scene=>{
      const pack=object(scene.domain_pack),compatible=pack.pack_id===state.project.domain_pack&&pack.pack_version===state.project.domain_pack_version;
      return <label key={str(scene.scenario_id)} className="record"><input type="radio" name="scenario" checked={selection?.scenario_id===scene.scenario_id&&selection?.scenario_version===scene.scenario_version} disabled={!can||busy} onChange={()=>change({scenario_id:scene.scenario_id,scenario_version:scene.scenario_version})}/>{str(scene.name)} · v{str(scene.scenario_version)}<small>{str(scene.purpose)}；{compatible?'领域包匹配，仍需数据预检':'与当前锁定领域包不兼容，请新建对应项目'}</small></label>;
    })}</div>
    {chosen&&<>
      <details><summary>五步骤 Prompt 模板预览</summary>{(Array.isArray(chosen.additions)?chosen.additions as string[][]:[]).map(([pre,post],index)=><section key={index} aria-label={`S${index+1} 场景 Prompt`}><h4>S{index+1}</h4><p>生成前指导：{pre}</p><p>生成后审核：{post}</p></section>)}</details>
      <p>场景预设与专家指导共同用于生成、审核、修订；各步骤的专家指导区仍可编辑并确认。切换场景不覆盖手写指导，须重新确认。</p>
      <button type="button" disabled={busy||!can||!runId} onClick={inspect}>只读预检场景模板（不调用模型）</button>
      {preview&&<section aria-label="场景配置预检"><p>预检：{str(preview.status)}；最早失效阶段：{str(preview.earliest_affected_stage)}；项目兼容：{String(preview.project_compatible)}</p><details><summary>输入适配与冻结模板</summary><pre>{JSON.stringify({stages:object(preview.effective).stages,inputs:preview.inputs},null,2)}</pre></details></section>}
      {!!session.session_id&&<button type="button" disabled={busy||!can||preview?.status!=='AVAILABLE'} onClick={()=>submit('/toolchain/modeling.scenario.save',{selection,expected_revision:session.revision})}>保存场景模板为新版本（待专家重确认）</button>}
    </>}
    {error&&<p role="alert">{error}</p>}
    {!!active.scenario_id&&<p>当前模板：{str(active.scenario_id)} · v{str(active.scenario_version)}；冻结摘要 {str(active.digest)}</p>}
    {rows(session.outputs).some(o=>o.status==='STALE')&&<p>已有产物失效；请从提示的最早阶段重验、重审，不沿用旧 PASS。</p>}
  </details>;
}

export function ScenarioStageResults({stage}:{stage:number}){
  const {state,principal,submit,busy}=useWorkspace();
  const session=object(state.modeling_session),effective=object(object(session.scenario).effective);
  if(!effective.scenario_id||effective.scenario_version!=='2.0.0')return null;
  const digest=object(effective.stage_digests)[`S${stage}`];
  const currentOutputs=rows(session.outputs).filter(o=>o.status==='CURRENT'),loops=rows(object(session.expert).loops);
  const result=state.results.filter(r=>currentOutputs.some(o=>o.job_id===r.job_id)||loops.some(l=>l.job_id===r.job_id&&l.current&&rows(l.methods).some(m=>m.stage_id===stage&&m.current)))
    .flatMap(r=>rows(r.result.scenario_outputs)).filter(r=>r.stage_id===stage&&r.stage_configuration_digest===digest).at(-1);
  const build=currentOutputs.filter(r=>r.operation==='compile.build').at(-1);
  const quality=object(session.scenario_quality),currentQuality=build&&quality.package_id===build.identifier&&quality.configuration_digest===effective.digest?object(quality.metrics):{status:'NOT_EVALUATED_NO_CURRENT_INDEPENDENT_LABELS'};
  const can=principal.permissions.includes('*')||principal.permissions.includes('acceptance:run');
  return <section aria-label="场景实际输出"><h3>S{stage} 实际产物与独立质量</h3>
    {result?<><p>实际候选计数：{JSON.stringify(result.observed_counts)}</p><details><summary>实际输出引用、诊断展开与服务契约</summary><pre>{JSON.stringify(result,null,2)}</pre></details></>:<p>NOT_RUN：当前配置还没有本阶段产物。</p>}
    <p>独立质量：{str(currentQuality.status)}；只有预先冻结标注才计算对象、关系、属性各自的 TP/FP/FN。</p>
    {stage===5&&<><pre>{JSON.stringify(currentQuality,null,2)}</pre><button disabled={busy||!can||!build} onClick={()=>submit('/toolchain/modeling.scenario.quality',{package_id:build?.identifier,expected_revision:session.revision})}>对当前包执行独立质量评测（不调用模型）</button></>}
  </section>;
}
