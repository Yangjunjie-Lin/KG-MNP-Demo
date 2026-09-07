import {useState} from 'react';
import {DataTable,Field,Panel,SelectDocument} from './components';
import {type Document} from './api';
import {useWorkspace} from './shell';

export function ConsumerForm({packages}:{packages:Document[]}){
  const {state,submit,busy}=useWorkspace();
  const [packageId,setPackage]=useState(''),[queryType,setQueryType]=useState('SELECT');
  return <Panel title="消费者契约与版本反馈">
    <SelectDocument label="契约基准 Package" items={packages} idKey="package_id" value={packageId} onChange={setPackage}/>
    <form onSubmit={event=>{
      event.preventDefault();const values=new FormData(event.currentTarget);
      const query=String(values.get('query')).trim();
      submit('/lifecycle/consumers',{
        package_id:packageId,name:values.get('name'),
        required_term_iris:String(values.get('terms')).split('\n').map(s=>s.trim()).filter(Boolean),
        query_contracts:query?[{query_type:queryType,query_text:query,
          target_graph_roles:String(values.get('roles')).split(',').map(s=>s.trim()).filter(Boolean),
          assertions:[{assertion_type:queryType==='ASK'?'BOOLEAN_EQUALS':'MIN_ROW_COUNT',
            boolean_value:queryType==='ASK'?values.get('boolean')==='true':null,
            integer_value:queryType==='ASK'?null:Number(values.get('minimum')),string_values:[],semantic_hash:null}]}]:[],
      });
    }}>
      <Field label="消费者名称"><input name="name" required pattern="[a-z][a-z0-9-]*"/></Field>
      <Field label="必需术语 IRI（每行一项）"><textarea name="terms"/></Field>
      <Field label="查询契约类型"><select value={queryType} onChange={e=>setQueryType(e.target.value)}><option>SELECT</option><option>ASK</option><option>CONSTRUCT</option></select></Field>
      <Field label="受控只读 SPARQL 契约（可选）"><textarea name="query" spellCheck={false} maxLength={100000}/></Field>
      <Field label="目标图角色（逗号分隔）"><input name="roles" defaultValue="abox" required/></Field>
      {queryType==='ASK'?<Field label="期望布尔结果"><select name="boolean"><option value="true">true</option><option value="false">false</option></select></Field>
        :<Field label="Oracle 最少结果数"><input name="minimum" type="number" min="0" max="100000" defaultValue="1" required/></Field>}
      <button disabled={busy||!packageId}>登记消费者契约</button>
    </form>
    <p>查询将在后续版本回归中实际执行。禁止 UPDATE、SERVICE 和远程 FROM；执行受隔离、时间与结果上限约束。未填写查询不会生成虚假的查询通过记录。</p>
    <DataTable data={state.results.filter(r=>r.operation==='consumer.register').map(r=>r.result)} fields={[["consumer_name","消费者"],["required_term_iris","术语契约"],["query_contracts","查询与 Oracle"],["status","状态"]]}/>
    <form onSubmit={event=>{event.preventDefault();const values=new FormData(event.currentTarget);submit('/lifecycle/feedback',{package_id:packageId,observations:[values.get('observation')],severity:values.get('severity')});}}>
      <Field label="版本反馈"><textarea name="observation" required maxLength={4000}/></Field>
      <Field label="反馈严重程度"><select name="severity"><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></Field>
      <button disabled={busy||!packageId}>提交版本反馈</button>
    </form>
    <DataTable data={state.results.filter(r=>r.operation==='feedback.add').map(r=>r.result)} fields={[["feedback_id","反馈"],["observations","记录"],["severity","严重程度"]]}/>
  </Panel>;
}
