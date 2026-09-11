import {object, str, type Document, type Result} from './api';

// Both sources are observations of the same server-owned review log. This is
// only an optimistic-concurrency token; the service still validates live CAS.
export function observedReviewHead(results:Result[],reviewId:string,replayed:Document[]):{head:string|null;conflict:boolean} {
  const committed=results.filter(r=>r.operation==='review.action').map(r=>object(r.result.action)).filter(a=>a.review_queue_id===reviewId);
  const commitHead=str(committed.at(-1)?.action_hash)||null, replayHead=str(replayed.at(-1)?.action_hash)||null;
  if(!commitHead)return {head:replayHead,conflict:false};
  if(!replayHead||committed.some(a=>a.action_hash===replayHead))return {head:commitHead,conflict:false};
  if(replayed.some(a=>a.action_hash===commitHead))return {head:replayHead,conflict:false};
  return {head:null,conflict:true};
}
