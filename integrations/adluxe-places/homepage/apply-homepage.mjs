#!/usr/bin/env node
/** Bounded frontend patch. Run only after the OS release gate passes. Default: inspect. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
const argv=process.argv.slice(2), apply=argv.includes('--apply'), rollback=argv.includes('--rollback');
const at=argv.indexOf('--root');
const root=await fs.realpath(at<0?'/home/adluxeplaces/adspot':argv[at+1]);
const dir=path.dirname(fileURLToPath(import.meta.url));
const version='20260908', stem=`al-homepage-responsive-${version}`;
const targets=['index.html','build/frontend/index.html'];
const shas={css:'bd66e4c4d3f13ad013173393f71c2887bb303ce60c65b24407b44efa85733544',js:'29408e4b01c4a66e61b7d1de36dc22711cf5dcc1bddd86cab1d8a9c86ea24175'};
const hash=v=>crypto.createHash('sha256').update(v).digest('hex');
const expectedArg=argv.indexOf('--expected');
const expected=expectedArg<0?null:JSON.parse(await fs.readFile(argv[expectedArg+1],'utf8'));
const snapshot=path.join(path.dirname(root),`.ct-${stem}-snapshot`);
const lock=path.join(root,'tmp',`.ct-${stem}.lock`);
const tag=`<!-- ${stem} -->`;
const patch=s=>{
 if(s.includes(tag)) throw Error('ALREADY_PATCHED');
 if((s.match(/<\/head>/gi)||[]).length!==1||(s.match(/<\/body>/gi)||[]).length!==1)throw Error('UNEXPECTED_HTML_SHAPE');
 return s.replace(/<\/head>/i,`${tag}\n<link rel="stylesheet" href="/${stem}.css">\n</head>`).replace(/<\/body>/i,`<script defer src="/${stem}.js"></script>\n</body>`);
};
async function file(rel){const p=path.join(root,rel);if((await fs.lstat(p)).isSymbolicLink())throw Error('SYMLINK_NOT_ALLOWED');const real=await fs.realpath(p);if(!real.startsWith(root+path.sep))throw Error('PATH_OUTSIDE_APP');return fs.readFile(p);}
async function atomic(p,bytes,mode=0o644){const tmp=p+'.ct-'+crypto.randomUUID();try{await fs.writeFile(tmp,bytes,{flag:'wx',mode});await fs.rename(tmp,p);}finally{await fs.rm(tmp,{force:true});}}
async function inspect(){const result={};for(const rel of targets){const bytes=await file(rel);result[rel]={sha256:hash(bytes),bytes:bytes.length,patched:bytes.toString().includes(tag)};}return result;}
let locked=false;
try {
 if(apply&&rollback)throw Error('CHOOSE_APPLY_OR_ROLLBACK');
 if(!apply&&!rollback){console.log(JSON.stringify({mode:'inspect',root,expected:await inspect(),provider_write:false},null,2));process.exit(0);}
 await fs.writeFile(lock,JSON.stringify({pid:process.pid,started_at:new Date().toISOString()}),{flag:'wx',mode:0o600});locked=true;
 if(rollback){
  const manifest=JSON.parse(await fs.readFile(path.join(snapshot,'manifest.json'),'utf8'));
  for(const rel of targets){if(hash(await file(rel))!==manifest.after[rel])throw Error('ROLLBACK_CONCURRENT_CHANGE:'+rel);}
  for(let i=0;i<targets.length;i++){const original=await fs.readFile(path.join(snapshot,`${i}.original`));if(hash(original)!==manifest.before[targets[i]])throw Error('BACKUP_DIGEST_MISMATCH');await atomic(path.join(root,targets[i]),original);}
  console.log(JSON.stringify({mode:'rollback',restored:await inspect(),retained_assets:true},null,2));
 }else{
  if(!expected)throw Error('EXPECTED_HASH_FILE_REQUIRED');
  const states=await inspect(),before={},after={},originals={};
  for(const rel of targets){const want=expected.expected?.[rel]?.sha256??expected[rel]?.sha256??expected[rel];if(want!==states[rel].sha256)throw Error('CONCURRENT_CHANGE:'+rel);originals[rel]=await file(rel);before[rel]=hash(originals[rel]);if(states[rel].patched)throw Error('ALREADY_PATCHED');}
  const built=originals['build/frontend/index.html'].toString('utf8');
  if(!built.includes('/assets/index-CGLrHdox.js')||!built.includes('/assets/index-DSnp2kZG.css'))throw Error('BUILD_BASELINE_MOVED');
  const assets={};for(const ext of ['css','js']){assets[ext]=await fs.readFile(path.join(dir,`homepage-responsive.${ext}`));if(hash(assets[ext])!==shas[ext])throw Error('ASSET_DIGEST_MISMATCH:'+ext);}
  // Source/public copies survive future Vite builds. Built copies serve this release.
  for(const folder of ['public','build/frontend']){const real=await fs.realpath(path.join(root,folder));if(!real.startsWith(root+path.sep))throw Error('ASSET_ROOT_OUTSIDE_APP');for(const ext of ['css','js']){const dest=path.join(real,`${stem}.${ext}`);try{await fs.writeFile(dest,assets[ext],{flag:'wx',mode:0o644});}catch(e){if(e.code!=='EEXIST'||hash(await fs.readFile(dest))!==shas[ext])throw e;}}}
  await fs.mkdir(snapshot,{mode:0o700});
  for(let i=0;i<targets.length;i++)await fs.writeFile(path.join(snapshot,`${i}.original`),originals[targets[i]],{flag:'wx',mode:0o600});
  for(const rel of targets)after[rel]=hash(Buffer.from(patch(originals[rel].toString('utf8'))));
  await fs.writeFile(path.join(snapshot,'manifest.json'),JSON.stringify({version,root,before,after,asset_sha256:shas,created_at:new Date().toISOString()},null,2),{flag:'wx',mode:0o600});
  const changed=[];
  try{for(const rel of targets){if(hash(await file(rel))!==before[rel])throw Error('CONCURRENT_CHANGE:'+rel);await atomic(path.join(root,rel),Buffer.from(patch(originals[rel].toString('utf8'))));changed.push(rel);if(hash(await file(rel))!==after[rel])throw Error('WRITE_READBACK_FAILED:'+rel);}}
  catch(e){for(const rel of changed.reverse()){if(hash(await file(rel))===after[rel])await atomic(path.join(root,rel),originals[rel]);}throw e;}
  console.log(JSON.stringify({mode:'applied',root,backup:snapshot,files:await inspect(),asset_sha256:shas,public_http_readback_required:true,institutional_completion:false},null,2));
 }
}catch(e){console.error(JSON.stringify({state:'FAILED_CLOSED',reason:e.message}));process.exitCode=1;}
finally{if(locked)await fs.rm(lock,{force:true});}
