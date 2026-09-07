import {MarkerType,type Node,type Edge} from '@xyflow/react';
import {object,str,type Document} from './api';
export function boundedCandidateGraph(candidates:Document[]){
 const nodes:Node[]=candidates.slice(0,200).map((c,i)=>({id:str(c.candidate_id),position:{x:(i%4)*250,y:Math.floor(i/4)*100},data:{label:str(object(c.body).label||object(c.body).candidate_type)},draggable:true}));
 const ids=new Set(nodes.map(n=>n.id));
 const availableEdges:Edge[]=candidates.flatMap(c=>(Array.isArray(c.dependency_candidate_refs)?c.dependency_candidate_refs:[]).map((id,i)=>({id:`${c.candidate_id}-${i}`,source:str(id),target:str(c.candidate_id),label:'被依赖 → 当前候选',markerEnd:{type:MarkerType.ArrowClosed}}))).filter(e=>ids.has(e.source)&&ids.has(e.target));
 const edges=availableEdges.slice(0,400);
 return {nodes,edges,truncated:candidates.length>200||availableEdges.length>400};
}
