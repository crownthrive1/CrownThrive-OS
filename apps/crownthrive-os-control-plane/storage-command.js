(() => {
  'use strict';
  const CONTRACT = 'ct.command.storage-status.v1';
  const ENDPOINT = '/api/storage-command';
  const PORTAL = 'https://crownthrive-storage-fabric.vercel.app';
  const RUNBOOK = 'https://github.com/crownthrive1/CrownThrive-OS/blob/main/apps/crownthrive-os-control-plane/STORAGE-COMMAND-RELEASE.md';
  const pages = new Map();
  let snapshot = null;
  let pending = null;
  let lastAttempt = 0;
  let staleTimer = null;
  let activeController = null;
  const fmt = new Intl.NumberFormat('en-US');
  const validNumber = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;
  const number = (v) => validNumber(v) ? fmt.format(v) : 'Not observed';
  const flag = (v, yes, no) => v === true ? yes : v === false ? no : 'Not observed';
  const state = (v) => typeof v === 'string' ? v.replaceAll('_', ' ') : 'Not observed';
  function time(value) {
    const parsed = typeof value === 'string' ? Date.parse(value) : NaN;
    return Number.isFinite(parsed) ? new Date(parsed).toLocaleString('en-US', { timeZone: 'America/New_York', timeZoneName: 'short' }) : 'Not observed';
  }
  function bytes(v) {
    if (!validNumber(v)) return 'Not observed';
    return v >= 1e12 ? `${fmt.format(v / 1e12)} TB` : v >= 1e9 ? `${fmt.format(v / 1e9)} GB` : `${fmt.format(v)} bytes`;
  }
  function node(tag, text = '', className = '') {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== '') el.textContent = String(text);
    return el;
  }
  function link(href, text) {
    const el = node('a', text);
    el.href = href;
    if (href.startsWith('https:')) { el.target = '_blank'; el.rel = 'noopener noreferrer'; }
    return el;
  }
  function metric(root, label, value, detail = '') {
    const el = node('div', '', 'storage-metric');
    el.append(node('span', label), node('strong', value));
    if (detail) el.append(node('small', detail));
    root.append(el);
  }
  function grid(root) { const el = node('div', '', 'storage-metrics'); root.append(el); return el; }
  function note(root, text) { root.append(node('p', text, 'storage-note')); }
  function mount() {
    const titles = {
      overview: ['Storage pulse', 'Archive progress and commercial readiness are separate.'],
      dail: ['DAIL → Wasabi archive', 'One canonical history. Million-event sections count actual events, not sequence positions.'],
      infrastructure: ['PentaFabric Storage command', 'Private object custody, archive continuity, consumer cutovers, and bounded delivery.'],
      commerce: ['Storage commercial readiness', 'Catalog registration is not proof of payment, entitlement, or fulfillment.'],
      evidence: ['Storage evidence and recovery', 'Observed runtime state, source retention, and recovery boundaries.'],
      integrations: ['Storage integration boundaries', 'ThriveBase controls metadata and authority; storage providers hold object bytes.'],
    };
    for (const [page, [title, subtitle]] of Object.entries(titles)) {
      const parent = document.querySelector(`[data-page="${page}"]`);
      if (!parent || parent.querySelector('[data-storage-command-panel]')) continue;
      const panel = node('article', '', 'panel storage-command-panel');
      panel.dataset.storageCommandPanel = page;
      panel.id = page === 'infrastructure' ? 'storage-command' : `storage-command-${page}`;
      panel.tabIndex = -1;
      const head = node('div', '', 'storage-head');
      const heading = node('div');
      heading.append(node('p', 'PentaFabric · Wasabi · DAIL', 'eyebrow'), node('h3', title), node('p', subtitle, 'storage-note'));
      const badge = node('span', 'Reading storage', 'storage-state');
      badge.setAttribute('role', 'status');
      badge.setAttribute('aria-live', 'polite');
      const body = node('div', '', 'storage-body');
      const stamp = node('p', 'No storage snapshot received.', 'storage-stamp');
      head.append(heading, badge);
      panel.append(head, stamp, body);
      parent.append(panel);
      pages.set(page, { panel, badge, body, stamp });
    }
    const nav = document.querySelector('#nav');
    if (nav && !nav.querySelector('[data-storage-command-link]')) {
      const item = link('/infrastructure#storage-command', 'Storage command');
      item.dataset.storageCommandLink = '';
      nav.append(item);
    }
    document.documentElement.dataset.storageCommandVersion = '1.0.0';
    if (location.hash === '#storage-command') requestAnimationFrame(() => document.querySelector('#storage-command')?.scrollIntoView());
  }
  function renderArchive(root, s) {
    const a = s.archive;
    const g = grid(root);
    metric(g, 'Actual events archived', number(a?.total_archived_events), 'Cumulative verified archive cursor');
    metric(g, 'Current section', number(a?.section_no), `${number(a?.section_events)} / ${number(a?.section_target_events)} actual events`);
    metric(g, 'Sealed sections in status', number(a?.sealed_sections_in_status), 'A copy in progress is not a sealed section');
    metric(g, 'Archive state', state(a?.state), `Next shard: ${number(a?.next_shard_no)}`);
    const progress = node('progress');
    progress.max = 100;
    if (validNumber(a?.section_progress_percent)) progress.value = Math.min(100, a.section_progress_percent);
    progress.setAttribute('aria-label', 'Current million-event section completion');
    root.append(progress);
    note(root, `Last archive work: ${time(a?.last_run_at)}. Last copied batch: ${number(a?.last_run_events_copied)} events.`);
    note(root, 'The hot window is a logical latest-million-row view. No database-space reclamation or complete historical migration is implied. Sequence identifiers and sequence-span lag are not exact event counts.');
  }
  function renderCommerce(root, s) {
    const c = s.commerce;
    note(root, `External sales: ${flag(c?.sales_enabled, 'gate open in current source', 'held by current source')}. ${state(c?.activation_state)}.`);
    note(root, 'Provider capacity and commercial use, payment path, tax configuration, and fulfillment acceptance must pass in the canonical owner systems. This panel cannot open those gates.');
    const list = node('div', '', 'storage-offers');
    for (const offer of c?.offers || []) {
      const item = node('div', '', 'storage-offer');
      const price = offer.currency === 'usd' && validNumber(offer.billing_amount_cents) && offer.billing_interval_months > 0
        ? `$${fmt.format(offer.billing_amount_cents / 100)} every ${offer.billing_interval_months} month${offer.billing_interval_months === 1 ? '' : 's'}` : 'Billing not observed';
      item.append(node('strong', offer.name), node('span', `${price} · ${bytes(offer.included_bytes)}`), node('small', flag(offer.catalog_binding_present, 'Catalog binding recorded', 'Catalog binding absent')));
      list.append(item);
    }
    root.append(list);
    root.append(link(PORTAL, 'Open PentaFabric Storage portal ↗'));
    note(root, 'Prices are current catalog readback, not a new Stripe payment verification. No checkout or payment is initiated here.');
  }
  function render(s, stale = false) {
    for (const [page, item] of pages) {
      item.body.replaceChildren();
      item.badge.textContent = stale ? 'STALE / last known' : s.status === 'OBSERVED' ? 'Readback observed' : 'Partial readback';
      item.badge.dataset.state = stale ? 'STALE' : s.status;
      item.stamp.textContent = `${stale ? 'Last known snapshot' : 'Retrieved'}: ${time(s.retrieved_at)}. Stored provider evidence is not a new provider probe.`;
      if (page === 'overview') {
        const g = grid(item.body);
        metric(g, 'Actual archived events', number(s.archive?.total_archived_events));
        metric(g, 'Section completion', validNumber(s.archive?.section_progress_percent) ? `${number(s.archive.section_progress_percent)}%` : 'Not observed');
        metric(g, 'Storage sales', flag(s.commerce?.sales_enabled, 'Source gate open', 'Held'));
        item.body.append(link('/infrastructure#storage-command', 'Inspect storage command'));
      } else if (page === 'dail') renderArchive(item.body, s);
      else if (page === 'commerce') renderCommerce(item.body, s);
      else if (page === 'infrastructure') {
        renderArchive(item.body, s);
        const g = grid(item.body);
        metric(g, 'Storage writes', flag(s.controls?.writes_enabled, 'Enabled within limits', 'Held'));
        metric(g, 'PentaBalancer', state(s.controls?.balancer_mode), `Pressure: ${number(s.controls?.pressure)}`);
        metric(g, 'Registered object bytes', bytes(s.custody?.registered_bytes), 'Registry total, not provider billable usage');
        metric(g, 'External delivery bindings', number(s.custody?.external_delivery_enabled_count), 'Known consumer allowlist only');
        const table = node('table', '', 'storage-table');
        const caption = node('caption', 'Registered consumer cutover states'); table.append(caption);
        const head = node('tr'); for (const label of ['Consumer', 'Backend', 'Native cutover']) { const th = node('th', label); th.scope = 'col'; head.append(th); }
        const thead = node('thead'); thead.append(head); table.append(thead);
        const tbody = node('tbody');
        for (const row of s.custody?.consumers || []) { const tr = node('tr'); for (const value of [row.name, state(row.backend_state), state(row.cutover_state)]) tr.append(node('td', value)); tbody.append(tr); }
        table.append(tbody); const wrap = node('div', '', 'storage-table-wrap'); wrap.tabIndex = 0; wrap.setAttribute('aria-label', 'Scrollable storage consumer table'); wrap.append(table); item.body.append(wrap);
      } else if (page === 'evidence') {
        const g = grid(item.body);
        metric(g, 'Source pruning', flag(s.archive?.source_pruning_enabled, 'Enabled in source', 'Disabled in source'));
        metric(g, 'Recorded retention', s.custody?.retention_mode || 'Not observed', `${number(s.custody?.retention_days)} days; registered policy`);
        metric(g, 'Configured single-PUT ceiling', bytes(s.controls?.single_put_ceiling_bytes));
        metric(g, 'Largest empirical qualification', bytes(s.controls?.largest_empirical_test_bytes), 'Not the configured maximum');
        note(item.body, `Local write stop: ${time(s.controls?.local_write_stop_at)}. This is not a provider cancellation date. Independent credential recovery and an isolated full restore are not proved by this read-only status.`);
        item.body.append(link(RUNBOOK, 'Public-safe operating and rollback notes ↗'), document.createTextNode(' · '), link(ENDPOINT, 'Inspect sanitized storage API'));
        const exportButton = node('button', 'Export storage snapshot'); exportButton.type = 'button';
        exportButton.addEventListener('click', () => { const url = URL.createObjectURL(new Blob([JSON.stringify({ ...s, exported_at: new Date().toISOString(), stale }, null, 2)], { type: 'application/json' })); const a = link(url, ''); a.download = 'crownthrive-storage-status.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
        item.body.append(exportButton);
      } else {
        note(item.body, 'ThriveBase remains the single canonical DAIL, metadata, rights, identity, and entitlement control plane. Wasabi is private off-chain object custody. CrownThrive IO hosting is not assumed to be unlimited resale storage; Storj is not counted as paid capacity without its own provider evidence.');
        const g = grid(item.body);
        for (const bucket of s.custody?.buckets || []) metric(g, `${bucket.lane} lane`, state(bucket.state), `Recorded verification: ${time(bucket.provider_verified_at)}`);
        note(item.body, `Independent blockchain or IPFS availability: ${flag(s.controls?.independent_blockchain_or_ipfs_network, 'reported by source; separate evidence required', 'not activated by this fabric')}. No credentials, signed object URLs, raw events, or customer records are exposed.`);
      }
    }
  }
  function markFailure() {
    if (snapshot) render(snapshot, true);
    else for (const item of pages.values()) { item.badge.textContent = 'Storage readback unavailable'; item.badge.dataset.state = 'UNAVAILABLE'; item.stamp.textContent = 'No current storage snapshot. Existing command-center functions remain available.'; }
  }
  function refresh(force = false) {
    if (pending || (!force && (document.hidden || Date.now() - lastAttempt < 25_000))) return pending;
    lastAttempt = Date.now();
    activeController = new AbortController();
    const timeout = setTimeout(() => activeController?.abort(), 12_000);
    pending = (async () => {
      try {
        const response = await fetch(ENDPOINT, { cache: 'no-store', credentials: 'same-origin', redirect: 'error', headers: { Accept: 'application/json' }, signal: activeController.signal });
        const data = await response.json();
        if (!response.ok || data?.schema !== CONTRACT || !['OBSERVED', 'PARTIAL'].includes(data.status) || typeof data.retrieved_at !== 'string') throw new Error('storage_readback_failed');
        const age = Date.now() - Date.parse(data.retrieved_at);
        if (!Number.isFinite(age) || age < -60_000 || age > 90_000) throw new Error('storage_readback_stale');
        snapshot = data; render(data);
        clearTimeout(staleTimer);
        staleTimer = setTimeout(() => render(snapshot, true), Math.max(0, 90_000 - age));
      } catch { markFailure(); }
      finally { clearTimeout(timeout); activeController = null; pending = null; }
    })();
    return pending;
  }
  try {
    mount();
    if (!pages.size) return;
    const observer = new MutationObserver(() => refresh());
    const fresh = document.querySelector('#fresh');
    if (fresh) observer.observe(fresh, { childList: true, subtree: true, characterData: true });
    document.querySelector('#refresh')?.addEventListener('click', () => refresh(true));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    window.addEventListener('pagehide', () => { observer.disconnect(); activeController?.abort(); clearTimeout(staleTimer); });
    window.addEventListener('pageshow', (event) => { if (event.persisted) { if (fresh) observer.observe(fresh, { childList: true, subtree: true, characterData: true }); refresh(true); } });
    refresh(true);
  } catch { document.documentElement.dataset.storageCommandState = 'UNAVAILABLE'; }
})();
