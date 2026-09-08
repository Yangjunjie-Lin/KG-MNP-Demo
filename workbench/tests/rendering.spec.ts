import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';

test('first graph expansion fits visible nodes and wraps long labels',async({page},info)=>{
  await page.goto('/tests/graph-expansion.html');
  const toggle=page.getByText('概念与依赖图（布局拖动不修改语义）',{exact:true});
  await page.getByText('候选依赖树（键盘联动）',{exact:true}).click();
  await page.getByRole('button',{name:'树选择 Entity',exact:true}).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('选择候选（键盘替代图选择）')).toHaveValue('synthetic-1');
  await page.getByText('候选依赖树（键盘联动）',{exact:true}).click();
  await expect(page.locator('.react-flow')).toHaveCount(0);
  for(let opening=0;opening<2;opening++){
    await toggle.click();
    await expect(page.locator('.react-flow__node')).toHaveCount(6);
    await expect.poll(()=>page.locator('.graph').evaluate(container=>{
      const bounds=container.getBoundingClientRect();
      return [...container.querySelectorAll<HTMLElement>('.react-flow__node')].every(node=>{
        const box=node.getBoundingClientRect();
        return box.width>50&&box.left>=bounds.left&&box.right<=bounds.right&&box.top>=bounds.top&&box.bottom<=bounds.bottom&&node.scrollWidth<=node.clientWidth;
      });
    })).toBe(true);
    await toggle.evaluate(e=>e.scrollIntoView({block:'start'}));
    await page.screenshot({path:info.outputPath(`graph-opening-${opening}.png`)});
    await toggle.click();
    await expect(page.locator('.react-flow')).toHaveCount(0);
  }
});

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
