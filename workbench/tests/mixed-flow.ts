import {expect,type Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

export function mixedInputs() {
 const python=process.env.KG_MNP_TEST_PYTHON;
 if(!python)throw new Error('Explicit locked test Python required');
 const files=JSON.parse(execFileSync(python,['-c',"import json,base64; from tests.services.test_mixed_source_workflow import mixed_files; print(json.dumps([{'name':n,'mimeType':m,'data':base64.b64encode(b).decode()} for n,m,b in mixed_files()]))"],{cwd:path.resolve('..'),encoding:'utf8',timeout:30000})) as {name:string;mimeType:string;data:string}[];
 return files.map(({name,mimeType,data})=>({name,mimeType,buffer:Buffer.from(data,'base64')}));
}

export async function mixedMapping(page:Page, prepared:{input_inventory:{tables:unknown[];text_items:{source_ids:string[]}[]}}, classIri:string) {
 const form=page.locator('section').filter({has:page.getByRole('heading',{name:'混合资料建模：表格、文本与统一身份',exact:true})});
 async function fields(panel:ReturnType<Page['locator']>) {
  await panel.getByLabel('对象类型',{exact:true}).selectOption(classIri);
  await panel.getByRole('button',{name:'添加数据属性',exact:true}).click();
  await panel.getByLabel('数据字段 1',{exact:true}).fill('label');
  await panel.getByLabel('数据属性 1',{exact:true}).selectOption(classIri.replace(/Entity$/,'label'));
 }
 for(let index=0;index<prepared.input_inventory.tables.length;index++) {
  const panel=form.locator('details').nth(index);
  await panel.locator('summary').click();
  await panel.getByLabel(`纳入表格 ${index+1}`,{exact:true}).check();
  await fields(panel);
  if((await panel.locator('summary').textContent())?.includes('facts.docx')) {
   await panel.getByRole('button',{name:'声明身份别名',exact:true}).click();
   await panel.getByLabel('原始主键 1',{exact:true}).fill('legacy-A');
   await panel.getByLabel('统一主键 1',{exact:true}).fill('T001');
   await panel.getByLabel('身份合并依据 1',{exact:true}).fill('Synthetic explicit identity cross-reference');
  }
 }
 const sources=[...new Set(prepared.input_inventory.text_items.flatMap(i=>i.source_ids))];
 for(let index=0;index<sources.length;index++) {
  await form.getByRole('button',{name:'添加文本模板',exact:true}).click();
  const panel=form.getByRole('group',{name:`文本模板 ${index+1}`,exact:true});
  await panel.getByLabel(`模板资料 ${index+1}`,{exact:true}).selectOption(sources[index]);
  await panel.getByLabel(`匹配模板 ${index+1}`,{exact:true}).fill('实体 {id} 的标签为 {label}。');
  await fields(panel);
 }
 await expect(form.getByRole('button',{name:'生成混合资料候选',exact:true})).toBeEnabled();
 await form.getByRole('button',{name:'生成混合资料候选',exact:true}).click();
}
