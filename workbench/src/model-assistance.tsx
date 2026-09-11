import {useState} from 'react';
import {object,rows,str} from './api';
import {Field,Panel} from './components';
import {useWorkspace} from './shell';
import {ArtifactViewer} from './modeling-components';

export function ModelAssistance({repair=false}:{repair?:boolean}){
  const {state,submit,busy}=useWorkspace();const [newIris,setNewIris]=useState(''),[mapping,setMapping]=useState(''),[error,setError]=useState('');
  const session=object(state.modeling_session);
  const current=state.results.filter(r=>rows(session.outputs).some(o=>o.job_id===r.job_id&&o.status==='CURRENT'));
  const prepared=current.filter(r=>r.operation==='modeling.prepare').at(-1)?.result;
  const proposal=current.filter(r=>r.operation==='modeling.proposal').at(-1)?.result;
  const receipts=state.results.filter(r=>r.operation==='modeling.proposal'&&r.result.model_assistance);
  function run(){
    setError('');
    try{submit('/modeling/proposals',{bundle_id:object(prepared?.bundle).modeling_input_bundle_id,providers:repair?['manual-candidate-provider']:['baseline-reuse-provider','manual-candidate-provider'],
      ...(mapping.trim()?{record_mapping:JSON.parse(mapping)}:{}),
      model_assistance:{execution_mode:'LIVE',action:repair?'REPAIR':'GENERATE',retrieval:'LLM_SUBSTITUTE',chunking:'UNICODE_SUBSTITUTE',
        approved_new_iris:newIris.split('\n').map(s=>s.trim()).filter(Boolean),parent_proposal_id:repair?object(proposal?.proposal).proposal_id:null,expected_session_revision:session.revision}});
    }catch{setError('映射配置需要有效 JSON。');}
  }
  return <details><summary>{repair?'模型辅助局部修复与重验':'调用已有 LLM 辅助建模'}</summary><Panel title={repair?'白名单修复 · 新候选、新检查、新审核':'LIVE 模型辅助 · 显式替代方法'}>
    <p>使用服务器已有 API 配置；会发送本项目规则和来源片段。模型只提出候选，不能批准或修改独立答案。当前使用 LLM 检索替代与 Unicode 分块替代，不计为 BGE／FAISS 推理。</p>
    {!repair&&<Field label="明确允许新建的 IRI（每行一个；留空仅复用）"><textarea value={newIris} onChange={e=>setNewIris(e.target.value)}/></Field>}
    {!repair&&<Field label="可选声明式映射 JSON（留空使用锁定领域配置）"><textarea value={mapping} onChange={e=>setMapping(e.target.value)}/></Field>}
    {repair&&<p>仅修复当前候选中的属性值或关系目标，并核验逐字引文；结构、硬规则和验收答案不可修改。无安全补丁会明确拒绝。</p>}
    <button disabled={busy||!prepared||!session.session_id||(repair&&!proposal)} onClick={run}>{repair?'生成修复版本并自动重验':'运行两轮建模、抽取与自动重验'}</button>
    {!session.session_id&&<p className="notice">请先冻结第一阶段会话。</p>}{error&&<p role="alert">{error}</p>}
    {receipts.map(r=><details key={r.job_id}><summary>真实调用与验证 · {str(r.job_id)}</summary><ArtifactViewer value={{model_assistance:r.result.model_assistance,automatic_validation:r.result.automatic_validation}}/></details>)}
  </Panel></details>;
}
