/* SPDX-License-Identifier: MIT. Read MP4 metadata without decoding or merging. */
'use strict';
function inspect(buffer) {
  const data=new DataView(buffer), length=data.byteLength;
  const u32=p=>data.getUint32(p,false);
  const u64=p=>u32(p)*4294967296+u32(p+4);
  const text=p=>String.fromCharCode(data.getUint8(p),data.getUint8(p+1),data.getUint8(p+2),data.getUint8(p+3));
  function boxes(start,end){
    const result=[];
    for(let p=start;p+8<=end;){
      let size=u32(p),header=8;if(size===1){if(p+16>end)break;size=u64(p+8);header=16;}if(size===0)size=end-p;
      if(size<header||!Number.isSafeInteger(size)||p+size>end)break;
      result.push({type:text(p+4),start:p+header,end:p+size});p+=size;
    }return result;
  }
  const find=(items,type)=>items.find(b=>b.type===type);
  const children=b=>b?boxes(b.start,b.end):[];
  function timing(box){
    if(!box)return {};
    const version=data.getUint8(box.start),offset=version===1?20:12;
    if(box.start+offset+(version===1?12:8)>box.end)return {};
    const scale=u32(box.start+offset),ticks=version===1?u64(box.start+offset+4):u32(box.start+offset+4);
    return {scale,duration:scale&&ticks?ticks/scale:null};
  }
  const moov=find(boxes(0,length),'moov');if(!moov)return {};
  const movie=children(moov), result={duration:timing(find(movie,'mvhd')).duration||null,has_audio:false};
  for(const track of movie.filter(b=>b.type==='trak')){
    const fields=children(track),mdia=children(find(fields,'mdia')),handler=find(mdia,'hdlr');
    if(!handler||handler.start+12>handler.end)continue;
    const type=text(handler.start+8),timingInfo=timing(find(mdia,'mdhd'));
    const stbl=children(find(children(find(mdia,'minf')),'stbl')),stsd=find(stbl,'stsd');
    const codec=stsd&&stsd.start+16<=stsd.end?text(stsd.start+12):null;
    if(codec==='encv'||codec==='enca')result.has_drm=true;
    if(type==='soun'){result.has_audio=true;result.audio_codec=codec;}
    if(type==='vide'){
      result.codec=codec;const tkhd=find(fields,'tkhd');
      if(tkhd&&tkhd.end-tkhd.start>=8){result.width=u32(tkhd.end-8)/65536;result.source_height=u32(tkhd.end-4)/65536;}
      const stts=find(stbl,'stts');let count=0,ticks=0;
      if(stts&&stts.start+8<=stts.end){
        const entries=u32(stts.start+4);
        if(entries<=(stts.end-stts.start-8)/8)for(let i=0;i<entries;i++){
          const p=stts.start+8+i*8,n=u32(p),delta=u32(p+4);count+=n;ticks+=n*delta;
        }
      }
      if(ticks&&timingInfo.scale)result.fps=Math.round(count*timingInfo.scale/ticks*100)/100;
    }
  }
  return result;
}
module.exports={inspect};
