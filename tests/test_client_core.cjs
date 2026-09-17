const assert = require('node:assert/strict');
const core = require('../clients/shared/core.js');
assert.equal(core.validateLink('watch https://www.youtube.com/watch?v=abc').platform, 'YouTube');
for (const u of ['https://youtube.com.evil.test/watch?v=a','https://evil@youtube.com/watch?v=a', 'https://youtube.com:123/watch?v=a','https://127.0.0.1/video','https://youtube.com\\@evil.test/a']) {
  assert.throws(() => core.validateLink(u));
}
assert.throws(() => core.validateLink('https://youtube.com/playlist?list=a'), /PLAYLIST/);
const info = {title:'Portrait',duration:10,formats:[
  {format_id:'v',url:'https://cdn.example/v',width:1080,height:1920,ext:'mp4',vcodec:'avc1',acodec:'none',filesize:1000,fps:30},
  {format_id:'a',url:'https://cdn.example/a',ext:'m4a',vcodec:'none',acodec:'mp4a',filesize:100,abr:128},
  {format_id:'evil/best',url:'https://cdn.example/e',ext:'mp4',width:9999,height:9999},
  {format_id:'drm',url:'https://cdn.example/d',ext:'mp4',height:2160,has_drm:true}
]};
let media = core.buildMedia(info,'https://vimeo.com/123');
assert.equal(media.options.length,1);
assert.deepEqual([media.options[0].label, media.options[0].id, media.options[0].filesize],['1080p','v+a',1100]);
assert.equal(media.options[0].needs_merge,true);
assert.equal(core.buildMedia({formats:[{...info.formats[0], acodec:null}]},'https://vimeo.com/123').options[0].has_audio,null);
assert.throws(() => core.buildMedia({...info, is_live:true},'https://vimeo.com/123'),/LIVE_NOT_SUPPORTED/);
assert.throws(() => core.buildMedia({...info, has_drm:true},'https://vimeo.com/123'),/DRM_PROTECTED/);
assert.equal(core.actions('processing').pause,false);
assert.equal(core.actions('paused').resume,true);
assert.equal(core.actions('ready').save,true);
assert.equal(core.confirmation(media,{filesize:null}).secondsMax,null);
assert.equal(core.estimate(2000,1000),2);
assert.equal(core.duration(3661),'1:01:01');
console.log('Shared client domain: validation, metadata, consent estimates and task controls passed.');
