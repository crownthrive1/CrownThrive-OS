(() => {
  'use strict';

  const VERSION = '3.1.0';
  const REFRESH_MS = 30_000;
  const ENDPOINTS = Object.freeze({
    command: '/api/command?limit=12',
    catalog: '/api/catalog',
    operations: '/api/operations',
    health: '/api/health',
  });
  const CATEGORY_LABELS = Object.freeze({
    education: 'Education',
    playbooks: 'Playbooks',
    infrastructure: 'Infrastructure',
    'api-platform': 'API platform',
    publishing: 'Publishing',
    advertising: 'Advertising',
    credits: 'Crown Credits',
    'event-production': 'Experiences',
    'rights-kit': 'Licensing',
    'scripted-audio': 'Scripted audio',
    'stage-screen': 'Stage & screen',
    'digital-art': 'Digital art',
    'local-media': 'Local media',
    promotion: 'Promotion',
    'creative-services': 'Creative services',
    'managed-services': 'Managed services',
    merchandise: 'Digital merchandise',
    'digital-product': 'Digital products',
  });

  const number = new Intl.NumberFormat('en-US');
  let lastSnapshot = null;
  let refreshTimer = null;
  let hydrating = false;

  function formatNumber(value, fallback = '—') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? number.format(parsed) : fallback;
  }

  function formatPercent(value, digits = 4) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${parsed.toFixed(digits)}%` : '—';
  }

  function money(amountMinor, currency = 'USD') {
    const amount = Number(amountMinor);
    if (!Number.isFinite(amount)) return '—';
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: String(currency || 'USD').toUpperCase(),
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(amount / 100);
    } catch {
      return `$${(amount / 100).toFixed(2)}`;
    }
  }

  function formatTime(value) {
    const date = new Date(value || '');
    if (!Number.isFinite(date.getTime())) return 'Not observed';
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', second: '2-digit',
      timeZone: 'America/New_York', timeZoneName: 'short',
    }).format(date);
  }

  function humanize(value) {
    return String(value || 'unknown')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function text(node, value) {
    if (node) node.textContent = String(value ?? '—');
  }

  function query(selector, root = document) {
    return root.querySelector(selector);
  }

  function element(tag, className = '', content = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== '') node.textContent = String(content);
    return node;
  }

  function toneForState(value) {
    const state = String(value || '').toUpperCase();
    if (['PASS', 'OPERATIONAL', 'PRODUCTION', 'ENFORCED', 'BOUND', 'ACTIVE', 'LIVE'].some((token) => state.includes(token))
      && !['PARTIAL', 'PENDING', 'HOLD', 'REQUIRED', 'STALE'].some((token) => state.includes(token))) return 'pass';
    if (['HOLD', 'FAILED', 'ERROR', 'STALE', 'REQUIRED'].some((token) => state.includes(token))) return 'hold';
    return 'attention';
  }

  function safeExternalLink(href, label, className = '') {
    const link = element('a', className, label);
    link.href = href;
    link.target = '_blank';
    link.rel = 'noreferrer noopener';
    return link;
  }

  function addReleaseChrome() {
    document.documentElement.dataset.commandVersion = VERSION;
    const sourcebar = query('.sourcebar');
    if (sourcebar && !query('[data-command-release-chip]', sourcebar)) {
      const chip = element('span', 'ct-release-chip');
      chip.dataset.commandReleaseChip = '';
      chip.append(element('i'), document.createTextNode(`Command ${VERSION}`));
      sourcebar.append(chip);
    }

    const nav = query('#nav');
    if (nav && !query('[data-marketplace-link]', nav)) {
      const link = element('a');
      link.href = '/store';
      link.dataset.marketplaceLink = '';
      link.append(element('b', '', '10'), document.createTextNode('Marketplace'));
      nav.append(link);
    }

    const topActions = query('.top-actions');
    if (topActions && !query('#ctExecutiveRefresh', topActions)) {
      const button = element('button', '', 'Pulse');
      button.id = 'ctExecutiveRefresh';
      button.type = 'button';
      button.title = 'Refresh executive command extensions';
      button.addEventListener('click', () => hydrate({ force: true }));
      topActions.insertBefore(button, query('#refresh', topActions));
    }
  }

  function addOverviewShell() {
    const page = query('[data-page="overview"]');
    const metrics = query('#overviewMetrics', page);
    if (!page || !metrics || query('#ctExecutivePulse', page)) return;

    const section = element('section', 'ct-upgrade-section');
    section.id = 'ctExecutivePulse';
    section.innerHTML = `
      <div class="ct-upgrade-head">
        <div><p class="eyebrow">Executive pulse</p><h3>Institutional decisions in one readback</h3><p>Live wallet, DAIL, operations, infrastructure, and catalog signals. Partial remains partial.</p></div>
        <span class="badge pending" id="ctPulseState">READING</span>
      </div>
      <div class="ct-pulse-grid">
        <article class="ct-pulse-card" id="ctPulseCommand"><span>Command state</span><strong>—</strong><small>Public-safe aggregate</small></article>
        <article class="ct-pulse-card" id="ctPulseWallet"><span>Wallet gate</span><strong>—</strong><small>Bindings and receipts</small></article>
        <article class="ct-pulse-card" id="ctPulseDail"><span>DAIL assurance</span><strong>—</strong><small>Verified prefix</small></article>
        <article class="ct-pulse-card" id="ctPulseActivity"><span>24-hour activity</span><strong>—</strong><small>Unified runtime events</small></article>
        <article class="ct-pulse-card" id="ctPulseCatalog"><span>Commercial estate</span><strong>—</strong><small>Products and checkouts</small></article>
        <article class="ct-pulse-card" id="ctPulseProviders"><span>Provider fabric</span><strong>—</strong><small>Active / registered</small></article>
      </div>
      <div class="ct-upgrade-split">
        <article class="panel"><div class="panel-head"><div><p class="eyebrow">Decision queue</p><h3>Bounded states requiring attention</h3></div><span class="badge pending" id="ctDecisionCount">READING</span></div><div class="ct-decision-list" id="ctDecisionList"></div></article>
        <article class="panel"><p class="eyebrow">Founder shortcuts</p><h3>Inspect and distribute</h3><div class="ct-quick-links" id="ctQuickLinks"></div><p class="ct-boundary-note"><span><strong>Read-only surface.</strong> Economic mutations, credentials, wallet identifiers, actors, balances, and private evidence remain outside this interface.</span></p></article>
      </div>`;
    metrics.insertAdjacentElement('afterend', section);

    const links = query('#ctQuickLinks');
    links.append(
      makeRouteLink('/wallet', 'Wallet gate'),
      makeRouteLink('/dail', 'DAIL assurance'),
      makeRouteLink('/commerce', 'Commerce'),
      safeExternalLink('/api/command', 'Command API'),
      safeExternalLink('/api/catalog', 'Catalog API'),
      safeExternalLink('https://go-flipbooks.vercel.app/store', 'Go Flipbooks', 'ct-primary-link'),
    );
    const copy = element('button', '', 'Copy status summary');
    copy.type = 'button';
    copy.addEventListener('click', copyStatusSummary);
    links.append(copy);
  }

  function makeRouteLink(href, label) {
    const link = element('a', '', label);
    link.href = href;
    return link;
  }

  function addWalletShell() {
    const page = query('[data-page="wallet"]');
    const metrics = query('.metrics.five', page);
    if (!page || !metrics || query('#ctWalletAssurance', page)) return;
    const section = element('section', 'ct-upgrade-section');
    section.id = 'ctWalletAssurance';
    section.innerHTML = `
      <article class="panel">
        <div class="panel-head"><div><p class="eyebrow">Wallet assurance pulse</p><h3>Gate receipts, canary evidence, and movement boundaries</h3></div><span class="badge pending" id="ctWalletPulseState">READING</span></div>
        <div class="ct-mini-metrics">
          <div class="ct-mini-metric"><span>Gate receipts</span><strong id="ctWalletReceipts">—</strong><small>Verified economic decisions</small></div>
          <div class="ct-mini-metric"><span>Canary cases</span><strong id="ctWalletCanary">—</strong><small id="ctWalletCanarySub">Awaiting readback</small></div>
          <div class="ct-mini-metric"><span>Agent wallet</span><strong id="ctAgentWallet">—</strong><small id="ctAgentWalletSub">External movement bounded</small></div>
          <div class="ct-mini-metric"><span>External wallet</span><strong id="ctExternalWallet">—</strong><small>Optional participation rail</small></div>
          <div class="ct-mini-metric"><span>Card issuing</span><strong id="ctCardIssuing">—</strong><small>Provider contract boundary</small></div>
          <div class="ct-mini-metric"><span>Stablecoin</span><strong id="ctStablecoin">—</strong><small>Checkout boundary</small></div>
        </div>
      </article>`;
    metrics.insertAdjacentElement('afterend', section);
  }

  function addDailShell() {
    const page = query('[data-page="dail"]');
    const metrics = query('.metrics.five', page);
    if (!page || !metrics || query('#ctDailAssurance', page)) return;
    const section = element('article', 'panel ct-assurance-panel');
    section.id = 'ctDailAssurance';
    section.innerHTML = `
      <div class="ct-assurance-copy"><div><p class="eyebrow">Assurance completion</p><h3>Verified prefix against current event head</h3></div><progress id="ctDailProgress" max="1" value="0">0%</progress><div class="ct-assurance-meta"><span id="ctDailVerifiedMeta">Verified: —</span><span id="ctDailHeadMeta">Head: —</span><span id="ctDailSegmentMeta">Segments: —</span><span id="ctDailAnchorMeta">Anchor: —</span></div></div>
      <div class="ct-assurance-score"><strong id="ctDailPercent">—</strong><small id="ctDailProgressState">READING</small></div>`;
    metrics.insertAdjacentElement('afterend', section);
  }

  function addOperationsShell() {
    const page = query('[data-page="ops"]');
    const metrics = query('#opsMetrics', page);
    if (!page || !metrics || query('#ctOperationsPulse', page)) return;
    const section = element('article', 'panel ct-upgrade-section');
    section.id = 'ctOperationsPulse';
    section.innerHTML = `
      <div class="panel-head"><div><p class="eyebrow">24-hour execution pulse</p><h3>Unified activity—not a single-ledger projection</h3></div><span class="badge pending" id="ctOperationsPulseState">READING</span></div>
      <div class="ct-mini-metrics">
        <div class="ct-mini-metric"><span>Total events</span><strong id="ctOpsEvents">—</strong><small>Unified activity window</small></div>
        <div class="ct-mini-metric"><span>PentaSuper runs</span><strong id="ctOpsSuper">—</strong><small>Execution cycles</small></div>
        <div class="ct-mini-metric"><span>Wake requests</span><strong id="ctOpsWake">—</strong><small>PentaTime dispatch</small></div>
        <div class="ct-mini-metric"><span>Remediation</span><strong id="ctOpsRemediation">—</strong><small>Window events</small></div>
        <div class="ct-mini-metric"><span>Protocols</span><strong id="ctOpsProtocols">—</strong><small>Active protocol classes</small></div>
        <div class="ct-mini-metric"><span>Routes</span><strong id="ctOpsRoutes">—</strong><small>Observed active routes</small></div>
      </div>`;
    metrics.insertAdjacentElement('afterend', section);
  }

  function addCommerceShell() {
    const page = query('[data-page="commerce"]');
    const grid = query('#commerceGrid', page);
    if (!page || !grid || query('#marketplaceCatalogPanel', page)) return;
    const panel = element('article', 'panel ct-upgrade-section');
    panel.id = 'marketplaceCatalogPanel';
    panel.innerHTML = `
      <div class="panel-head"><div><p class="eyebrow">Commercial inventory</p><h3>Live marketplace catalog</h3><p>Active digital products, checkout options, category distribution, and catalog-boundary evidence.</p></div><span class="badge pending" id="marketplaceCatalogState">READING</span></div>
      <div class="ct-market-grid">
        <div class="ct-mini-metric"><span>Active products</span><strong id="marketplaceProductCount">—</strong><small>Digital inventory</small></div>
        <div class="ct-mini-metric"><span>Checkout options</span><strong id="marketplaceCheckoutCount">—</strong><small>Active commercial routes</small></div>
        <div class="ct-mini-metric"><span>Categories</span><strong id="marketplaceCategoryCount">—</strong><small>Commercial corridors</small></div>
        <div class="ct-mini-metric"><span>Price range</span><strong id="marketplacePriceRange">—</strong><small>Catalog readback</small></div>
      </div>
      <div class="ct-market-rows" id="marketplaceCategoryRows"></div>
      <div class="ct-status-actions"><a href="/store">Open CrownThrive marketplace</a><a href="https://go-flipbooks.vercel.app/store" target="_blank" rel="noreferrer noopener">Open Go Flipbooks ↗</a><a href="/api/catalog" target="_blank" rel="noreferrer noopener">Raw catalog evidence ↗</a></div>
      <p class="ct-boundary-note" id="marketplaceBoundary"><span><strong>Catalog boundary:</strong> reading current exclusions and duplicate-collapse evidence.</span></p>`;
    grid.insertAdjacentElement('afterend', panel);
  }

  function addShells() {
    addReleaseChrome();
    addOverviewShell();
    addWalletShell();
    addDailShell();
    addOperationsShell();
    addCommerceShell();
  }

  async function fetchJson(url) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15_000);
    try {
      const response = await fetch(url, {
        cache: 'no-store',
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload || typeof payload !== 'object') throw new Error(`${url}_${response.status}`);
      return payload;
    } finally {
      clearTimeout(timer);
    }
  }

  async function hydrate({ force = false } = {}) {
    if (hydrating && !force) return;
    hydrating = true;
    setGlobalReading();
    const [commandResult, catalogResult, operationsResult, healthResult] = await Promise.allSettled([
      fetchJson(ENDPOINTS.command),
      fetchJson(ENDPOINTS.catalog),
      fetchJson(ENDPOINTS.operations),
      fetchJson(ENDPOINTS.health),
    ]);

    const snapshot = {
      command: commandResult.status === 'fulfilled' ? commandResult.value : null,
      catalog: catalogResult.status === 'fulfilled' ? catalogResult.value : null,
      operations: operationsResult.status === 'fulfilled' ? operationsResult.value : null,
      health: healthResult.status === 'fulfilled' ? healthResult.value : null,
      errors: {
        command: commandResult.status === 'rejected' ? String(commandResult.reason?.message || commandResult.reason) : null,
        catalog: catalogResult.status === 'rejected' ? String(catalogResult.reason?.message || catalogResult.reason) : null,
        operations: operationsResult.status === 'rejected' ? String(operationsResult.reason?.message || operationsResult.reason) : null,
        health: healthResult.status === 'rejected' ? String(healthResult.reason?.message || healthResult.reason) : null,
      },
      hydratedAt: new Date().toISOString(),
    };
    lastSnapshot = snapshot;

    hydrateExecutive(snapshot);
    hydrateWallet(snapshot.command);
    hydrateDail(snapshot.command);
    hydrateOperations(snapshot.operations);
    hydrateCatalog(snapshot.catalog);
    hydrating = false;
    window.dispatchEvent(new CustomEvent('ct:command-v31-hydrated', {
      detail: { version: VERSION, observedAt: snapshot.hydratedAt },
    }));
  }

  function setGlobalReading() {
    const state = query('#ctPulseState');
    if (state) {
      state.className = 'badge pending';
      state.textContent = 'READING';
    }
  }

  function hydrateExecutive(snapshot) {
    const command = snapshot.command;
    const operations = snapshot.operations;
    const catalog = snapshot.catalog;
    const health = snapshot.health;
    const state = query('#ctPulseState');
    if (!command) {
      if (state) {
        state.className = 'badge hold';
        state.textContent = 'READBACK HOLD';
      }
      hydrateDecisionQueue(snapshot);
      return;
    }

    const wallet = command.wallet || {};
    const assurance = command.dail?.assurance || {};
    const inventory = wallet.inventory || {};
    const activity = operations?.activity || {};
    const stats = operations?.stats || {};
    const commandStatus = String(command.status || 'PARTIAL');
    const verified = Number(assurance.verified_through_sequence_id || 0);
    const head = Number(assurance.current_head_sequence_id || 0);
    const percent = head > 0 ? (verified / head) * 100 : 0;
    const productCount = Number(catalog?.active_product_count || 0);
    const checkoutCount = Number(catalog?.active_checkout_count || 0);
    const activeProviders = Number(stats.active_providers || 0);
    const registeredProviders = Number(stats.registered_providers || 0);

    pulse('#ctPulseCommand', commandStatus, command.source?.state || 'Aggregate readback', toneForState(commandStatus));
    pulse('#ctPulseWallet', humanize(wallet.enforcement_state), `${formatNumber(inventory.service_bindings)} bindings · ${formatNumber(inventory.gate_receipts)} receipts`, toneForState(wallet.enforcement_state));
    pulse('#ctPulseDail', formatPercent(percent), `${formatNumber(assurance.sequence_span_lag)} events beyond verified prefix`, assurance.ok ? 'pass' : 'attention');
    pulse('#ctPulseActivity', formatNumber(activity.total_events), `${formatNumber(activity.penta_super_runs)} PentaSuper runs · 24h`, toneForState(operations?.status));
    pulse('#ctPulseCatalog', formatNumber(productCount), `${formatNumber(checkoutCount)} active checkout options`, productCount > 0 ? 'pass' : 'hold');
    pulse('#ctPulseProviders', `${formatNumber(activeProviders)}/${formatNumber(registeredProviders)}`, health?.vercel_provider_state || 'Provider registry', activeProviders > 0 ? 'pass' : 'attention');

    if (state) {
      state.className = `badge ${toneForState(commandStatus)}`;
      state.textContent = commandStatus;
    }
    hydrateDecisionQueue(snapshot);
  }

  function pulse(selector, value, subtitle, tone) {
    const card = query(selector);
    if (!card) return;
    card.dataset.tone = tone;
    text(query('strong', card), value);
    text(query('small', card), subtitle);
  }

  function hydrateDecisionQueue(snapshot) {
    const command = snapshot.command || {};
    const wallet = command.wallet || {};
    const assurance = command.dail?.assurance || {};
    const health = snapshot.health || {};
    const decisions = [];
    const lag = Number(assurance.sequence_span_lag || 0);

    decisions.push({
      tone: lag === 0 && assurance.verified_prefix_ok ? 'pass' : 'attention',
      title: 'DAIL verified-prefix catch-up',
      detail: lag === 0 ? 'The verified prefix is aligned with the current event head.' : 'New events exist beyond the last verified checkpoint; prior verified evidence remains valid.',
      state: lag === 0 ? 'Aligned' : `${formatNumber(lag)} events pending`,
    });
    decisions.push({
      tone: String(assurance.public_chain_anchor_state || '').includes('REQUIRED') ? 'hold' : 'pass',
      title: 'Public chain anchor',
      detail: 'No chain-broadcast success is claimed without an authoritative provider receipt.',
      state: humanize(assurance.public_chain_anchor_state),
    });
    decisions.push({
      tone: wallet.agent_wallet?.fresh ? 'pass' : 'hold',
      title: 'Agent wallet heartbeat',
      detail: 'Unattended external value movement remains disabled while freshness is not verified.',
      state: wallet.agent_wallet?.fresh ? 'Fresh' : `$0 movement · stale`,
    });
    const bridge = health.integrations?.chlom_chain_evidence || {};
    decisions.push({
      tone: toneForState(bridge.status),
      title: 'CHLOM chain-evidence bridge',
      detail: 'Token binding, custody, and broadcast authority remain independently gated.',
      state: humanize(bridge.status),
    });
    decisions.push({
      tone: String(wallet.card_issuing?.state || '').includes('required') ? 'attention' : 'pass',
      title: 'Card issuing',
      detail: 'No card-program production state is represented without a legitimate issuer or BIN sponsor.',
      state: humanize(wallet.card_issuing?.state),
    });
    decisions.push({
      tone: wallet.stablecoin_checkout?.state === 'HOLD' ? 'attention' : 'pass',
      title: 'Stablecoin checkout',
      detail: 'The checkout rail remains outside production until its independent release predicates pass.',
      state: humanize(wallet.stablecoin_checkout?.state),
    });

    const list = query('#ctDecisionList');
    if (list) {
      list.replaceChildren(...decisions.map((decision) => {
        const row = element('div', 'ct-decision');
        row.dataset.tone = decision.tone;
        const dot = element('i', 'ct-decision-dot');
        const copy = element('span');
        copy.append(element('strong', '', decision.title), element('small', '', decision.detail));
        row.append(dot, copy, element('span', 'ct-decision-state', decision.state));
        return row;
      }));
    }
    const count = query('#ctDecisionCount');
    const attention = decisions.filter((item) => item.tone !== 'pass').length;
    if (count) {
      count.className = `badge ${attention ? 'pending' : 'pass'}`;
      count.textContent = attention ? `${attention} BOUNDED` : 'ALL CLEAR';
    }
  }

  function hydrateWallet(command) {
    const state = query('#ctWalletPulseState');
    if (!command?.wallet) {
      if (state) {
        state.className = 'badge hold';
        state.textContent = 'READBACK HOLD';
      }
      return;
    }
    const wallet = command.wallet;
    const canary = wallet.latest_canary || {};
    text(query('#ctWalletReceipts'), formatNumber(wallet.inventory?.gate_receipts));
    text(query('#ctWalletCanary'), `${formatNumber(canary.pass_count)}/${formatNumber(canary.case_count)}`);
    text(query('#ctWalletCanarySub'), `${formatNumber(canary.fail_count)} failures · ${formatTime(canary.created_at)}`);
    text(query('#ctAgentWallet'), wallet.agent_wallet?.fresh ? 'FRESH' : 'STALE');
    text(query('#ctAgentWalletSub'), `${formatNumber(wallet.agent_wallet?.max_unattended_value_minor, '0')} unattended value · ${humanize(wallet.agent_wallet?.runner_state)}`);
    text(query('#ctExternalWallet'), wallet.external_wallet?.required ? 'REQUIRED' : 'OPTIONAL');
    text(query('#ctCardIssuing'), wallet.card_issuing?.production ? 'PRODUCTION' : 'NOT LIVE');
    text(query('#ctStablecoin'), humanize(wallet.stablecoin_checkout?.state));
    if (state) {
      state.className = `badge ${canary.result === 'PASS' && wallet.enforcement_state === 'enforced' ? 'pass' : 'pending'}`;
      state.textContent = canary.result === 'PASS' ? '15/15 PASS' : humanize(canary.result);
    }
  }

  function hydrateDail(command) {
    const assurance = command?.dail?.assurance;
    if (!assurance) return;
    const head = Number(assurance.current_head_sequence_id || 0);
    const verified = Number(assurance.verified_through_sequence_id || 0);
    const percent = head > 0 ? Math.min(100, Math.max(0, (verified / head) * 100)) : 0;
    const progress = query('#ctDailProgress');
    if (progress) {
      progress.max = Math.max(1, head);
      progress.value = Math.min(head, verified);
      progress.textContent = formatPercent(percent);
    }
    text(query('#ctDailPercent'), formatPercent(percent));
    text(query('#ctDailProgressState'), humanize(assurance.integrity_state));
    text(query('#ctDailVerifiedMeta'), `Verified: ${formatNumber(verified)}`);
    text(query('#ctDailHeadMeta'), `Head: ${formatNumber(head)}`);
    text(query('#ctDailSegmentMeta'), `Segments: ${formatNumber(assurance.v4_segment_count)}`);
    text(query('#ctDailAnchorMeta'), `Anchor: ${humanize(assurance.public_chain_anchor_state)}`);
  }

  function hydrateOperations(operations) {
    const state = query('#ctOperationsPulseState');
    if (!operations) {
      if (state) {
        state.className = 'badge hold';
        state.textContent = 'READBACK HOLD';
      }
      return;
    }
    const activity = operations.activity || {};
    text(query('#ctOpsEvents'), formatNumber(activity.total_events));
    text(query('#ctOpsSuper'), formatNumber(activity.penta_super_runs));
    text(query('#ctOpsWake'), formatNumber(activity.wake_requests));
    text(query('#ctOpsRemediation'), formatNumber(activity.remediation_events));
    text(query('#ctOpsProtocols'), formatNumber(activity.active_protocols));
    text(query('#ctOpsRoutes'), formatNumber(activity.active_routes));
    if (state) {
      state.className = `badge ${toneForState(operations.status)}`;
      state.textContent = humanize(operations.status);
    }
  }

  function hydrateCatalog(payload) {
    const state = query('#marketplaceCatalogState');
    const rows = query('#marketplaceCategoryRows');
    if (!payload || !Array.isArray(payload.products)) {
      if (state) {
        state.className = 'badge hold';
        state.textContent = 'READBACK HOLD';
      }
      if (rows) rows.replaceChildren(errorRow('Catalog unavailable', 'No cached product count or fabricated checkout state was substituted.'));
      return;
    }

    const products = payload.products.filter((product) => product.checkout_state === 'active');
    const counts = new Map();
    const prices = [];
    for (const product of products) {
      const category = String(product.category || 'digital-product');
      const offers = Array.isArray(product.offers) ? product.offers : [];
      const entry = counts.get(category) || { products: 0, checkouts: 0 };
      entry.products += 1;
      entry.checkouts += Math.max(1, offers.length);
      counts.set(category, entry);
      if (offers.length) {
        for (const offer of offers) {
          const amount = Number(offer.amount_minor);
          if (Number.isFinite(amount)) prices.push(amount);
        }
      } else {
        const amount = Number(product.price_minor);
        if (Number.isFinite(amount)) prices.push(amount);
      }
    }

    const productCount = Number(payload.active_product_count || products.length);
    const checkoutCount = Number(payload.active_checkout_count || [...counts.values()].reduce((sum, entry) => sum + entry.checkouts, 0));
    const categoryCount = Number(payload.category_count || counts.size);
    text(query('#marketplaceProductCount'), formatNumber(productCount));
    text(query('#marketplaceCheckoutCount'), formatNumber(checkoutCount));
    text(query('#marketplaceCategoryCount'), formatNumber(categoryCount));
    text(query('#marketplacePriceRange'), prices.length ? `${money(Math.min(...prices))}–${money(Math.max(...prices))}` : '—');
    if (state) {
      state.className = 'badge pass';
      state.textContent = `${formatNumber(productCount)} PRODUCTS`;
    }

    if (rows) {
      const ordered = [...counts.entries()]
        .sort((left, right) => right[1].products - left[1].products || left[0].localeCompare(right[0]))
        .slice(0, 12);
      rows.replaceChildren(...ordered.map(([category, entry]) => {
        const row = element('div', 'ct-market-row');
        const copy = element('span');
        copy.append(
          element('strong', '', CATEGORY_LABELS[category] || humanize(category)),
          element('small', '', `${formatNumber(entry.products)} products · ${formatNumber(entry.checkouts)} checkout options`),
        );
        row.append(copy, element('b', '', formatNumber(entry.products)));
        return row;
      }));
    }

    const exclusions = Number(payload.physical_products_excluded || 0);
    const duplicates = Number(payload.duplicate_active_links_collapsed || 0);
    const boundary = query('#marketplaceBoundary span');
    if (boundary) {
      boundary.replaceChildren(
        element('strong', '', 'Catalog boundary: '),
        document.createTextNode(`${formatNumber(exclusions)} physical made-to-order products excluded · ${formatNumber(duplicates)} duplicate active links collapsed · CHLOM and PentaGreen governance preserved.`),
      );
    }
  }

  function errorRow(title, detail) {
    const row = element('div', 'ct-command-upgrade-error');
    row.append(element('strong', '', title), document.createTextNode(` — ${detail}`));
    return row;
  }

  function statusSummary() {
    if (!lastSnapshot?.command) return `CrownThrive Command ${VERSION}\nLive command readback unavailable.`;
    const command = lastSnapshot.command;
    const wallet = command.wallet || {};
    const assurance = command.dail?.assurance || {};
    const activity = lastSnapshot.operations?.activity || {};
    const catalog = lastSnapshot.catalog || {};
    return [
      `CrownThrive Command ${VERSION}`,
      `State: ${command.status || 'UNKNOWN'}`,
      `Wallet: ${wallet.enforcement_state || 'UNKNOWN'} · ${formatNumber(wallet.inventory?.service_bindings)} bindings · ${formatNumber(wallet.inventory?.gate_receipts)} gate receipts`,
      `Internal economy: ${formatNumber(wallet.inventory?.active_wallets)} wallets · ${formatNumber(wallet.inventory?.verified_internal_accounts)} verified ledger accounts`,
      `Canary: ${formatNumber(wallet.latest_canary?.pass_count)}/${formatNumber(wallet.latest_canary?.case_count)} PASS · ${formatNumber(wallet.latest_canary?.fail_count)} failures`,
      `DAIL: ${formatNumber(assurance.verified_through_sequence_id)} verified / ${formatNumber(assurance.current_head_sequence_id)} head · ${formatNumber(assurance.sequence_span_lag)} pending`,
      `Operations: ${formatNumber(activity.total_events)} events / 24h · ${formatNumber(activity.penta_super_runs)} PentaSuper runs`,
      `Catalog: ${formatNumber(catalog.active_product_count)} products · ${formatNumber(catalog.active_checkout_count)} checkout options · ${formatNumber(catalog.category_count)} categories`,
      `Observed: ${formatTime(command.observed_at)}`,
      'Boundary: read-only public-safe projection; no balances, actors, credentials, wallet identifiers, private payloads, or economic mutations.',
    ].join('\n');
  }

  async function copyStatusSummary(event) {
    const button = event.currentTarget;
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(statusSummary());
      button.textContent = 'Status copied';
    } catch {
      const area = document.createElement('textarea');
      area.value = statusSummary();
      area.className = 'ct-visually-hidden';
      document.body.append(area);
      area.select();
      document.execCommand('copy');
      area.remove();
      button.textContent = 'Status copied';
    }
    setTimeout(() => { button.textContent = original; }, 1800);
  }

  function startRefreshLoop() {
    clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      const automatic = query('#autoRefresh');
      if (!automatic || automatic.checked) hydrate();
    }, REFRESH_MS);
    query('#refresh')?.addEventListener('click', () => setTimeout(() => hydrate({ force: true }), 250));
  }

  function init() {
    addShells();
    hydrate();
    startRefreshLoop();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
