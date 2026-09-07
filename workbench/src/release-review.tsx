import {str,rows,type Document} from './api';
import {DataTable,Field,Id,Panel} from './components';
import {useWorkspace} from './shell';

export function ReleaseReview({candidates,reviews}:{candidates:Document[];reviews:Document[]}){
  const {state,submit,busy,principal}=useWorkspace();
  return <Panel title="Release 人工审核">
    <p>当前身份：{principal.principal_id} · {principal.principal_type}。角色与人数要求来自服务器策略，不能由表单覆盖。</p>
    {candidates.map(candidate=>{
      const current=reviews.filter(r=>r.release_candidate_id===candidate.release_candidate_id).at(-1);
      return <div className="record" key={str(candidate.release_candidate_id)}>
        <Id value={candidate.release_candidate_id}/>
        <p>必需角色：{str(candidate.required_roles)}；独立审核人数至少 {str(candidate.minimum_distinct_reviewers)}。</p>
        <form onSubmit={event=>{
          event.preventDefault();const fields=new FormData(event.currentTarget);
          submit('/lifecycle/release-reviews',{candidate_id:candidate.release_candidate_id,decision:fields.get('decision'),rationale:fields.get('rationale')});
        }}>
          <Field label="Release 审核决定"><select name="decision"><option value="APPROVE">批准</option><option value="REJECT">拒绝</option></select></Field>
          <Field label="Release 审核理由"><textarea name="rationale" required/></Field>
          <button disabled={busy||principal.principal_type!=='HUMAN'}>以当前身份批准该 Release</button>
        </form>
        {current&&<>
          <p>角色与人数满足：{current.quorum_satisfied===true?'是':'否'}；审核完成：{current.finalized===true?'是':'否'}。</p>
          <DataTable data={rows(current.actions)} fields={[["reviewer_id","审核人"],["reviewer_roles","授权角色"],["action","决定"],["rationale","理由"]]}/>
          <button type="button" disabled={busy||current.quorum_satisfied!==true||current.finalized!==true}
            onClick={()=>submit('/lifecycle/releases',{candidate_id:candidate.release_candidate_id,review_id:current.review_id,expected_registry_head_hash:state.registry_head})}>使用当前 Registry CAS 发布</button>
        </>}
      </div>;
    })}
    <DataTable data={state.results.filter(r=>r.operation==='release.publish').map(r=>r.result.release as Document)} fields={[["release_id","Release"],["package_version","版本"],["release_status","发布状态"]]}/>
    <p className="muted">本地 Release 不代表环境已选择或外部系统已部署。后续版本、回归和历史回滚见“差异与环境”。</p>
  </Panel>;
}
