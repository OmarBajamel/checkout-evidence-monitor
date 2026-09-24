// Guard developer runtime commands before starting a child. No install/build hook calls this.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
function files(dir){return fs.existsSync(dir)?fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.name==='__pycache__'?[]:e.isDirectory()?files(path.join(dir,e.name)):e.isFile()?[path.join(dir,e.name)]:[]):[];}
const h=crypto.createHash('sha256');
for(const dir of ['src','frontend/src','lab','tests','benchmarks','tools','schemas','migrations','frontend/public','frontend/.storybook'])
 for(const p of files(path.join(root,dir)).sort((a,b)=>{const x=path.relative(root,a).replaceAll('\\','/'),y=path.relative(root,b).replaceAll('\\','/');return x<y?-1:x>y?1:0;})){
  h.update(path.relative(root,p).replaceAll('\\','/')+'\0');h.update(crypto.createHash('sha256').update(fs.readFileSync(p)).digest());
 }
for(const name of ['pyproject.toml','requirements-win.lock','requirements-linux.lock','requirements-dev-win.lock','requirements-dev-linux.lock','frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/vite.config.ts','frontend/index.html','frontend/.npmrc']){
 const p=path.join(root,name);if(fs.existsSync(p)){h.update(name+'\0');h.update(crypto.createHash('sha256').update(fs.readFileSync(p)).digest());}
}
try {
 const s=JSON.parse(fs.readFileSync(process.env.CEM_TEST_SESSION||'', 'utf8'));
 if(s.instruction!=='TEST APPROVED'||(!Number.isFinite(Date.parse(s.expires_at))||Date.parse(s.expires_at)<=Date.now())||!['OFFLINE','LAB','OFFLINE_AND_LAB'].includes(s.profile)||s.source_snapshot!==h.digest('hex'))throw Error();
 const ap=path.join(root,'state/APPROVAL_RECORD.json');
 if(fs.existsSync(ap)&&!JSON.parse(fs.readFileSync(ap,'utf8').replace(/^\uFEFF/,'' )).testing.authorized)throw Error();
} catch {console.error('TEST_APPROVAL_REQUIRED: matching local runtime/visual permission is required.');process.exit(3);}
const [command,...args]=process.argv.slice(2);
const bins={storybook:'../frontend/node_modules/storybook/dist/bin/dispatcher.js',playwright:'../frontend/node_modules/@playwright/test/cli.js'};
if(!Object.hasOwn(bins,command)){console.error('Unsupported guarded command');process.exit(3);}
const r=spawnSync(process.execPath,[path.resolve(import.meta.dirname,bins[command]),...args],{stdio:'inherit',env:{...process.env,STORYBOOK_DISABLE_TELEMETRY:'1'}});
process.exit(r.status??1);
