import {expect,type Page} from '@playwright/test';

// All business mutations go through the rendered forms. HTTP is observation
// only; there are no routed mocks, fabricated records or automatic approvals.
export async function versionFlow(page:Page,projectPath:string,initialPackage:string,initialRelease:string,capture?:(name:string)=>Promise<void>){
  async function state(){const r=await page.request.get('/api/v1'+projectPath+'/state');if(!r.ok())throw new Error(`State HTTP ${r.status()}: ${await r.text()}`);return r.json();}
  async function count(operation:string){return (await state()).results.filter((r:{operation:string})=>r.operation===operation).length;}
  async function changed(operation:string,before:number){
    await expect.poll(async()=>{const s=await state();const failed=s.jobs.find((j:{operation_id:string;status:string})=>j.operation_id===operation&&['FAILED','RECOVERY_REQUIRED'].includes(j.status));if(failed)throw new Error(JSON.stringify(failed));return count(operation);},{timeout:600000}).toBe(before+1);
    return (await state()).results.filter((r:{operation:string})=>r.operation===operation).at(-1).result;
  }
  await page.getByLabel('本体包版本',{exact:true}).first().fill('0.1.1');
  await page.getByLabel('Version IRI',{exact:true}).fill('urn:synthetic:browser:minimal:0.1.1');
  await page.getByRole('button',{name:'生成编译计划',exact:true}).click();
  const planned=await changed('compile.plan',1);
  await page.getByTestId('compilation-plan-'+planned.plan.plan_id).getByRole('button',{name:'执行真实编译与验证',exact:true}).click();
  const built=await changed('compile.build',1);
  await page.getByTestId('package-build-'+built.package_id).getByRole('button',{name:'验证并导入本地 Registry',exact:true}).click();
  await changed('registry.import',1);
  await page.getByRole('link',{name:'差异与环境',exact:true}).click();
  await page.getByLabel('Base Package',{exact:true}).selectOption(initialPackage);
  await page.getByLabel('Candidate Package',{exact:true}).selectOption(built.package_id);
  await page.getByRole('button',{name:'运行语义 Diff 与版本检查',exact:true}).click();
  const diff=await changed('change.diff',0);
  await page.getByLabel('Diff 报告',{exact:true}).selectOption(diff.diff.diff_id);
  await page.getByRole('button',{name:'分析本地依赖影响',exact:true}).click();
  await changed('change.impact',0);
  await page.getByRole('button',{name:'实际重跑 Candidate 与 Base CQ Oracle',exact:true}).click();
  const regression=await changed('change.regression',0);
  expect(regression.report.required_passed).toBe(true);
  await capture?.('version-diff');
  await page.getByLabel('后续版本变更理由',{exact:true}).fill('Explicit synthetic successor evaluation');
  await page.getByRole('button',{name:'生成并评估 Change Proposal',exact:true}).click();
  await changed('change.evaluate',0);
  await page.getByRole('button',{name:'提交后续 Release Candidate',exact:true}).click();
  await changed('release.candidate',1);
  await page.getByRole('link',{name:'验证与发布',exact:true}).click();
  await page.getByLabel('Release 审核理由',{exact:true}).last().fill('Independent explicit successor approval');
  await page.getByRole('button',{name:'以当前身份批准该 Release',exact:true}).last().click();
  await changed('release.review',1);
  await page.getByRole('button',{name:'使用当前 Registry CAS 发布',exact:true}).last().click();
  const successor=await changed('release.publish',1);
  await page.getByRole('link',{name:'差异与环境',exact:true}).click();
  await page.getByLabel('新环境名称',{exact:true}).fill('synthetic-browser-development');
  await page.getByRole('button',{name:'创建本地环境',exact:true}).click();
  const env=await changed('environment.create',0);
  await page.getByLabel('环境',{exact:true}).selectOption(env.environment_id);
  let activationCount=0;
  for(const [index,intent] of [
    {kind:'ACTIVATE',target:initialRelease},
    {kind:'ACTIVATE',target:successor.release.release_id},
    {kind:'ROLLBACK',target:initialRelease},
  ].entries()){
    await page.getByLabel('明确目标 Release',{exact:true}).selectOption(intent.target);
    await page.getByLabel('操作意图',{exact:true}).selectOption(intent.kind);
    await page.getByLabel('环境变更理由',{exact:true}).fill(`Explicit ${intent.kind} to selected synthetic release`);
    await page.getByRole('button',{name:'提交独立环境提案',exact:true}).click();
    const proposal=await changed('environment.propose',index);
    const proposalPanel=page.getByTestId('environment-proposal-'+proposal.activation_proposal_id);
    await proposalPanel.getByLabel('环境审核理由',{exact:true}).fill('Reviewed exact target and local control-plane effect');
    await proposalPanel.getByLabel('确认已检查目标与变化影响',{exact:true}).check();
    await proposalPanel.getByRole('button',{name:'人工批准此环境提案',exact:true}).click();
    await changed('environment.review',index);
    await proposalPanel.getByRole('button',{name:'执行已审核意图与当前 CAS',exact:true}).click();
    const applied=await changed(intent.kind==='ROLLBACK'?'environment.rollback':'environment.activate',intent.kind==='ROLLBACK'?0:activationCount++);
    expect(applied.receipt.target_release_id).toBe(intent.target);
    const response=await page.request.get('/api/v1'+projectPath+'/environment-pointer?environment_id='+encodeURIComponent(env.environment_id));
    expect(response.ok()).toBe(true);
    const pointer=await response.json();
    expect(pointer.active_release_id).toBe(intent.target);
    expect(pointer.generation).toBe(index+1);
  }
  return {successor_package_id:built.package_id,successor_release_id:successor.release.release_id,environment_id:env.environment_id,rollback_target:initialRelease};
}
