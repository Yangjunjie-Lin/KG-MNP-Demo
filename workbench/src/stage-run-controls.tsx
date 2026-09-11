import {useEffect,useRef,useState} from 'react';
import {object,outputs,post,rows,str,type Document} from './api';
import {useWorkspace} from './shell';

export function StageRunControls({stage,runId,navigate}:{stage:number;runId:string;navigate:(n:number)=>void}){
  const {state,prefix}=useWorkspace();const [message,setMessage]=useState('');const [jobId,setJob]=useState('');
  const continuous=useRef(false),consumed=useRef(''),startRef=useRef<(n:number)=>Promise<void>>(async()=>{});
  const scope=outputs(state,'modeling.scope','scope').at(-1),approval=outputs(state,'modeling.scope.approve','approval').at(-1);
  const prepared=state.results.filter(r=>r.operation==='modeling.prepare').at(-1)?.result;
  const proposed=state.results.filter(r=>r.operation==='modeling.proposal').at(-1)?.result;
  const plan=state.results.filter(r=>['compile.plan','compile.plan.exact'].includes(r.operation)).at(-1)?.result.plan;
  async function start(n:number){
    let path='',body:Document={};
    if(n===1&&runId){path='/modeling/profiles';body={run_id:runId};}
    if(n===2&&scope&&approval&&approval.scope_id===scope.scope_id&&approval.decision==='APPROVE'&&prepared){
      path='/modeling/preparations';body={scope_id:scope.scope_id,approval_id:approval.approval_id,questions:rows(object(prepared.questions).questions).map(q=>({question_text:q.question_text,purpose:q.purpose,required_concepts:q.required_concepts,expected_answer_shape:q.expected_answer_shape}))};
    }
    if(n===3&&prepared&&prepared.record_mapping){path='/modeling/proposals';body={bundle_id:object(prepared.bundle).modeling_input_bundle_id,providers:['baseline-reuse-provider','manual-candidate-provider']};}
    if(n===4&&proposed){path='/modeling/semantic-checks';body={review_id:object(proposed.queue).review_queue_id,candidate_ids:['tbox_candidates','abox_candidates','mapping_candidates','shacl_candidates'].flatMap(k=>rows(object(proposed.proposal)[k]).map(c=>c.candidate_id))};}
    if(n===5&&plan){path='/compilations/builds';body={plan_id:object(plan).plan_id};}
    if(!path){continuous.current=false;setMessage('已暂停：此阶段需要先在下方填写配置或完成真实人工审核，不会自动补填或批准。');return;}
    try{setMessage('正在提交真实阶段操作…');const result=await post<{job_id:string}>(prefix+path,body);setJob(result.job_id);setMessage('已提交后台任务；暂停流转不会取消已提交的工作。');}
    catch(error){continuous.current=false;setMessage(`已暂停：${String(error)}。重新认证或修正配置后，请先核对任务收据。`);}
  }
  useEffect(()=>{startRef.current=start;});
  const job=state.jobs.find(j=>j.job_id===jobId),result=state.results.find(r=>r.job_id===jobId)?.result;
  useEffect(()=>{
    if(!job||consumed.current===jobId||['QUEUED','RUNNING','CANCEL_REQUESTED'].includes(job.status))return;
    if(job.status==='SUCCEEDED'&&!result)return;
    consumed.current=jobId;
    const failedCheck=result&&(rows(object(result.five_stage).step_runs).some(r=>r.validation_status==='FAIL')||object(result.prevalidation).status==='FAIL');
    if(job.status!=='SUCCEEDED'||failedCheck){continuous.current=false;setMessage(`已暂停：${job.error?.code||job.status}，请核对检查结果。`);return;}
    if(stage===4||stage===5){continuous.current=false;setMessage(stage===4?'检查已运行。等待真实人工逐项审核，不自动批准或冻结。':'阶段操作完成，请核对实际验证与交付结果。');return;}
    if(continuous.current){navigate(stage+1);void startRef.current(stage+1);}else setMessage('阶段操作完成。可查看真实前后变化。');
  },[job,result,jobId,stage,navigate]);
  const busy=!!job&&['QUEUED','RUNNING','CANCEL_REQUESTED'].includes(job.status);
  return <div className="stage-run-controls"><div className="actions"><button disabled={busy} onClick={()=>{continuous.current=false;void start(stage);}}>运行当前阶段／重新运行</button><button disabled={busy} onClick={()=>{continuous.current=true;void start(stage);}}>连续运行可执行阶段</button><button onClick={()=>{continuous.current=false;setMessage('已暂停流转；已提交任务仍可在运行记录中查看或取消。');}}>暂停流转</button></div>{message&&<p role="status" className="notice">{message}</p>}{jobId&&<details><summary>当前任务引用</summary><code>{str(jobId)}</code></details>}</div>;
}
