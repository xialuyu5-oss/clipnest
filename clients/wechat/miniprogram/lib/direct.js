/* SPDX-License-Identifier: MIT. The Mini Program never calls a parsing server. */
'use strict';
const {inspect}=require('./mp4');
function problem(code) { return Object.assign(new Error(code), {code}); }
function mediaUrl(input) {
  const text=String(input||'').trim();
  if(text.length>4096 || /[\u0000-\u0020\\]/.test(text))throw problem('INVALID_URL');
  const m=/^https:\/\/([a-z0-9.-]+)(\/[^#]*)$/i.exec(text);
  if(!m || !m[1].includes('.') || /^\d+\.\d+\.\d+\.\d+$/.test(m[1]) || /(?:^|\.)(localhost|local|internal)$/.test(m[1]))throw problem('HTTPS_REQUIRED');
  if(!/\.mp4(?:\?|$)/i.test(m[2]))throw problem('DIRECT_MP4_REQUIRED');
  return text;
}
function headers(raw) { const h={};Object.keys(raw||{}).forEach(k=>{h[k.toLowerCase()]=String(raw[k]);});return h; }
function request(wx,options,observe) {
  return new Promise((resolve,reject)=>{
    const task=wx.request({...options,success:resolve,fail:e=>reject(problem(e.errMsg||'NETWORK_ERROR'))});
    if(observe)observe(task);
  });
}
async function analyze(wx,input) {
  const url=mediaUrl(input);
  let h={};
  try {
    const response=await request(wx,{url,method:'HEAD',timeout:15000});
    if(response.statusCode>=200&&response.statusCode<300)h=headers(response.header);
  } catch { /* Some valid source servers do not implement HEAD. */ }
  const size=Number(h['content-length'])>0?Number(h['content-length']):null;
  const identity=(h.etag&&!h.etag.startsWith('W/'))||h['last-modified'];
  const ranges=h['accept-ranges']==='bytes'&&size!==null&&!!identity;
  let metadata={};
  if(ranges)try{metadata=await probe(wx,url,size);}catch{ /* Metadata is optional; download stays available. */ }
  if(metadata.has_drm)throw problem('DRM_PROTECTED');
  const title=decodeURIComponent(url.split('?')[0].split('/').pop()).slice(0,200);
  return {id:'direct-'+Date.now(),url,title,platform:'Direct MP4',duration:metadata.duration||null,is_demo:false,
    etag:h.etag||null,lastModified:h['last-modified']||null,ranges,
    options:[{id:'original',label:metadata.source_height?Math.min(metadata.width,metadata.source_height)+'p':'Original',container:'mp4',filesize:size,approximate:false,
      has_audio:null,needs_merge:false,codec:'unknown',fps:null,...metadata}]};
}
async function probe(wx,url,size){
  async function range(start,end){
    const response=await request(wx,{url,header:{Range:`bytes=${start}-${end}`},method:'GET',responseType:'arraybuffer',timeout:15000},task=>{
      if(task.onHeadersReceived)task.onHeadersReceived(r=>{if(r.statusCode&&r.statusCode!==206)task.abort();});
      else task.abort();
    });
    const h=headers(response.header),expected=`bytes ${start}-${end}/${size}`;
    if(response.statusCode!==206||h['content-range']!==expected||response.data.byteLength!==end-start+1)throw problem('METADATA_UNAVAILABLE');
    return response.data;
  }
  // Read atom headers and skip media payload. The metadata sampling budget does
  // not limit downloadable file size; large/absent metadata remains unknown.
  let offset=0;
  for(let atoms=0;atoms<32&&offset+8<=size;atoms++){
    const header=await range(offset,Math.min(size-1,offset+15)),v=new DataView(header);
    let atomSize=v.getUint32(0,false);const type=String.fromCharCode(v.getUint8(4),v.getUint8(5),v.getUint8(6),v.getUint8(7));
    if(atomSize===1){if(v.byteLength<16)return {};atomSize=v.getUint32(8,false)*4294967296+v.getUint32(12,false);}
    if(!Number.isSafeInteger(atomSize)||atomSize<8||offset+atomSize>size)return {};
    if(type==='moov')return atomSize<=4*1024*1024?inspect(await range(offset,offset+atomSize-1)):{};
    offset+=atomSize;
  }return {};
}
module.exports={analyze,mediaUrl,headers,request,problem,probe};
