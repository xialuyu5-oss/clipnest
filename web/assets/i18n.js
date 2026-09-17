'use strict';
(() => {
  const catalogs = window.CLIPNEST_CATALOGS;
  const languages = {
    en: 'English', 'zh-CN': '简体中文', 'zh-TW': '繁體中文', ja: '日本語', ko: '한국어',
    es: 'Español', fr: 'Français', de: 'Deutsch', pt: 'Português', ru: 'Русский', ar: 'العربية', hi: 'हिन्दी',
  };
  let locale = 'en';
  try {
    const saved = localStorage.getItem('clipnest_language');
    if (Object.hasOwn(languages, saved)) locale = saved;
  } catch { /* The interface still works when browser storage is unavailable. */ }

  function t(key, params = {}) {
    const message = catalogs[locale]?.[key] ?? catalogs.en[key] ?? key;
    return message.replace(/\{(\w+)\}/g, (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
  }
  function apply(root = document) {
    for (const attribute of ['text', 'aria-label', 'title', 'placeholder', 'alt', 'content']) {
      const marker = attribute === 'text' ? 'data-i18n' : 'data-i18n-' + attribute;
      for (const node of root.querySelectorAll('[' + marker + ']')) {
        const params = node.dataset.i18nParams ? JSON.parse(node.dataset.i18nParams) : {};
        const value = t(node.getAttribute(marker), params);
        if (attribute === 'text') node.textContent = value;
        else node.setAttribute(attribute, value);
      }
    }
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
  }
  function text(node, key, params = {}) {
    node.setAttribute('data-i18n', key);
    node.dataset.i18nParams = JSON.stringify(params);
    node.textContent = t(key, params);
  }
  function setLocale(next) {
    if (!Object.hasOwn(languages, next)) next = 'en';
    locale = next;
    try { localStorage.setItem('clipnest_language', locale); } catch {}
    apply();
    document.dispatchEvent(new CustomEvent('clipnest:languagechange'));
  }
  function key(message) {
    return Object.keys(catalogs[locale] || catalogs.en).find(k => catalogs[locale]?.[k] === message) || message;
  }
  window.ClipNestI18n = {t, text, key, apply, setLocale, languages, get locale() { return locale; }};
  apply();
})();
