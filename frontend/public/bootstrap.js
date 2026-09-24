/* Tiny same-origin bootstrap runs before the main application module. */
(() => {
  const hash = new URLSearchParams(location.hash.slice(1));
  let secret = hash.get('bootstrap');
  history.replaceState(null, '', location.pathname + location.search);
  window.cemBootstrap = secret
    ? fetch('/api/v1/session/bootstrap', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({secret}), cache:'no-store'})
        .then(async r => { const data=await r.json(); if(!r.ok) throw new Error(data.error?.message || 'Local session unavailable.'); return data; })
    : Promise.reject(new Error('Open a fresh bootstrap link from the local terminal.'));
  secret = null;
  window.cemBootstrap.catch(() => {}); // Main UI presents this error; never a synthetic fallback.
})();
