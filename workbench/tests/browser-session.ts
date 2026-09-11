import {expect,type Page} from '@playwright/test';
import fs from 'node:fs';

// Synthetic operator reauthentication only. Never retries a business mutation.
// A revoked credential still fails login; 403 is never turned into an admin.
export async function readProjectState(page:Page,prefix:string){
  let response=await page.request.get('/api/v1'+prefix+'/state');
  if(response.status()===401){
    const path=process.env.KG_MNP_BROWSER_CREDENTIAL;
    if(!path)throw new Error('Explicit synthetic credential required for reauthentication');
    const token=JSON.parse(fs.readFileSync(path,'utf8')).token;
    await page.reload();
    await expect(page.getByLabel('访问凭证')).toBeVisible();
    await page.getByLabel('访问凭证').fill(token);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await expect(page.getByLabel('访问凭证')).toHaveCount(0);
    response=await page.request.get('/api/v1'+prefix+'/state');
  }
  if(!response.ok())throw new Error(`Project state HTTP ${response.status()}`);
  return response.json();
}
