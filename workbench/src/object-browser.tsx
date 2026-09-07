import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,post,str,type Document} from './api';
import {DataTable,Field,Id,Panel,SelectDocument} from './components';
import {useWorkspace} from './shell';

type ObjectPage={package_id:string;rows:Document[];page:{offset:number;limit:number;truncated:boolean}};
export function ObjectBrowser({packages,releases}:{packages:Document[];releases:Document[]}){
  const {state,prefix}=useWorkspace();
  const [packageId,setPackage]=useState(''),[releaseId,setRelease]=useState(''),[classIri,setClass]=useState('');
  const [result,setResult]=useState<ObjectPage|null>(null),[trace,setTrace]=useState<Document[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  function selectPackage(id:string){setPackage(id);setResult(null);setTrace([]);setError('');}
  const metadata=useQuery({queryKey:['metadata',state.project.project_id,packageId,releaseId],
    queryFn:({signal})=>api<{rows:Document[];view:string}>(`${prefix}/metadata?package_id=${encodeURIComponent(packageId)}${releaseId?'&release_id='+encodeURIComponent(releaseId):''}`,{signal}),enabled:!!packageId});
  async function query(offset=0){
    setBusy(true);setError('');setTrace([]);
    try{setResult(await post<ObjectPage>(`${prefix}/objects/query`,{package_id:packageId,release_id:releaseId||null,class_iri:classIri,offset,limit:100}));}
    catch(err){setError(String(err));setResult(null);}finally{setBusy(false);}
  }
  return <Panel title="固定 Package 对象浏览">
    <SelectDocument label="本体包版本" items={packages} idKey="package_id" value={packageId} onChange={id=>{selectPackage(id);setRelease('');}}/>
    <Field label="或选择固定 Release"><select value={releaseId} onChange={event=>{const id=event.target.value;setRelease(id);if(id)selectPackage(str(releases.find(r=>r.release_id===id)?.package_id));else setResult(null);}}>
      <option value="">使用上方 Package</option>{releases.map(r=><option key={str(r.release_id)} value={str(r.release_id)}>{str(r.package_version)} · {str(r.release_id)}</option>)}
    </select></Field>
    {packageId&&<p>固定 Package：<Id value={packageId}/> {releaseId&&<>；Release：<Id value={releaseId}/></>}</p>}
    {metadata.error?<p className="error" role="alert">元数据读取失败：{String(metadata.error)}</p>:metadata.isFetching?<p role="status">正在读取固定版本元数据…</p>:metadata.data&&<>
      <p>所选视图状态：{metadata.data.view}</p><DataTable data={metadata.data.rows} fields={[["iri","术语 IRI"],["kind","类型"],["labels","标签"]]}/>
    </>}
    <form onSubmit={event=>{event.preventDefault();query();}}>
      <Field label="实例所属 Class IRI"><input required value={classIri} onChange={event=>setClass(event.target.value)}/></Field>
      <button disabled={!packageId||busy}>查询实例</button>
    </form>
    {busy&&<p role="status">正在执行有界只读查询…</p>}{error&&<p className="error" role="alert">{error}</p>}
    {result&&<>
      <DataTable data={result.rows} fields={[["iri","实例 IRI"]]}/>
      <div className="pager"><button disabled={busy||result.page.offset===0} onClick={()=>query(Math.max(0,result.page.offset-result.page.limit))}>上一批实例结果</button>
        <span>从第 {result.page.offset+1} 条起；{result.page.truncated?'还有结果，当前批次已截断':'已到结果末尾'}</span>
        <button disabled={busy||!result.page.truncated} onClick={()=>query(result.page.offset+result.page.limit)}>下一批实例结果</button></div>
      {result.rows.map(row=><button key={str(row.iri)} onClick={async()=>{setError('');try{const response=await post<{evidence:Document[]}>(`${prefix}/objects/trace`,{package_id:packageId,instance_iri:row.iri});setTrace(response.evidence);}catch(err){setError(String(err));}}}>追溯 {str(row.iri)}</button>)}
    </>}
    {!!trace.length&&<DataTable data={trace} fields={[["observed_value","原始值"],["locator","文件定位"],["source_id","来源"]]}/>}
    {[...new Set(trace.map(row=>str(row.source_id)))].map(id=><p key={id}><a href={`/api/v1${prefix}/sources/${encodeURIComponent(id)}/content`}>下载关联原始资料 {id}</a></p>)}
  </Panel>;
}
