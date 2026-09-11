import {useState} from 'react';
import {object,str} from './api';
import {Field} from './components';
import {useWorkspace} from './shell';

export function ManualDrafts(){
  const {state,submit,busy}=useWorkspace();const [error,setError]=useState('');
  const prepared=state.results.filter(r=>r.operation==='modeling.prepare').at(-1)?.result;
  if(!prepared)return null;
  return <details><summary>无基线新建／人工结构与事实草案</summary><p>仅接受现有 CandidateDraft 契约。IRI、来源、依赖和候选类型仍由后端校验；上传 APPROVED 或脚本不能授予权限。此入口不会执行模型或自动审核。</p><form onSubmit={e=>{e.preventDefault();setError('');try{const drafts=JSON.parse(String(new FormData(e.currentTarget).get('drafts')));submit('/modeling/proposals',{bundle_id:str(object(prepared.bundle).modeling_input_bundle_id),providers:['manual-candidate-provider'],manual_drafts:drafts});}catch{setError('草案必须是合法 JSON 数组。');}}}><Field label="CandidateDraft JSON（含真实证据和依赖引用）"><textarea name="drafts" required rows={8}/></Field><button disabled={busy}>提交新版本人工候选（待检查和审核）</button>{error&&<p role="alert">{error}</p>}</form></details>;
}
