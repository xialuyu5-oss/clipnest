'use strict';

(() => {
  const i18n = window.ClipNestI18n;
  const t = i18n.t;
  const $ = (selector) => document.querySelector(selector);
  const PREVIEW = Boolean(window.CLIPNEST_PREVIEW || location.protocol === 'file:');
  const state = {
    csrf: '', authenticated: false, health: null, media: null, selected: null,
    filter: 'all', jobs: [], busy: false, downloading: false, connection: null, connectError: null,
    pollTimer: null, lastJobsJSON: '', pollFailures: 0, refreshing: false,
    epoch: 0, member: null, qrFlow: null, qrTimer: null, memberEpoch: 0, qrStarting: false,
    qrExpires: 0, qrPolling: false, pendingDownload: null,
  };
  const platforms = [
    ['YouTube', 'youtube.com · youtu.be', 'youtube.png'],
    ['X / Twitter', 'x.com · twitter.com', 'x.png'],
    ['TikTok', 'tiktok.com', 'tiktok.png'],
    ['Instagram', 'instagram.com', 'instagram.webp'],
    ['Facebook', 'facebook.com · fb.watch', 'facebook.ico'],
    ['Vimeo', 'vimeo.com', 'vimeo.png'],
    ['Bilibili', 'bilibili.com · b23.tv', 'bilibili.ico'],
    ['Dailymotion', 'dailymotion.com · dai.ly', 'dailymotion.png'],
    ['Reddit', 'reddit.com · redd.it', 'reddit.png'],
    ['Twitch', 'twitch.tv', 'twitch.png'],
    ['Douyin', 'douyin.com', 'douyin.ico'],
    ['Xiaohongshu', 'xiaohongshu.com · xhslink.com', 'xiaohongshu.png'],
    ['Weibo', 'weibo.com · weibo.cn', 'weibo.ico'],
    ['Ixigua', 'ixigua.com', 'ixigua.ico'],
    ['AcFun', 'acfun.cn', 'acfun.ico'],
    ['Xinpianchang', 'xinpianchang.com', 'xinpianchang.ico'],
    ['TED', 'ted.com', 'ted.ico'],
    ['Pinterest', 'pinterest.com · pin.it', 'pinterest.png'],
    ['Niconico', 'nicovideo.jp · nico.ms', 'niconico.png'],
  ];

  function platformLabel(name) {
    return t(name === '哔哩哔哩' ? 'Bilibili' : name);
  }
  function errorMessage(code, fallback = 'The request could not be completed. Check your input and try again.') {
    const messages = {
      INVALID_REQUEST: 'Video link invalid. Use one supported video\'s original URL.',
      RATE_LIMITED: 'Too many requests. Please wait and try again.',
      SERVER_BUSY: 'The server is busy. Please try again later.',
      JOB_NOT_PAUSABLE: 'This stage cannot be paused. Wait for merging to finish or cancel the task.',
      JOB_NOT_RESUMABLE: 'Only paused or failed downloads can be resumed.',
      CLEANUP_FAILED: 'Some cached files are still in use. Try cancelling or deleting again.',
      UNAUTHORIZED: 'Session expired or access key incorrect. Reconnect and try again.',
      DISK_FULL: 'Not enough free disk space. The download stopped.',
      INVALID_FILE: 'The media file is invalid or incomplete. Please try again.',
      INVALID_MEDIA: 'The media file is invalid or incomplete. Please try again.',
      EMPTY_FILE: 'The media file is invalid or incomplete. Please try again.',
      REQUEST_TOO_LARGE: 'The request was rejected. Refresh this page and try again.',
      INVALID_BODY: 'The request was rejected. Refresh this page and try again.',
      CROSS_ORIGIN: 'The request was rejected. Refresh this page and try again.',
      CSRF_FAILED: 'The request was rejected. Refresh this page and try again.',
      // LOCAL_ONLY is raised by the middleware for every request from a non-loopback client
      // while member login is enabled, so it must explain the deployment switch, not sign-in.
      LOCAL_ONLY: 'This instance only accepts requests from this computer. For LAN, Docker or public hosting, set ENABLE_MEMBER_LOGIN=false in .env and restart the server (platform sign-in is then unavailable).',
      ACCOUNT_DISABLED: 'Platform sign-in is unavailable on this instance.',
      MISSING_DEPENDENCY: 'Required server components are missing. Complete setup and restart.',
      MISSING_FFMPEG: 'Required server components are missing. Complete setup and restart.',
      DEMO_DISABLED: 'Demo files are unavailable on this server.',
      DEMO_MISSING: 'Demo files are unavailable on this server.',
      CONSENT_REQUIRED: 'Please confirm your permission to download this video.',
      DOWNLOAD_CONFIRMATION_REQUIRED: 'Please review the details and confirm the download.',
      ANALYSIS_EXPIRED: 'Analysis expired. Analyze the link again.',
      INVALID_FORMAT: 'Invalid quality selection. Analyze the link again.',
      QUEUE_FULL: 'The download queue is full. Wait for existing tasks to finish.',
      NOT_FOUND: 'The task was not found or has expired.',
      FILE_IN_USE: 'This file is being saved. Wait before deleting it.',
      FILE_NOT_READY: 'The file is not ready yet.',
      FILE_EXPIRED: 'The file expired. Analyze the link and download again.',
      ACCOUNT_INVALID: 'Platform account expired or changed. Sign in and analyze the link again.',
      ACCOUNT_EXPIRED: 'Platform account expired or changed. Sign in and analyze the link again.',
      ACCOUNT_CHANGED: 'Platform account expired or changed. Sign in and analyze the link again.',
      ACCOUNT_MISMATCH: 'Platform account expired or changed. Sign in and analyze the link again.',
      ACCOUNT_NETWORK: 'Cannot reach the platform sign-in service. Try again later.',
      ACCOUNT_CONNECTED: 'Disconnect the current account before switching accounts.',
      ACCOUNT_RESPONSE: 'The platform returned an invalid sign-in response. Generate a new QR code.',
      LOGIN_CANCELLED: 'QR sign-in cancelled.',
      QR_EXPIRED: 'QR code expired. Generate and scan a new code.',
      SHORT_LINK_FAILED: 'Cannot resolve this short link. Paste the original video URL.',
      UNSUPPORTED_SITE: 'This platform or link is not supported.',
      UNSUPPORTED_URL: 'This platform or link is not supported.',
      NO_FORMATS: 'No downloadable formats were found. Check access and update the extractor.',
      MERGE_FAILED: 'Audio and video could not be merged. Please try again.',
      QUALITY_CHANGED: 'The returned quality changed. Analyze the link again.',
      MISSING_AUDIO: 'The downloaded file is missing the expected audio.',
      LIVE_NOT_SUPPORTED: 'Live streams and playlists are not supported. Use a single replay or video.',
      PLAYLIST_NOT_SUPPORTED: 'Live streams and playlists are not supported. Use a single replay or video.',
      DRM_PROTECTED: 'DRM-protected content cannot be downloaded.',
      AUTH_REQUIRED: 'The platform requires sign-in or permission to access this video.',
      REGION_RESTRICTED: 'This video is unavailable in the server\'s region.',
      PLATFORM_BLOCKED: 'The platform refused access. Check server connectivity and update the extractor.',
      NOT_AVAILABLE: 'This video was removed or is not available.',
      NETWORK_ERROR: 'The source platform could not be reached. Check the server\'s network connection.',
      UNSAFE_TARGET: 'The network target or proxy configuration was rejected.',
      LOCAL_PROXY_REQUIRED: 'Your VPN uses virtual DNS addresses. Restart ClipNest with its local proxy option, then try again.',
      PROXY_CONFIG: 'The network target or proxy configuration was rejected.',
      TIMEOUT: 'Processing timed out. Please try again.',
      // Catch-all codes: friendly_error() fallback, worker crash and unexpected server failure.
      EXTRACTION_FAILED: 'Analysis or download failed. Check that the video is publicly accessible and update the extractor, then try again.',
      WORKER_ERROR: 'The processing worker stopped unexpectedly. Check server components and try again.',
      SERVER_ERROR: 'The server failed to process this task. Check the server logs.',
    };
    return t(messages[code] || fallback);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-' + name);
    svg.append(use);
    return svg;
  }
  function asset(url) {
    return PREVIEW && window.CLIPNEST_ASSETS?.[url] ? window.CLIPNEST_ASSETS[url] : url;
  }
  function setImage(img, url) {
    if (!url || !(url.startsWith('/assets/') || /^https:\/\//i.test(url))) {
      img.hidden = true;
      img.removeAttribute('src');
      return;
    }
    img.hidden = false;
    img.referrerPolicy = 'no-referrer';
    img.onerror = () => { img.hidden = true; };
    img.src = asset(url);
  }
  function formatBytes(value, estimated = false) {
    if (!Number.isFinite(value) || value <= 0) return t("Size unknown");
    let size = value, unit = 'B';
    for (const label of ['KB', 'MB', 'GB']) {
      if (size < 1024) break;
      size /= 1024;
      unit = label;
    }
    const formatted = new Intl.NumberFormat(i18n.locale, {maximumFractionDigits: size >= 100 ? 0 : 1}).format(size) + ' ' + unit;
    return estimated ? t('About {size}', {size: formatted}) : formatted;
  }
  function timeLabel(value) {
    if (!Number.isFinite(value) || value < 0) return t("Duration unknown");
    const s = Math.floor(value);
    return s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
      : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }
  function toast(message, error = false, params = {}) {
    const node = el('div', 'toast' + (error ? ' error' : ''));
    node.append(icon(error ? 'info' : 'check'), el('span', '', message));
    $('#toast-region').append(node);
    i18n.text(node.querySelector('span'), i18n.key(message), params);
    // These timers only dismiss UI notifications; they do not create download work.
    setTimeout(() => node.remove(), 5500);
  }
  function showDialog(id) {
    const dialog = document.getElementById(id);
    if (!dialog) return;
    if (id === 'settings-dialog') renderSettings();
    if (id === 'accounts-dialog') refreshMember().catch(err => memberMessage(err.message, true));
    if (!dialog.open) dialog.showModal();
  }
  function apiError(message, code = 'REQUEST_FAILED') {
    const err = new Error(message);
    err.code = code;
    return err;
  }

  const previewJobs = [];
  async function previewApi(path, options = {}) {
    const method = options.method || 'GET';
    if (path === '/api/health') return {
      status: 'preview', dependencies: {}, platforms: platforms.map(p => p[0]),
      download_confirmation_required: true, file_ttl_seconds: null,
      access_key_required: false, demo_enabled: true, version: '1.3.1',
    };
    if (path === '/api/session') return { authenticated: true, csrf_token: 'preview-only' };
    if (path === '/api/analyze') throw apiError(t("Start the server to analyze real links, or try a demo in this offline preview."), 'PREVIEW_ONLY');
    if (path === '/api/demo') return {
      id: 'preview-demo-media', title: t("A little motion"), uploader: t("ClipNest original demo"),
      duration: 6, platform: t("Demo"), url: 'demo://clipnest', thumbnail: '/assets/demo-cover.svg',
      description: t("An original CC0 animation. Saving this demo does not test a platform download."),
      is_demo: true, expires_at: Date.now() / 1000 + 3600,
      options: [1080, 720, 480].map(h => ({
        id: 'demo-' + h, label: h + 'p', height: h, source_height: h, width: Math.ceil(h * 16 / 9 / 2) * 2,
        fps: 24, container: 'mp4', codec: 'h264', has_audio: true, needs_merge: false,
        filesize: window.CLIPNEST_DEMO_SIZES?.[h] || null, approximate: false, dynamic_range: 'SDR',
      })),
    };
    if (path === '/api/downloads' && method === 'GET') return { items: [...previewJobs] };
    if (path === '/api/downloads' && method === 'POST') {
      if (!options.body.rights_confirmed) throw apiError(t("Please confirm your permission to download this video."));
      if (!options.body.download_confirmed) throw apiError(t("Please review the details and confirm the download."));
      const opt = state.media?.options.find(o => o.id === options.body.option_id);
      if (!opt) throw apiError(t("Choose a demo quality."));
      const job = {
        id: 'preview-' + Date.now(), title: state.media.title, platform: t("Demo"),
        thumbnail: '/assets/demo-cover.svg', is_demo: true, quality: opt.label,
        container: 'mp4', state: 'ready', progress: 100, created_at: Date.now() / 1000,
        expires_at: null, actual: {
          filesize: opt.filesize, width: opt.width, height: opt.height, duration: 6,
          container: 'mp4', codec: 'h264', has_audio: true,
        }, file_url: '/assets/demo-' + opt.height + '.mp4',
      };
      previewJobs.unshift(job);
      return job;
    }
    if (path.startsWith('/api/downloads/') && method === 'DELETE') {
      const i = previewJobs.findIndex(j => j.id === path.split('/').pop());
      if (i >= 0) previewJobs.splice(i, 1);
      return { ok: true };
    }
    throw apiError(t("This action is unavailable in offline preview."));
  }

  async function api(path, options = {}) {
    if (PREVIEW) return previewApi(path, options);
    const headers = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (state.csrf) headers['X-CSRF-Token'] = state.csrf;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), path === '/api/analyze' ? 190000 : 30000);
    let response, data;
    const epoch = state.epoch;
    try {
      response = await fetch(path, {
        method: options.method || 'GET', headers, credentials: 'same-origin',
        signal: controller.signal,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
      try { data = await response.json(); } catch (err) {
        if (err.name === 'AbortError') throw err;
        throw apiError(t("The server returned an invalid response. Check its configuration."), 'INVALID_RESPONSE');
      }
      if (epoch !== state.epoch) throw apiError(t("The session changed. Please try again."), 'STALE_SESSION');
    } catch (err) {
      if (err.code) throw err;
      throw apiError(err.name === 'AbortError'
        ? t("The request timed out. Refresh downloads before submitting again.")
        : t("Cannot reach the server. Check that it is running and connected."), 'NETWORK_ERROR');
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      const code = data.error?.code || (response.status === 401 ? 'UNAUTHORIZED' : 'REQUEST_FAILED');
      if (code === 'UNAUTHORIZED') {
        state.epoch += 1;
        state.authenticated = false;
        state.csrf = '';
        state.jobs = []; state.media = null; state.member = null;
        state.lastJobsJSON = ''; renderJobs(); invalidateMedia(); renderMember();
        $('#access-banner').hidden = !state.health?.access_key_required;
      }
      throw apiError(errorMessage(code), code);
    }
    return data;
  }

  async function connect() {
    $('#service-text').textContent = t("Connecting");
    $('.status-dot').className = 'status-dot checking';
    try {
      const health = await api('/api/health');
      state.health = health; state.connectError = null;
      try {
        const session = await api('/api/session');
        state.csrf = session.csrf_token || '';
        state.authenticated = !!session.authenticated;
      } catch (err) {
        if (err.code !== 'UNAUTHORIZED') throw err;
      }
      updateServiceStatus();
      $('#demo-button').hidden = !health.demo_enabled;
      $('#access-banner').hidden = !(health.access_key_required && !state.authenticated);
      i18n.text($('#retention-note'), PREVIEW
        ? 'Offline preview saves demo files only. Start the server for real links.'
        : 'Pause to keep your progress. Cancel to delete cached files.');
      if (state.authenticated) await refreshJobs(false);
    } catch (err) {
      state.health = null; state.connectError = err.code || null;
      updateServiceStatus();
    }
    renderSettings();
  }
  function updateServiceStatus() {
    const h = state.health;
    let text = t("Server disconnected"), cls = 'offline';
    if (PREVIEW) { text = t("Offline preview"); cls = 'warn'; }
    else if (!h && state.connectError === 'LOCAL_ONLY') text = t("Local access only");
    else if (h) {
      if (h.access_key_required && !state.authenticated) { text = t("Access key required"); cls = 'warn'; }
      else if (!h.dependencies?.yt_dlp) { text = t("Extractor not installed"); cls = 'warn'; }
      else if (!h.dependencies?.ffmpeg || !h.dependencies?.ffprobe) { text = t("Media tools not installed"); cls = 'warn'; }
      else if (!h.dependencies?.js_runtime || !h.dependencies?.ejs) { text = t("Online · Setup incomplete"); cls = 'warn'; }
      else { text = t("Server connected"); cls = ''; }
    }
    $('#service-text').textContent = text;
    $('.status-dot').className = 'status-dot ' + cls;
  }
  function renderSettings() {
    const h = state.health;
    $('#connection-summary').replaceChildren(icon('info'));
    let summary = !h ? (state.connectError === 'LOCAL_ONLY' ? errorMessage('LOCAL_ONLY') : t("Start the server and open the local address shown at startup."))
      : PREVIEW ? t("This is an offline preview. Embedded demos can be saved; real links require the server.")
        : h.access_key_required ? (state.authenticated ? t("Connected. Downloads are visible only in this browser session.") : t("Enter the access key set by the instance administrator."))
          : t("Connected locally. Browser downloads are available. No access key is set; keep this instance private.");
    $('#connection-summary').append(el('p', '', summary));
    $('#login-form').hidden = !h?.access_key_required || state.authenticated;
    $('#logout-button').hidden = !h?.access_key_required || !state.authenticated;
    const list = $('#dependency-list');
    list.replaceChildren();
    if (!h || PREVIEW) { list.hidden = true; return; }
    list.hidden = false;
    const d = h.dependencies || {};
    const rows = [
      [t("yt-dlp extractor"), d.yt_dlp || t("Not installed"), !d.yt_dlp],
      [t("Media tools"), d.ffmpeg && d.ffprobe ? t("FFmpeg + FFprobe detected") : t("FFmpeg / FFprobe missing"), !(d.ffmpeg && d.ffprobe)],
      [t("JavaScript runtime"), d.js_runtime ? t('{runtime} detected', {runtime:d.js_runtime}) : t("Deno / Node not detected"), !d.js_runtime],
      [t("YouTube EJS component"), d.ejs || t("Missing · Install yt-dlp[default]"), !d.ejs],
      [t("Download size and duration"), t("No fixed limit; confirm each download"), false],
      [t("File retention"), t('Until you delete the task'), false],
    ];
    for (const [name, value, missing] of rows) {
      const row = el('div', 'dependency-item');
      row.append(el('span', '', name), el('strong', missing ? 'missing' : '', value));
      list.append(row);
    }
  }
  async function requireSession() {
    if (state.connection) await state.connection;
    if ((!state.authenticated || !state.csrf) && !state.health?.access_key_required) {
      state.connection = connect();
      await state.connection;
    }
    if (!state.authenticated || !state.csrf) {
      showDialog('settings-dialog');
      throw apiError(state.health?.access_key_required ? t("Enter the instance access key.") : t("Start the server and reconnect."), 'UNAUTHORIZED');
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    $('#analyze-button').disabled = busy;
    $('#demo-button').disabled = busy;
    $('#analyzing').hidden = !busy;
    const button = $('#analyze-button');
    button.replaceChildren();
    if (busy) button.append(el('span', 'spinner'), el('span', '', t("Analyzing")));
    else button.append(el('span', '', t("Analyze video")), icon('arrow'));
  }
  async function analyze(demo = false) {
    if (state.busy) return;
    const value = $('#video-url').value.trim();
    if (!demo && !value) {
      $('#video-url').focus();
      showAnalysisError(t("Paste a video link to get started."));
      return;
    }
    $('#analyze-error').hidden = true;
    try {
      setBusy(true);
      await requireSession();
      state.media = null;
      $('#result-section').hidden = true;
      const media = await api(demo ? '/api/demo' : '/api/analyze', {
        method: 'POST', ...(demo ? {} : { body: { url: value, use_account: !!(state.member?.status === 'connected' && $('#use-member').checked) } }),
      });
      state.media = media;
      state.filter = 'all';
      state.selected = media.options[0]?.id;
      $('#rights-confirmed').checked = false;
      renderMedia();
      if (demo) toast(t("Demo loaded. Choose a quality to try the download process."));
      $('#result-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      showAnalysisError(err.message);
    } finally {
      setBusy(false);
    }
  }
  function showAnalysisError(message) {
    const error = $('#analyze-error');
    i18n.text(error, i18n.key(message));
    error.hidden = false;
  }
  function renderMedia() {
    const m = state.media;
    if (!m) return;
    $('#result-section').hidden = false;
    $('#media-title').textContent = m.is_demo ? t('A little motion') : m.title;
    $('#media-platform').textContent = (m.is_demo ? t('Demo') : platformLabel(m.platform)) + (m.access_mode === 'member_session' ? ' · ' + t('Using account session') : '');
    $('#media-uploader').textContent = (m.is_demo ? t('ClipNest original demo') : m.uploader) + (m.duration ? ' · ' + timeLabel(m.duration) : '');
    $('#media-summary').textContent = m.is_demo ? t('An original CC0 animation. Saving this demo does not test a platform download.') : m.description || t("Video details loaded. Choose an available quality and format.");
    $('#media-demo-tag').hidden = !m.is_demo;
    $('#media-duration').textContent = timeLabel(m.duration);
    setImage($('#media-thumbnail'), m.thumbnail);
    const original = $('#media-original');
    original.hidden = m.is_demo || !/^https?:\/\//i.test(m.url);
    if (!original.hidden) original.href = m.url;
    else original.removeAttribute('href');
    $('#format-note').textContent = m.is_demo
      ? t("Original CC0 demo in three resolutions. Demo success does not verify source platforms.")
      : t("Original formats only. Portrait quality uses the shorter edge. Sizes may be estimates; codec support varies by player.");
    renderQualities();
  }
  function codecLabel(codec) {
    if (!codec || codec === 'unknown') return t("Codec unknown");
    // Two naming schemes reach the UI on purpose: platform metadata via yt-dlp uses
    // RFC 6381 tags (avc1 / hev1 / hvc1 / vp09 / av01), while FFprobe-measured values use
    // FFmpeg codec names (h264 / hevc / vp9 / av1 / aac). Keep both sets of keys.
    return ({h264: 'H.264', avc1: 'H.264', hevc: 'H.265', hev1: 'H.265', hvc1: 'H.265',
      vp09: 'VP9', vp9: 'VP9', av01: 'AV1', av1: 'AV1', aac: 'AAC', opus: 'Opus', mp3: 'MP3'})[codec]
      || String(codec).toUpperCase();
  }
  function audioLabel(option) {
    if (option.has_audio === true) return (option.needs_merge ? t("Audio + video merge") : t("With audio"))
      + (option.audio_codec ? ' · ' + codecLabel(option.audio_codec) : '');
    return option.has_audio === false ? t("No audio") : t("Audio unknown");
  }
  function renderQualities() {
    const m = state.media;
    if (!m) return;
    const tabs = $('#format-tabs');
    tabs.replaceChildren();
    const containers = [...new Set(m.options.map(o => o.container))];
    const available = state.filter === 'all' ? m.options : m.options.filter(o => o.container === state.filter);
    if (!available.some(o => o.id === state.selected)) state.selected = available[0]?.id;
    for (const type of ['all', ...containers]) {
      const btn = el('button', type === state.filter ? 'active' : '', type === 'all' ? t("All") : type.toUpperCase());
      btn.type = 'button';
      btn.setAttribute('aria-pressed', type === state.filter ? 'true' : 'false');
      btn.addEventListener('click', () => { state.filter = type; renderQualities(); });
      tabs.append(btn);
    }
    $('#quality-count').textContent = t('Formats: {count}', {count:available.length});
    const grid = $('#quality-options');
    grid.replaceChildren();
    const highest = Math.max(...m.options.map(o => o.height));
    for (const opt of available) {
      const label = el('label', 'quality-option');
      const radio = el('input');
      radio.type = 'radio'; radio.name = 'quality'; radio.value = opt.id; radio.checked = state.selected === opt.id;
      radio.setAttribute('aria-label', `${opt.label} ${opt.container.toUpperCase()} ${opt.fps || ''} fps ${audioLabel(opt)}`);
      radio.addEventListener('change', () => { state.selected = opt.id; renderSelected(); });
      const box = el('div', 'quality-box');
      const check = el('span', 'quality-radio'); check.append(icon('check'));
      const top = el('div', 'quality-top'); top.append(el('strong', '', opt.label));
      if (opt.height === highest) top.append(el('span', '', opt.height >= 2160 ? '4K' : opt.height >= 1080 ? 'HD' : t("Best")));
      const dimensions = opt.width && opt.source_height ? `${opt.width} × ${opt.source_height}` : opt.label;
      const tech = el('p', 'quality-tech', `${dimensions} · ${opt.fps ? opt.fps + ' fps' : t("Frame rate unknown")}`);
      const codec = el('p', 'quality-tech', `${opt.container.toUpperCase()} · ${codecLabel(opt.codec)}${opt.dynamic_range && opt.dynamic_range !== 'SDR' ? ' · ' + opt.dynamic_range : ''}`);
      const bottom = el('div', 'quality-bottom');
      bottom.append(el('span', '', audioLabel(opt)),
        el('span', '', formatBytes(opt.filesize, opt.approximate)));
      box.append(check, top, tech, codec, bottom); label.append(radio, box); grid.append(label);
    }
    renderSelected();
  }
  function renderSelected() {
    const opt = state.media?.options.find(o => o.id === state.selected);
    $('#selected-format').textContent = opt ? `${opt.label} / ${opt.container.toUpperCase()}` : '—';
    $('#selected-size').textContent = opt ? formatBytes(opt.filesize, opt.approximate) : '';
    $('#download-button').disabled = !opt || !$('#rights-confirmed').checked || state.downloading;
  }
  function confirmDownload() {
    if (state.downloading || !state.media || !state.selected) return;
    if (!$('#rights-confirmed').checked) { toast(t("Please confirm your permission to download this video."), true); return; }
    const opt = state.media.options.find(o => o.id === state.selected);
    if (!opt) return;
    state.pendingDownload = { analysis_id: state.media.id, option_id: opt.id };
    renderDownloadConfirmation();
    showDialog('download-dialog');
  }
  function renderDownloadConfirmation() {
    const opt = state.media?.options.find(o => o.id === state.pendingDownload?.option_id);
    if (!opt) return;
    $('#confirm-title').textContent = state.media.is_demo ? t('A little motion') : state.media.title;
    $('#confirm-format').textContent = `${opt.label} / ${opt.container.toUpperCase()}`;
    $('#confirm-duration').textContent = timeLabel(state.media.duration);
    $('#confirm-size').textContent = opt.filesize > 0
      ? formatBytes(opt.filesize, opt.approximate) : t("Size unavailable; the file may be large");
    $('#confirm-time').textContent = opt.filesize > 0
      ? t('{fast}–{slow} at 1–10 MB/s; reference only', {fast: timeLabel(Math.max(1, Math.ceil(opt.filesize / (10 * 1024 * 1024)))), slow: timeLabel(Math.max(1, Math.ceil(opt.filesize / (1024 * 1024))))})
      : t("Cannot estimate without the file size");
  }
  async function createDownload() {
    const selection = state.pendingDownload;
    if (state.downloading || !selection) return;
    $('#download-dialog').close();
    if (selection.analysis_id !== state.media?.id || selection.option_id !== state.selected || !$('#rights-confirmed').checked) {
      toast(t("Download options changed. Please confirm again."), true); return;
    }
    try {
      state.downloading = true; renderSelected();
      await requireSession();
      await api('/api/downloads', {
        method: 'POST', body: { ...selection, rights_confirmed: true, download_confirmed: true },
      });
      toast(PREVIEW ? t("Demo ready. Select Save file.") : t("Added to downloads. Select Save file when ready."));
      await refreshJobs(false);
      $('#downloads').scrollIntoView({ behavior: 'smooth', block: 'start' });
      schedulePoll();
    } catch (err) {
      toast(err.message, true);
    } finally {
      state.downloading = false; renderSelected();
    }
  }

  async function refreshJobs(notify = false) {
    if (!state.authenticated || state.refreshing) return;
    state.refreshing = true;
    const epoch = state.epoch;
    try {
      const data = await api('/api/downloads');
      if (epoch !== state.epoch || !state.authenticated) return;
      const previous = new Map(state.jobs.map(j => [j.id, j]));
      for (const job of data.items) {
        if (job.state === 'ready' && previous.has(job.id) && previous.get(job.id).state !== 'ready') {
          toast('{quality} is ready. Save it to your device.', false, {quality:job.quality});
        }
        if (job.state === 'error' && previous.has(job.id) && previous.get(job.id).state !== 'error') {
          toast(errorMessage(job.error_code, 'Download failed. Please analyze the link again.'), true);
        }
      }
      state.jobs = data.items;
      const json = JSON.stringify(data.items);
      if (json !== state.lastJobsJSON) {
        renderJobs();
        state.lastJobsJSON = json;
      }
      state.pollFailures = 0;
      $('#queue-error').hidden = true;
      if (notify) toast(t("Downloads refreshed."));
    } catch (err) {
      if (epoch !== state.epoch) return;
      state.pollFailures += 1;
      if (notify || state.pollFailures >= 3) {
        i18n.text($('#queue-error'), i18n.key(err.message));
        $('#queue-error').hidden = false;
      }
      if (notify) toast(err.message, true);
    } finally {
      state.refreshing = false;
    }
  }
  function schedulePoll() {
    clearTimeout(state.pollTimer);
    const active = state.jobs.some(j => ['queued', 'downloading', 'processing'].includes(j.state));
    state.pollTimer = setTimeout(async () => {
      if (!document.hidden && state.authenticated) await refreshJobs(false);
      schedulePoll();
    }, active ? 1500 : 15000);
  }
  function renderJobs() {
    const root = $('#jobs-list'); root.replaceChildren();
    $('#empty-state').hidden = state.jobs.length > 0;
    $('#job-count').textContent = state.jobs.length;
    const active = state.jobs.filter(j => ['queued', 'downloading', 'processing'].includes(j.state)).length;
    $('#nav-count').textContent = active || state.jobs.length;
    const statusNames = { queued: t("Queued"), downloading: t("Downloading"), paused: t("Paused"), processing: t("Merging / checking"), ready: t("Ready to save"), error: t("Failed"), cancelled: t("Cancelled") };
    for (const job of state.jobs) {
      const card = el('article', 'job-card');
      const thumb = el('div', 'job-thumb');
      if (job.thumbnail) {
        const img = el('img'); img.alt = ''; img.loading = 'lazy'; setImage(img, job.thumbnail); thumb.append(img);
      } else thumb.append(icon('film'));
      const body = el('div', 'job-body');
      const title = el('h3', 'job-title', job.is_demo ? t('A little motion') : job.title); title.title = title.textContent;
      const meta = el('div', 'job-meta');
      const parts = [job.is_demo ? t('Demo') : platformLabel(job.platform), `${job.quality} · ${job.container.toUpperCase()}`];
      if (job.state === 'ready' && job.actual) {
        parts.push(formatBytes(job.actual.filesize));
        if (job.actual.width && job.actual.height) parts.push(`${job.actual.width}×${job.actual.height}`);
        if (job.actual.fps) parts.push(`${job.actual.fps} fps`);
        parts.push(t('Measured: {audio}', {audio:audioLabel(job.actual)}));
      }
      if (job.speed) parts.push(formatBytes(job.speed) + '/s');
      if (job.state === 'downloading' && typeof job.progress === 'number') {
        parts.push(job.track ? t('Current track: {progress}%', {progress:Math.round(job.progress)}) : Math.round(job.progress) + '%');
      }
      parts.forEach(part => meta.append(el('span', '', part)));
      body.append(title, meta);
      if (job.state === 'downloading') {
        const remaining = Number.isFinite(job.eta) && job.eta >= 0
          ? (job.eta_scope === 'track' ? t('Current track: about {time} left', {time: timeLabel(Math.max(1, Math.ceil(job.eta)))})
            : t('About {time} left', {time: timeLabel(Math.max(1, Math.ceil(job.eta)))}))
          : t('Estimating remaining time…');
        body.append(el('p', 'job-detail', remaining));
      } else if (job.state === 'paused') {
        body.append(el('p', 'job-detail', t('Progress saved. Resume when ready.')));
      } else if (job.state === 'processing') {
        body.append(el('p', 'job-detail', t('Download complete. Merging and checking the file…')));
      }
      if (['downloading', 'processing', 'queued'].includes(job.state)) {
        const bar = el('div', 'job-progress' + (job.progress == null || job.state !== 'downloading' ? ' indeterminate' : ''));
        bar.setAttribute('role', 'progressbar');
        bar.setAttribute('aria-label', job.state === 'downloading' ? t("Current track progress") : statusNames[job.state]);
        if (typeof job.progress === 'number' && job.state === 'downloading') {
          bar.setAttribute('aria-valuenow', Math.round(job.progress));
          bar.setAttribute('aria-valuemin', '0'); bar.setAttribute('aria-valuemax', '100');
        }
        const fill = el('span');
        if (job.state === 'downloading' && job.progress != null) fill.style.width = Math.max(0, Math.min(100, job.progress)) + '%';
        bar.append(fill); body.append(bar);
      }
      // Cancelled jobs carry a note but no error code; they must not read as failures.
      if (job.state === 'cancelled') body.append(el('p', 'job-error', t("Download cancelled.")));
      else if (job.error || job.error_code) body.append(el('p', 'job-error', errorMessage(job.error_code, 'Download failed. Please analyze the link again.')));
      const actions = el('div', 'job-actions');
      actions.append(el('span', 'job-status' + (job.state === 'error' ? ' error' : ''), statusNames[job.state] || job.state));
      if (job.state === 'ready') {
        const save = el('button', 'save-button'); save.type = 'button';
        save.append(icon('download'), el('span', '', t("Save file")));
        save.addEventListener('click', () => saveFile(job)); actions.append(save);
      }
      if (['queued', 'downloading', 'paused', 'error'].includes(job.state)) {
        const resumable = ['paused', 'error'].includes(job.state);
        const action = resumable ? 'resume' : 'pause';
        const toggle = el('button', 'subtle-button', resumable ? t('Resume') : t('Pause'));
        toggle.type = 'button';
        toggle.addEventListener('click', async () => {
          toggle.disabled = true;
          try {
            await api('/api/downloads/' + encodeURIComponent(job.id) + '/' + action, {method: 'POST'});
            await refreshJobs(false); schedulePoll();
          } catch (err) { toast(err.message, true); toggle.disabled = false; }
        });
        actions.append(toggle);
      }
      const remove = el('button', 'icon-button danger-button'); remove.type = 'button';
      const running = ['queued', 'downloading', 'processing', 'paused'].includes(job.state);
      const label = running ? t("Cancel download") : t("Delete task and temporary files");
      remove.setAttribute('aria-label', label); remove.title = label;
      remove.append(icon(running ? 'close' : 'trash'));
      remove.addEventListener('click', async () => {
        remove.disabled = true;
        try {
          await api('/api/downloads/' + encodeURIComponent(job.id), { method: 'DELETE' });
          await refreshJobs(false);
          toast(running ? t("Download cancelled and temporary files cleared.") : t("Task and temporary files deleted."));
        } catch (err) { toast(err.message, true); remove.disabled = false; }
      });
      actions.append(remove); card.append(thumb, body, actions); root.append(card);
    }
  }
  function saveFile(job) {
    if (!job.file_url || (job.expires_at && job.expires_at < Date.now() / 1000)) {
      toast(t("The file expired. Analyze the link and download again."), true); return;
    }
    const anchor = el('a');
    let blobUrl = null;
    if (PREVIEW) {
      const source = asset(job.file_url);
      if (source.startsWith('data:video/mp4;base64,')) {
        const raw = atob(source.split(',')[1]);
        const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
        blobUrl = URL.createObjectURL(new Blob([bytes], { type: 'video/mp4' }));
        anchor.href = blobUrl;
      } else if (window.CLIPNEST_PREVIEW) {
        toast(t("This preview has no embedded video. Start the server to download."), true); return;
      } else anchor.href = '.' + job.file_url;
    } else {
      if (!/^\/api\/downloads\/[a-f0-9]{32}\/file$/.test(job.file_url)) {
        toast(t("The download link is invalid. Refresh downloads and try again."), true); return;
      }
      anchor.href = job.file_url;
    }
    anchor.download = job.title.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 90) + '_' + job.quality + '.' + job.container;
    anchor.hidden = true;
    document.body.append(anchor); anchor.click(); anchor.remove();
    if (blobUrl) setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    toast(t("Sent to your browser. Check its downloads list."));
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const button = $('#theme-button'); button.replaceChildren(icon(theme === 'dark' ? 'sun' : 'moon'));
    const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
    button.setAttribute('data-i18n-aria-label', label);
    button.setAttribute('aria-label', t(label));
    try { localStorage.setItem('clipnest_theme', theme); } catch {}
  }
  try { setTheme(localStorage.getItem('clipnest_theme') === 'dark' ? 'dark' : 'light'); } catch { setTheme('light'); }
  $('#theme-button').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  $('#analyze-form').addEventListener('submit', e => { e.preventDefault(); analyze(false); });
  $('#demo-button').addEventListener('click', () => analyze(true));
  $('#download-button').addEventListener('click', confirmDownload);
  $('#confirm-download-button').addEventListener('click', createDownload);
  $('#download-dialog').addEventListener('close', () => { state.pendingDownload = null; });
  $('#rights-confirmed').addEventListener('change', renderSelected);
  $('#video-url').addEventListener('input', () => { $('#clear-input').hidden = !$('#video-url').value; });
  $('#clear-input').addEventListener('click', () => { $('#video-url').value = ''; $('#clear-input').hidden = true; $('#video-url').focus(); });
  $('#paste-button').addEventListener('click', async () => {
    try {
      if (!navigator.clipboard?.readText) throw new Error();
      const text = await navigator.clipboard.readText();
      $('#video-url').value = text.slice(0, 4096); $('#clear-input').hidden = !text; $('#video-url').focus();
      toast(t("Link pasted. Select Analyze video."));
    } catch { toast(t("Clipboard access is unavailable. Use Ctrl+V or touch and hold to paste."), true); $('#video-url').focus(); }
  });
  $('#refresh-jobs').addEventListener('click', async () => {
    try { await requireSession(); await refreshJobs(true); } catch (err) { toast(err.message, true); }
  });
  $('#reconnect-button').addEventListener('click', async () => {
    $('#reconnect-button').disabled = true;
    state.connection = connect(); await state.connection;
    $('#reconnect-button').disabled = false;
    toast(state.health ? t("Connection status updated.") : t("Still disconnected. Check that the server is running."), !state.health);
  });
  $('#login-form').addEventListener('submit', async e => {
    e.preventDefault(); const button = $('#login-form button'); button.disabled = true;
    $('#login-error').hidden = true;
    try {
      const data = await api('/api/login', { method: 'POST', body: { key: $('#access-key').value } });
      state.epoch += 1;
      state.csrf = data.csrf_token; state.authenticated = true;
      $('#access-key').value = ''; $('#access-banner').hidden = true;
      renderSettings(); updateServiceStatus(); await refreshJobs(false);
      $('#settings-dialog').close(); toast(t("Connected to ClipNest."));
    } catch (err) { i18n.text($('#login-error'), i18n.key(err.message)); $('#login-error').hidden = false; }
    finally { button.disabled = false; }
  });
  $('#logout-button').addEventListener('click', async () => {
    try {
      await api('/api/logout', { method: 'POST' });
      state.epoch += 1; state.memberEpoch += 1;
      clearTimeout(state.qrTimer); state.member = null; state.qrFlow = null; renderMember();
      state.csrf = ''; state.authenticated = false; state.jobs = []; state.media = null;
      state.lastJobsJSON = ''; $('#result-section').hidden = true; $('#access-banner').hidden = false;
      renderJobs(); renderSettings(); updateServiceStatus(); toast(t("Signed out. Active downloads were cancelled."));
    } catch (err) { toast(err.message, true); }
  });
  function memberMessage(text, error = false) {
    i18n.text($('#member-message'), i18n.key(text));
    $('#member-message').classList.toggle('member-error', error);
  }
  function invalidateMedia() {
    state.media = null; state.selected = null;
    $('#result-section').hidden = true;
  }
  function renderMember() {
    const connected = state.member?.status === 'connected';
    $('#member-status').textContent = connected
      ? (state.member.vip ? t("Connected · Bilibili Premium") : t("Connected · Bilibili account")) : t("Not connected");
    $('#member-start').hidden = connected;
    $('#member-disconnect').hidden = !connected;
    $('#member-verify').hidden = !connected;
    $('#use-member').disabled = !connected;
    if (!connected) $('#use-member').checked = false;
    $('#member-start').disabled = PREVIEW || !state.health?.member_login || state.qrStarting;
    if (!state.qrFlow) {
      $('#member-qr').hidden = true; $('#member-qr').removeAttribute('src');
      $('#member-save-qr').removeAttribute('href');
    }
    $('#member-phone-steps').hidden = !state.qrFlow;
    $('#member-cancel').hidden = !state.qrFlow;
  }
  async function refreshMember() {
    if (PREVIEW || !state.health?.member_login) {
      state.member = null; renderMember();
      memberMessage(t("QR sign-in is available only on the running local server.")); return;
    }
    await requireSession();
    state.member = await api('/api/accounts/bilibili'); renderMember();
  }
  async function pollMember(epoch) {
    if (epoch !== state.memberEpoch || !state.qrFlow || document.hidden) return;
    clearTimeout(state.qrTimer);
    if (state.qrPolling) {
      state.qrTimer = setTimeout(() => pollMember(epoch), 3000); return;
    }
    if (Date.now() >= state.qrExpires) {
      state.qrFlow = null; renderMember();
      memberMessage(t("QR code expired. Generate and scan a new code."), true); return;
    }
    state.qrPolling = true;
    $('#member-check-qr').disabled = true;
    try {
      const status = await api('/api/accounts/bilibili/poll', { method: 'POST', body: {flow_id:state.qrFlow} });
      if (epoch !== state.memberEpoch) return;
      if (status.status === 'connected') {
        state.member = status; state.qrFlow = null; invalidateMedia();
        renderMember(); $('#use-member').checked = true;
        memberMessage(t("Signed in. Analyze the Bilibili link again to see available formats.")); return;
      }
      memberMessage(status.status === 'scanned' ? t("Scanned. Approve sign-in in the Bilibili app, then return here.") : t("Waiting for a scan. Follow the phone instructions, then return here."));
      state.qrTimer = setTimeout(() => pollMember(epoch), 3000);
    } catch (err) {
      if (epoch !== state.memberEpoch) return;
      if (['RATE_LIMITED', 'NETWORK_ERROR', 'ACCOUNT_NETWORK'].includes(err.code)) {
        if (err.code !== 'RATE_LIMITED') memberMessage(t("Connection interrupted. Retrying; you can also check sign-in manually."), true);
        state.qrTimer = setTimeout(() => pollMember(epoch), 5000); return;
      }
      state.qrFlow = null; renderMember(); memberMessage(err.message, true);
    } finally {
      state.qrPolling = false;
      $('#member-check-qr').disabled = false;
    }
  }
  document.addEventListener('visibilitychange', () => {
    clearTimeout(state.qrTimer);
    if (!document.hidden && state.qrFlow) pollMember(state.memberEpoch);
  });
  $('#member-check-qr').addEventListener('click', () => pollMember(state.memberEpoch));
  $('#member-start').addEventListener('click', async () => {
    const epoch = ++state.memberEpoch;
    state.qrStarting = true;
    clearTimeout(state.qrTimer); $('#member-start').disabled = true;
    memberMessage(t("Requesting a Bilibili QR code…"));
    try {
      await requireSession();
      const qr = await api('/api/accounts/bilibili/qr', {method:'POST'});
      if (epoch !== state.memberEpoch) return;
      if (!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(qr.qr_image)) throw apiError(t("Invalid QR image."));
      state.qrFlow = qr.flow_id;
      state.qrExpires = qr.expires_at * 1000;
      $('#member-qr').src = qr.qr_image; $('#member-qr').hidden = false;
      $('#member-save-qr').href = qr.qr_image;
      renderMember();
      memberMessage(t("The QR code lasts about 3 minutes. Scan from another device or follow the phone instructions."));
      state.qrTimer = setTimeout(() => pollMember(epoch), 3000);
    } catch (err) { if (epoch === state.memberEpoch) memberMessage(err.message, true); }
    finally { if (epoch === state.memberEpoch) { state.qrStarting = false; $('#member-start').disabled = false; } }
  });
  async function cancelMemberQR() {
    state.memberEpoch += 1; state.qrStarting = false; clearTimeout(state.qrTimer); state.qrFlow = null; renderMember();
    if (!PREVIEW && state.health?.member_login && state.authenticated) {
      try { await api('/api/accounts/bilibili/qr', {method:'DELETE'}); }
      catch (err) { memberMessage(err.message, true); return; }
    }
    memberMessage(t("QR sign-in cancelled."));
  }
  $('#member-cancel').addEventListener('click', cancelMemberQR);
  $('#accounts-dialog').addEventListener('close', () => { if (state.qrFlow || state.qrStarting) cancelMemberQR(); });
  $('#member-disconnect').addEventListener('click', async () => {
    try {
      state.memberEpoch += 1; clearTimeout(state.qrTimer);
      await api('/api/accounts/bilibili', {method:'DELETE'});
      state.member = null; state.qrFlow = null; invalidateMedia(); renderMember();
      await refreshJobs(); memberMessage(t("Local account session cleared. Related pending downloads were cancelled."));
    } catch (err) { memberMessage(err.message, true); }
  });
  $('#member-verify').addEventListener('click', async () => {
    try { state.member = await api('/api/accounts/bilibili/verify', {method:'POST'}); renderMember(); memberMessage(t("Account session checked.")); }
    catch (err) { if (err.code === 'ACCOUNT_EXPIRED') {state.member = null; invalidateMedia(); renderMember();} memberMessage(err.message,true); }
  });
  $('#use-member').addEventListener('change', invalidateMedia);
  document.querySelectorAll('[data-dialog]').forEach(button => button.addEventListener('click', () => showDialog(button.dataset.dialog)));
  document.querySelectorAll('dialog').forEach(dialog => {
    dialog.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
    });
  });
  document.querySelectorAll('[data-nav]').forEach(link => link.addEventListener('click', () => {
    document.querySelectorAll('[data-nav]').forEach(other => other.classList.toggle('active', other === link));
  }));
  for (const [name, domain, logo] of platforms) {
    const card = el('article', 'platform-item'), body = el('div');
    const heading = el('h3', '', name);
    i18n.text(heading, name);
    const badge = el('span', 'platform-badge'), image = el('img');
    image.alt = ''; image.width = 32; image.height = 32;
    setImage(image, '/assets/platforms/' + logo);
    badge.append(image);
    body.append(heading, el('p', '', domain));
    card.append(badge, body); $('#platforms-grid').append(card);
  }
  const languageSelect = $('#language-select');
  for (const nav of document.querySelectorAll('.main-nav > .nav-item')) {
    const label = nav.querySelector('[data-i18n]').getAttribute('data-i18n');
    nav.setAttribute('data-i18n-aria-label', label);
    nav.setAttribute('aria-label', t(label));
  }
  for (const [locale, name] of Object.entries(i18n.languages)) {
    const option = el('option', '', name);
    option.value = locale; option.lang = locale;
    languageSelect.append(option);
  }
  languageSelect.value = i18n.locale;
  languageSelect.addEventListener('change', () => i18n.setLocale(languageSelect.value));
  document.addEventListener('clipnest:languagechange', () => {
    languageSelect.value = i18n.locale;
    updateServiceStatus(); renderSettings(); setBusy(state.busy);
    renderMedia(); renderJobs(); renderMember(); renderDownloadConfirmation();
  });
  $('#preview-banner').hidden = !PREVIEW;
  if (PREVIEW) document.querySelectorAll('img[src^="/assets/"]').forEach(img => setImage(img, img.getAttribute('src')));
  state.connection = connect();
  schedulePoll();
})();
