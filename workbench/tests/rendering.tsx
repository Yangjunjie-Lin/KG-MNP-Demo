// Test-only rendering fixture, excluded from the product build entry point.
// No business API is replaced or mocked. These are synthetic component props.
import {createRoot} from 'react-dom/client';
import {Background,Controls,ReactFlow} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import '../src/styles.css';
import {DataTable,Panel} from '../src/components';
import {boundedCandidateGraph} from '../src/graph';

const started=performance.now();
const candidates=Array.from({length:250},(_,i)=>({candidate_id:`synthetic-${i}`,body:{label:`合成节点 ${i}`},dependency_candidate_refs:[`synthetic-${(i+1)%200}`,`synthetic-${(i+2)%200}`,`synthetic-${(i+3)%200}`]}));
const graph=boundedCandidateGraph(candidates);
createRoot(document.getElementById('root')!).render(<main className="projects">
  <h1>组件容量测试</h1><p>仅测试同一套正式组件的渲染容量；不是业务 API 或审核/编译验收。</p>
  <Panel title="1000 条合成表格记录"><DataTable data={Array.from({length:1000},(_,i)=>({id:`row-${i}`,label:`合成结果 ${i}`}))} fields={[["id","记录"],["label","内容"]]}/></Panel>
  <Panel title="200 节点 / 400 边有界图"><p data-testid="graph-size">{graph.nodes.length} nodes / {graph.edges.length} edges</p><div className="graph"><ReactFlow nodes={graph.nodes} edges={graph.edges} fitView nodesConnectable={false}><Background/><Controls/></ReactFlow></div></Panel>
  <output id="render-timing" aria-label="首屏渲染毫秒"/>
</main>);
requestAnimationFrame(()=>requestAnimationFrame(()=>{const output=document.getElementById('render-timing');if(output)output.textContent=String(performance.now()-started);}));
