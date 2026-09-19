const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {classify,destination,detect}=require('../site/app.js');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
const context={window:{}};
for(const file of ['catalogs.js','check-catalogs.js']) vm.runInNewContext(fs.readFileSync(path.join(root,'site',file),'utf8'),context);
const catalogs=context.window.CLIPNEST_SITE;
assert.equal(Object.keys(catalogs).length,12);
const keys=[...html.matchAll(/data-key="([^"]+)"/g)].map(match=>match[1]);
keys.push(...['checking','ready','missing','unreachable','incompatible'].flatMap(s=>[s+'Title',s+'Detail']),
  'python','ffmpeg','javascript','extractor','available','required','unknown','publisher','missingInstall','firstInstall','missingSteps','firstSteps');
for(const [locale,catalog] of Object.entries(catalogs))for(const key of keys){
  assert.equal(typeof catalog[key],'string',locale+': '+key);assert(catalog[key].trim());
}
const good={product:'clipnest',protocol:1,ready:true,checks:['python','ffmpeg','javascript','extractor'].map(id=>({id,ready:true}))};
assert.equal(classify(good),'ready');
assert.equal(classify({...good,ready:false,checks:good.checks.map(c=>({...c,ready:c.id!=='ffmpeg'}))}),'missing');
for(const bad of [null,{}, {...good,ready:'true'}, {...good,ready:false}, {...good,checks:[]}, {...good,protocol:2}, {...good,checks:[good.checks[0],...good.checks.slice(0,3)]}]) assert.equal(classify(bad),'incompatible');
assert.equal(destination('zh-CN'),'http://127.0.0.1:8000/?lang=zh-CN');
assert.equal(destination('https://evil.example'),'http://127.0.0.1:8000/?lang=en');
assert(html.includes('connect-src http://127.0.0.1:8000;'));
(async()=>{
  const result=await detect(async(url,options)=>{
    assert.equal(url,'http://127.0.0.1:8000/local/environment');
    assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');
    return {ok:true,json:async()=>good};
  });
  assert.equal(result.status,'ready');
  assert.equal((await detect(async()=>{throw new TypeError('Permission denied')})).status,'unreachable');
  assert.equal((await detect(async()=>({ok:false,status:404}))).status,'incompatible');
  assert.equal((await detect(async()=>({ok:true,json:async()=>{throw new Error('HTML')} }))).status,'unreachable');
  console.log('Website check: 12 languages; ready/missing/unreachable/invalid; fixed local destination; no credentials.');
})().catch(error=>{console.error(error);process.exitCode=1;});
