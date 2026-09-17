const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'..');
const extra=JSON.parse(fs.readFileSync(path.join(root,'clients/shared/strings.json'),'utf8'));
assert.equal(new Set(extra.locales).size,12);
const catalogs=Object.fromEntries(extra.locales.map(locale=>[locale,JSON.parse(fs.readFileSync(path.join(root,'web/assets/locales',locale+'.json'),'utf8'))]));
for(const [key,values] of Object.entries(extra.messages)){
  assert.equal(values.length,12,key);
  values.forEach((value,i)=>{assert.equal(typeof value,'string',key);assert(value.trim(),key);catalogs[extra.locales[i]][key]=value;});
}
const required=new Set();
const html=fs.readFileSync(path.join(root,'clients/mobile-ui/index.html'),'utf8');
for(const match of html.matchAll(/data-i18n(?:-[a-z-]+)?="([^"]+)"/g))required.add(match[1]);
for(const file of ['clients/mobile-ui/app.js','clients/wechat/miniprogram/pages/home/index.js']){
  const source=fs.readFileSync(path.join(root,file),'utf8');
  for(const name of ['states','labels']){
    const match=source.match(new RegExp('const '+name+'\\s*=\\s*(\\{[^;]+\\});'));
    if(match)Object.values(vm.runInNewContext('('+match[1]+')')).forEach(key=>required.add(key));
  }
}
for(const key of required)for(const locale of extra.locales)assert(catalogs[locale][key],locale+': '+key);
const placeholders=value=>(value.match(/\{[^}]+\}/g)||[]).sort();
for(const key of Object.keys(catalogs.en))for(const locale of extra.locales)assert.deepEqual(placeholders(catalogs[locale][key]),placeholders(catalogs.en[key]),locale+': '+key);
console.log(`Mobile catalogs: 12 locales, ${Object.keys(catalogs.en).length} keys each, placeholders and ${required.size} interface/state labels passed.`);
