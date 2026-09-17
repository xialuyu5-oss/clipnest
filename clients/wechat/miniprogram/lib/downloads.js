/* SPDX-License-Identifier: MIT */
'use strict';
const {mediaUrl,headers,request,problem}=require('./direct');
const CHUNK=1024*1024; // Memory/transfer chunk size, never a file-size limit.
const KEY='clipnest_device_jobs_v1';
class DownloadStore {
  constructor(wx) {
    this.wx=wx;this.fs=wx.getFileSystemManager();this.jobs=[];this.active=null;this.listeners=new Set();
    const saved=wx.getStorageSync(KEY);
    for(const record of Array.isArray(saved)?saved:[]) {
      if(!/^cn-[a-z0-9-]+$/.test(record.id))continue;
      const job={...record,path:this.path(record.id),task:null,intent:null,runner:null,exporting:false,transferred:0};
      if(['queued','downloading','processing'].includes(job.state))job.state='paused';
      try{const size=this.fs.statSync(job.path).size;if(size!==job.downloaded&&(job.ranges||job.state==='ready')){job.state='error';job.error_code='CHECKPOINT_MISMATCH';}}
      catch{if(job.downloaded||job.state==='ready'){job.state='error';job.error_code='FILE_MISSING';}}
      this.jobs.push(job);
    }
    this.persist();
  }
  path(id){if(!/^cn-[a-z0-9-]+$/.test(id))throw problem('INVALID_TASK');return this.wx.env.USER_DATA_PATH+'/'+id+'.mp4';}
  on(listener){this.listeners.add(listener);return()=>this.listeners.delete(listener);}
  public(job){const {task,intent,runner,exporting,...record}=job;return record;}
  changed(){this.listeners.forEach(fn=>fn(this.list()));}
  list(){return this.jobs.map(j=>this.public(j));}
  persist(){this.wx.setStorageSync(KEY,this.list());this.changed();}
  get(id){const job=this.jobs.find(j=>j.id===id);if(!job)throw problem('NOT_FOUND');return job;}
  start(media,option,consent) {
    if(!consent.rights_confirmed||!consent.download_confirmed)throw problem('CONSENT_REQUIRED');
    mediaUrl(media.url);if(option.id!=='original')throw problem('INVALID_FORMAT');
    const id='cn-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,10);
    const job={id,path:this.path(id),url:media.url,title:media.title,quality:'Original',container:'mp4',
      state:'queued',downloaded:0,total:option.filesize,progress:0,speed:null,eta:null,
      etag:media.etag,lastModified:media.lastModified,ranges:media.ranges,
      created_at:Date.now(),task:null,intent:null,runner:null,exporting:false,transferred:0};
    this.jobs.unshift(job);this.persist();this.pump();return this.public(job);
  }
  pump(){
    if(this.active)return;
    const job=this.jobs.find(j=>j.state==='queued');if(!job)return;
    this.active=job;job.intent=null;job.state='downloading';job.error_code=null;this.persist();
    job.runner=this.run(job).then(()=>{if(!job.intent){job.state='ready';job.progress=100;job.eta=null;}})
      .catch(e=>{if(!job.intent){job.state='error';job.error_code=e.code||e.errMsg||'DOWNLOAD_FAILED';job.eta=null;}})
      .finally(()=>{job.task=null;if(job.intent)job.state='paused';this.active=null;this.persist();this.pump();});
  }
  async run(job){
    if(!job.ranges){await this.whole(job);return;}
    // Revalidate identity before resuming a saved prefix.
    if(job.downloaded){
      const response=await request(this.wx,{url:job.url,method:'HEAD',timeout:15000},task=>{job.task=task;});
      const h=headers(response.header);
      if(response.statusCode!==200 || Number(h['content-length'])!==job.total ||
        (job.etag&&h.etag!==job.etag) || (job.lastModified&&h['last-modified']!==job.lastModified))throw problem('SOURCE_CHANGED');
    }
    if(job.intent)return;
    if(!job.downloaded)this.fs.writeFileSync(job.path,new ArrayBuffer(0));
    if(this.fs.statSync(job.path).size!==job.downloaded)throw problem('CHECKPOINT_MISMATCH');
    const started=Date.now(),initial=job.downloaded;
    while(job.downloaded<job.total&&!job.intent){
      const start=job.downloaded,end=Math.min(job.total-1,start+CHUNK-1);
      const header={Range:`bytes=${start}-${end}`};
      if(job.etag&&!job.etag.startsWith('W/'))header['If-Range']=job.etag;
      else if(job.lastModified)header['If-Range']=job.lastModified;
      const response=await request(this.wx,{url:job.url,method:'GET',header,responseType:'arraybuffer',timeout:60000},task=>{
        job.task=task;
        if(task.onHeadersReceived)task.onHeadersReceived(r=>{if(r.statusCode&&r.statusCode!==206)task.abort();});
        else task.abort();
      });
      if(job.intent)return;
      const h=headers(response.header),range=/^bytes (\d+)-(\d+)\/(\d+)$/.exec(h['content-range']||'');
      if(response.statusCode!==206||!range||Number(range[1])!==start||Number(range[2])!==end||Number(range[3])!==job.total||response.data.byteLength!==end-start+1|| (job.etag&&h.etag&&h.etag!==job.etag))throw problem('SOURCE_CHANGED');
      this.fs.appendFileSync(job.path,response.data);
      job.downloaded=end+1;job.speed=(job.downloaded-initial)/Math.max(.1,(Date.now()-started)/1000);
      job.eta=Math.ceil((job.total-job.downloaded)/job.speed);job.progress=Math.floor(job.downloaded/job.total*100);this.persist();
    }
  }
  whole(job){
    if(job.downloaded)throw problem('RESUME_UNAVAILABLE');
    return new Promise((resolve,reject)=>{
      const started=Date.now();
      job.task=this.wx.downloadFile({url:job.url,filePath:job.path,timeout:600000,
        success:r=>{
          if(r.statusCode!==200){reject(problem('DOWNLOAD_FAILED'));return;}
          try{
            const received=r.filePath||r.tempFilePath;
            if(job.intent){resolve();return;}
            if(received!==job.path){this.fs.copyFileSync(received,job.path);this.fs.unlinkSync(received);}
            job.downloaded=this.fs.statSync(job.path).size;job.total=job.downloaded;
            if(!job.downloaded)throw problem('EMPTY_FILE');resolve();
          }catch(e){reject(e);}
        },fail:e=>reject(problem(e.errMsg||'NETWORK_ERROR'))});
      job.task.onProgressUpdate(r=>{
        job.progress=r.progress;job.total=r.totalBytesExpectedToWrite||null;job.transferred=r.totalBytesWritten;
        // The native API's temporary partial file is not a resumable checkpoint.
        job.speed=r.totalBytesWritten/Math.max(.1,(Date.now()-started)/1000);
        job.eta=job.total?Math.ceil((job.total-r.totalBytesWritten)/job.speed):null;this.changed();
      });
    });
  }
  async pause(id){
    const job=this.get(id);
    if(!['queued','downloading','paused'].includes(job.state))throw problem('JOB_NOT_PAUSABLE');
    job.intent='pause';if(job.task)job.task.abort();
    if(job.runner)await job.runner;job.state='paused';job.eta=null;job.speed=null;this.persist();
  }
  async resume(id){
    const job=this.get(id);if(!['paused','error'].includes(job.state))throw problem('JOB_NOT_RESUMABLE');
    if(['SOURCE_CHANGED','CHECKPOINT_MISMATCH','FILE_MISSING'].includes(job.error_code))throw problem(job.error_code);
    if(!job.ranges){
      let exists=false;try{this.fs.accessSync(job.path);exists=true;}catch{}
      if(exists)this.fs.unlinkSync(job.path);
      job.downloaded=0;job.transferred=0;job.progress=0;
    }
    job.intent=null;job.state='queued';job.error_code=null;this.persist();this.pump();
  }
  async remove(id){
    const job=this.get(id);if(job.exporting)throw problem('FILE_IN_USE');job.intent='remove';if(job.task)job.task.abort();if(job.runner)await job.runner;
    let exists=false;try{this.fs.accessSync(job.path);exists=true;}catch{}
    if(exists)this.fs.unlinkSync(job.path); // Leave the task visible if deletion fails.
    this.jobs=this.jobs.filter(j=>j.id!==id);this.persist();
  }
  async save(id){
    const job=this.get(id);if(job.state!=='ready')throw problem('FILE_NOT_READY');
    if(job.exporting||job.intent)throw problem('FILE_IN_USE');job.exporting=true;
    try{await new Promise((resolve,reject)=>this.wx.saveVideoToPhotosAlbum({filePath:job.path,success:resolve,fail:reject}));}
    finally{job.exporting=false;}
  }
  pauseAll(){for(const job of this.jobs)if(['queued','downloading'].includes(job.state))this.pause(job.id).catch(()=>{});}
}
module.exports={DownloadStore,CHUNK};
