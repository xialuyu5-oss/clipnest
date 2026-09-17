import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = fs.readFileSync(new URL('../web/app.js', import.meta.url),'utf8');
const t = (key, params = {}) => key.replace(/\{(\w+)\}/g, (match, name) => params[name] ?? match);
new vm.Script(source);
const apiCode=source.slice(source.indexOf('  async function api('),source.indexOf('  async function connect('));
let timer, bodyPending=false;
const apiContext=vm.createContext({
  PREVIEW:false,state:{csrf:'',epoch:0},AbortController,t,
  setTimeout:fn=>{timer=fn;return 1;},clearTimeout:()=>{timer=null;},
  apiError:(text,code)=>Object.assign(new Error(text),{code}),
  fetch:async(_url,options)=>({ok:true,json:()=>new Promise((_resolve,reject)=>{
    bodyPending=true;
    options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('abort'),{name:'AbortError'})));
  })}),
});
vm.runInContext(apiCode+'\nglobalThis.invoke=api;',apiContext);
const pending=apiContext.invoke('/api/analyze');
for(let i=0;i<5;i++)await Promise.resolve();
assert.ok(bodyPending && timer,'Timeout must remain active while response body stalls');
timer();
await assert.rejects(pending,err=>err.code==='NETWORK_ERROR');
assert.equal(timer,null);
const refreshCode=source.slice(source.indexOf('  async function refreshJobs('),source.indexOf('  function schedulePoll('));
const logoutCode=source.match(/\$\('#logout-button'\)\.addEventListener\('click', (async \(\) => \{[\s\S]*?\n  \})\);/)[1];
let release;
const state={authenticated:true,csrf:'test',epoch:0,memberEpoch:0,jobs:[],refreshing:false,pollFailures:0};
const context=vm.createContext({state,t,
  api:path=>path==='/api/downloads'?new Promise(resolve=>{release=resolve;}):Promise.resolve({ok:true}),
  $:()=>({}),toast(){},renderJobs(){},renderSettings(){},updateServiceStatus(){},renderMember(){},clearTimeout(){},
});
vm.runInContext(refreshCode+'\nglobalThis.refresh=refreshJobs;globalThis.logout='+logoutCode+';',context);
const refreshing=context.refresh(false);
await context.logout();release({items:[{id:'old-session',state:'ready'}]});await refreshing;
assert.equal(state.authenticated,false);
assert.equal(state.jobs.length,0,'Stale response must not repopulate logged-out jobs');
const audioCode=source.slice(source.indexOf('  function codecLabel('),source.indexOf('  function renderQualities('));
const audioContext=vm.createContext({t});
vm.runInContext(audioCode+'\nglobalThis.label=audioLabel;',audioContext);
assert.equal(audioContext.label({has_audio:null}),'Audio unknown');
assert.equal(audioContext.label({has_audio:false}),'No audio');
assert.equal(audioContext.label({has_audio:true}),'With audio');
assert.equal(audioContext.label({has_audio:true,audio_codec:'aac'}),'With audio · AAC');
const pollCode=source.slice(source.indexOf('  async function pollMember('),source.indexOf("  $('#member-start').addEventListener"));
let visibilityChanged, polls=0, message='', scheduled;
const qrState={memberEpoch:1,qrFlow:'test-flow',qrExpires:Date.now()+180000,qrPolling:false};
const page={hidden:true,addEventListener:(_event,handler)=>{visibilityChanged=handler;}};
const nodes=new Map();
const qrContext=vm.createContext({state:qrState,document:page,Date,t,
  $:selector=>{if(!nodes.has(selector))nodes.set(selector,{addEventListener(){}});return nodes.get(selector);},
  api:async()=>{polls++;return {status:'connected',vip:true};},
  clearTimeout(){scheduled=null;},setTimeout:fn=>{scheduled=fn;return 1;},
  renderMember(){},invalidateMedia(){},memberMessage:text=>{message=text;},
});
vm.runInContext(pollCode+'\nglobalThis.poll=pollMember;',qrContext);
await qrContext.poll(1);assert.equal(polls,0,'Do not poll while the App is foreground');
page.hidden=false;visibilityChanged();for(let i=0;i<5;i++)await Promise.resolve();
assert.equal(qrState.member.status,'connected');assert.equal(qrState.qrFlow,null);
assert.equal(nodes.get('#use-member').checked,true,'Returning to the page picks up authorization');
qrState.qrFlow='expired';qrState.qrExpires=Date.now()-1;
await qrContext.poll(1);assert.equal(polls,1);assert.equal(qrState.qrFlow,null);assert.match(message,/expired/);
qrState.qrFlow='cancelled';qrState.memberEpoch=2;await qrContext.poll(1);assert.equal(polls,1);
// Job cards: a cancelled job must not be described as a failure, and failed jobs use the code map.
const jobsCode=source.slice(source.indexOf('  function errorMessage('),source.indexOf('  function el('))
  +source.slice(source.indexOf('  function renderJobs('),source.indexOf('  function saveFile('));
const fake=(tag,className='',text='')=>({tag,className,textContent:text,children:[],attrs:{},style:{},title:'',
  append(...nodes){this.children.push(...nodes);},replaceChildren(){this.children=[];},setAttribute(k,v){this.attrs[k]=v;},addEventListener(){}});
const dom={'#jobs-list':fake('div'),'#empty-state':fake('div'),'#job-count':fake('span'),'#nav-count':fake('span')};
const jobsState={jobs:[
  {id:'a',state:'cancelled',error:'任务已取消。',quality:'720p',container:'mp4',title:'A',platform:'YouTube'},
  {id:'b',state:'error',error:'解析失败',error_code:'EXTRACTION_FAILED',quality:'1080p',container:'mp4',title:'B',platform:'YouTube'},
  {id:'c',state:'ready',quality:'480p',container:'mp4',title:'C',platform:'YouTube',actual:{filesize:10,has_audio:true}},
  {id:'d',state:'downloading',quality:'480p',container:'mp4',title:'D',platform:'YouTube',eta:120,eta_scope:'track'},
  {id:'e',state:'paused',quality:'480p',container:'mp4',title:'E',platform:'YouTube'},
  {id:'f',state:'downloading',quality:'480p',container:'mp4',title:'F',platform:'YouTube',eta:null},
  {id:'g',state:'downloading',quality:'480p',container:'mp4',title:'G',platform:'YouTube',eta:90,eta_scope:'download'}]};
const jobsContext=vm.createContext({state:jobsState,t,el:fake,icon:()=>fake('svg'),$:s=>dom[s],setImage(){},platformLabel:n=>n,
  formatBytes:v=>v+' B',timeLabel:v=>v+'s',audioLabel:()=>'audio',api(){},refreshJobs(){},toast(){},saveFile(){}});
vm.runInContext(jobsCode+'\nrenderJobs();',jobsContext);
const texts=(node,cls)=>node.children.flatMap(c=>(c.className===cls?[c.textContent]:[]).concat(texts(c,cls)));
assert.deepEqual(texts(dom['#jobs-list'],'job-error'),['Download cancelled.',
  'Analysis or download failed. Check that the video is publicly accessible and update the extractor, then try again.']);
assert.deepEqual(texts(dom['#jobs-list'],'job-status'),['Cancelled','Ready to save','Downloading','Paused','Downloading','Downloading']);
assert.deepEqual(texts(dom['#jobs-list'],'job-status error'),['Failed']);
assert.deepEqual(texts(dom['#jobs-list'],'job-detail'),['Current track: about 120s left','Progress saved. Resume when ready.','Estimating remaining time…','About 90s left']);
assert.deepEqual(texts(dom['#jobs-list'],'subtle-button'),['Resume','Pause','Resume','Pause','Pause']);
console.log('PASS: syntax; API timeout; logout race; audio labels; QR lifecycle; job cards; ETA scope and unknown ETA; pause/resume availability');
