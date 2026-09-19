import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const read = path => fs.readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const catalogs = Object.fromEntries(fs.readdirSync(new URL('../web/assets/locales/', import.meta.url))
  .filter(name => name.endsWith('.json')).map(name => [name.slice(0, -5), JSON.parse(read('web/assets/locales/' + name))]));
const languages = ['en', 'zh-CN', 'zh-TW', 'ja', 'ko', 'es', 'fr', 'de', 'pt', 'ru', 'ar', 'hi'];
assert.deepEqual(Object.keys(catalogs).sort(), [...languages].sort());
const placeholders = text => (text.match(/\{\w+\}/g) || []).sort();
for (const [locale, catalog] of Object.entries(catalogs)) {
  assert.deepEqual(Object.keys(catalog).sort(), Object.keys(catalogs.en).sort(), locale + ' completeness');
  for (const [key, value] of Object.entries(catalog)) {
    assert.ok(value.trim(), locale + ': ' + key);
    assert.deepEqual(placeholders(value), placeholders(key), locale + ': ' + key);
  }
}
const bundle = {window: {}};
vm.runInNewContext(read('web/assets/i18n-catalogs.js'), bundle);
assert.equal(JSON.stringify(bundle.window.CLIPNEST_CATALOGS), JSON.stringify(catalogs), 'Bundle must match source catalogs');

function node(attributes = {}) {
  return {attributes, dataset: {}, textContent: '',
    getAttribute(name) { return this.attributes[name]; },
    setAttribute(name, value) { this.attributes[name] = value; },
  };
}
function runtime(saved, blocked = false, search = '') {
  const nodes = [node({'data-i18n': 'Downloads'}), node({'data-i18n-aria-label': 'Interface language'})];
  let stored = saved, events = 0, replacedURL;
  const document = {documentElement: {},
    querySelectorAll: selector => nodes.filter(n => selector.slice(1, -1) in n.attributes),
    dispatchEvent: () => { events++; },
  };
  const context = {window: {CLIPNEST_CATALOGS: catalogs}, document, navigator: {language: 'ja'},
    location: {search, href:'http://127.0.0.1:8000/'+search}, URLSearchParams, URL,
    history: {replaceState(_state,_title,url) { replacedURL=url; }},
    CustomEvent: class { constructor(type) { this.type = type; } },
    localStorage: {
      getItem() { if (blocked) throw new Error('storage blocked'); return stored; },
      setItem(key, value) { if (blocked) throw new Error('storage blocked'); stored = value; },
    },
  };
  vm.runInNewContext(read('web/assets/i18n.js'), context);
  return {i18n: context.window.ClipNestI18n, document, nodes, stored: () => stored, events: () => events, replacedURL};
}
const page = runtime();
assert.equal(runtime('en', false, '?lang=zh-CN').i18n.locale, 'zh-CN');
assert.equal(runtime('ja', false, '?lang=javascript:bad').i18n.locale, 'ja');
assert.equal(runtime(null, true, '?lang=ar').document.documentElement.dir, 'rtl');
assert.equal(runtime('en', false, '?lang=zh-CN&keep=yes').replacedURL, '/?keep=yes');
assert.equal(page.i18n.locale, 'en', 'Default stays English even for a Japanese browser');
assert.equal(page.nodes[0].textContent, 'Downloads');
page.i18n.setLocale('ar');
assert.equal(page.document.documentElement.dir, 'rtl');
assert.equal(page.nodes[1].attributes['aria-label'], catalogs.ar['Interface language']);
const message = node(); page.nodes.push(message);
page.i18n.text(message, 'Formats: {count}', {count: 3});
page.i18n.setLocale('ja');
assert.equal(page.document.documentElement.dir, 'ltr');
assert.equal(message.textContent, catalogs.ja['Formats: {count}'].replace('{count}', '3'));
assert.equal(page.stored(), 'ja');
assert.equal(runtime(page.stored()).i18n.locale, 'ja', 'Saved selection survives startup');
assert.equal(runtime('unsupported').i18n.locale, 'en');
const blocked = runtime(null, true); blocked.i18n.setLocale('de');
assert.equal(blocked.i18n.locale, 'de', 'Blocked storage must not block switching');
assert.equal(page.i18n.t('Future untranslated key'), 'Future untranslated key');

const source = read('web/app.js');
for (const [, literal] of source.matchAll(/\bt\(\s*('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/g)) {
  const key = vm.runInNewContext(literal);
  assert.ok(Object.hasOwn(catalogs.en, key), 'Missing UI key: ' + key);
}
const decode = value => value.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'");
for (const [, key] of read('web/index.html').matchAll(/data-i18n(?:-(?:aria-label|title|placeholder|alt|content))?="([^"]*)"/g)) {
  assert.ok(Object.hasOwn(catalogs.en, decode(key)), 'Missing HTML key: ' + key);
}
const errors = source.slice(source.indexOf('  function errorMessage('), source.indexOf('  function el('));
// Every text in the code map (and the default fallback) must be a catalog key, or t() would
// silently show English in other languages.
for (const [, literal] of errors.matchAll(/(?:^\s+[A-Z][A-Z0-9_]+:|fallback =)\s*('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/gm)) {
  const text = vm.runInNewContext(literal);
  assert.ok(Object.hasOwn(catalogs.en, text), 'Error text missing from catalog: ' + text);
}
const errorContext = {t: page.i18n.t};
vm.runInNewContext(errors + '\nglobalThis.message = errorMessage;', errorContext);
assert.equal(errorContext.message('DISK_FULL'), catalogs.ja['Not enough free disk space. The download stopped.']);
assert.equal(errorContext.message('UNRECOGNIZED_CODE'), catalogs.ja['The request could not be completed. Check your input and try again.']);
assert.equal(errorContext.message('EXTRACTION_FAILED'), catalogs.ja['Analysis or download failed. Check that the video is publicly accessible and update the extractor, then try again.']);
assert.match(errorContext.message('LOCAL_ONLY'), /ENABLE_MEMBER_LOGIN=false/, 'LOCAL_ONLY must explain the deployment switch');
assert.notEqual(errorContext.message('LOCAL_ONLY'), errorContext.message('ACCOUNT_DISABLED'));
console.log(`PASS: ${languages.length} complete catalogs; ${Object.keys(catalogs.en).length} keys; placeholders; English default; saved language; RTL; storage fallback; error map texts; error localization`);
