const STATE_KEY = '__ctCrownAffiliatesInstrumentationV1';

const state = (() => {
    if (window[STATE_KEY]) return window[STATE_KEY];
    const created = {
        initialized: false,
        loadedScripts: new Set(),
        providers: {},
        events: [],
    };
    window[STATE_KEY] = created;
    return created;
})();

const ALLOWED_CLIENT_EVENTS = new Set([
    'program.view',
    'program.search',
    'program.filter',
    'program.apply.click',
    'affiliate.profile.view',
    'guide.view',
    'guide.cta.click',
    'biolink.click',
    'qr.visit',
    'push.opt_in',
]);

function safeJson(value, fallback = {}) {
    try {
        if (typeof value === 'string') return JSON.parse(value);
        return value && typeof value === 'object' ? value : fallback;
    } catch {
        return fallback;
    }
}

function validHttpsUrl(value) {
    try {
        const url = new URL(value, window.location.origin);
        return url.protocol === 'https:' ? url : null;
    } catch {
        return null;
    }
}

function sameHostOrAllowlisted(url, allowlist = []) {
    if (!url) return false;
    return url.host === window.location.host || allowlist.includes(url.host);
}

function loadScriptOnce(provider, src, options = {}) {
    const url = validHttpsUrl(src);
    const allowlist = Array.isArray(options.allowlist) ? options.allowlist : [];
    if (!url || !sameHostOrAllowlisted(url, allowlist)) return Promise.resolve(false);

    const key = `${provider}:${url.href}`;
    if (state.loadedScripts.has(key) || document.querySelector(`script[data-ct-provider="${provider}"]`)) {
        state.loadedScripts.add(key);
        return Promise.resolve(true);
    }

    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = url.href;
        script.async = true;
        script.defer = true;
        script.dataset.ctProvider = provider;
        script.referrerPolicy = 'strict-origin-when-cross-origin';
        if (options.integrity) {
            script.integrity = options.integrity;
            script.crossOrigin = 'anonymous';
        }
        script.addEventListener('load', () => {
            state.loadedScripts.add(key);
            resolve(true);
        }, { once: true });
        script.addEventListener('error', () => resolve(false), { once: true });
        document.head.appendChild(script);
    });
}

function consent(name) {
    const key = `ct_consent_${name}`;
    return window.localStorage.getItem(key) === 'granted';
}

function setConsent(name, granted) {
    const key = `ct_consent_${name}`;
    window.localStorage.setItem(key, granted ? 'granted' : 'denied');
    document.dispatchEvent(new CustomEvent('ct:consent.changed', { detail: { name, granted } }));
}

async function requestPushPermission() {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) return 'unsupported';
    if (!consent('push_operational') && !consent('push_promotional')) return 'prepermission_required';
    if (Notification.permission === 'granted') return 'granted';
    if (Notification.permission === 'denied') return 'denied';

    // Must only be called from a user gesture exposed by the UI layer.
    const result = await Notification.requestPermission();
    if (result === 'granted') {
        document.dispatchEvent(new CustomEvent('ct:client.event', { detail: { name: 'push.opt_in', properties: {} } }));
    }
    return result;
}

function captureEvent(name, properties = {}) {
    if (!ALLOWED_CLIENT_EVENTS.has(name)) return false;
    const clean = safeJson(properties, {});
    const event = {
        name,
        properties: clean,
        ts: new Date().toISOString(),
        path: window.location.pathname,
    };
    state.events.push(event);
    if (state.events.length > 100) state.events.shift();
    document.dispatchEvent(new CustomEvent('ct:instrumentation.event', { detail: event }));
    return true;
}

async function activateProvider(name, config) {
    const provider = safeJson(config, {});
    state.providers[name] = { state: provider.state || 'unavailable', loaded: false };

    // Phase 03 is intentionally fail-closed until the exact production property is certified.
    if (provider.state !== 'active_exact_property_certified') return false;

    if (name === 'crownlytics' && !consent('analytics')) return false;
    if (name === 'crownpulse' && !consent('social_proof')) return false;
    if (name === 'thrivepush' && !consent('push_operational') && !consent('push_promotional')) return false;

    const loaded = await loadScriptOnce(name, provider.script_url, {
        allowlist: provider.script_hosts || [],
        integrity: provider.integrity || null,
    });
    state.providers[name].loaded = loaded;
    return loaded;
}

async function initialize() {
    if (state.initialized) return state;
    const root = document.querySelector('[data-ct-instrumentation]');
    if (!root) return state;

    state.initialized = true;
    const config = safeJson(root.dataset.ctInstrumentation, {});

    await Promise.all([
        activateProvider('thrivepush', config.thrivepush),
        activateProvider('crownlytics', config.crownlytics),
        activateProvider('crownpulse', config.crownpulse),
    ]);

    return state;
}

document.addEventListener('ct:client.event', (event) => {
    const detail = safeJson(event.detail, {});
    captureEvent(detail.name, detail.properties || {});
});

document.addEventListener('ct:consent.changed', () => {
    initialize();
});

document.addEventListener('DOMContentLoaded', initialize, { once: true });

window.CrownAffiliatesInstrumentation = Object.freeze({
    initialize,
    captureEvent,
    consent,
    setConsent,
    requestPushPermission,
    state: () => ({
        initialized: state.initialized,
        providers: structuredClone ? structuredClone(state.providers) : JSON.parse(JSON.stringify(state.providers)),
        eventCount: state.events.length,
    }),
});
