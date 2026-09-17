/* SPDX-License-Identifier: MIT */
'use strict';
(() => {
  const pending = new Map(); let serial = 0;
  function receive(raw) {
    let data; try { data = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch { return; }
    const entry = pending.get(data?.id); if (!entry) return;
    clearTimeout(entry.timer); pending.delete(data.id);
    if (data.error) entry.reject(Object.assign(new Error(data.error.message || data.error.code), data.error));
    else entry.resolve(data.result);
  }
  if (window.ClipNestNative) window.ClipNestNative.onmessage = event => receive(event.data);
  // Future iOS adapter calls this function after validating the bundled page.
  window.ClipNestReceive = receive;
  window.ClipNestClient = {call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = 'r' + (++serial), payload = JSON.stringify({id, method, params});
      const timer = setTimeout(() => { pending.delete(id); reject(Object.assign(new Error('TIMEOUT'),{code:'TIMEOUT'})); }, method === 'save' ? 1800000 : 150000);
      pending.set(id, {resolve, reject, timer});
      if (window.ClipNestNative) window.ClipNestNative.postMessage(payload);
      else if (window.webkit?.messageHandlers?.clipnest) window.webkit.messageHandlers.clipnest.postMessage({id,method,params});
      else { clearTimeout(timer); pending.delete(id); reject(Object.assign(new Error('Native engine is unavailable.'),{code:'ENGINE_UNAVAILABLE'})); }
    });
  }};
})();
