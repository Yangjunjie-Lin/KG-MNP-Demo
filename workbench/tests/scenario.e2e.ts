import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

test('scene Prompt presets, expert confirmation, Worker loop and same-snapshot download',async({page},info)=>{
  test.skip(process.env.ZHIGOU_SCENARIO_MOCK!=='1','Requires the explicitly isolated owned MockTransport test server; never fall back to LIVE.');
  test.setTimeout(1500000);
  const credential=JSON.parse(fs.readFileSync(process.env.KG_MNP_BROWSER_CREDENTIAL!,'utf8'));
  const auth={Authorization:'Bearer '+credential.token};
  async function waitJob(id:string){let result:any;await expect.poll(async()=>{const response=await page.request.get(`/api/v1/jobs/${id}`,{headers:auth,timeout:120000});expect(response.ok()).toBeTruthy();const job=await response.json();if(['FAILED','CANCELLED','RECOVERY_REQUIRED'].includes(job.status))throw new Error(JSON.stringify(job.error));result=job.result;return job.status;},{timeout:600000,intervals:[500,1000,2000]}).toBe('SUCCEEDED');return result;}
  let projectId='';
  async function op(name:string,params:Record<string,unknown>){const response=await page.request.post('/api/v1/operations/'+name,{headers:{...auth,'Idempotency-Key':crypto.randomUUID()},data:{project_id:projectId,...params},timeout:120000});expect(response.ok(),await response.text()).toBeTruthy();const body=await response.json();return body.job_id?waitJob(body.job_id):body.payload;}
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByLabel('项目名称').fill('合成场景模板浏览器验证');await page.getByLabel('领域包与版本').selectOption('hr@0.1.0');await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible();
  const prefix=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  projectId=decodeURIComponent(prefix.split('/')[2]);
  const sources:any[]=[];
  for(const name of ['employees.csv','departments.csv','assignments.csv']){
    const response=await page.request.post(`/api/v1${prefix}/sources`,{headers:{...auth,'Content-Type':'text/csv','X-Filename':name,'Idempotency-Key':crypto.randomUUID()},data:fs.readFileSync(path.resolve('../tests/fixtures/scenarios/organization_management',name)),timeout:120000});
    expect(response.status()).toBe(202);sources.push((await waitJob((await response.json()).job_id)).source);
  }
  const batch=(await op('source.batch',{source_ids:sources.map(s=>s.source_id)})).batch;
  const plan=(await op('ingestion.plan',{batch_id:batch.batch_id})).plan;
  const ingestion=(await op('ingestion.run',{plan_id:plan.plan_id})).run;
  await page.goto(`${prefix}/modeling?stage=1&run=${encodeURIComponent(ingestion.run_id)}`);
  await page.getByRole('radio').first().check();
  await expect(page.getByLabel(/S[1-5] 粒度/)).toHaveCount(0);
  await page.getByText('五步骤 Prompt 模板预览',{exact:true}).click();
  for(const stage of [1,2,3,4,5])await expect(page.getByRole('region',{name:`S${stage} 场景 Prompt`})).toBeVisible();
  await page.getByRole('button',{name:'只读预检场景模板（不调用模型）'}).click();
  await expect(page.getByRole('region',{name:'场景配置预检'})).toContainText('AVAILABLE');
  const expected={schema_version:'1.0.0',query_type:'SELECT',comparison:'MULTISET',variables:['employeeId','departmentId'],rows:[{employeeId:{kind:'LITERAL',value:'E-001',datatype:'http://www.w3.org/2001/XMLSchema#string'},departmentId:{kind:'LITERAL',value:'D-01',datatype:'http://www.w3.org/2001/XMLSchema#string'}}]};
  await page.getByText('冻结或变更本轮规则与独立答案',{exact:true}).click();
  await page.getByLabel('确认的业务规则（每行一项）').fill('Preserve exact identifiers, explicit negatives, unknown values and all source evidence');
  await page.getByLabel('构建前独立答案（查询资产及类型化预期）').fill(JSON.stringify([{query_asset_id:'hr-query-employees',expected}]));
  let accepted=page.waitForResponse(r=>r.url().endsWith('/toolchain/modeling.session.open')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'冻结本轮输入与验收基线（启用专家闭环）'}).click();
  await waitJob((await (await accepted).json()).job_id);
  async function state(){return (await page.request.get(`/api/v1${prefix}/state`,{headers:auth,timeout:120000})).json();}
  for(const stage of [1,2,3,4,5]){
    await page.goto(`${prefix}/modeling?stage=${stage}&run=${encodeURIComponent(ingestion.run_id)}`);
    const box=page.locator('details.expert-guidance');await box.locator('summary').first().click();
    await box.locator('details').locator('summary').click();
    const s=await state(),budget=s.modeling_session.expert.stages[String(stage)].configuration.budget;
    await page.getByLabel('循环预算 JSON').fill(JSON.stringify({...budget,max_tokens:600000}));
    await box.getByRole('checkbox').check();
    accepted=page.waitForResponse(r=>r.url().endsWith('/toolchain/modeling.expert.save')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'保存并确认指导（新版本）'}).click();
    await waitJob((await (await accepted).json()).job_id);
  }
  await page.goto(`${prefix}/modeling?stage=1&run=${encodeURIComponent(ingestion.run_id)}`);
  accepted=page.waitForResponse(r=>r.url().endsWith('/modeling/profiles')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'核验输入并生成画像',exact:true}).click();await waitJob((await (await accepted).json()).job_id);
  const effective=(await state()).modeling_session.scenario.effective;
  expect(effective.scenario_version).toBe('2.0.0');
  expect(Object.keys(effective.selection).sort()).toEqual(['scenario_id','scenario_version']);
  for(const stage of Object.values(effective.stages) as Record<string,unknown>[])expect(stage).not.toHaveProperty('level');
  const scopeResult=await op('modeling.scope',{run_id:ingestion.run_id,description:'Synthetic engineering regression',object_families:effective.stages.S1.enabled_object_families,in_scope:['synthetic approved scene'],namespace:effective.namespace});
  expect(scopeResult.expert_loop.revision_round).toBe(1);expect(scopeResult.expert_loop.decision).toBe('PASS');
  const approved=(await op('modeling.scope.approve',{scope_id:scopeResult.scope.scope_id,rationale:'Synthetic browser identity, not a real expert'})).approval;
  const prepared=await op('modeling.prepare',{scope_id:scopeResult.scope.scope_id,approval_id:approved.approval_id,questions:[{question_text:'Which current department belongs to E-001?',purpose:'Frozen source-bound synthetic CQ',required_concepts:['Employee','Department'],expected_answer_shape:'ENTITY_LIST'}]});
  const proposal=await op('modeling.proposal',{bundle_id:prepared.bundle.modeling_input_bundle_id,providers:['baseline-reuse-provider','manual-candidate-provider']});
  expect(proposal.expert_loop.decision).toBe('PASS');
  const candidates=['tbox_candidates','abox_candidates','mapping_candidates','shacl_candidates'].flatMap(k=>proposal.proposal[k]);
  expect(candidates.some(c=>c.body.predicate_iri==='urn:scenario:organization_management:jobTitle')).toBeTruthy();
  const reviewId=proposal.queue.review_queue_id;
  await op('modeling.semantic.check',{review_id:reviewId,candidate_ids:candidates.map(c=>c.candidate_id)});
  let head=null;
  for(const candidate of candidates){const result=await op('review.action',{review_id:reviewId,candidate_id:candidate.candidate_id,decision:'ACCEPT',rationale:'Explicit synthetic per-item browser test decision; not expert certification',expected_head:head});head=result.action.action_hash;}
  const confirmed=(await op('review.finalize',{review_id:reviewId})).confirmed_package;
  const compiledPlan=(await op('compile.plan.exact',{confirmed_package_id:confirmed.package_id,package_name:'synthetic-scene-browser',package_version:'0.1.0',ontology_iri:'urn:synthetic:scene-browser:ontology',version_iri:'urn:synthetic:scene-browser:ontology:0.1.0',oracles:[{question_id:prepared.questions.questions[0].question_id,query_asset_id:'hr-query-employees',expected}]})).plan;
  const built=await op('compile.build',{plan_id:compiledPlan.plan_id});expect(built.reports['competency-question-test-report.json'].required_passed).toBeTruthy();
  const revision=(await state()).modeling_session.revision;
  const request={package_id:built.package_id,expected_revision:revision,recipient:'synthetic-browser-check',data_classification:'SYNTHETIC',source_grants:sources.map(s=>({source_id:s.source_id,sha256:s.content_sha256,license:'PROJECT_SYNTHETIC_FIXTURE',permission_basis:'Local synthetic browser test'}))};
  const exportResult=await op('modeling.handoff.export',request);
  const saved=await state(),job=saved.jobs.find((j:any)=>j.operation_id==='modeling.handoff.export');
  await page.goto(`${prefix}/modeling?stage=5`);
  const link=page.locator(`a[href$="/handoffs/${job.job_id}/archive"]`);await expect(link).toBeVisible({timeout:120000});
  const downloading=page.waitForEvent('download');await link.click();const downloaded=await downloading;
  const output=info.outputPath('scenario-handoff.zip');await downloaded.saveAs(output);
  const raw=fs.readFileSync(output);expect(raw.length).toBe(exportResult.size_bytes);expect(crypto.createHash('sha256').update(raw).digest('hex')).toBe(exportResult.sha256);
  expect(await (await page.request.get(`/api/v1${prefix}/handoffs/${job.job_id}/archive`,{headers:auth})).body()).toEqual(raw);
  await page.screenshot({path:info.outputPath('scenario-five-stage.png'),fullPage:true});
  fs.writeFileSync(info.outputPath('scenario-browser-receipt.json'),JSON.stringify({nature:'SYNTHETIC_MOCK_NOT_LIVE',effective,scope_revision_round:scopeResult.expert_loop.revision_round,package_id:built.package_id,sha256:exportResult.sha256,size_bytes:raw.length,receiver:'NOT_CONTACTED'},null,2));
});
