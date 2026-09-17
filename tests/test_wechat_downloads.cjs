const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const http=require('node:http');
const {DownloadStore,CHUNK}=require('../clients/wechat/miniprogram/lib/downloads');
const {analyze,mediaUrl}=require('../clients/wechat/miniprogram/lib/direct');
let bytes=Buffer.alloc(CHUNK*3+177,42);const ranges=[];
let changed=false, ignoreRange=false;
const server=http.createServer((req,res)=>{
  const etag=changed?'"v2"':'"v1"';
  if(req.method==='HEAD'){res.writeHead(200,{'content-length':bytes.length,'accept-ranges':'bytes',etag});res.end();return;}
  const m=/bytes=(\d+)-(\d+)/.exec(req.headers.range||'');
  if(m&&!ignoreRange){const start=+m[1],end=+m[2];ranges.push(start);res.writeHead(206,{'content-range':`bytes ${start}-${end}/${bytes.length}`,etag});setTimeout(()=>res.end(bytes.subarray(start,end+1)),25);}
  else {res.writeHead(200,{'content-length':bytes.length,etag});res.end(bytes);}
});
function platform(root,port,storage){return {
  env:{USER_DATA_PATH:root},getStorageSync:k=>storage[k],setStorageSync:(k,v)=>storage[k]=JSON.parse(JSON.stringify(v)),
  getFileSystemManager:()=>({statSync:fs.statSync,accessSync:fs.accessSync,unlinkSync:fs.unlinkSync,copyFileSync:fs.copyFileSync,
    writeFileSync:(p,d)=>fs.writeFileSync(p,Buffer.from(d)),appendFileSync:(p,d)=>fs.appendFileSync(p,Buffer.from(d))}),
  downloadFile(options){
    let progress=()=>{},cancelled=false,count=0;fs.writeFileSync(options.filePath,Buffer.alloc(0));
    const timer=setInterval(()=>{
      if(cancelled)return;
      const next=Math.min(bytes.length,count+65536);fs.appendFileSync(options.filePath,bytes.subarray(count,next));count=next;
      progress({progress:Math.floor(count/bytes.length*100),totalBytesWritten:count,totalBytesExpectedToWrite:bytes.length});
      if(count===bytes.length){clearInterval(timer);options.success({statusCode:200,filePath:options.filePath});}
    },2);
    return {onProgressUpdate:fn=>progress=fn,abort:()=>{cancelled=true;clearInterval(timer);options.fail({errMsg:'request:fail abort'});}};
  },
  saveVideoToPhotosAlbum(options){setTimeout(options.success,20);},
  request(options){
    const ctrl=new AbortController();let observe=()=>{};
    fetch(`http://127.0.0.1:${port}/fixture.mp4`,{method:options.method,headers:options.header,signal:ctrl.signal}).then(async r=>{
      const header=Object.fromEntries(r.headers);observe({statusCode:r.status,header});
      const data=await r.arrayBuffer();options.success({statusCode:r.status,header,data});
    }).catch(e=>options.fail({errMsg:e.message}));
    return {abort:()=>ctrl.abort(),onHeadersReceived:fn=>observe=fn};
  }
};}
const wait=async predicate=>{for(let i=0;i<500;i++){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw Error('Wait timed out');};
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'clipnest-mini-test-')), storage={},wx=platform(root,server.address().port,storage);
  try {
    for(const input of ['http://media.example/v.mp4','https://127.0.0.1/v.mp4','https://user@host.example/v.mp4','https://youtu.be/abc'])assert.throws(()=>mediaUrl(input));
    const media=await analyze(wx,'https://media.example/fixture.mp4');assert.equal(media.ranges,true);
    let store=new DownloadStore(wx);assert.throws(()=>store.start(media,media.options[0],{}),/CONSENT/);
    const task=store.start(media,media.options[0],{rights_confirmed:true,download_confirmed:true});
    await wait(()=>store.get(task.id).downloaded>=CHUNK);
    await store.pause(task.id);const checkpoint=store.get(task.id).downloaded;assert(checkpoint>0&&checkpoint<bytes.length);
    assert.equal(fs.statSync(task.path).size,checkpoint);
    store=new DownloadStore(wx);assert.equal(store.get(task.id).state,'paused');
    ranges.length=0;await store.resume(task.id);await wait(()=>store.get(task.id).state==='ready');
    assert.equal(ranges[0],checkpoint);assert.deepEqual(fs.readFileSync(task.path),bytes);
    await store.remove(task.id);assert.equal(fs.existsSync(task.path),false);assert.equal(store.list().length,0);
    const other=store.start(media,media.options[0],{rights_confirmed:true,download_confirmed:true});
    await wait(()=>store.get(other.id).downloaded>=CHUNK);await store.pause(other.id);changed=true;
    await store.resume(other.id);await wait(()=>store.get(other.id).state==='error');assert.equal(store.get(other.id).error_code,'SOURCE_CHANGED');
    await store.remove(other.id);changed=false;
    ignoreRange=true;const broken=store.start(media,media.options[0],{rights_confirmed:true,download_confirmed:true});
    await wait(()=>store.get(broken.id).state==='error');assert.equal(store.get(broken.id).downloaded,0);await store.remove(broken.id);
    ignoreRange=false;const cancelled=store.start(media,media.options[0],{rights_confirmed:true,download_confirmed:true});
    await wait(()=>store.get(cancelled.id).downloaded>=CHUNK);await store.remove(cancelled.id);assert.equal(fs.existsSync(cancelled.path),false);
    const full={...media,ranges:false};const fallback=store.start(full,full.options[0],{rights_confirmed:true,download_confirmed:true});
    await wait(()=>store.get(fallback.id).transferred>0);await store.pause(fallback.id);assert(fs.statSync(fallback.path).size>0);
    store=new DownloadStore(wx);assert.equal(store.get(fallback.id).state,'paused');
    await store.resume(fallback.id);await wait(()=>store.get(fallback.id).state==='ready');assert.deepEqual(fs.readFileSync(fallback.path),bytes);
    const saved=store.save(fallback.id);await assert.rejects(store.remove(fallback.id),/FILE_IN_USE/);await saved;await store.remove(fallback.id);
    const cancelFull=store.start(full,full.options[0],{rights_confirmed:true,download_confirmed:true});await wait(()=>store.get(cancelFull.id).transferred>0);
    await store.remove(cancelFull.id);assert.equal(fs.existsSync(cancelFull.path),false);
    bytes=fs.readFileSync(path.join(__dirname,'../web/assets/demo-480.mp4'));
    const probed=await analyze(wx,'https://media.example/fixture.mp4');assert.equal(probed.options[0].fps,24);assert.equal(probed.options[0].width,854);assert.equal(probed.options[0].audio_codec,'mp4a');
    console.log('Mini Program adapter: HTTP metadata/Range, exact bytes, pause/reload/resume, changed source, ignored Range, full-file restart/cancel and album-save lease passed.');
  }finally{server.close();assert.equal(path.dirname(path.resolve(root)),path.resolve(os.tmpdir()));assert(path.basename(root).startsWith('clipnest-mini-test-'));fs.rmSync(root,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
