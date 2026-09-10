(() => {
  'use strict';

  const VERSION = '4.0.0';
  const PAGE_SIZE = 60;
  const REFRESH_MS = 30_000;
  const ENDPOINTS = Object.freeze({
    estate: '/api/estate?limit=1000',
    command: '/api/command?limit=12',
    operations: '/api/operations?window=24',
    catalog: '/api/catalog',
    health: '/api/health',
  });
  const state = {
    estate: null,
    command: null,
    operations: null,
    catalog: null,
    health: null,
    query: '',
    family: 'all',
    source: 'all',
    visibility: 'all',
    visible: PAGE_SIZE,
    hydratedAt: null,
  };
  const number = new Intl.NumberFormat('en-US');
  let timer = null;
  let hydrating = false;

  function el(tag, className = '', content = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== '') node.textContent = String(content);
    return node;
  }

  function text(node, value) {
    if (node) node.textContent = String(value ?? '—');
  }

  function formatNumber(value, fallback = '—') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? number.format(parsed) : fallback;
  }

  function percent(numerator, denominator) {
    const top = Number(numerator);
    const bottom = Number(denominator);
    return Number.isFinite(top) && Number.isFinite(bottom) && bottom > 0
      ? `${((top / bottom) * 100).toFixed(4)}%`
      : '—';
  }

  function humanize(value) {
    return String(value || 'unknown')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function tone(value) {
    const stateValue = String(value || '').toUpperCase();
    if (['FAILED','ERROR','STALE','HOLD','REQUIRED_NOT','UNAVAILABLE'].some((token) => stateValue.includes(token))) return 'hold';
    if (['PARTIAL','PENDING','REQUIRED','BOUNDED','SAMPLED','MINIMUM'].some((token) => stateValue.includes(token))) return 'attention';
    if (['PASS','ACTIVE','PRODUCTION','VERIFIED','ENFORCED','OPERATIONAL','INDEXED','INSTALLED'].some((token) => stateValue.includes(token))) return 'pass';
    return 'attention';
  }

  function pathIsEstate() {
    return /^\/estate(?:\.html)?\/?$/i.test(location.pathname);
  }

  function installNavigation() {
    const nav = document.querySelector('#nav');
    if (nav && !nav.querySelector('[data-estate-link]')) {
      const link = el('a');
      link.href = '/estate';
      link.dataset.estateLink = '';
      link.append(el('b', '', '79'), document.createTextNode('Estate'));
      nav.append(link);
    }
  }

  function buildPage() {
    const workspace = document.querySelector('.workspace');
    if (!workspace) return null;
    let page = document.querySelector('[data-page="estate"]');
    if (page) return page;

    page = el('section', 'page ct-estate-page');
    page.dataset.page = 'estate';
    page.id = 'ctEstatePage';
    page.innerHTML = `
      <div class="page-header">
        <div><p class="eyebrow">Governed estate atlas</p><h2>Every system class. One searchable command surface.</h2><p>Authoritative counts, names, health, lineage, and visibility tiers across CrownThrive—without turning credentials, private correspondence, balances, identities, or raw payloads into public data.</p></div>
        <div class="ct-estate-actions"><a href="/api/estate" target="_blank" rel="noreferrer noopener">Raw estate index ↗</a><button type="button" id="ctEstateRefresh">Refresh</button><button type="button" id="ctEstateCopy">Copy census</button></div>
      </div>
      <div class="ct-estate-shell">
        <section class="ct-estate-hero">
          <div><p class="eyebrow">CrownThrive Convergent Ecosystem</p><h2>Governed visibility—not a dangerous raw-data dump.</h2><p>Command v4 indexes DAIL, CHLOM Wallet, ledgers, fabrics, meshes, bridges, routers, factories, builders, plugins, connectors, repositories, contracts, runtimes, schedules, documents, storage, commerce, and source custody. The existence and operating state of restricted classes are visible; their protected values remain behind explicit authority.</p></div>
          <div class="ct-estate-hero-side">
            <div class="ct-estate-release"><span>Command release</span><strong>v4 · Governed Estate</strong><small id="ctEstateObserved">Reading authoritative sources…</small></div>
            <div class="ct-estate-visibility">
              <div class="ct-estate-tier" data-tier="public"><b>Public</b><small>Safe counts, names, boundaries, and status.</small></div>
              <div class="ct-estate-tier" data-tier="operator"><b>Operator</b><small>Authenticated indexes, lineage, ownership, and evidence.</small></div>
              <div class="ct-estate-tier" data-tier="restricted"><b>Restricted</b><small>Secrets, PII, bodies, balances, identifiers, and raw payloads.</small></div>
            </div>
          </div>
        </section>

        <section class="ct-estate-metrics" id="ctEstateMetrics"></section>

        <section class="ct-estate-section">
          <div class="ct-estate-section-head"><div><p class="eyebrow">Indexed object families</p><h3>System scale by governed family</h3><p>These are overlapping database-object indexes. A table or routine can belong to more than one family; the totals are not unique-system counts.</p></div><span class="ct-estate-badge" data-tone="attention">OVERLAPPING INDEX</span></div>
          <div class="ct-estate-family-grid" id="ctEstateFamilies"></div>
        </section>

        <section class="ct-estate-section">
          <div class="ct-estate-section-head"><div><p class="eyebrow">Live institutional state</p><h3>Command, wallet, DAIL, operations, commerce, and provider fabric</h3><p>Live overlays remain separate from the bounded census so a historical inventory cannot masquerade as present health.</p></div><span class="ct-estate-badge" id="ctEstateLiveState" data-tone="attention">READING</span></div>
          <div class="ct-estate-live-grid" id="ctEstateLiveGrid"></div>
          <div class="ct-estate-assurance">
            <div><strong>Three DAIL verified-prefix progress</strong><progress id="ctEstateDailProgress" max="1" value="0">0%</progress><div class="ct-estate-assurance-meta"><span id="ctEstateVerified">Verified: —</span><span id="ctEstateHead">Head: —</span><span id="ctEstateLag">Lag: —</span><span id="ctEstateSegments">Segments: —</span><span id="ctEstateAnchor">Anchor: —</span></div></div>
            <div class="ct-estate-assurance-score"><strong id="ctEstateDailPercent">—</strong><small id="ctEstateDailState">READING</small></div>
          </div>
        </section>

        <section class="ct-estate-section">
          <div class="ct-estate-section-head"><div><p class="eyebrow">DAIL topology</p><h3>Primary and supporting evidence systems</h3><p>Row totals are bounded census estimates. Delivery is not claimed until the current DAIL receipt and checkpoint predicates pass.</p></div><span class="ct-estate-badge" id="ctDailSystemCount" data-tone="attention">READING</span></div>
          <div class="ct-estate-table-wrap"><table class="ct-estate-table"><thead><tr><th>System</th><th>Role</th><th>Class</th><th>Lane</th><th>Estimated rows</th><th>Visibility</th></tr></thead><tbody id="ctEstateDailTable"></tbody></table></div>
        </section>

        <section class="ct-estate-section">
          <div class="ct-estate-section-head"><div><p class="eyebrow">Estate explorer</p><h3>Search systems, software, plugins, contracts, documents, and boundaries</h3><p>Filter by family, source, or visibility tier. Restricted records disclose the protected class—not the protected value.</p></div><span class="ct-estate-badge" id="ctEstateRecordBadge" data-tone="attention">READING</span></div>
          <div class="ct-estate-toolbar">
            <label class="ct-estate-control"><span>Search estate</span><input id="ctEstateSearch" type="search" placeholder="Search DAIL, fabric, wallet, contract, repository…" autocomplete="off"></label>
            <label class="ct-estate-control"><span>Family</span><select id="ctEstateFamily"><option value="all">All families</option></select></label>
            <label class="ct-estate-control"><span>Source</span><select id="ctEstateSource"><option value="all">All sources</option></select></label>
            <label class="ct-estate-control"><span>Visibility</span><select id="ctEstateVisibility"><option value="all">All tiers</option><option value="public">Public</option><option value="operator">Operator</option><option value="restricted">Restricted</option></select></label>
          </div>
          <div class="ct-estate-summary"><span id="ctEstateRecordSummary">Reading records…</span><span>Raw protected values remain outside the public surface.</span></div>
          <div class="ct-estate-records" id="ctEstateRecords"></div>
          <button class="ct-estate-load" type="button" id="ctEstateMore" hidden>Show more</button>
        </section>

        <section class="ct-estate-section">
          <div class="ct-estate-section-head"><div><p class="eyebrow">Source coverage</p><h3>What was crawled, what is live, and what remains restricted</h3><p>Coverage state is reported independently by source so sample bounds and authorization limits remain visible.</p></div><span class="ct-estate-badge" data-tone="attention">BOUNDED CENSUS</span></div>
          <div class="ct-estate-source-grid" id="ctEstateSources"></div>
          <div class="ct-estate-boundary"><span>◆</span><span><strong>No exceptions does not mean no security.</strong> Command exposes the estate map, system classes, counts, health, lineage, source coverage, and access tier. It does not publish secret values, private chats, personal email bodies, balances, wallet/account identifiers, customer data, private document bodies, signing material, or provider credentials.</span></div>
        </section>
      </div>`;
    workspace.append(page);

    document.querySelector('#ctEstateRefresh')?.addEventListener('click', () => hydrate(true));
    document.querySelector('#ctEstateCopy')?.addEventListener('click', copyCensus);
    document.querySelector('#ctEstateSearch')?.addEventListener('input', (event) => {
      state.query = event.currentTarget.value.trim().toLowerCase();
      state.visible = PAGE_SIZE;
      renderRecords();
    });
    document.querySelector('#ctEstateFamily')?.addEventListener('change', (event) => {
      state.family = event.currentTarget.value;
      state.visible = PAGE_SIZE;
      renderRecords();
    });
    document.querySelector('#ctEstateSource')?.addEventListener('change', (event) => {
      state.source = event.currentTarget.value;
      state.visible = PAGE_SIZE;
      renderRecords();
    });
    document.querySelector('#ctEstateVisibility')?.addEventListener('change', (event) => {
      state.visibility = event.currentTarget.value;
      state.visible = PAGE_SIZE;
      renderRecords();
    });
    document.querySelector('#ctEstateMore')?.addEventListener('click', () => {
      state.visible += PAGE_SIZE;
      renderRecords();
    });
    return page;
  }

  function activatePage() {
    if (!pathIsEstate()) return;
    document.querySelectorAll('.page').forEach((page) => page.classList.remove('active'));
    const page = document.querySelector('[data-page="estate"]');
    page?.classList.add('active');
    document.querySelectorAll('#nav a').forEach((link) => link.classList.toggle('active', link.hasAttribute('data-estate-link')));
    document.title = 'Governed Estate Atlas · CrownThrive Command';
  }

  async function fetchJson(url) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 18_000);
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
      clearTimeout(timeout);
    }
  }

  async function hydrate(force = false) {
    if (hydrating && !force) return;
    hydrating = true;
    const results = await Promise.allSettled([
      fetchJson(ENDPOINTS.estate),
      fetchJson(ENDPOINTS.command),
      fetchJson(ENDPOINTS.operations),
      fetchJson(ENDPOINTS.catalog),
      fetchJson(ENDPOINTS.health),
    ]);
    if (results[0].status === 'fulfilled') state.estate = results[0].value;
    if (results[1].status === 'fulfilled') state.command = results[1].value;
    if (results[2].status === 'fulfilled') state.operations = results[2].value;
    if (results[3].status === 'fulfilled') state.catalog = results[3].value;
    if (results[4].status === 'fulfilled') state.health = results[4].value;
    state.hydratedAt = new Date().toISOString();

    if (state.estate) {
      renderMetrics();
      renderFamilies();
      renderFilterOptions();
      renderRecords();
      renderSources();
      renderDailTable();
    } else {
      renderEstateError();
    }
    renderLive();
    text(document.querySelector('#ctEstateObserved'), `Snapshot ${formatTime(state.estate?.provenance?.snapshot_at)} · live overlay ${formatTime(state.hydratedAt)}`);
    hydrating = false;
    window.dispatchEvent(new CustomEvent('ct:estate-v4-hydrated', { detail: { version: VERSION, observedAt: state.hydratedAt } }));
  }

  function formatTime(value) {
    const date = new Date(value || '');
    if (!Number.isFinite(date.getTime())) return 'not observed';
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short',
    }).format(date);
  }

  function renderMetrics() {
    const root = document.querySelector('#ctEstateMetrics');
    const census = state.estate?.census || {};
    const database = census.database || {};
    if (!root) return;
    const metrics = [
      ['Schemas', database.schemas, 'Authoritative namespaces'],
      ['Tables', database.tables, 'Persistent and partitioned'],
      ['Routines', database.routines, 'Functions and procedures'],
      ['Active jobs', database.cron_jobs_active, `${formatNumber(database.cron_jobs_total)} total schedules`],
      ['Storage', database.storage_buckets, `${formatNumber(database.storage_buckets_private)} private buckets`],
      ['Repositories', census.github_repositories_observed, 'GitHub census'],
      ['Providers', census.capability_providers_discoverable, 'Discoverable connectors'],
    ];
    root.replaceChildren(...metrics.map(([label, value, detail]) => {
      const card = el('article', 'ct-estate-metric');
      card.append(el('span', '', label), el('strong', '', formatNumber(value)), el('small', '', detail));
      return card;
    }));
  }

  function renderFamilies() {
    const root = document.querySelector('#ctEstateFamilies');
    if (!root) return;
    const families = state.estate?.census?.indexed_object_families || {};
    const labels = {
      dail: 'DAIL',
      wallet_ledger_treasury: 'Wallet / ledger / treasury',
      fabric_mesh_bridge_router: 'Fabric / mesh / bridge / router',
      factory_builder_generator: 'Factory / builder / generator',
      plugin_connector_integration: 'Plugin / connector / integration',
      contract_policy_license: 'Contract / policy / license',
      runtime_scheduler_queue: 'Runtime / scheduler / queue',
      registry_catalog_census: 'Registry / catalog / census',
      agent_penta_oracle: 'Agent / Penta / oracle',
    };
    root.replaceChildren(...Object.entries(families).map(([key, count]) => {
      const card = el('article', 'ct-estate-family-card');
      card.append(el('span', '', labels[key] || humanize(key)), el('strong', '', formatNumber(count)), el('small', '', 'Indexed database objects'));
      return card;
    }));
  }

  function renderLive() {
    const root = document.querySelector('#ctEstateLiveGrid');
    if (!root) return;
    const command = state.command || {};
    const wallet = command.wallet || {};
    const assurance = command.dail?.assurance || {};
    const operations = state.operations || {};
    const catalog = state.catalog || {};
    const health = state.health || {};
    const metrics = [
      ['Command', command.status || 'READBACK HOLD', command.source?.state || 'Aggregate state'],
      ['Wallet gate', wallet.enforcement_state || 'UNOBSERVED', `${formatNumber(wallet.inventory?.service_bindings)} bindings · ${formatNumber(wallet.inventory?.gate_receipts)} receipts`],
      ['Wallets / ledgers', `${formatNumber(wallet.inventory?.active_wallets)}/${formatNumber(wallet.inventory?.verified_internal_accounts)}`, 'Aggregate only; identifiers and balances restricted'],
      ['Canary', `${formatNumber(wallet.latest_canary?.pass_count)}/${formatNumber(wallet.latest_canary?.case_count)}`, `${formatNumber(wallet.latest_canary?.fail_count)} failures`],
      ['24-hour events', formatNumber(operations.activity?.total_events), `${formatNumber(operations.activity?.penta_super_runs)} PentaSuper runs`],
      ['Commercial products', formatNumber(catalog.active_product_count), `${formatNumber(catalog.active_checkout_count)} checkout options`],
      ['Providers', `${formatNumber(operations.stats?.active_providers)}/${formatNumber(operations.stats?.registered_providers)}`, health.vercel_provider_state || 'Provider fabric'],
      ['Command health', health.status || health.public_state || 'UNOBSERVED', health.pass_manufactured === false ? 'No manufactured PASS' : 'Boundary readback'],
    ];
    root.replaceChildren(...metrics.map(([label, value, detail]) => {
      const card = el('article', 'ct-estate-live');
      card.dataset.tone = tone(value);
      card.append(el('span', '', label), el('strong', '', value), el('small', '', detail));
      return card;
    }));

    const liveState = document.querySelector('#ctEstateLiveState');
    const liveStatus = command.status || (state.command ? 'PARTIAL' : 'READBACK HOLD');
    if (liveState) {
      liveState.dataset.tone = tone(liveStatus);
      liveState.textContent = liveStatus;
    }

    const head = Number(assurance.current_head_sequence_id || 0);
    const verified = Number(assurance.verified_through_sequence_id || 0);
    const progress = document.querySelector('#ctEstateDailProgress');
    if (progress) {
      progress.max = Math.max(1, head);
      progress.value = Math.min(head, verified);
    }
    text(document.querySelector('#ctEstateDailPercent'), percent(verified, head));
    text(document.querySelector('#ctEstateDailState'), humanize(assurance.integrity_state || 'unobserved'));
    text(document.querySelector('#ctEstateVerified'), `Verified: ${formatNumber(verified)}`);
    text(document.querySelector('#ctEstateHead'), `Head: ${formatNumber(head)}`);
    text(document.querySelector('#ctEstateLag'), `Lag: ${formatNumber(assurance.sequence_span_lag)}`);
    text(document.querySelector('#ctEstateSegments'), `Segments: ${formatNumber(assurance.v4_segment_count)}`);
    text(document.querySelector('#ctEstateAnchor'), `Anchor: ${humanize(assurance.public_chain_anchor_state)}`);
  }

  function renderFilterOptions() {
    const records = state.estate?.records || [];
    const familySelect = document.querySelector('#ctEstateFamily');
    const sourceSelect = document.querySelector('#ctEstateSource');
    if (familySelect && familySelect.options.length === 1) {
      const families = [...new Set(records.map((record) => record.family).filter(Boolean))].sort();
      familySelect.append(...families.map((value) => {
        const option = el('option', '', humanize(value));
        option.value = value;
        return option;
      }));
    }
    if (sourceSelect && sourceSelect.options.length === 1) {
      const sources = [...new Set(records.map((record) => record.source).filter(Boolean))].sort();
      sourceSelect.append(...sources.map((value) => {
        const option = el('option', '', value);
        option.value = value;
        return option;
      }));
    }
  }

  function matchingRecords() {
    const records = state.estate?.records || [];
    return records.filter((record) => {
      if (state.family !== 'all' && record.family !== state.family) return false;
      if (state.source !== 'all' && record.source !== state.source) return false;
      if (state.visibility !== 'all' && record.visibility !== state.visibility) return false;
      if (!state.query) return true;
      const haystack = [record.name,record.family,record.source,record.visibility,record.status,record.kind,record.description]
        .join(' ').toLowerCase();
      return haystack.includes(state.query);
    }).sort((left, right) => {
      const tier = { public: 0, operator: 1, restricted: 2 };
      return (tier[left.visibility] ?? 3) - (tier[right.visibility] ?? 3)
        || String(left.family).localeCompare(String(right.family))
        || String(left.name).localeCompare(String(right.name));
    });
  }

  function renderRecords() {
    const root = document.querySelector('#ctEstateRecords');
    if (!root) return;
    const records = matchingRecords();
    const shown = records.slice(0, state.visible);
    root.replaceChildren(...shown.map(recordCard));
    if (!shown.length) root.append(el('div', 'ct-estate-empty', 'No governed estate record matches the current filters.'));
    text(document.querySelector('#ctEstateRecordSummary'), `${formatNumber(shown.length)} of ${formatNumber(records.length)} matching records · ${formatNumber(state.estate?.total_records)} indexed records in this public-safe snapshot`);
    const badge = document.querySelector('#ctEstateRecordBadge');
    if (badge) {
      badge.dataset.tone = 'attention';
      badge.textContent = `${formatNumber(records.length)} MATCHING`;
    }
    const more = document.querySelector('#ctEstateMore');
    if (more) {
      more.hidden = shown.length >= records.length;
      more.textContent = `Show ${formatNumber(Math.min(PAGE_SIZE, records.length - shown.length))} more`;
    }
  }

  function recordCard(record) {
    const card = el('article', 'ct-estate-record');
    const head = el('div', 'ct-estate-record-head');
    head.append(el('span', 'ct-estate-record-family', humanize(record.family)), visibilityPill(record.visibility));
    card.append(head, el('h4', '', record.name), el('p', '', record.description || 'Governed estate record.'));
    const footer = el('div', 'ct-estate-record-footer');
    footer.append(el('span', 'ct-estate-record-source', `${record.source} · ${humanize(record.status)}`));
    if (record.count !== undefined && record.count !== null) footer.append(el('span', 'ct-estate-record-count', formatNumber(record.count)));
    card.append(footer);
    return card;
  }

  function visibilityPill(value) {
    const pill = el('span', 'ct-estate-visibility-pill', value || 'operator');
    pill.dataset.tier = value || 'operator';
    return pill;
  }

  function renderSources() {
    const root = document.querySelector('#ctEstateSources');
    if (!root) return;
    const sources = state.estate?.source_coverage || [];
    root.replaceChildren(...sources.map((source) => {
      const card = el('article', 'ct-estate-source');
      card.append(el('strong', '', source.source), el('span', '', humanize(source.state)), el('small', '', source.coverage));
      return card;
    }));
  }

  function renderDailTable() {
    const body = document.querySelector('#ctEstateDailTable');
    if (!body) return;
    const primary = state.estate?.dail?.primary_systems || [];
    const supporting = state.estate?.dail?.supporting_systems || [];
    const rows = [
      ...primary.map((system) => ({ name: system.name, id: system.id, role: 'Primary', class: system.class, lane: system.lane, count: system.estimated_rows, visibility: 'Operator' })),
      ...supporting.map((name) => ({ name, id: name, role: 'Supporting', class: 'Evidence', lane: 'Routing / lineage / delivery', count: null, visibility: 'Operator' })),
    ];
    body.replaceChildren(...rows.map((system) => {
      const row = el('tr');
      const name = el('td');
      name.append(el('strong', '', system.name), el('small', '', system.id));
      row.append(name, el('td', '', system.role), el('td', '', humanize(system.class)), el('td', '', system.lane), el('td', '', system.count === null ? 'Indexed' : formatNumber(system.count)), el('td', '', system.visibility));
      return row;
    }));
    const badge = document.querySelector('#ctDailSystemCount');
    if (badge) {
      badge.dataset.tone = 'pass';
      badge.textContent = `${formatNumber(rows.length)} SYSTEMS`;
    }
  }

  function renderEstateError() {
    const root = document.querySelector('#ctEstateRecords');
    if (root) root.replaceChildren(el('div', 'ct-estate-error', 'Estate census readback failed. No cached inventory or fabricated count was substituted.'));
    const badge = document.querySelector('#ctEstateRecordBadge');
    if (badge) {
      badge.dataset.tone = 'hold';
      badge.textContent = 'READBACK HOLD';
    }
  }

  async function copyCensus(event) {
    const button = event.currentTarget;
    const original = button.textContent;
    const estate = state.estate || {};
    const command = state.command || {};
    const wallet = command.wallet || {};
    const assurance = command.dail?.assurance || {};
    const database = estate.census?.database || {};
    const output = [
      `CrownThrive Command ${VERSION} · Governed Estate Atlas`,
      `Estate status: ${estate.status || 'UNOBSERVED'} · Command status: ${command.status || 'UNOBSERVED'}`,
      `Database: ${formatNumber(database.schemas)} schemas · ${formatNumber(database.tables)} tables · ${formatNumber(database.routines)} routines`,
      `Scheduling: ${formatNumber(database.cron_jobs_active)} active / ${formatNumber(database.cron_jobs_total)} total jobs`,
      `Storage: ${formatNumber(database.storage_buckets)} buckets · ${formatNumber(database.storage_buckets_private)} private`,
      `Software: ${formatNumber(estate.census?.github_repositories_observed)} repositories observed`,
      `Connectors: ${formatNumber(estate.census?.capability_providers_discoverable)} capability providers discoverable`,
      `Wallet: ${wallet.enforcement_state || 'UNOBSERVED'} · ${formatNumber(wallet.inventory?.active_wallets)} wallets · ${formatNumber(wallet.inventory?.verified_internal_accounts)} verified accounts · ${formatNumber(wallet.inventory?.service_bindings)} bindings · ${formatNumber(wallet.inventory?.gate_receipts)} receipts`,
      `DAIL: ${formatNumber(assurance.verified_through_sequence_id)} verified / ${formatNumber(assurance.current_head_sequence_id)} head · ${formatNumber(assurance.sequence_span_lag)} pending`,
      `Visibility: PUBLIC safe aggregate · OPERATOR authenticated indexes · RESTRICTED secrets, private bodies, PII, balances, identifiers, and raw payloads`,
      `Observed: ${formatTime(state.hydratedAt)}`,
      'No credential, balance, wallet identifier, private communication body, personal data, signing material, or private document body is included.',
    ].join('\n');
    try {
      await navigator.clipboard.writeText(output);
    } catch {
      const area = el('textarea');
      area.value = output;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    button.textContent = 'Census copied';
    setTimeout(() => { button.textContent = original; }, 1600);
  }

  function startTimer() {
    clearInterval(timer);
    timer = setInterval(() => {
      if (pathIsEstate()) hydrate();
    }, REFRESH_MS);
  }

  function init() {
    document.documentElement.dataset.commandEstateVersion = VERSION;
    installNavigation();
    buildPage();
    activatePage();
    hydrate();
    startTimer();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
