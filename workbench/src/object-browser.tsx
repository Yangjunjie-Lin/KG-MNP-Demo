import {useRef,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,object,post,str,type Document} from './api';
import {DataTable,Field,Id,Panel,SelectDocument} from './components';
import {useWorkspace} from './shell';

type ObjectPage={package_id:string;release_id:string|null;rows:Document[];page:{offset:number;limit:number;truncated:boolean}};
type MetadataPage={package_id:string;rows:Document[];view:string;semantic_digest:string|null;page:{offset:number;limit:number;total:number}};
export function ObjectBrowser({packages,releases}:{packages:Document[];releases:Document[]}){
  const {state,prefix}=useWorkspace();
  const [packageId,setPackage]=useState(''),[releaseId,setRelease]=useState(''),[classIri,setClass]=useState('');
  const [metadataOffset,setMetadataOffset]=useState(0);
  const [metadataOpen,setMetadataOpen]=useState(false);
  const [result,setResult]=useState<ObjectPage|null>(null),[details,setDetails]=useState<(ObjectPage&{iri:string})|null>(null);
  const [trace,setTrace]=useState<Document[]>([]),[traceChecked,setTraceChecked]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const readRevision=useRef(0);
  function clearReads(){readRevision.current++;setResult(null);setDetails(null);setTrace([]);setTraceChecked(false);setError('');setBusy(false);}
  function selectPackage(id:string){clearReads();setPackage(id);setMetadataOffset(0);setMetadataOpen(false);}
  const metadata=useQuery({queryKey:['metadata',state.project.project_id,packageId,releaseId,metadataOffset],
    queryFn:({signal})=>api<MetadataPage>(prefix+'/metadata?package_id='+encodeURIComponent(packageId)+'&offset='+metadataOffset+'&limit=100'+(releaseId?'&release_id='+encodeURIComponent(releaseId):''),{signal}),enabled:!!packageId&&metadataOpen});
  async function query(offset=0,instanceIri?:string){
    const revision=++readRevision.current;
    setBusy(true);setError('');setTrace([]);setTraceChecked(false);
    if(instanceIri)setDetails(null);else{setResult(null);setDetails(null);}
    try{
      const page=await post<ObjectPage>(prefix+'/objects/query',{package_id:packageId,release_id:releaseId||null,
        ...(instanceIri?{instance_iri:instanceIri}:{class_iri:classIri}),offset,limit:100});
      if(revision!==readRevision.current)return;
      if(page.package_id!==packageId||page.release_id!==(releaseId||null))throw new Error('VERSION_BINDING_INVALID');
      if(instanceIri)setDetails({...page,iri:instanceIri});else setResult(page);
    }catch(err){if(revision===readRevision.current)setError(String(err));}
    finally{if(revision===readRevision.current)setBusy(false);}
  }
  async function traceObject(iri:string){
    const revision=++readRevision.current;
    setBusy(true);setError('');setTrace([]);setTraceChecked(false);
    try{
      const response=await post<{evidence:Document[]}>(prefix+'/objects/trace',{package_id:packageId,instance_iri:iri});
      if(revision===readRevision.current){setTrace(response.evidence);setTraceChecked(true);}
    }catch(err){if(revision===readRevision.current)setError(String(err));}
    finally{if(revision===readRevision.current)setBusy(false);}
  }
  return <Panel title="固定 Package 对象浏览">
    <SelectDocument label="本体包版本" items={packages} idKey="package_id" value={packageId} onChange={id=>{selectPackage(id);setRelease('');}}/>
    <Field label="或选择固定 Release"><select value={releaseId} onChange={event=>{const id=event.target.value;setRelease(id);selectPackage(id?str(releases.find(r=>r.release_id===id)?.package_id):packageId);}}>
      <option value="">使用上方 Package</option>{releases.map(r=><option key={str(r.release_id)} value={str(r.release_id)}>{str(r.package_version)} · {str(r.release_id)}</option>)}
    </select></Field>
    {packageId&&<p>固定 Package：<Id value={packageId}/> {releaseId&&<>；Release：<Id value={releaseId}/></>}</p>}
    {!!packageId&&!metadataOpen&&<p><button onClick={()=>setMetadataOpen(true)}>读取锁定术语与定义</button><span className="muted"> 按需独立复验当前包并读取元数据；实例查询仍执行其自身校验。</span></p>}
    {metadataOpen&&(metadata.error?<p className="error" role="alert">元数据读取失败：{String(metadata.error)}</p>:metadata.isFetching?<p role="status">正在读取固定版本元数据…</p>:metadata.data&&<>
      <p>所选视图状态：{metadata.data.view}；语义摘要：<Id value={metadata.data.semantic_digest??'未提供'}/></p>
      <DataTable data={metadata.data.rows} fields={[["iri","术语 IRI"],["kind","类型"],["labels","标签"],["definitions","定义"],["domain","定义域"],["range","值域"]]}/>
      <div className="pager"><button disabled={metadataOffset===0} onClick={()=>setMetadataOffset(Math.max(0,metadataOffset-100))}>上一批术语</button>
        <span>术语 {metadata.data.rows.length?metadata.data.page.offset+1:0}–{metadata.data.page.offset+metadata.data.rows.length} / {metadata.data.page.total}</span>
        <button disabled={metadataOffset+100>=metadata.data.page.total} onClick={()=>setMetadataOffset(metadataOffset+100)}>下一批术语</button></div>
    </>)}
    <form onSubmit={event=>{event.preventDefault();query();}}>
      <Field label="实例所属 Class IRI"><input required value={classIri} onChange={event=>{setClass(event.target.value);clearReads();}}/></Field>
      <button disabled={!packageId||busy}>查询实例</button>
    </form>
    {busy&&<p role="status">正在执行有界只读查询…</p>}{error&&<p className="error" role="alert">{error}</p>}
    {result&&<>
      <DataTable data={result.rows} fields={[["iri","实例 IRI"]]}/>
      <div className="pager"><button disabled={busy||result.page.offset===0} onClick={()=>query(Math.max(0,result.page.offset-result.page.limit))}>上一批实例结果</button>
        <span>从第 {result.page.offset+1} 条起；{result.page.truncated?'还有结果，当前批次已截断':'已到结果末尾'}</span>
        <button disabled={busy||!result.page.truncated} onClick={()=>query(result.page.offset+result.page.limit)}>下一批实例结果</button></div>
      {result.rows.map(row=><div className="actions" key={str(row.iri)}><button disabled={busy} onClick={()=>query(0,str(row.iri))}>查看属性与关系 {str(row.iri)}</button><button disabled={busy} onClick={()=>traceObject(str(row.iri))}>追溯 {str(row.iri)}</button></div>)}
    </>}
    {details&&<section aria-label="对象属性与关系"><h3>对象属性与关系</h3><p>对象：<Id value={details.iri}/>；固定 Package：<Id value={details.package_id}/></p>
      <DataTable data={details.rows.map(row=>({predicate:row.predicate,...object(row.object)}))} fields={[["predicate","属性 IRI"],["term_type","值类型"],["value","值或关联对象"],["datatype","数据类型"],["language","语言"]]}/>
      <div className="pager"><button disabled={busy||details.page.offset===0} onClick={()=>query(Math.max(0,details.page.offset-details.page.limit),details.iri)}>上一批属性</button><span>{details.page.truncated?'属性结果已截断，可读取下一批':'已到属性结果末尾'}</span><button disabled={busy||!details.page.truncated} onClick={()=>query(details.page.offset+details.page.limit,details.iri)}>下一批属性</button></div>
      {[...new Set(details.rows.filter(row=>object(row.object).term_type==='IRI').map(row=>str(object(row.object).value)))].map(iri=><button key={iri} disabled={busy} onClick={()=>query(0,iri)}>浏览关联对象 {iri}</button>)}
      <button disabled={busy} onClick={()=>traceObject(details.iri)}>追溯当前对象证据</button>
    </section>}
    {!!trace.length&&<DataTable data={trace} fields={[["observed_value","原始值"],["locator","文件定位"],["source_id","来源"]]}/>}
    {traceChecked&&!trace.length&&<p>本次对象没有关联 Source 证据；不生成虚构的来源记录。</p>}
    {[...new Set(trace.map(row=>str(row.source_id)))].map(id=><p key={id}><a href={'/api/v1'+prefix+'/sources/'+encodeURIComponent(id)+'/content'}>下载关联原始资料 {id}</a></p>)}
  </Panel>;
}
