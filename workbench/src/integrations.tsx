import {useState} from 'react';
import {object,outputs,str} from './api';
import {DataTable,Field,Panel,SelectDocument} from './components';
import {useWorkspace} from './shell';

export function Integrations(){
 const {state,submit,busy}=useWorkspace();const [release,setRelease]=useState('');
 const releases=outputs(state,'release.publish','release');
 const plans=state.results.filter(r=>r.operation==='integration.plan').map(r=>r.result);
 const approvals=state.results.filter(r=>r.operation==='integration.review').map(r=>r.result);
 const observations=state.results.filter(r=>['integration.execute','integration.verify'].includes(r.operation)).map(r=>r.result);
 return <><h1>集成状态</h1><Panel title="GraphDB 可用性与审核计划"><p>本地工具链不依赖 GraphDB。当前没有配置经许可的外部传输；离线项目不会因批准计划而获准联网。</p><SelectDocument label="已发布版本" items={releases} idKey="release_id" value={release} onChange={setRelease}/><button disabled={busy||!release} onClick={()=>submit('/integrations/plans',{release_id:release,target_id:'local-graphdb'})}>生成受版本约束的集成计划</button>{plans.map(item=>{const plan=object(item.plan);return <div className="record" key={str(plan.plan_id)}><code>{str(plan.plan_id)}</code><p>{str(item.availability)} · offline_only={str(item.offline_only)}</p><form onSubmit={e=>{e.preventDefault();submit('/integrations/reviews',{plan_id:plan.plan_id,rationale:new FormData(e.currentTarget).get('reason')});}}><Field label="计划审核理由"><textarea name="reason" required/></Field><button disabled={busy}>人工审核计划</button></form>{approvals.filter(a=>object(a.approval).plan_id===plan.plan_id).map(a=><button key={str(object(a.approval).approval_id)} disabled={busy} onClick={()=>submit('/integrations/observations',{plan_id:plan.plan_id,approval_id:object(a.approval).approval_id})}>读取实际可用性与部署观测</button>)}</div>})}<DataTable data={observations} fields={[["status","集成状态"],["external_request_attempted","是否实际尝试外部请求"],["observed_deployed_release_id","实际观测部署"],["reason","阻断原因"]]}/></Panel><Panel title="本地业务请求 Outbox"><form onSubmit={e=>{e.preventDefault();submit('/integrations/workflow-requests',{release_id:release,action_id:'request-source-review',note:new FormData(e.currentTarget).get('note')});}}><Field label="请求说明"><textarea name="note" required/></Field><button disabled={busy||!release}>将来源复核请求加入 Outbox</button></form><p>入队不等于业务执行。此配置没有外部业务执行器。</p><DataTable data={state.results.filter(r=>r.operation==='workflow.enqueue').map(r=>r.result)} fields={[["status","队列状态"],["last_verification_status","执行验证"],["desired_release_id","关联版本"]]}/></Panel></>;
}
