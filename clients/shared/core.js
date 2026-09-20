/* SPDX-License-Identifier: MIT
 * Portable domain functions. No DOM, wx, Android or iOS dependencies.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ClipNestCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const platforms = {
    YouTube: ['youtube.com', 'youtu.be'], 'X / Twitter': ['x.com', 'twitter.com'],
    TikTok: ['tiktok.com'], Instagram: ['instagram.com'], Facebook: ['facebook.com', 'fb.watch'],
    Vimeo: ['vimeo.com'], Bilibili: ['bilibili.com', 'b23.tv'],
    Dailymotion: ['dailymotion.com', 'dai.ly'], Reddit: ['reddit.com', 'redd.it'], Twitch: ['twitch.tv'],
    Douyin: ['douyin.com', 'iesdouyin.com'], Xiaohongshu: ['xiaohongshu.com', 'xhslink.com'],
    Weibo: ['weibo.com', 'weibo.cn', 't.cn'], Ixigua: ['ixigua.com'],
    AcFun: ['acfun.cn'], Xinpianchang: ['xinpianchang.com'], TED: ['ted.com'],
    Pinterest: ['pinterest.com', 'pinterest.jp', 'pinterest.co.uk', 'pinterest.ca',
      'pinterest.de', 'pinterest.fr', 'pinterest.com.au', 'pin.it'],
    Niconico: ['nicovideo.jp', 'nico.ms'],
  };
  function fail(code) { const error = new Error(code); error.code = code; throw error; }
  function number(value) { const n = Number(value); return Number.isFinite(n) && n > 0 ? n : 0; }
  function validateLink(input) {
    if (typeof input !== 'string' || input.length > 4096) fail('INVALID_REQUEST');
    const links = input.trim().match(/https?:\/\/[^\s<>"\u3000]+/gi) || [];
    if (links.length !== 1) fail('INVALID_REQUEST');
    const link = links[0].replace(/[。，、！；）)\]}〉》']+$/, '');
    // URL is deliberately not required: some Mini Program JS engines lack it.
    const match = /^(https?):\/\/([a-z0-9.-]+)(?::(80|443))?(\/[^\s\\#]*)?(?:#.*)?$/i.exec(link);
    if (!match || !match[4] || match[4] === '/' || /[\u0000-\u001f]/.test(link)) fail('INVALID_REQUEST');
    const host = match[2].toLowerCase().replace(/\.$/, '');
    const platform = Object.keys(platforms).find(p => platforms[p].some(d => host === d || host.endsWith('.' + d)));
    if (!platform) fail('UNSUPPORTED_SITE');
    if (platform === 'YouTube' && /^\/(playlist|feed|results)(?:[/?]|$)/.test(match[4])) fail('PLAYLIST_NOT_SUPPORTED');
    return {url: 'https://' + host + match[4], platform};
  }
  function sizeOf(format, duration) {
    if (number(format.filesize)) return {bytes: number(format.filesize), approximate: false};
    const bytes = number(format.filesize_approx) || number(format.tbr) * 125 * number(duration);
    return {bytes: bytes || null, approximate: true};
  }
  function formatId(format) {
    const id = String(format.format_id || '');
    return /^[a-z0-9_.:-]{1,120}$/i.test(id) ? id : null;
  }
  function buildMedia(info, originalUrl) {
    if (info.entries || ['playlist', 'multi_video'].includes(info._type)) fail('PLAYLIST_NOT_SUPPORTED');
    if (info.is_live || ['is_live', 'is_upcoming'].includes(info.live_status)) fail('LIVE_NOT_SUPPORTED');
    if (info.has_drm) fail('DRM_PROTECTED');
    const source = validateLink(originalUrl);
    const formats = (info.formats || (info.url ? [info] : [])).filter(f =>
      !f.has_drm && /^https?:\/\//i.test(f.url || '') && formatId(f) &&
      ['http', 'https', 'm3u8_native', 'm3u8', 'http_dash_segments'].includes(f.protocol || 'https'));
    const audios = formats.filter(f => f.vcodec === 'none' && f.acodec && f.acodec !== 'none');
    const best = new Map();
    for (const video of formats) {
      const w = number(video.width), h = number(video.height), height = Math.min(w || h, h || w);
      if (!height || video.vcodec === 'none' || !['mp4', 'webm', 'mkv', 'mov', 'm4v'].includes(video.ext)) continue;
      let container = video.ext, audio = null;
      let hasAudio = video.acodec ? video.acodec !== 'none' : null;
      if (hasAudio === false && audios.length) {
        const preferred = audios.filter(a => container === 'mp4' ? ['m4a', 'mp4'].includes(a.ext) : container === 'webm' ? ['webm', 'opus'].includes(a.ext) : true);
        audio = (preferred.length ? preferred : audios).slice().sort((a,b) =>
          number(b.language_preference) - number(a.language_preference) || number(b.quality) - number(a.quality) || number(b.abr || b.tbr) - number(a.abr || a.tbr))[0];
        hasAudio = true;
        if (!((container === 'mp4' && ['m4a', 'mp4'].includes(audio.ext)) || (container === 'webm' && ['webm', 'opus'].includes(audio.ext)))) container = 'mkv';
      }
      const vSize = sizeOf(video, info.duration), aSize = audio ? sizeOf(audio, info.duration) : null;
      const selector = formatId(video) + (audio ? '+' + formatId(audio) : '');
      const item = {id: selector, label: height + 'p', height, width: w, source_height: h,
        fps: number(video.fps) || null, codec: String(video.vcodec || 'unknown').split('.')[0],
        audio_codec: hasAudio ? (audio || video).acodec || null : null,
        container, has_audio: hasAudio, needs_merge: !!audio,
        filesize: aSize ? (vSize.bytes && aSize.bytes ? vSize.bytes + aSize.bytes : null) : vSize.bytes,
        approximate: vSize.approximate || !!aSize?.approximate,
        _score: [number(video.quality), number(video.fps), number(video.tbr)]};
      const key = [height, container, hasAudio].join('/'), previous = best.get(key);
      if (!previous || item._score.some((v, i) => v > previous._score[i] && item._score.slice(0, i).every((n,j) => n === previous._score[j]))) best.set(key, item);
    }
    const order = value => value === true ? 0 : value === null ? 1 : 2;
    const options = [...best.values()].sort((a,b) => b.height - a.height || order(a.has_audio) - order(b.has_audio) || (a.container !== 'mp4') - (b.container !== 'mp4') || number(b.fps) - number(a.fps));
    options.forEach(o => delete o._score);
    if (!options.length) fail('NO_FORMATS');
    return {title: String(info.title || 'Untitled video').slice(0,240),
      uploader: String(info.uploader || info.channel || source.platform).slice(0,120),
      duration: number(info.duration) || null, platform: source.platform, url: source.url,
      options: options.slice(0,24), is_demo: false};
  }
  function actions(state) {
    return {pause: ['queued','downloading'].includes(state), resume: ['paused','error'].includes(state),
      remove: ['queued','downloading','paused','processing','ready','error'].includes(state), save: state === 'ready'};
  }
  function estimate(bytes, speed) {
    return number(bytes) && number(speed) ? Math.ceil(number(bytes) / number(speed)) : null;
  }
  function confirmation(media, option) {
    return {duration: number(media.duration) || null, bytes: number(option.filesize) || null,
      secondsMin: estimate(option.filesize, 10000000), secondsMax: estimate(option.filesize, 1000000),
      referenceOnly: true, needsMerge: !!option.needs_merge};
  }
  function duration(seconds) {
    if (seconds == null || !Number.isFinite(Number(seconds))) return '—';
    const n = Math.max(0, Math.round(Number(seconds)));
    return (n >= 3600 ? Math.floor(n/3600) + ':' : '') + String(Math.floor(n/60)%60).padStart(n >= 3600 ? 2 : 1,'0') + ':' + String(n%60).padStart(2,'0');
  }
  function bytes(n) {
    if (!number(n)) return '—';
    const power = Math.min(3, Math.floor(Math.log(number(n))/Math.log(1024)));
    return (number(n)/1024**power).toFixed(power ? 1 : 0) + ' ' + ['B','KB','MB','GB'][power];
  }
  return {schemaVersion: 1, platforms, validateLink, buildMedia, actions, confirmation, estimate, duration, bytes};
});
