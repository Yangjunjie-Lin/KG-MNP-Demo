import {test,expect} from '@playwright/test';
import fs from 'node:fs';

test('legacy tutorial URL redirects to the single console without mutating project authority',async({page})=>{
  const credentials=process.env.KG_MNP_BROWSER_CREDENTIAL;
  if(!credentials)throw new Error('owned synthetic credentials required');
  const credential=JSON.parse(fs.readFileSync(credentials,'utf8'));
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByLabel('项目名称').fill('兼容链接只读验收');
  await page.getByLabel('领域包与版本').selectOption('minimal@0.1.0');
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible();
  const prefix=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  const before=await (await page.request.get('/api/v1'+prefix+'/state')).json();
  await page.goto(prefix+'/modeling/tutorial/employee-department?step=3.6&view=output');
  await expect(page.getByRole('heading',{name:'本体建模工作台'})).toBeVisible();
  await expect(page.getByRole('navigation',{name:'本体建模五阶段'}).getByRole('button')).toHaveCount(5);
  const after=await (await page.request.get('/api/v1'+prefix+'/state')).json();
  expect(after.project.authority_revision).toBe(before.project.authority_revision);
  expect(after.results).toEqual(before.results);
  expect(page.url()).not.toContain('/tutorial/');
});
