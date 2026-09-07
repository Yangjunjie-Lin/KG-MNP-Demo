import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests',testMatch:'rendering.spec.ts',workers:1,retries:0,
  outputDir:'../runtime_logs/p09/rendering/output',reporter:[['./tests/redacted-reporter.ts'],['list'],['junit',{outputFile:'../runtime_logs/p09/rendering/junit.xml'}]],
  use:{baseURL:process.env.KG_MNP_RENDERING_URL,viewport:{width:1440,height:900},trace:'off'}});
