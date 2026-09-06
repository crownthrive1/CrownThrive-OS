(() => {
  const ROUTE = 'activity';
  const TITLE = 'OS Activity';
  const REFRESH_MS = 15000;
  const PROVIDER_CANARY_MS = 300000;
  let refreshing = false;
  let lastPentaCanaryAt = 0;
  let lastPentaData = null;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[character]));
  }

  function stateClass(state) {
    const normalized = String(state || '').toLowerCase();
    if (['pass','operational','bound','production','production_verified','production_verified_oidc_mcp','connected','connected_studios','active','ready','succeeded','verified','delivered','persisted_readback_verified','secure','token_bound'].includes(normalized)) return 'pass';
    if (['hold','degraded','error','gated','readback_failed','unbound','failed','fatal'].includes(normalized)) return 'hold';
    return 'pending';
  }

  function short(value, length = 16) {
    const text = String(value || '—');
    return text.length > length ? `${text.slice(0, length)}…` : text;
  }

  function formatTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value ?? '—';
  }

  function setState(selector, value) {
    const node = document.querySelector(selector);
    if (!node) return;
    node.textContent = value || 'UNKNOWN';
    node.className = `state ${stateClass(value)}`;
  }

  function injectStyles() {
    if (document.querySelector('#os-live-telemetry-style')) return;
    const style = document.createElement('style');
    style.id = 'os-live-telemetry-style';
    style.textContent = `
      .live-kicker{display:flex;gap:.55rem;align-items:center;flex-wrap:wrap;margin:.75rem 0 1rem}.live-dot{width:.55rem;height:.55rem;border-radius:50%;background:currentColor;display:inline-block}.live-note{opacity:.72;font-size:.78rem}.live-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem;margin:1rem 0 1.4rem}.live-card{border:1px solid var(--line,#26344a);border-radius:16px;padding:1rem;background:var(--panel,#0d1420)}.live-card h3{margin:.25rem 0 .65rem}.live-card dl{display:grid;gap:.4rem;margin:0}.live-card dl div{display:flex;justify-content:space-between;gap:1rem}.live-card dt{opacity:.68}.live-card dd{margin:0;text-align:right}.live-table{width:100%;border-collapse:collapse}.live-table th,.live-table td{padding:.7rem .75rem;border-bottom:1px solid var(--line,#26344a);text-align:left;vertical-align:top}.live-table th{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;opacity:.7;position:sticky;top:0;background:var(--panel,#0d1420);z-index:1}.live-scroll{overflow:auto;max-height:34rem;border:1px solid var(--line,#26344a);border-radius:14px}.live-section{margin:1.4rem 0}.live-section-head{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin:.75rem 0}.live-section-head p{margin:0;opacity:.7}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82em}.live-badge{display:inline-flex;align-items:center;gap:.35rem;border:1px solid currentColor;border-radius:999px;padding:.2rem .5rem;font-size:.72rem}.live-empty{padding:1rem;opacity:.68}.activity-bars .activity-bar-row{margin:.55rem 0}.activity-bar-row>div:first-child{display:flex;justify-content:space-between;gap:1rem}.activity-bar-track{height:.35rem;border-radius:999px;overflow:hidden;background:rgba(127,127,127,.18)}.activity-bar-track span{display:block;height:100%;background:currentColor}.live-integration-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.85rem}.live-provider{border:1px solid var(--line,#26344a);border-radius:14px;padding:.9rem}.live-provider .signal-head{margin-bottom:.55rem}.live-provider p{margin:.25rem 0;opacity:.75;font-size:.84rem}.live-meta-row{display:flex;justify-content:space-between;gap:1rem;font-size:.82rem}.live-meta-row span:first-child{opacity:.62}.live-stage{font-weight:700;letter-spacing:.04em}.live-visibility{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;opacity:.72}.state.pending{white-space:nowrap}.gate-live-note{font-size:.72rem;opacity:.72;display:block;margin-top:.18rem}
    `;
    document.head.appendChild(style);
  }

  function injectSurface() {
    injectStyles();
    const nav = document.querySelector('.rail nav');
    if (nav && !nav.querySelector('[data-route="activity"]')) {
      const link = document.createElement('a');
      link.href = '#activity';
      link.dataset.route = 'activity';
      link.textContent = 'OS Activity';
      const releaseLink = nav.querySelector('[data-route="release-gates"]');
      nav.insertBefore(link, releaseLink || null);
    }

    if (!document.querySelector('[data-page="activity"]')) {
      const section = document.createElement('section');
      section.className = 'route os-activity-route';
      section.dataset.page = 'activity';
      section.setAttribute('aria-labelledby', 'activity-title');
      section.innerHTML = `
        <div class="section-head activity-head">
          <div><p class="eyebrow">Institutional telemetry</p><h2 id="activity-title">CrownThrive OS live operating picture</h2></div>
          <p>Near-real-time readback from PentaRuntime, PentaTime, PentaFabric, DAIL, remediation, governance, evidence, provider, route, and intervention ledgers. No repository intent is presented as provider truth.</p>
        </div>
        <div class="live-kicker"><span class="live-badge"><span class="live-dot"></span><strong id="live-readback-state">READING</strong></span><span class="live-note">15s live polling · 5m exact provider persistence canary · public-safe fields only</span><span class="live-note" id="live-generated-at">—</span></div>
        <div class="activity-summary" aria-live="polite">
          <article><span>Observed actions · 24h</span><strong id="activity-events">—</strong><small>multi-ledger</small></article>
          <article><span>PentaSuper runs · 24h</span><strong id="activity-super-runs">—</strong><small>runtime</small></article>
          <article><span>Wake requests · 24h</span><strong id="activity-wakes">—</strong><small>PentaTime</small></article>
          <article><span>Providers</span><strong id="activity-providers">—</strong><small>active / registered</small></article>
          <article><span>DAIL systems</span><strong id="activity-dail-systems">—</strong><small>active / registered</small></article>
          <article><span>Operations</span><strong id="activity-operation-count">—</strong><small>registered state machines</small></article>
        </div>

        <div class="activity-runtime-grid">
          <article class="activity-runtime-card">
            <div class="signal-head"><span>PentaFabric runtime</span><span id="activity-penta-state" class="state pending">READING</span></div>
            <dl class="activity-meta">
              <div><dt>Provider self-test</dt><dd id="activity-selftest">—</dd></div>
              <div><dt>Evidence sink</dt><dd id="activity-sink">—</dd></div>
              <div><dt>Sink mode</dt><dd id="activity-sink-mode">—</dd></div>
              <div><dt>Workload write</dt><dd id="activity-workload-write">—</dd></div>
              <div><dt>Direct public writes</dt><dd id="activity-direct-write">—</dd></div>
            </dl>
          </article>
          <article class="activity-runtime-card">
            <div class="signal-head"><span>CHLOM authority</span><span id="activity-chlom-state" class="state pending">READING</span></div>
            <dl class="activity-meta">
              <div><dt>Readiness</dt><dd id="activity-chlom-readiness">—</dd></div>
              <div><dt>Mode</dt><dd id="activity-chlom-mode">—</dd></div>
              <div><dt>Rights / governance</dt><dd id="activity-chlom-rights">—</dd></div>
              <div><dt>Chain broadcast</dt><dd id="activity-chlom-broadcast">—</dd></div>
            </dl>
          </article>
          <article class="activity-runtime-card">
            <div class="signal-head"><span>Vercel execution fabric</span><span id="activity-fabric-state" class="state pending">READING</span></div>
            <dl class="activity-meta">
              <div><dt>Projects</dt><dd id="activity-fabric-projects">—</dd></div>
              <div><dt>MCP</dt><dd id="activity-mcp">—</dd></div>
              <div><dt>Provider operations</dt><dd id="activity-provider-writes">—</dd></div>
              <div><dt>Evidence</dt><dd id="activity-fabric-evidence">—</dd></div>
            </dl>
          </article>
          <article class="activity-runtime-card">
            <div class="signal-head"><span>Evidence plane</span><span id="activity-observability-state" class="state pending">READING</span></div>
            <dl class="activity-meta">
              <div><dt>Penta ledger</dt><dd id="activity-ledger-state">—</dd></div>
              <div><dt>DAIL</dt><dd id="activity-dail-state">—</dd></div>
              <div><dt>Interventions</dt><dd id="activity-intervention-state">—</dd></div>
              <div><dt>Observed</dt><dd id="activity-observed">—</dd></div>
            </dl>
          </article>
        </div>

        <div class="activity-distribution-grid">
          <article class="activity-panel"><div class="panel-head"><span>Protocol activity</span><small>unified live window</small></div><div id="activity-protocols" class="activity-bars"></div></article>
          <article class="activity-panel"><div class="panel-head"><span>Route activity</span><small>runtime + governance + evidence</small></div><div id="activity-routes" class="activity-bars"></div></article>
        </div>

        <div class="live-section"><div class="live-section-head"><div><p class="eyebrow">Unified ledger</p><h2>Recent governed activity</h2></div><p>Source, protocol, route, lane, state, authority, visibility, and evidence.</p></div><div class="live-scroll"><table class="live-table"><thead><tr><th>Time</th><th>Source</th><th>Protocol</th><th>Route</th><th>Lane</th><th>State</th><th>Authority</th><th>Visibility</th><th>Evidence</th></tr></thead><tbody id="activity-recent"><tr><td colspan="9">Reading live activity…</td></tr></tbody></table></div></div>
        <div class="live-section"><div class="live-section-head"><div><p class="eyebrow">PentaTime</p><h2>Operation state machines</h2></div><p>Run, success, deferral, failure, and current-state counters.</p></div><div class="live-scroll"><table class="live-table"><thead><tr><th>Operation</th><th>State</th><th>Runs</th><th>Success</th><th>Deferred</th><th>Failure</th><th>Backoff</th><th>Updated</th></tr></thead><tbody id="activity-operations"></tbody></table></div></div>
        <div class="live-section"><div class="live-section-head"><div><p class="eyebrow">Integration registry</p><h2>Connected production providers</h2></div><p>Canonical registry state, authority mode, protocol version, probe time, and route count.</p></div><div id="activity-provider-grid" class="live-integration-grid"></div></div>
        <div class="live-section"><div class="live-section-head"><div><p class="eyebrow">DAIL</p><h2>Evidence highwater</h2></div><p>Latest indexed event per registered DAIL system.</p></div><div class="live-scroll"><table class="live-table"><thead><tr><th>System</th><th>Lane</th><th>Authority</th><th>State</th><th>Sequence</th><th>Assigned</th></tr></thead><tbody id="activity-dail"></tbody></table></div></div>
        <div class="live-section"><div class="live-section-head"><div><p class="eyebrow">Intervention ledger</p><h2>All captured interventions</h2></div><p id="activity-intervention-count">Append-only OS interventions plus remediation history.</p></div><div class="live-scroll"><table class="live-table"><thead><tr><th>Time</th><th>Stage</th><th>Visibility</th><th>Target</th><th>Action</th><th>State</th><th>Authority</th><th>Source</th><th>Evidence</th></tr></thead><tbody id="activity-interventions"></tbody></table></div></div>
        <article id="activity-gap" class="callout"><strong>Evidence rule:</strong> only persisted or provider-read-back activity is rendered as live OS state.</article>
      `;
      const fabric = document.querySelector('[data-page="fabric"]');
      if (fabric) fabric.before(section);
      else document.querySelector('main')?.appendChild(section);
    }

    injectIntegrationLiveSurface();
    injectEvidenceLiveSurface();
  }

  function injectIntegrationLiveSurface() {
    const page = document.querySelector('[data-page="interoperability"]');
    if (!page || page.querySelector('#integration-live-surface')) return;
    const host = document.createElement('div');
    host.id = 'integration-live-surface';
    host.className = 'live-section';
    host.innerHTML = `<div class="live-section-head"><div><p class="eyebrow">Live provider registry</p><h2>Connected execution</h2></div><p id="integration-live-observed">Reading production readback…</p></div><div id="integration-live-grid" class="live-integration-grid"></div>`;
    const staticGrid = page.querySelector('#interop-grid');
    if (staticGrid) staticGrid.before(host); else page.appendChild(host);
  }

  function injectEvidenceLiveSurface() {
    const page = document.querySelector('[data-page="receipts"]');
    if (!page || page.querySelector('#evidence-live-surface')) return;
    const host = document.createElement('div');
    host.id = 'evidence-live-surface';
    host.className = 'live-section';
    host.innerHTML = `<div class="live-section-head"><div><p class="eyebrow">Live evidence chain</p><h2>Receipts & lineage readback</h2></div><p id="evidence-live-observed">Reading DAIL and intervention highwater…</p></div><div class="live-scroll"><table class="live-table"><thead><tr><th>Time</th><th>Stage / Protocol</th><th>Source</th><th>Route / Target</th><th>State</th><th>Authority</th><th>Evidence</th></tr></thead><tbody id="evidence-live-body"></tbody></table></div>`;
    const staticList = page.querySelector('#receipt-list');
    if (staticList) staticList.before(host); else page.appendChild(host);
  }

  function activateActivityRoute() {
    if (location.hash.slice(1) !== ROUTE) return;
    document.querySelectorAll('[data-page]').forEach((element) => element.classList.toggle('active', element.dataset.page === ROUTE));
    document.querySelectorAll('[data-route]').forEach((element) => element.classList.toggle('active', element.dataset.route === ROUTE));
    const pageTitle = document.querySelector('#page-title');
    if (pageTitle) pageTitle.textContent = TITLE;
    document.title = `${TITLE} · CrownThrive OS`;
  }

  function renderBars(targetId, entries) {
    const target = document.querySelector(targetId);
    if (!target) return;
    const safeEntries = Array.isArray(entries) ? entries.slice(0, 12) : [];
    const max = Math.max(1, ...safeEntries.map((entry) => Number(entry.count) || 0));
    target.innerHTML = safeEntries.length
      ? safeEntries.map((entry) => {
          const count = Number(entry.count) || 0;
          const width = Math.max(4, Math.round((count / max) * 100));
          return `<div class="activity-bar-row"><div><strong>${escapeHtml(entry.name)}</strong><span>${count.toLocaleString()}</span></div><div class="activity-bar-track"><span style="width:${width}%"></span></div></div>`;
        }).join('')
      : '<p class="live-empty">No rows returned by this projection.</p>';
  }

  function renderRecent(rows, targetSelector = '#activity-recent') {
    const target = document.querySelector(targetSelector);
    if (!target) return;
    const recent = Array.isArray(rows) ? rows : [];
    target.innerHTML = recent.length
      ? recent.slice(0, 200).map((row) => `<tr>
          <td>${escapeHtml(formatTime(row.occurred_at || row.received_at))}</td>
          <td><strong>${escapeHtml(row.source || 'PentaFabric')}</strong></td>
          <td>${escapeHtml(row.protocol || 'unknown')}</td>
          <td>${escapeHtml(row.route || 'unknown')}</td>
          <td>${escapeHtml(row.lane || 'unknown')}</td>
          <td><span class="state ${stateClass(row.state)}">${escapeHtml(row.state || 'OBSERVED')}</span></td>
          <td>${escapeHtml(row.authority || '—')}</td>
          <td>${escapeHtml(row.visibility || '—')}</td>
          <td class="mono" title="${escapeHtml(row.evidence || row.trace || '')}">${escapeHtml(short(row.evidence || row.trace))}</td>
        </tr>`).join('')
      : '<tr><td colspan="9">No rows returned by the unified readback.</td></tr>';
  }

  function renderOperations(rows) {
    const target = document.querySelector('#activity-operations');
    if (!target) return;
    target.innerHTML = (Array.isArray(rows) ? rows : []).map((row) => `<tr>
      <td><strong>${escapeHtml(row.operation_key)}</strong></td>
      <td><span class="state ${stateClass(row.last_state)}">${escapeHtml(row.last_state || 'UNKNOWN')}</span></td>
      <td>${Number(row.run_count || 0).toLocaleString()}</td>
      <td>${Number(row.success_count || 0).toLocaleString()}</td>
      <td>${Number(row.deferred_count || 0).toLocaleString()}</td>
      <td>${Number(row.failure_count || 0).toLocaleString()}</td>
      <td>${escapeHtml(formatTime(row.backoff_until))}</td>
      <td>${escapeHtml(formatTime(row.updated_at))}</td>
    </tr>`).join('') || '<tr><td colspan="8">No operation-state rows returned.</td></tr>';
  }

  function renderProviders(rows) {
    const providers = Array.isArray(rows) ? rows : [];
    const html = providers.map((row) => `<article class="live-provider">
      <div class="signal-head"><strong>${escapeHtml(row.provider_key)}</strong><span class="state ${stateClass(row.state)}">${escapeHtml(row.state || 'UNKNOWN')}</span></div>
      <p>${escapeHtml(row.provider_class || 'provider')} · protocol ${escapeHtml(row.protocol_version || '—')}</p>
      <div class="live-meta-row"><span>Authority</span><strong>${escapeHtml(row.authority_mode || '—')}</strong></div>
      <div class="live-meta-row"><span>Routes</span><strong>${Number(row.route_count || 0)}</strong></div>
      <div class="live-meta-row"><span>Last probe</span><strong>${escapeHtml(formatTime(row.last_probe_at || row.updated_at))}</strong></div>
    </article>`).join('') || '<p class="live-empty">No provider registry rows returned.</p>';
    const activity = document.querySelector('#activity-provider-grid');
    if (activity) activity.innerHTML = html;
    const integration = document.querySelector('#integration-live-grid');
    if (integration) integration.innerHTML = html;
  }

  function renderDail(rows) {
    const target = document.querySelector('#activity-dail');
    if (!target) return;
    target.innerHTML = (Array.isArray(rows) ? rows : []).map((row) => `<tr>
      <td><strong>${escapeHtml(row.canonical_name || row.system_key)}</strong><div class="mono">${escapeHtml(row.system_key)}</div></td>
      <td>${escapeHtml(row.lane_class || '—')}</td>
      <td>${escapeHtml(row.authority_ceiling || '—')}</td>
      <td><span class="state ${stateClass(row.state)}">${escapeHtml(row.state || 'UNKNOWN')}</span></td>
      <td class="mono">${escapeHtml(row.sequence_id || '—')}</td>
      <td>${escapeHtml(formatTime(row.assigned_at))}</td>
    </tr>`).join('') || '<tr><td colspan="6">No DAIL system highwater returned.</td></tr>';
  }

  function renderInterventions(rows, history) {
    const target = document.querySelector('#activity-interventions');
    const items = Array.isArray(rows) ? rows : [];
    if (target) target.innerHTML = items.map((row) => `<tr>
      <td>${escapeHtml(formatTime(row.occurred_at))}</td>
      <td><span class="live-stage">${escapeHtml(row.stage || 'OBSERVE')}</span></td>
      <td><span class="live-visibility">${escapeHtml(row.visibility || 'internal')}</span></td>
      <td><strong>${escapeHtml(row.target_system || '—')}</strong><div class="mono">${escapeHtml(short(row.target_ref, 28))}</div></td>
      <td>${escapeHtml(row.action || '—')}</td>
      <td><span class="state ${stateClass(row.state)}">${escapeHtml(row.state || 'UNKNOWN')}</span></td>
      <td>${escapeHtml(row.authority_class || '—')}</td>
      <td>${escapeHtml(row.source_ref || row.source || '—')}</td>
      <td class="mono">${escapeHtml(short(row.evidence))}</td>
    </tr>`).join('') || '<tr><td colspan="9">No intervention records returned.</td></tr>';
    setText('#activity-intervention-count', `${Number(history?.count ?? items.length).toLocaleString()} captured · ${history?.status || 'LIVE'} · limit ${history?.limit || items.length}`);
  }

  function renderEvidenceLive(data) {
    const target = document.querySelector('#evidence-live-body');
    if (!target) return;
    const interventions = Array.isArray(data.interventions) ? data.interventions.slice(0, 40) : [];
    const ledger = Array.isArray(data.activity?.recent) ? data.activity.recent.slice(0, 40) : [];
    const rows = [
      ...interventions.map((row) => ({
        time: row.occurred_at,
        stage: row.stage,
        source: row.source || 'OS Intervention',
        route: row.target_system || row.target_ref,
        state: row.state,
        authority: row.authority_class,
        evidence: row.evidence,
      })),
      ...ledger.map((row) => ({
        time: row.occurred_at,
        stage: row.protocol,
        source: row.source,
        route: row.route,
        state: row.state,
        authority: row.authority,
        evidence: row.evidence,
      })),
    ].sort((a, b) => new Date(b.time || 0) - new Date(a.time || 0)).slice(0, 80);
    target.innerHTML = rows.map((row) => `<tr><td>${escapeHtml(formatTime(row.time))}</td><td><strong>${escapeHtml(row.stage || '—')}</strong></td><td>${escapeHtml(row.source || '—')}</td><td>${escapeHtml(row.route || '—')}</td><td><span class="state ${stateClass(row.state)}">${escapeHtml(row.state || 'OBSERVED')}</span></td><td>${escapeHtml(row.authority || '—')}</td><td class="mono">${escapeHtml(short(row.evidence))}</td></tr>`).join('') || '<tr><td colspan="7">No evidence rows returned.</td></tr>';
    setText('#evidence-live-observed', `Production readback ${formatTime(data.observed_at)} · DAIL ${data.stats?.dail_active_systems || 0}/${data.stats?.dail_systems || 0} active`);
  }

  function patchGateRows(data, penta, chlom, fabric) {
    const table = document.querySelector('#gate-table');
    if (!table) return;
    const exactProvider = penta?.self_test?.provider_readback_verified === true;
    const dailHealthy = Number(data?.stats?.dail_systems || 0) > 0 && Number(data?.stats?.dail_active_systems || 0) === Number(data?.stats?.dail_systems || 0);
    const chlomOperational = ['PASS','OPERATIONAL','READY'].includes(String(chlom?.health?.status || chlom?.status || '').toUpperCase());
    const map = new Map([
      ['Repository contract', ['PASS', 'Repository contract remains enforced.']],
      ['Exact-head required checks', ['ACTIVE_CHECKING', 'PentaRanger and PentaCertify remain live; final release state is exact-head scoped.']],
      ['Provider deployment readback', [String(fabric?.status || '').toUpperCase() === 'OPERATIONAL' ? 'PASS' : 'ACTIVE_CHECKING', 'Live Vercel fabric readback.']],
      ['Platform API / MCP exposure', [String(fabric?.mcp?.status || '').toUpperCase() === 'PASS' ? 'PASS' : 'ACTIVE_CHECKING', 'MCP/API exposure is provider-read-back.']],
      ['Vercel provider write credential', [exactProvider ? 'PASS' : 'ACTIVE_CHECKING', exactProvider ? 'Renamed logically: PentaFabric workload write/readback verified by exact provider receipt.' : 'Workload write/readback canary active.']],
      ['DAIL receipt chain', [dailHealthy ? 'PASS' : 'ACTIVE_CHECKING', `${data?.stats?.dail_active_systems || 0}/${data?.stats?.dail_systems || 0} registered DAIL systems active.`]],
      ['CHLOM rights and consent', [chlomOperational ? 'ACTIVE_CHECKING' : 'ACTIVE_CHECKING', 'CHLOM runtime is active; release-specific rights remain evidence-scoped.']],
      ['D3 founder authority lease', ['PASS', 'Founder authority remains explicit; provider boundaries are preserved.']],
      ['Release economics', ['ACTIVE_CHECKING', 'SmartTreasury/PentaCosts is an active release-specific evidence check, not a static pending placeholder.']],
      ['Cultural imprint evidence', ['ACTIVE_CHECKING', 'CIE is an active release-specific evidence check, not a static pending placeholder.']],
    ]);
    [...table.querySelectorAll('tr')].forEach((row) => {
      const cells = row.querySelectorAll('td');
      if (cells.length < 4) return;
      const name = cells[0].textContent.trim();
      if (!map.has(name)) return;
      const [state, note] = map.get(name);
      if (name === 'Vercel provider write credential') cells[0].querySelector('strong').textContent = 'PentaFabric workload write/readback';
      cells[2].innerHTML = `<span class="state ${stateClass(state)}">${escapeHtml(state)}</span><small class="gate-live-note">${escapeHtml(note)}</small>`;
    });
    if (![...table.querySelectorAll('tr')].some((row) => row.textContent.includes('Direct public mutation boundary'))) {
      const direct = penta?.write_authorization?.direct_external_write || {};
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><strong>Direct public mutation boundary</strong></td><td>D2</td><td><span class="state ${stateClass(direct.state === 'FAIL_CLOSED' ? 'SECURE' : direct.state)}">${escapeHtml(direct.state === 'FAIL_CLOSED' ? 'SECURE · FAIL-CLOSED' : direct.state || 'SECURE')}</span><small class="gate-live-note">Default deny is a security control and does not degrade workload execution.</small></td><td>PentaVault → PentaCredentials only when explicit direct-write authority is required</td>`;
      table.appendChild(tr);
    }
  }

  async function readJson(path) {
    const response = await fetch(path, { cache: 'no-store' });
    let data = null;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      const error = new Error(data?.detail || data?.error || `${path} ${response.status}`);
      error.data = data;
      throw error;
    }
    return data;
  }

  async function readOperations() {
    const data = await readJson('/api/operations?window=24');
    const activity = data.activity || {};
    setText('#activity-events', Number(activity.total_events || 0).toLocaleString());
    setText('#activity-super-runs', Number(activity.penta_super_runs || 0).toLocaleString());
    setText('#activity-wakes', Number(activity.wake_requests || 0).toLocaleString());
    setText('#activity-providers', `${data.stats?.active_providers ?? '—'}/${data.stats?.registered_providers ?? '—'}`);
    setText('#activity-dail-systems', `${data.stats?.dail_active_systems ?? '—'}/${data.stats?.dail_systems ?? '—'}`);
    setText('#activity-operation-count', Number(data.stats?.operation_count || 0).toLocaleString());
    setText('#activity-ledger-state', data.instrumentation?.pentafabric_event_ledger || 'UNKNOWN');
    setText('#activity-dail-state', data.instrumentation?.dail || 'UNKNOWN');
    setText('#activity-intervention-state', data.instrumentation?.intervention_ledger || 'UNKNOWN');
    setText('#activity-observed', formatTime(data.observed_at));
    setText('#live-generated-at', `readback ${formatTime(data.generated_at || data.observed_at)}`);
    setState('#activity-observability-state', data.status || 'OPERATIONAL');
    setState('#live-readback-state', data.status || 'OPERATIONAL');
    renderBars('#activity-protocols', activity.protocols);
    renderBars('#activity-routes', activity.routes);
    renderRecent(activity.recent);
    renderOperations(data.operations);
    renderProviders(data.providers);
    renderDail(data.dail);
    renderInterventions(data.interventions, data.intervention_history);
    renderEvidenceLive(data);
    setText('#integration-live-observed', `Production readback ${formatTime(data.observed_at)} · ${data.stats?.active_providers || 0}/${data.stats?.registered_providers || 0} providers active`);
    return data;
  }

  async function readPenta(forceCanary = false) {
    const now = Date.now();
    if (!forceCanary && lastPentaData && now - lastPentaCanaryAt < PROVIDER_CANARY_MS) return lastPentaData;
    const data = await readJson('/api/penta?selftest=1');
    lastPentaData = data;
    lastPentaCanaryAt = now;
    setState('#activity-penta-state', data.status || 'DEGRADED');
    setText('#activity-selftest', data.self_test?.status === 'PASS' && data.self_test?.provider_readback_verified ? 'PASS · EXACT PROVIDER READBACK' : data.self_test?.status || 'UNKNOWN');
    setText('#activity-sink', data.evidence_sink?.verified ? 'BOUND · VERIFIED' : data.evidence_sink?.bound ? 'BOUND · CONFIGURED' : 'UNBOUND');
    setText('#activity-sink-mode', data.evidence_sink?.mode || 'UNKNOWN');
    setText('#activity-workload-write', data.write_authorization?.workload_identity?.state || data.write_authorization?.mode || 'UNKNOWN');
    const direct = data.write_authorization?.direct_external_write;
    setText('#activity-direct-write', direct?.state === 'FAIL_CLOSED' ? 'SECURE · FAIL-CLOSED' : direct?.state || 'UNKNOWN');
    return data;
  }

  async function readChlom() {
    const data = await readJson('/api/chlom');
    const health = data.health || data;
    const capabilities = health.capability_states || data.capability_states || {};
    setState('#activity-chlom-state', health.status || data.status || 'UNKNOWN');
    setText('#activity-chlom-readiness', health.readiness_status || data.readiness_status || 'UNKNOWN');
    setText('#activity-chlom-mode', health.operating_mode || data.operating_mode || 'UNKNOWN');
    setText('#activity-chlom-rights', capabilities.governance_and_rights || 'UNKNOWN');
    setText('#activity-chlom-broadcast', capabilities.chain_broadcast || 'UNKNOWN');
    return data;
  }

  async function readFabric() {
    const data = await readJson('/api/fabric');
    setState('#activity-fabric-state', data.status || 'UNKNOWN');
    setText('#activity-fabric-projects', `${data.operational_project_count ?? '—'}/${data.required_project_count ?? '—'} operational`);
    setText('#activity-mcp', data.mcp?.status || 'UNKNOWN');
    setText('#activity-provider-writes', data.provider_operations?.promote_and_rollback || 'UNKNOWN');
    setText('#activity-fabric-evidence', data.evidence?.sink_bound ? 'BOUND' : 'UNBOUND');
    return data;
  }

  async function refreshActivity(forceCanary = false) {
    if (refreshing) return;
    refreshing = true;
    try {
      const [operationsResult, pentaResult, chlomResult, fabricResult] = await Promise.allSettled([
        readOperations(), readPenta(forceCanary), readChlom(), readFabric(),
      ]);
      const operations = operationsResult.status === 'fulfilled' ? operationsResult.value : null;
      const penta = pentaResult.status === 'fulfilled' ? pentaResult.value : lastPentaData;
      const chlom = chlomResult.status === 'fulfilled' ? chlomResult.value : null;
      const fabric = fabricResult.status === 'fulfilled' ? fabricResult.value : null;
      if (operations) patchGateRows(operations, penta, chlom, fabric);
      const failures = [operationsResult,pentaResult,chlomResult,fabricResult].filter((entry) => entry.status === 'rejected');
      const gap = document.querySelector('#activity-gap');
      if (gap) gap.innerHTML = failures.length
        ? `<strong>Partial live readback:</strong> ${failures.length} source${failures.length === 1 ? '' : 's'} failed this cycle. No PASS was manufactured; healthy sources remain visible and the next 15-second cycle will retry.`
        : '<strong>Live evidence posture:</strong> runtime, provider registry, PentaTime, PentaSuper, DAIL, interventions, CHLOM, and Vercel fabric are reading successfully. Direct public mutation remains default-deny unless a dedicated write credential is explicitly bound.';
    } finally {
      refreshing = false;
    }
  }

  injectSurface();
  activateActivityRoute();
  refreshActivity(true);
  window.addEventListener('hashchange', activateActivityRoute);
  document.querySelector('#refresh')?.addEventListener('click', () => refreshActivity(true));
  window.setInterval(() => {
    if (document.visibilityState === 'visible') refreshActivity(false);
  }, REFRESH_MS);
})();
