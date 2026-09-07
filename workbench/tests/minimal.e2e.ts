import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {versionFlow} from './version-flow';
import AxeBuilder from '@axe-core/playwright';
import os from 'node:os';
const scenarios=[
 {id:'minimal',version:'0.1.0',files:[],concepts:'Entity',question:'Which entities and labels are present?',query:'minimal-query-list-entities',bindings:'entity,label',count:1,classIri:'https://yangjunjie-lin.github.io/KG-MNP-Demo/domain-packs/minimal/terms#Entity'},
 {id:'forestry',version:'0.2.0',files:['sites.csv','trees.csv','inspections.csv'],concepts:'TreeRecord,InspectionRecord,Site',question:'Which synthetic trees have inspections and sites?',query:'forestry-query-tree-inspections',bindings:'tree,treeCode,inspection,inspectionCode,site',count:6,classIri:'https://example.invalid/forestry#TreeRecord'}
 ,{id:'mnp',version:'1.0.0',files:[],concepts:'MappingRecord',question:'Which MappingRecord exists?',query:'mnp-queries-source-alignment',bindings:'term,mapApi,mapField,mapTarget,mapReview',count:1,classIri:'https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#MappingRecord'}
];
for(const scenario of scenarios) test(`real browser ${scenario.id} source review fixed reasoner and release`,async({page},testInfo)=>{
  test.setTimeout(3600000);
  const evidenceRoot=testInfo.outputPath('screenshots');
  const started=performance.now();
  fs.mkdirSync(evidenceRoot,{recursive:true});
  const credentialPath=process.env.KG_MNP_BROWSER_CREDENTIAL;
  if(!credentialPath) throw new Error('explicit synthetic test server credential path required');
  const credential=JSON.parse(fs.readFileSync(credentialPath,'utf8'));
  await page.goto('/');
  await page.getByLabel('访问凭证').fill(credential.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('heading',{name:'选择项目',exact:true})).toBeVisible();
  const name='合成本体验收-'+Date.now();
  await page.getByLabel('项目名称').fill(name);
  await page.getByLabel('领域包与版本').selectOption(`${scenario.id}@${scenario.version}`);
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible({timeout:60000});
  const projectPath=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  async function state(){const response=await page.request.get('/api/v1'+projectPath+'/state');if(!response.ok())throw new Error(`Project state HTTP ${response.status()}: ${await response.text()}`);return response.json();}
  async function output(operation:string,key?:string){await expect.poll(async()=>{const s=await state();const failed=s.jobs.find((j:{status:string;operation_id:string})=>j.status==='FAILED'&&j.operation_id===operation);if(failed)throw new Error(JSON.stringify(failed));return s.results.filter((r:{operation:string})=>r.operation===operation).length;},{timeout:/^(compile|registry|release|change|environment)\./.test(operation)?600000:120000}).toBeGreaterThan(0);const s=await state();const result=s.results.filter((r:{operation:string})=>r.operation===operation).at(-1).result;return key?result[key]:result;}
  async function screenshot(name:string){const targets:Record<string,string>={'source-evidence':'证据定位与转换记录','scope-cq':'范围确认与能力问题','review':'候选审核','compilation':'正式验证结果','release-objects':'固定 Package 对象浏览'};if(targets[name])await page.getByRole('heading',{name:targets[name],exact:true}).scrollIntoViewIfNeeded();else await page.evaluate(()=>window.scrollTo(0,0));const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();fs.writeFileSync(path.join(evidenceRoot,name+'-accessibility.json'),JSON.stringify(scan,null,2));expect(scan.violations).toEqual([]);await page.screenshot({path:path.join(evidenceRoot,name+'.png'),fullPage:false});}
  await screenshot('project-overview');
  await page.getByRole('link',{name:'资料与证据',exact:true}).click();
  const inputs=scenario.files.length?scenario.files.map(name=>({name,mimeType:'text/csv',buffer:fs.readFileSync(path.resolve('../domain_packs',scenario.id,'fixtures',name))})):scenario.id==='mnp'?[{name:'mapping.csv',mimeType:'text/csv',buffer:Buffer.from(['mappingCode,sourceApi,sourceFieldPath,targetTerm,mappingReviewStatus','SYN-M01,Synthetic source,sample.field,Subscriber,SYNTHETIC_TEST',''].join(String.fromCharCode(10)))}]:[{name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from(['entity,label','synthetic,Synthetic entity',''].join(String.fromCharCode(10)))}];
  for(let index=0;index<inputs.length;index++){
    await page.getByLabel('资料文件').setInputFiles(inputs[index]);
    await page.getByRole('button',{name:'上传并登记 Source',exact:true}).click();
    await expect.poll(async()=>{const s=await state();const failed=s.jobs.find((j:{operation_id:string;status:string})=>j.operation_id==='source.register'&&['FAILED','RECOVERY_REQUIRED'].includes(j.status));if(failed)throw new Error(JSON.stringify(failed));return s.results.filter((r:{operation:string})=>r.operation==='source.register').length;},{timeout:120000}).toBe(index+1);
  }
  const registration=await output('source.register');
  let batchId=registration.batch.batch_id;
  if(inputs.length>1){
    for(const input of inputs)await page.getByRole('checkbox',{name:input.name,exact:true}).check();
    await page.getByRole('button',{name:'创建选中来源的批次',exact:true}).click();
    batchId=(await output('source.batch','batch')).batch_id;
  }
  await page.getByLabel('资料批次').selectOption(batchId);
  await page.getByRole('button',{name:'生成解析计划',exact:true}).click();
  await output('ingestion.plan');
  await expect(page.getByRole('button',{name:'运行解析',exact:true})).toBeEnabled({timeout:15000});
  await page.getByRole('button',{name:'运行解析',exact:true}).click();
  const run=await output('ingestion.run','run');
  await page.getByLabel('解析运行').selectOption(run.run_id);
  await expect(page.getByRole('heading',{name:'证据定位与转换记录',exact:true})).toBeVisible();
  await screenshot('source-evidence');
  await page.getByRole('link',{name:'本体建模与审核',exact:true}).click();
  await page.getByLabel('已验证的解析运行').selectOption(run.run_id);
  await page.getByLabel('目标对象（逗号分隔）').fill(scenario.concepts);
  await page.getByLabel('范围说明').fill(`Synthetic ${scenario.id} browser acceptance`);
  await page.getByLabel('纳入范围（每行一项）').fill('entity labels');
  await page.getByLabel('排除范围（每行一项）').fill('production deployment');
  await page.getByRole('button',{name:'保存范围草案',exact:true}).click();
  const scope=await output('modeling.scope','scope');
  await page.getByLabel('范围版本').selectOption(scope.scope_id);
  await page.getByLabel('范围批准理由').fill('Explicit synthetic human scope approval');
  await page.getByRole('button',{name:'以当前身份批准范围',exact:true}).click();
  await output('modeling.scope.approve');
  await page.getByLabel('能力问题',{exact:true}).fill(scenario.question);
  await page.getByLabel('验证目的').fill('structural retrieval and traceability');
  await page.getByLabel('需要的概念（逗号分隔）').fill(scenario.concepts);
  await page.getByRole('button',{name:'保存 CQ 并准备基线、术语与映射',exact:true}).click();
  const prepared=await output('modeling.prepare');
  await screenshot('scope-cq');
  if(scenario.id==='mnp'){
    await page.getByLabel('记录表标识').fill('mappings');
    await page.getByLabel('映射资料文件').selectOption('mapping.csv');
    await page.getByLabel('目标基线类').selectOption(scenario.classIri);
    await page.getByLabel('来源身份字段').fill('mappingCode');
    const fields=['sourceApi','sourceFieldPath','targetTerm','mappingReviewStatus'];
    for(let i=0;i<fields.length;i++){
      if(i)await page.getByRole('button',{name:'添加字段映射',exact:true}).click();
      await page.getByLabel(`来源字段 ${i+1}`,{exact:true}).fill(fields[i]);
      await page.getByLabel(`目标数据属性 ${i+1}`,{exact:true}).selectOption('https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#'+fields[i]);
    }
    await page.getByRole('button',{name:'生成自定义映射候选',exact:true}).click();
  } else await page.getByRole('button',{name:'运行离线候选 Provider',exact:true}).click();
  const proposal=await output('modeling.proposal');
  await page.getByLabel('审核队列').selectOption(proposal.queue.review_queue_id);
  await page.getByLabel('本次审核理由').fill('Explicit human decision for this synthetic candidate');
  const items=proposal.queue.items.filter((i:{candidate_id?:string})=>i.candidate_id);
  for(let index=0;index<items.length;index++){
    const actions=await state();const count=actions.results.filter((r:{operation:string})=>r.operation==='review.action').length;
    await page.getByRole('button',{name:'接受此项',exact:true}).nth(index).click();
    await expect.poll(async()=>{const s=await state();const failed=s.jobs.find((j:{operation_id:string;status:string})=>j.operation_id==='review.action'&&j.status==='FAILED');if(failed)throw new Error(JSON.stringify(failed));return s.results.filter((r:{operation:string})=>r.operation==='review.action').length;},{timeout:120000}).toBe(count+1);
    // Wait for the actual action table, not a fixed delay or a forged head.
    const updated=await state();
    const action=updated.results.filter((r:{operation:string})=>r.operation==='review.action').at(-1).result.action;
    await expect(page.getByTestId('review-head')).toHaveText(action.action_hash,{timeout:15000});
  }
  await screenshot('review');
  await page.getByRole('button',{name:'Finalize：校验审核并生成确认包',exact:true}).click();
  const confirmed=await output('review.finalize','confirmed_package');
  // Long real review sessions can approach the deliberately short session TTL.
  // Explicitly sign in again via the UI and recover the persisted workspace;
  // never alter session policy or retry an approval to prolong a test.
  if(performance.now()-started>1200000){
    await page.getByRole('button',{name:'退出',exact:true}).click();
    await page.getByLabel('访问凭证').fill(credential.token);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await expect(page.getByRole('heading',{name:'选择项目',exact:true})).toBeVisible();
    await page.goto(projectPath+'/modeling');
  }
  await page.getByRole('link',{name:'验证与发布',exact:true}).click();
  await page.getByLabel('确认包',{exact:true}).selectOption(confirmed.package_id);
  await page.getByLabel('本体包名称').fill(`synthetic-browser-${scenario.id}`);
  await page.getByLabel('本体包版本',{exact:true}).first().fill(scenario.version);
  await page.getByLabel('Ontology IRI',{exact:true}).fill(`urn:synthetic:browser:${scenario.id}`);
  await page.getByLabel('Version IRI',{exact:true}).fill(`urn:synthetic:browser:${scenario.id}:${scenario.version}`);
  await page.getByLabel('能力问题',{exact:true}).selectOption(prepared.questions.questions[0].question_id);
  await page.getByLabel('锁定领域包中的查询 Asset ID').fill(scenario.query);
  await page.getByLabel('必须返回的变量（逗号分隔）').fill(scenario.bindings);
  await page.getByLabel('最少结果行数（非空 Oracle）').fill(String(scenario.count));
  await page.getByRole('button',{name:'生成编译计划',exact:true}).click();
  await output('compile.plan');
  await page.getByRole('button',{name:'执行真实编译与验证',exact:true}).click();
  const built=await output('compile.build');
  expect(built.reports['competency-question-test-report.json'].required_passed).toBe(true);
  await screenshot('compilation');
  await page.getByRole('button',{name:'验证并导入本地 Registry',exact:true}).click();
  await output('registry.import');
  await page.getByRole('button',{name:'创建初始 Release Candidate',exact:true}).click();
  const candidate=await output('release.candidate');
  await page.getByLabel('Release 审核理由').fill('Explicit synthetic initial release review');
  await page.getByRole('button',{name:'以当前身份批准该 Release',exact:true}).click();
  await output('release.review');
  await page.getByRole('button',{name:'使用当前 Registry CAS 发布',exact:true}).click();
  const released=await output('release.publish');
  expect(released.release.release_status).toBe('RELEASED');
  await page.getByLabel('本体包版本',{exact:true}).last().selectOption(built.package_id);
  await page.getByLabel('实例所属 Class IRI').fill(scenario.classIri);
  await page.getByRole('button',{name:'查询实例',exact:true}).click();
  await expect(page.getByRole('table').filter({has:page.getByRole('columnheader',{name:'实例 IRI',exact:true})}).getByRole('row')).toHaveCount(scenario.count+1,{timeout:120000});
  await page.getByRole('button',{name:/^追溯 /}).first().click();
  await expect(page.getByRole('link',{name:/^下载关联原始资料/}).first()).toBeVisible({timeout:90000});
  const downloadPromise=page.waitForEvent('download',{timeout:120000});
  await page.getByRole('link',{name:/^下载关联原始资料/}).first().click({timeout:120000});
  const download=await downloadPromise;
  const downloadedPath=await download.path();
  expect(downloadedPath).not.toBeNull();
  const downloadedBytes=fs.readFileSync(downloadedPath!);
  expect(inputs.some(input=>input.buffer.equals(downloadedBytes))).toBe(true);
  fs.copyFileSync(downloadedPath!,path.join(evidenceRoot,'traced-source.bin'));
  await screenshot('release-objects');
  if(scenario.id==='minimal'){
    const versionIds=await versionFlow(page,projectPath,built.package_id,released.release.release_id);
    fs.writeFileSync(path.join(evidenceRoot,'version-ids.json'),JSON.stringify(versionIds,null,2));
    await screenshot('environment-rollback');
    await page.getByRole('link',{name:'验证与发布',exact:true}).click();
  }
  await page.reload();
  await expect(page.getByRole('heading',{name:'验证与发布',exact:true})).toBeVisible({timeout:20000});
  const localStorageKeys=await page.evaluate(()=>Object.keys(localStorage));
  expect(localStorageKeys).toEqual([]);
  const final=await state();
  fs.writeFileSync(path.join(evidenceRoot,'ids.json'),JSON.stringify({project_id:final.project.project_id,source_id:registration.source.source_id,
    run_id:run.run_id,scope_id:scope.scope_id,proposal_id:proposal.proposal.proposal_id,review_id:proposal.queue.review_queue_id,
    package_id:built.package_id,release_id:released.release.release_id,job_ids:final.jobs.map((j:{job_id:string})=>j.job_id)},null,2));
  const viewports=[{width:1024,height:768},{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}];
  for(const viewport of viewports){await page.setViewportSize(viewport);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await screenshot(`viewport-${viewport.width}-${viewport.height}`);}
  fs.writeFileSync(path.join(evidenceRoot,'measurement.json'),JSON.stringify({domain:scenario.id,elapsed_seconds:(performance.now()-started)/1000,
    browser:page.context().browser()?.version(),platform:os.platform(),os_release:os.release(),cpu:os.cpus()[0]?.model,
    logical_cpus:os.cpus().length,total_memory_bytes:os.totalmem(),source_count:inputs.length,reviewed_candidate_count:items.length,
    expected_instance_count:scenario.count,viewports,method:'Real Chromium form actions; persistent worker completion observed through authorized HTTP state. Wall time includes polling and actual reasoner execution.'},null,2));
  await page.getByRole('button',{name:'退出',exact:true}).click();
  await expect(page.getByRole('button',{name:'登录',exact:true})).toBeVisible();
});
