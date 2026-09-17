import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import crypto from 'node:crypto';

test('two agents expose actual Worker before/after audit download',async({page},info)=>{
  const credentialPath=process.env.KG_MNP_BROWSER_CREDENTIAL;
  if(!credentialPath)throw new Error('Owned synthetic credential required');
  const credential=JSON.parse(fs.readFileSync(credentialPath,'utf8'));
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByLabel('项目名称').fill('双 Agent 审计合成验收');
  await page.getByLabel('领域包与版本').selectOption('hr@0.1.0');
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible({timeout:60000});
  const prefix=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  async function state(){const response=await page.request.get('/api/v1'+prefix+'/state');expect(response.ok()).toBeTruthy();return response.json();}
  await page.goto(prefix+'/sources');
  await page.getByRole('button',{name:'加载当前领域包的合成批次（仅空项目）'}).click();
  await expect.poll(async()=>(await state()).jobs.find((j:{operation_id:string})=>j.operation_id==='source.sample.load')?.status,{timeout:120000}).toBe('SUCCEEDED');
  const loaded=(await state()).results.find((r:{operation:string})=>r.operation==='source.sample.load').result;
  await page.goto(prefix+'/modeling?stage=1&run='+encodeURIComponent(loaded.run.run_id));
  await expect(page.getByRole('heading',{name:'规划 Agent',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'任务执行 Agent',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'核验输入并生成画像',exact:true}).click();
  await expect.poll(async()=>(await state()).jobs.find((j:{operation_id:string})=>j.operation_id==='modeling.profile')?.status,{timeout:120000}).toBe('SUCCEEDED');
  await page.getByText('逐步审计文件 · 处理前 / 处理后',{exact:true}).click();
  const link=page.getByRole('link',{name:'下载前后审计 ZIP',exact:true}).first();
  await expect(link).toBeVisible({timeout:15000});
  const href=await link.getAttribute('href');expect(href).toBeTruthy();
  const response=await page.request.get(href!);expect(response.status()).toBe(200);
  const apiBytes=await response.body();
  const [download]=await Promise.all([page.waitForEvent('download'),link.click()]);
  const destination=info.outputPath('modeling-step-audit.zip');await download.saveAs(destination);
  expect(fs.readFileSync(destination)).toEqual(apiBytes);
  fs.writeFileSync(info.outputPath('audit-download-receipt.json'),JSON.stringify({status:'PASS',sha256:crypto.createHash('sha256').update(apiBytes).digest('hex'),size_bytes:apiBytes.length,source:'REAL_API_WORKER_SYNTHETIC'}));
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
    await page.setViewportSize(viewport);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
    await page.screenshot({path:info.outputPath(`agents-${viewport.width}.png`),fullPage:true});
  }
});
