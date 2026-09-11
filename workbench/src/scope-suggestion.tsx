import {object} from './api';
import {Field} from './components';
import {ArtifactViewer} from './modeling-components';
import {useWorkspace} from './shell';

export function ScopeSuggestion({runId}:{runId:string}){
  const {state,submit,busy}=useWorkspace();
  const suggestion=state.results.filter(r=>r.operation==='modeling.scope.draft'&&object(r.result.five_stage).source_run_id===runId).at(-1);
  return <details><summary>可选实时模型范围建议（不会自动审批）</summary><p>调用服务端配置的固定 Qwen/vLLM 模型与修订。未配置或能力不符合要求时明确阻断，不用确定性模板冒充 LIVE 结果。</p><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);submit('/modeling/scope-drafts',{run_id:runId,business_goal:f.get('goal'),business_rules:String(f.get('rules')).split('\n').filter(Boolean)});}}><Field label="AI 草拟业务目标"><textarea name="goal" required/></Field><Field label="明确业务规则（每行一项）"><textarea name="rules" required/></Field><button disabled={busy||!runId}>请求已配置的 Qwen 范围提案</button></form>{suggestion&&<ArtifactViewer title="实际模型建议及请求收据" value={suggestion.result}/>}</details>;
}
