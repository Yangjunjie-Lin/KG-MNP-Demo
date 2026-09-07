import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';

test('actual shared table and graph components have bounded browser DOM',async({page},info)=>{
  await page.goto('/tests/rendering.html');
  await expect(page.getByLabel('首屏渲染毫秒')).not.toBeEmpty();
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(26);
  await expect(page.getByTestId('graph-size')).toHaveText('200 nodes / 400 edges');
  await expect(page.locator('.react-flow__node')).toHaveCount(200);
  await expect(page.locator('.react-flow__edge')).toHaveCount(400);
  await page.getByRole('button',{name:'下一页',exact:true}).click();
  await expect(page.getByText('row-25',{exact:true})).toBeVisible();
  await page.getByLabel('搜索表格',{exact:true}).fill('row-999');
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(2);
  await expect(page.getByText('row-999',{exact:true})).toBeVisible();
  const timing=Number(await page.getByLabel('首屏渲染毫秒').textContent());
  fs.writeFileSync(info.outputPath('measurement.json'),JSON.stringify({method:'Actual shared React components in test-only Vite entry; first render to two animation frames; no business API mocked',first_render_ms:timing,
    table_input:1000,table_dom_rows_before_filter:26,graph_input:250,graph_dom_nodes:200,graph_dom_edges:400,
    browser:page.context().browser()?.version(),cpu:os.cpus()[0]?.model,platform:os.platform(),release:os.release(),memory_bytes:os.totalmem()},null,2));
  await page.screenshot({path:info.outputPath('components.png'),fullPage:true});
});
