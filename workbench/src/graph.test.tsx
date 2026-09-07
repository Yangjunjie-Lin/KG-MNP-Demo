import {expect,it} from 'vitest';
import {boundedCandidateGraph} from './graph';

it('caps the graph at 200 nodes and 400 edges without changing candidate semantics',()=>{
 const candidates=Array.from({length:300},(_,i)=>({candidate_id:`node-${i}`,body:{candidate_type:'CLASS'},dependency_candidate_refs:Array.from({length:5},(_,j)=>`node-${(i+j+1)%200}`)}));
 const original=JSON.stringify(candidates);
 const graph=boundedCandidateGraph(candidates);
 expect(graph.nodes).toHaveLength(200);expect(graph.edges).toHaveLength(400);expect(graph.truncated).toBe(true);
 graph.nodes[0].position={x:2,y:3};expect(JSON.stringify(candidates)).toBe(original);
});
