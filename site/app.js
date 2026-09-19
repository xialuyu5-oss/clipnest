'use strict';
(() => {
  const BASE = 'http://127.0.0.1:8000';
  const IDS = ['python', 'ffmpeg', 'javascript', 'extractor'];
  const LANGUAGES = {en:'English','zh-CN':'简体中文','zh-TW':'繁體中文',ja:'日本語',ko:'한국어',es:'Español',fr:'Français',de:'Deutsch',pt:'Português',ru:'Русский',ar:'العربية',hi:'हिन्दी'};
  const LINKS = {python:'https://www.python.org/downloads/', ffmpeg:'https://ffmpeg.org/download.html', javascript:'https://nodejs.org/en/download'};
  function classify(data) {
    if (!data || data.product !== 'clipnest' || data.protocol !== 1 || typeof data.ready !== 'boolean'
        || !Array.isArray(data.checks) || data.checks.length !== IDS.length) return 'incompatible';
    const ids = new Set();
    for (const check of data.checks) {
      if (!check || !IDS.includes(check.id) || ids.has(check.id) || typeof check.ready !== 'boolean') return 'incompatible';
      ids.add(check.id);
    }
    const ready = data.checks.every(check => check.ready);
    if (ready !== data.ready) return 'incompatible';
    return ready ? 'ready' : 'missing';
  }
  function destination(locale) {
    return BASE + '/?lang=' + encodeURIComponent(Object.hasOwn(LANGUAGES, locale) ? locale : 'en');
  }
  async function detect(fetcher = fetch) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 18000);
    try {
      const response = await fetcher(BASE + '/local/environment', {
        method:'GET', mode:'cors', credentials:'omit', cache:'no-store', redirect:'error', signal:controller.signal,
      });
      if (!response.ok) return {status: response.status === 404 ? 'incompatible' : 'unreachable'};
      const data = await response.json();
      return {status:classify(data), checks:data.checks};
    } catch { return {status:'unreachable'}; }
    finally { clearTimeout(timer); }
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {classify, destination, detect};
    return;
  }
  const $ = id => document.getElementById(id);
  const selector = $('language');
  let locale = 'en', result = {status:'checking'}, busy = false, retryTimer;
  let retriesLeft = 60;
  for (const [code,label] of Object.entries(LANGUAGES)) {
    const option = document.createElement('option'); option.value=code; option.textContent=label; selector.append(option);
  }
  const t = key => window.CLIPNEST_SITE[locale][key];
  function render() {
    document.querySelectorAll('[data-key]').forEach(node => { node.textContent=t(node.dataset.key); });
    document.documentElement.lang=locale; document.documentElement.dir=locale==='ar'?'rtl':'ltr'; selector.value=locale;
    $('open-local').href=destination(locale);
    const status = result.status;
    $('environment').setAttribute('aria-busy', String(busy));
    $('environment').dataset.state=status;
    $('check-title').textContent=t(status + 'Title');
    $('check-detail').textContent=t(status + 'Detail');
    $('status-icon').textContent=status==='ready'?'✓':status==='checking'?'◌':'!';
    $('retry').disabled=busy;
    const checks = ['missing','ready'].includes(status) ? result.checks : [];
    $('checks').replaceChildren();
    for (const id of IDS) {
      const known=checks.find(check=>check.id===id);
      const row=document.createElement('li');
      const label=document.createElement('span'); label.textContent=t(id);
      const state=document.createElement('span'); state.className='component-state';
      state.textContent=t(known ? known.ready?'available':'required' : 'unknown');
      row.append(label,state);
      if (known && !known.ready && LINKS[id]) {
        const link=document.createElement('a'); link.href=LINKS[id]; link.target='_blank'; link.rel='noopener noreferrer';
        link.textContent=t('publisher'); row.append(link);
      }
      $('checks').append(row);
    }
    const missing=status==='missing';
    $('installation').hidden=['checking','ready'].includes(status);
    $('install-detail').textContent=t(missing?'missingInstall':'firstInstall');
    $('install-steps').textContent=t(missing?'missingSteps':'firstSteps');
    $('pc-package').hidden=missing;
    $('setup-package').hidden=!missing || !checks.some(check=>!check.ready && check.id!=='extractor');
  }
  function apply(next) {
    locale=Object.hasOwn(LANGUAGES,next)?next:'en';
    try { localStorage.setItem('clipnest_language',locale); } catch {}
    render();
  }
  async function check() {
    if (busy) return;
    clearTimeout(retryTimer);
    busy=true;
    if (result.status!=='missing') result={status:'checking'};
    render();
    result=await detect(); busy=false; render();
    if (result.status==='ready') {
      // Preserve the complete UI and same-origin task/account API. The response
      // can never choose a destination URL or run a local command.
      window.location.replace(destination(locale));
    } else if (result.status==='missing' && retriesLeft-- > 0) {
      retryTimer=setTimeout(() => { if (!document.hidden) check(); }, 10000);
    }
  }
  selector.onchange=()=>apply(selector.value);
  $('retry').onclick=()=>{ retriesLeft=60; check(); };
  window.addEventListener('focus',()=>{ if (result.status!=='ready') check(); });
  window.addEventListener('pagehide',()=>clearTimeout(retryTimer));
  try { locale=localStorage.getItem('clipnest_language')||'en'; } catch {}
  apply(locale); check();
})();
