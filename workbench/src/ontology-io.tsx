import {useState} from 'react';
import {Link} from 'react-router-dom';
import {api,object,rows,str,type Document} from './api';
import {DataTable,Panel,Status} from './components';
import {ArtifactViewer} from './modeling-components';
import {useWorkspace} from './shell';

export function OntologyIOEvaluation(){
  const {state,prefix}=useWorkspace();const [inspection,setInspection]=useState<Document|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const report=object(inspection?.report);
  async function read(file:File|undefined){
    if(!file)return;setError('');setInspection(null);setLoading(true);
    try{
      if(file.size>800000)throw new Error('报告超过 800 KB，请使用不含原始输入/回复的 scorecard。');
      const parsed:unknown=JSON.parse(await file.text());
      const response=await api<{payload:Document}>('/operations/ontology.io.inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:state.project.project_id,report:parsed})});
      setInspection(response.payload);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <><header className="modeling-heading"><div><h1>本体 I/O 评测</h1><p>独立科研报告，未审核的评测草稿不进入生产审批或发布。</p></div><Link to={`${prefix}/modeling`}>返回五阶段建模</Link></header>
    <Panel title="读取实际研究报告"><p>导入 CLI 生成的 scorecard。后端核验格式与敏感字段；导入文件中的成绩仍是外部声明，不是服务器签名或重新计分结果。</p><input aria-label="研究报告 JSON" type="file" accept="application/json,.json" disabled={loading} onChange={e=>void read(e.target.files?.[0])}/>{loading&&<p role="status">正在核验报告…</p>}{error&&<p role="alert">{error}</p>}</Panel>
    {!inspection?<Panel title="运行状态"><Status value="NOT_RUN"/><p>尚未导入实测报告。指标为 null，不显示演示高分。</p><p>专家审核对比：NOT_RUN。立项 80% / 90% / 90% 目标尚无独立验收证据。</p></Panel>:<>
      <Panel title="任务与允许输入"><DataTable data={[report]} fields={[["benchmark_id","Benchmark"],["task_id","任务"],["dataset_version","数据版本"],["evaluation_scope","评测范围"],["system_id","系统"],["model_id","模型"],["declared_revision","声明修订"],["split","切分"]]}/><p>输入摘要：{str(report.input_manifest_sha256)}；预测摘要：{str(report.prediction_manifest_sha256)}</p></Panel>
      <Panel title="原生指标与实际状态"><Status value={str(report.status)}/><DataTable data={rows(report.metrics).map(m=>({...m,value:m.value===null?`null / ${str(m.status)}`:m.value}))} fields={[["name","原指标名"],["source","评分来源"],["matching","匹配"],["value","值"],["unit","单位"],["status","状态"],["denominator","分母"]]}/><p>样本/重复记录数 {str(report.sample_count)}；失败 {str(report.failure_count)}。不计算跨任务加权总分。</p></Panel>
      <Panel title="同模型比较与不确定性">{report.comparison?<ArtifactViewer value={object(report.comparison)}/>:<p>NOT_RUN / null：未提供成对比较、置信区间与预算控制结果。</p>}</Panel>
      <Panel title="失败 投影 资源和依据"><ArtifactViewer value={{samples:report.samples,resources:report.resources,limitations:report.limitations,source_commit:report.source_commit,source_fingerprint_sha256:report.source_fingerprint_sha256,scorer_commit:report.scorer_commit,scorer_config_sha256:report.scorer_config_sha256,observed_model_ids:report.observed_model_ids}}/></Panel>
      <p className="notice">{str(inspection.source_authenticity)} · {str(inspection.validation)}。研究指标不会改变当前项目的候选、审核、版本或发布状态。</p>
    </>}
  </>;
}
