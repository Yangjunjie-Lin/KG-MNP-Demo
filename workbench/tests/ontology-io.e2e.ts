import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import {readProjectState} from './browser-session';

test('real browser imports a research report through authenticated read-only API',async({page},info)=>{
  const path=process.env.KG_MNP_BROWSER_CREDENTIAL;
  if(!path)throw new Error('owned synthetic credentials required');
  const credential=JSON.parse(fs.readFileSync(path,'utf8'));
  await page.goto('/');await page.getByLabel('访问凭证').fill(credential.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByLabel('项目名称').fill('本体输入输出只读浏览器回归');
  await page.getByLabel('领域包与版本').selectOption('minimal@0.1.0');
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible();
  const prefix=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  const before=await readProjectState(page,prefix);
  await page.goto(prefix+'/modeling/io');
  await expect(page.getByRole('heading',{name:'本体 I/O 评测',exact:true})).toBeVisible();
  await expect(page.getByText(/指标为 null/)).toBeVisible();
  const report={schema_version:'1.0.0',benchmark_id:'synthetic-ui-boundary',task_id:'report-import',dataset_version:'fixture-v1',split:'NONE',evaluation_scope:'ENGINEERING_CHECK',
    input_manifest_sha256:null,prediction_manifest_sha256:null,scorer_commit:null,scorer_config_sha256:null,system_id:'NOT_RUN',model_id:'NOT_RUN',declared_revision:'NOT_RUN',observed_model_ids:[],
    run_id:'synthetic-report-import',source_commit:null,source_fingerprint_sha256:null,metrics:[{name:'graph_similarity',source:'TEST_ONLY_NO_MEASUREMENT',matching:'exact',value:null,unit:'fraction',numerator:null,denominator:null,status:'NOT_RUN'}],
    sample_count:0,failure_count:0,status:'NOT_RUN',comparison:null,resources:[],limitations:['Synthetic UI boundary fixture; not a research measurement']};
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/v1/operations/ontology.io.inspect'));
  await page.getByLabel('研究报告 JSON').setInputFiles({name:'not-run.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(report))});
  expect((await responsePromise).status()).toBe(200);
  await expect(page.getByText('null / NOT_RUN',{exact:true})).toBeVisible();
  await expect(page.getByText(/UNVERIFIED_EXTERNAL_REPORT/)).toBeVisible();
  await page.screenshot({path:info.outputPath('ontology-io-report.png'),fullPage:true});
  const rejected=page.waitForResponse(r=>r.url().endsWith('/api/v1/operations/ontology.io.inspect'));
  await page.getByLabel('研究报告 JSON').setInputFiles({name:'private-field.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...report,private_gold:['DO_NOT_DISPLAY_SENTINEL']}))});
  expect((await rejected).status()).toBe(422);
  await expect(page.getByRole('alert')).toContainText('ONTOLOGY_IO_REPORT_INVALID');
  await expect(page.getByText('DO_NOT_DISPLAY_SENTINEL')).toHaveCount(0);
  const after=await readProjectState(page,prefix);
  expect(after.project.authority_revision).toBe(before.project.authority_revision);
  expect(after.results).toEqual(before.results);
  expect(after.registry_head).toBe(before.registry_head);
});
