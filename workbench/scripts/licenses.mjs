import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const lock=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json'),'utf8'));
const notices=['Third-party notices for installed production Workbench dependencies.\nGenerated from the locked local installation; not a claim that every package is directly bundled.'];
for(const [relative,entry] of Object.entries(lock.packages).sort(([a],[b])=>a.localeCompare(b))){
  if(!relative.startsWith('node_modules/') || entry.dev) continue;
  const directory=path.join(root,relative);
  if(!fs.existsSync(directory)){if(entry.optional)continue;throw new Error(`Missing installed package: ${relative}`);}
  const metadata=JSON.parse(fs.readFileSync(path.join(directory,'package.json'),'utf8'));
  const files=fs.readdirSync(directory).filter(name=>/^(licen[cs]e|notice|copying)(\.|$)/i.test(name) && fs.statSync(path.join(directory,name)).isFile());
  if(!files.length)throw new Error(`Review required: license text missing for ${metadata.name}`);
  notices.push(`\n${metadata.name} ${metadata.version} — ${metadata.license || entry.license || 'see text'}\n`+files.map(name=>fs.readFileSync(path.join(directory,name),'utf8')).join('\n'));
}
fs.writeFileSync(path.join(root,'dist/third-party-notices.txt'),notices.join('\n\n'),'utf8');
