import tseslint from 'typescript-eslint';
export default tseslint.config(...tseslint.configs.recommended,{
 files:['src/**/*.ts','src/**/*.tsx'],
 rules:{'@typescript-eslint/no-unused-vars':['error',{argsIgnorePattern:'^_',varsIgnorePattern:'^_'}]}
},{ignores:['dist/**','node_modules/**','tests/**','playwright.config.ts','vite.config.ts']});
