import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';

test('real session negative boundaries and identity cache isolation',async({page},info)=>{
  test.setTimeout(300000);
  const credentials=JSON.parse(fs.readFileSync(process.env.KG_MNP_BROWSER_CREDENTIAL!,'utf8'));
  if(!credentials.viewer_token)throw new Error('synthetic isolated viewer credential required');
  await page.goto('/');
  // Actively prove CSP rejects HTTP(S)/WS(S) egress. Routing is a safety net:
  // if CSP regresses, abort before any external network connection and fail.
  const intercepted:string[]=[];
  const origin=new URL(page.url()).origin;
  await page.route('**/*',async route=>{
    if(new URL(route.request().url()).origin!==origin){intercepted.push(route.request().url());await route.abort('blockedbyclient');}
    else await route.continue();
  });
  await page.routeWebSocket('**/*',socket=>{intercepted.push(socket.url());socket.close();});
  const networkProbe=await page.evaluate(async()=>{
    const blocked:string[]=[];
    const listener=(event:SecurityPolicyViolationEvent)=>{if(event.effectiveDirective==='connect-src')blocked.push(event.blockedURI);};
    window.addEventListener('securitypolicyviolation',listener);
    for(const url of ['http://external.invalid/probe','https://external.invalid/probe']){
      await fetch(url).then(()=>{throw new Error('Unexpected external fetch success');},()=>undefined);
    }
    for(const url of ['ws://external.invalid/probe','wss://external.invalid/probe']){
      await new Promise<void>(resolve=>{const socket=new WebSocket(url);socket.onerror=()=>resolve();socket.onclose=()=>resolve();setTimeout(()=>{socket.close();resolve();},1000);});
    }
    await new Promise(resolve=>setTimeout(resolve,50));
    window.removeEventListener('securitypolicyviolation',listener);
    return blocked;
  });
  expect(intercepted).toEqual([]);
  expect(networkProbe.length).toBeGreaterThanOrEqual(4);
  fs.writeFileSync(info.outputPath('network-boundary.json'),JSON.stringify({method:'Actual Chromium CSP, safety routes installed before probing',blocked:networkProbe,intercepted,status:'PASS'},null,2));
  await page.getByLabel('访问凭证').fill('synthetic-invalid-credential');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('访问凭证')).toHaveValue('');
  await page.getByLabel('访问凭证').fill(credentials.token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('heading',{name:'选择项目',exact:true})).toBeVisible();
  await page.getByLabel('项目名称').fill('会话隔离合成数据-'+Date.now());
  await page.getByLabel('领域包与版本').selectOption('minimal@0.1.0');
  await page.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'项目概览',exact:true})).toBeVisible({timeout:60000});
  const projectPath=new URL(page.url()).pathname.split('/').slice(0,3).join('/');
  const cookies=await page.context().cookies();
  expect(cookies.some(c=>c.httpOnly&&c.sameSite==='Strict')).toBe(true);
  expect(await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)}))).toEqual({local:[],session:[]});
  const noCsrf=await page.request.post('/api/v1/session/logout',{data:{}});
  expect(noCsrf.status()).toBe(403);
  const crossOrigin=await page.request.post('/api/v1'+projectPath+'/sources',{headers:{Origin:'https://example.invalid','X-Filename':'unsafe.txt','Content-Type':'text/plain'},data:'synthetic'});
  expect(crossOrigin.status()).toBe(403);
  await page.getByRole('link',{name:'资料与证据',exact:true}).click();
  await page.getByLabel('资料文件').setInputFiles({name:'inert.txt',mimeType:'text/plain',buffer:Buffer.from('<script>window.__unsafeExecuted=true</script> synthetic inert source')});
  await page.getByRole('button',{name:'上传并登记 Source',exact:true}).click();
  await expect.poll(async()=>{
    const r=await page.request.get('/api/v1'+projectPath+'/state');expect(r.ok()).toBe(true);
    return (await r.json()).results.filter((v:{operation:string})=>v.operation==='source.register').length;
  },{timeout:120000}).toBe(1);
  expect(await page.evaluate(()=>('__unsafeExecuted' in window))).toBe(false);
  const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  fs.writeFileSync(info.outputPath('negative-accessibility.json'),JSON.stringify(scan,null,2));
  expect(scan.violations).toEqual([]);
  // Keyboard-driven navigation checks are recorded separately from axe scan.
  await page.keyboard.press('Tab');
  await page.getByRole('link',{name:'任务中心',exact:true}).focus();
  await expect(page.getByRole('link',{name:'任务中心',exact:true})).toBeFocused();
  const focusVisible=await page.getByRole('link',{name:'任务中心',exact:true}).evaluate(element=>{const style=getComputedStyle(element);return style.outlineStyle!=='none'&&parseFloat(style.outlineWidth)>=2;});
  expect(focusVisible).toBe(true);
  await page.screenshot({path:info.outputPath('keyboard-focus.png')});
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading',{name:'任务中心',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'退出',exact:true}).click();
  await page.getByLabel('访问凭证').fill(credentials.viewer_token);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('heading',{name:'选择项目',exact:true})).toBeVisible();
  await expect(page.getByText('暂无可访问项目',{exact:true})).toBeVisible();
  await page.goto(projectPath+'/sources');
  await expect(page.getByRole('alert')).toContainText('403');
  await expect(page.getByText('inert.txt',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('资料文件')).toHaveCount(0);
  fs.writeFileSync(info.outputPath('keyboard-check.json'),JSON.stringify({method:'Automated Chromium keyboard focus and Enter, distinct from manual keyboard inspection',focus_visible_checked:focusVisible,navigation:'PASSED',identity_cache_isolation:'PASSED'},null,2));
  await page.getByRole('button',{name:'退出',exact:true}).click();
});
