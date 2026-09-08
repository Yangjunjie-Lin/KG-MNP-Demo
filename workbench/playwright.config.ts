import { defineConfig } from '@playwright/test';
const runRoot=process.env.KG_MNP_BROWSER_EVIDENCE ?? '../runtime_logs/p09/browser-runs/'+new Date().toISOString().replace(/[:.]/g,'-');
export default defineConfig({testDir:'tests',testMatch:'*.e2e.ts',timeout:600000,workers:1,retries:0,
  outputDir:runRoot+'/output',reporter:[['./tests/redacted-reporter.ts'],['list'],['junit',{outputFile:runRoot+'/junit.xml'}]],
  use:{baseURL:process.env.KG_MNP_BROWSER_URL,viewport:{width:1440,height:900},actionTimeout:20000,navigationTimeout:30000,trace:'off',video:'off',screenshot:'off'}});
