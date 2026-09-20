'use strict';
(() => {
  const catalogs = window.CLIPNEST_INTRODUCTIONS;
  const selector = document.getElementById('language');
  for (const [locale, data] of Object.entries(catalogs)) {
    const option = document.createElement('option');
    option.value = locale; option.textContent = data.name; selector.append(option);
  }
  function apply(locale) {
    if (!Object.hasOwn(catalogs, locale)) locale = 'en';
    const data = catalogs[locale];
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
    document.title = `ClipNest · ${data.title}`;
    document.querySelectorAll('[data-key]').forEach(node => { node.textContent = data[node.dataset.key]; });
    document.querySelectorAll('[data-alt]').forEach(node => { node.alt = data[node.dataset.alt]; });
    selector.value = locale;
    document.getElementById('try-demo').href = `app.html?lang=${encodeURIComponent(locale)}`;
    document.getElementById('hero-demo').href = `app.html?lang=${encodeURIComponent(locale)}`;
    document.getElementById('hero-demo').setAttribute('aria-label', data.preview);
    document.getElementById('open-app').href = `../?lang=${encodeURIComponent(locale)}`;
    try { localStorage.setItem('clipnest_language', locale); } catch {}
    const url = new URL(location.href); url.searchParams.set('lang', locale);
    try { history.replaceState(null, '', url); } catch {}
  }
  let saved = 'en';
  try { saved = localStorage.getItem('clipnest_language') || 'en'; } catch {}
  apply(new URLSearchParams(location.search).get('lang') || saved);
  selector.addEventListener('change', () => apply(selector.value));
})();
