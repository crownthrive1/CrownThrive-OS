(()=>{
  const PLANS = {
    creelpilot: {
      name: 'CreelPilot Pro',
      checkout: 'https://buy.stripe.com/14A8wO7nu3xo4XU0GzbAs42',
      entitlement: 'creelpilot_pro'
    },
    lifewright: {
      name: 'LifeWright Pro',
      checkout: 'https://buy.stripe.com/9B6eVcePWaZQ61YfBtbAt04',
      entitlement: 'lifewright_pro'
    },
    'zaza-room': {
      name: 'The ZaZa Room Pro',
      checkout: 'https://buy.stripe.com/9B6dR8ePWaZQaie9d5bAt05',
      entitlement: 'zaza_room_pro'
    },
    musiqhead: {
      name: 'MusiqHead Pro',
      checkout: 'https://buy.stripe.com/14A9AS23a6JA3TQ74XbAt06',
      entitlement: 'musiqhead_pro'
    },
    'melanin-magic-suite': {
      name: 'Melanin Magic Suite Pro',
      checkout: 'https://buy.stripe.com/7sY8wO0Z67NE3TQ0GzbAt07',
      entitlement: 'melanin_magic_suite_pro'
    }
  };

  const VERIFIED_TTL_MS = 72 * 60 * 60 * 1000;
  const stateKey = key => `ct:pro:${key}`;

  function read(key, fallback = null) {
    try {
      const value = localStorage.getItem(key);
      return value == null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  function write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
    return value;
  }

  function safe(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[char]);
  }

  function toast(text) {
    let el = document.querySelector('.ct-app-toast');
    if (!el) {
      el = document.createElement('div');
      el.className = 'ct-app-toast';
      el.setAttribute('role', 'status');
      document.body.append(el);
    }
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => el.classList.remove('show'), 2200);
  }

  function captureCheckout(key) {
    const params = new URLSearchParams(location.search);
    const sessionId = params.get('session_id') || '';
    const validReturn = params.get('upgrade') === 'success' && /^cs_live_[A-Za-z0-9_]+$/.test(sessionId);

    if (validReturn) {
      write(stateKey(key), {
        state: 'verification_pending',
        session_id: sessionId,
        verified: false,
        received_at: new Date().toISOString()
      });

      if (key === 'creelpilot') {
        try {
          localStorage.setItem('creelpilot:proSession', sessionId);
          sessionStorage.setItem('creelpilot:checkout-session', sessionId);
        } catch {}
      }

      params.delete('upgrade');
      params.delete('session_id');
      const query = params.toString();
      history.replaceState({}, '', location.pathname + (query ? `?${query}` : '') + location.hash);
      return sessionId;
    }

    return read(stateKey(key), {})?.session_id || '';
  }

  function validCached(state) {
    if (!state?.verified || !state?.verified_at) return false;
    const verifiedAt = Date.parse(state.verified_at);
    if (!Number.isFinite(verifiedAt)) return false;
    if (Date.now() - verifiedAt > VERIFIED_TTL_MS) return false;
    if (state.expires_at && Date.parse(state.expires_at) <= Date.now()) return false;
    return true;
  }

  function localPro(key) {
    if (validCached(read(stateKey(key), null))) return true;

    if (key === 'creelpilot') {
      const legacy = read('creelpilot:proState', null);
      if (legacy?.verified && legacy?.checked_at) {
        const checkedAt = Date.parse(legacy.checked_at);
        if (Number.isFinite(checkedAt) && Date.now() - checkedAt < VERIFIED_TTL_MS) return true;
      }
    }
    return false;
  }

  async function verifyPro(key) {
    const prior = read(stateKey(key), {});
    const sessionId = prior.session_id || captureCheckout(key);
    if (!sessionId) return validCached(prior) ? prior : { state: 'free', verified: false };

    try {
      const response = await fetch(
        `/api/app-entitlement?app=${encodeURIComponent(key)}&session_id=${encodeURIComponent(sessionId)}`,
        { cache: 'no-store', headers: { Accept: 'application/json' } }
      );
      const body = await response.json();

      if (response.ok && body?.verified === true) {
        const next = {
          state: 'pro_active',
          verified: true,
          session_id: sessionId,
          entitlement: body.entitlement || PLANS[key]?.entitlement,
          expires_at: body.expires_at || null,
          verified_at: new Date().toISOString()
        };
        write(stateKey(key), next);
        window.dispatchEvent(new CustomEvent('ct:prochange', { detail: { app: key, state: next } }));
        return next;
      }

      const next = {
        state: body?.state || 'pro_not_active',
        verified: false,
        session_id: sessionId,
        checked_at: new Date().toISOString()
      };
      write(stateKey(key), next);
      return next;
    } catch {
      if (validCached(prior)) return prior;
      return { ...prior, state: 'verification_unavailable', verified: false };
    }
  }

  function requirePro(key, fn) {
    if (localPro(key)) {
      fn?.();
      return true;
    }
    toast(`${PLANS[key]?.name || 'Pro'} requires a verified subscription.`);
    document.querySelector('[data-pro-home]')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
  }

  function exportJSON(filename, value) {
    const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' });
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(blob);
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(anchor.href), 1000);
  }

  async function share(title, text, url = location.href) {
    try {
      if (navigator.share) {
        await navigator.share({ title, text, url });
        return;
      }
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        toast('Copied to clipboard.');
      }
    } catch {}
  }

  function haptic(ms = 18) {
    try { navigator.vibrate?.(ms); } catch {}
  }

  function dock(items) {
    document.querySelector('.ct-dock')?.remove();
    const nav = document.createElement('nav');
    nav.className = 'ct-dock';
    nav.setAttribute('aria-label', 'App navigation');
    nav.innerHTML = items.map(item =>
      `<a href="${safe(item.href)}"><b>${safe(item.icon || '•')}</b>${safe(item.label)}</a>`
    ).join('');
    document.body.append(nav);
  }

  function providerHit(raw, id) {
    return raw.toLowerCase().includes(String(id).toLowerCase());
  }

  async function osRead() {
    const requests = ['/api/health', '/api/operations', '/api/catalog'].map(url =>
      fetch(url, { headers: { Accept: 'application/json' } })
        .then(async response => ({ ok: response.ok, data: response.ok ? await response.json() : null }))
        .catch(() => ({ ok: false, data: null }))
    );
    const [health, operations, catalog] = await Promise.all(requests);
    return { health, operations, catalog };
  }

  async function mountOS(target, providers = []) {
    const root = typeof target === 'string' ? document.querySelector(target) : target;
    if (!root) return;

    root.innerHTML = '<div class="ct-app-panel"><div class="ct-app-row"><div><h3>CrownThrive OS</h3><div class="ct-app-muted">Sanitized same-origin operating rails.</div></div><span class="ct-status pending">Checking</span></div><div class="ct-os-grid" data-os-grid></div></div>';
    const status = root.querySelector('.ct-status');
    const grid = root.querySelector('[data-os-grid]');
    const result = await osRead();
    const health = result.health.data || {};
    const operationsRaw = JSON.stringify(result.operations.data || {});
    const healthState = String(health.status || health.state || '').toLowerCase();
    const operational = result.health.ok && ['operational', 'ok', 'healthy'].some(token => healthState.includes(token));

    status.textContent = operational ? 'OS operational' : 'OS partial';
    status.className = `ct-status ${operational ? 'ok' : 'pending'}`;

    const nodes = [
      ['Control plane', result.health.ok ? 'Connected' : 'Unavailable'],
      ...providers.map(provider => [provider, providerHit(operationsRaw, provider) ? 'Available' : 'Not advertised']),
      ['Catalog', result.catalog.ok ? 'Connected' : 'Unavailable']
    ];
    grid.innerHTML = nodes.map(([name, value]) =>
      `<div class="ct-os-node"><span>${safe(name)}</span><b>${safe(value)}</b></div>`
    ).join('');
  }

  async function mountPro(target, key, features = [], copy = '') {
    const root = typeof target === 'string' ? document.querySelector(target) : target;
    const plan = PLANS[key];
    if (!root || !plan) return;

    captureCheckout(key);
    const state = await verifyPro(key);
    const verified = validCached(state);
    const statusLabel = verified
      ? 'Verified Pro'
      : state.state === 'verification_unavailable'
        ? 'Verification unavailable'
        : state.state === 'verification_pending'
          ? 'Verifying'
          : 'Free';

    const box = document.createElement('div');
    box.className = 'ct-pro-box';
    box.dataset.proHome = '1';
    box.innerHTML = `
      <div class="ct-app-row">
        <div>
          <span class="ct-status ${verified ? 'ok' : state.state === 'verification_pending' ? 'pending' : ''}">${safe(statusLabel)}</span>
          <h3>${safe(plan.name)}</h3>
          <div class="ct-price">$4.99 <small>/ month</small></div>
        </div>
        <a class="ct-buy" href="${safe(plan.checkout)}">${verified ? 'Reverify / manage Pro' : 'Upgrade to Pro'}</a>
      </div>
      <p class="ct-app-muted">${safe(copy)}</p>
      <div class="ct-pro-grid">
        ${features.map(feature => `<div class="ct-pro-node"><span>PRO TOOL</span><b>${safe(feature)}</b></div>`).join('')}
      </div>
      <div class="ct-app-muted" style="margin-top:10px">Checkout does not grant access by itself. Pro activates only after live Stripe verification through CrownThrive’s server entitlement rail; verified state may be cached for up to 72 hours for offline continuity.</div>
    `;
    root.append(box);
  }

  function install(slug, button) {
    let deferredPrompt = null;
    const el = typeof button === 'string' ? document.querySelector(button) : button;

    window.addEventListener('beforeinstallprompt', event => {
      event.preventDefault();
      deferredPrompt = event;
      if (el) el.hidden = false;
    });

    if (el) {
      el.onclick = async () => {
        if (!deferredPrompt) {
          toast('Use the browser install command if the native prompt is unavailable.');
          return;
        }
        deferredPrompt.prompt();
        await deferredPrompt.userChoice;
        deferredPrompt = null;
        el.hidden = true;
      };
    }

    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register(`/${slug}/sw.js`, { scope: `/${slug}` }).catch(() => {});
      });
    }
  }

  function persistStorage() {
    try { navigator.storage?.persist?.(); } catch {}
  }

  window.CrownApp = {
    plans: PLANS,
    read,
    write,
    safe,
    toast,
    captureCheckout,
    verifyPro,
    localPro,
    requirePro,
    exportJSON,
    share,
    haptic,
    dock,
    osRead,
    mountOS,
    mountPro,
    install,
    persistStorage
  };
})();
