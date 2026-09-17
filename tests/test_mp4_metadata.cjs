const assert=require('node:assert/strict');
const fs=require('node:fs');
const {inspect}=require('../clients/wechat/miniprogram/lib/mp4');
for(const height of [480,720,1080]){
  const bytes=fs.readFileSync(`web/assets/demo-${height}.mp4`);
  const info=inspect(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
  assert.equal(info.source_height,height);assert.equal(info.fps,24);
  assert.equal(info.has_audio,true);assert.equal(info.codec,'avc1');assert.equal(info.audio_codec,'mp4a');
  assert(Math.abs(info.duration-6)<.1);
}
assert.deepEqual(inspect(new ArrayBuffer(3)),{});
assert.deepEqual(inspect(new Uint8Array([255,255,255,255,109,111,111,118]).buffer),{});
console.log('On-device MP4 metadata: actual 480p/720p/1080p fixtures, duration, 24 fps, AVC/AAC and malformed input passed.');
