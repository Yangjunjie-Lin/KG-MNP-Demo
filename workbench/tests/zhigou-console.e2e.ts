import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';

test('five aggregate stages with real file ingestion, no frontend approval and responsive focus',async({page},info)=>{
  test.setTimeout(300000);
  const credentials=process.env.KG_MNP_BROWSER_CREDENTIAL;
  if(!credentials)throw new Error('Owned synthetic credentials required');
  const credential=JSON.parse(fs.readFileSync(credentials,'utf8'));
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByLabel('项目名称').fill('知构五流程验收');await page.getByLabel('领域包与版本').selectOption('hr@0.1.0',{timeout:120000});
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  // Creating a real project also verifies its locked domain pack and catalogue.
  // Use the same bounded readiness wait as the security/browser workflow; the
  // default five-second assertion timeout is not a service completion receipt.
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible({timeout:60000});
  const prefix=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  await page.goto(prefix+'/sources');
  await page.getByRole('button',{name:'加载当前领域包的合成批次（仅空项目）'}).click();
  async function state(){const response=await page.request.get('/api/v1'+prefix+'/state');expect(response.ok()).toBeTruthy();return response.json();}
  await expect.poll(async()=>{const s=await state();return s.jobs.find((j:{operation_id:string})=>j.operation_id==='source.sample.load')?.status;},{timeout:120000}).toBe('SUCCEEDED');
  const seededState=await state();const loaded=seededState.results.find((r:{operation:string})=>r.operation==='source.sample.load').result;
  expect(loaded.sources).toHaveLength(3);expect(loaded.approval).toBe('NOT_GRANTED');
  await page.goto(prefix+'/modeling?stage=1&run='+encodeURIComponent(loaded.run.run_id));
  await expect(page.getByRole('navigation',{name:'本体建模五阶段'}).getByRole('button')).toHaveCount(5);
  await expect(page.getByRole('navigation',{name:'工作台导航'}).getByRole('link')).toHaveCount(5);
  await page.getByRole('button',{name:'核验输入并生成画像'}).click();
  await expect.poll(async()=>{const s=await state();return s.jobs.find((j:{operation_id:string})=>j.operation_id==='modeling.profile')?.status;},{timeout:120000}).toBe('SUCCEEDED');
  const shots=info.outputPath('screenshots');fs.mkdirSync(shots,{recursive:true});
  for(let stage=1;stage<=5;stage++){
    await page.goto(prefix+`/modeling?stage=${stage}&focus=1`);
    await expect(page.getByRole('heading',{name:'本体建模工作台'})).toBeVisible();
    await expect(page.getByRole('region',{name:'处理前',exact:true})).toBeVisible();
    await expect(page.getByRole('region',{name:'处理后',exact:true})).toBeVisible();
    await page.screenshot({path:path.join(shots,`stage-${stage}.png`),fullPage:false});
  }
  for(const size of [{width:1440,height:900},{width:1366,height:768},{width:390,height:844}]){
    await page.setViewportSize(size);await page.goto(prefix+'/modeling?stage=1&focus=1');
    await expect(page.getByRole('heading',{name:'本体建模工作台'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
    const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    fs.writeFileSync(path.join(shots,`accessibility-${size.width}.json`),JSON.stringify(scan));expect(scan.violations).toEqual([]);
    await page.screenshot({path:path.join(shots,`focus-${size.width}.png`),fullPage:false});
  }
  await page.goto(prefix+'/modeling/tutorial/employee-department');
  await expect(page.getByRole('heading',{name:'本体建模工作台'})).toBeVisible();
  expect((await state()).results.some((r:{operation:string})=>r.operation==='review.action')).toBeFalsy();
  fs.writeFileSync(info.outputPath('real-run-state.json'),JSON.stringify(await state()));
});
