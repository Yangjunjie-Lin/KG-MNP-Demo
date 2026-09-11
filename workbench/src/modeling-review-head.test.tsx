import {expect,it} from 'vitest';
import {observedReviewHead} from './modeling-review-head';
import type {Result} from './api';

const entry=(hash:string,revision:number,review='r'):Result=>({operation:'review.action',revision,job_id:'job-'+revision,result:{action:{review_queue_id:review,action_hash:hash}}});
it('uses a real committed action when a slower replay response still has the previous head',()=>{
  expect(observedReviewHead([entry('a',1),entry('b',2)],'r',[{action_hash:'a'}])).toEqual({head:'b',conflict:false});
});
it('keeps a newer verified replay and never borrows another queue head',()=>{
  expect(observedReviewHead([entry('a',1),entry('foreign',2,'other')],'r',[{action_hash:'a'},{action_hash:'b'}])).toEqual({head:'b',conflict:false});
});
it('blocks divergent histories instead of guessing which approval branch wins',()=>{
  expect(observedReviewHead([entry('a',1)],'r',[{action_hash:'fork'}])).toEqual({head:null,conflict:true});
});
