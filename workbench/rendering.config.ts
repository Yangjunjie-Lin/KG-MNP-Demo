import {defineConfig} from '@playwright/test';
const externalURL=process.env.KG_MNP_RENDERING_URL;
const managedURL='http://127.0.0.1:4174';
export default defineConfig({testDir:'tests',testMatch:'rendering.spec.ts',workers:1,retries:0,
  outputDir:'../runtime_logs/p09/rendering/output',reporter:[['./tests/redacted-reporter.ts'],['list'],['junit',{outputFile:'../runtime_logs/p09/rendering/junit.xml'}]],
  webServer:externalURL?undefined:{command:'npm run dev -- --port 4174 --strictPort',url:managedURL+'/tests/rendering.html',reuseExistingServer:false,timeout:60000},
  use:{baseURL:externalURL??managedURL,viewport:{width:1440,height:900},trace:'off'}});
