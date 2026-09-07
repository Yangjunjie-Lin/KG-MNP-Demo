import {useState} from 'react';
import {post,queryClient,type Job} from './api';
import {Id,Panel,Status} from './components';
import {useWorkspace} from './shell';

export function Jobs(){
  const {state,principal,busy}=useWorkspace();const [error,setError]=useState(''),[pending,setPending]=useState(false);
  async function act(job:Job,mode?:string){
    setPending(true);setError('');
    try{await post(`/jobs/${job.job_id}/${mode?'recovery':'cancel'}`,mode?{mode,expected_attempt:job.attempt}:{});await queryClient.invalidateQueries({queryKey:['state']});}
    catch(err){setError(String(err));}finally{setPending(false);}
  }
  const canRecover=principal.permissions.includes('*')||principal.permissions.includes('job:recover');
  return <><h1>任务中心</h1><p>取消运行中的任务表示“请求取消”，不等于工件已撤销。已经提交的结果保持有效。</p>
    <p>恢复首先验证正式提交回执。只有未提交、租约已过期的本地任务才可显式重试；外部执行结果不确定时不会自动重放。</p>
    {error&&<p role="alert" className="error">{error}</p>}
    {state.jobs.map(job=><Panel key={job.job_id} title={job.operation_id}>
      <Id value={job.job_id}/><p><Status value={job.status}/> · 尝试 {job.attempt}{job.error&&<span role="alert" className="error">{job.error.code}</span>}</p>
      <button disabled={busy||pending||!['QUEUED','RUNNING'].includes(job.status)} onClick={()=>act(job)}>请求取消</button>
      {job.status==='RECOVERY_REQUIRED'&&<div className="actions">
        <button disabled={busy||pending||!canRecover} onClick={()=>act(job,'RECOVER_COMMITTED')}>恢复已提交回执</button>
        <button disabled={busy||pending||!canRecover} onClick={()=>act(job,'RETRY_LOCAL')}>重试未提交的本地任务</button>
      </div>}
    </Panel>)}
  </>;
}
