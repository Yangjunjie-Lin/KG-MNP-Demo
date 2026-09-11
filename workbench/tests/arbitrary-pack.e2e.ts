import {test,expect} from '@playwright/test';
import fs from 'node:fs';

test('arbitrary pack identifier uses the same real project UI',async({page})=>{
 const token=JSON.parse(fs.readFileSync(process.env.KG_MNP_BROWSER_CREDENTIAL!,'utf8')).token;
 await page.goto('/');await page.getByLabel('访问凭证').fill(token);await page.getByRole('button',{name:'登录',exact:true}).click();
 await expect(page.getByRole('heading',{name:'选择项目',exact:true})).toBeVisible({timeout:30000});
 await page.getByLabel('项目名称').fill('临时第四领域-'+Date.now());
 await page.getByLabel('领域包与版本').selectOption('arbitrary-validation-pack@0.1.0');
 await page.getByRole('button',{name:'创建项目',exact:true}).click();
 await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible({timeout:60000});
 await expect(page.getByText('arbitrary-validation-pack · 0.1.0',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'数据接入与规则化',exact:true}).click();
 await expect(page.getByLabel('资料文件')).toBeVisible();
 await page.getByRole('button',{name:'退出',exact:true}).click();
});
