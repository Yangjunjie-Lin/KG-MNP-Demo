import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('read actual completed stages and execution evidence without mutations',async({page},info)=>{
  test.skip(process.env.ZHIGOU_SAVED_EVIDENCE!=='1','Requires explicitly selected completed synthetic workspace; covered separately from fresh browser workflows.');
  const credential=JSON.parse(fs.readFileSync(process.env.KG_MNP_BROWSER_CREDENTIAL!,'utf8'));
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);await page.getByRole('button',{name:'登录',exact:true}).click();
  const card=page.locator('a.project-card');
  await expect(card).toBeVisible({timeout:120000});await expect(card).toHaveCount(1);
  const href=await card.getAttribute('href');if(!href)throw new Error('Project link missing');
  const prefix=href.split('/').slice(0,3).join('/');
  const before=await (await page.request.get('/api/v1'+prefix+'/state',{timeout:120000})).json();
  const output=info.outputPath('screenshots');fs.mkdirSync(output,{recursive:true});
  for(let stage=1;stage<=5;stage++){
    await page.goto(prefix+'/modeling?stage='+stage+'&focus=1');
    await expect(page.getByRole('heading',{name:'本体建模工作台'})).toBeVisible();
    await page.screenshot({path:path.join(output,'completed-stage-'+stage+'.png'),fullPage:false});
  }
  for(const route of ['releases','execution','evolution']){
    await page.goto(prefix+'/'+route);await expect(page.locator('h1').first()).toBeVisible();
    if(route==='execution')await expect(page.getByRole('status').filter({hasText:/已读取 \d+ 条工单/})).toBeVisible({timeout:120000});
    await page.screenshot({path:path.join(output,route+'.png'),fullPage:true});
  }
  const after=await (await page.request.get('/api/v1'+prefix+'/state',{timeout:120000})).json();
  expect(after.project.authority_revision).toBe(before.project.authority_revision);
  expect(after.results).toEqual(before.results);
  fs.writeFileSync(info.outputPath('completed-stage-state.json'),JSON.stringify(after));
});
