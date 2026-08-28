(() => {
  const ROUTE = 'activity';
  const TITLE = 'OS Activity';
  let refreshing = false;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[character]));
  }

  function stateClass(state) {
    const normalized = String(state || '').toLowerCase();
    if (['pass', 'operational', 'bound', 'production', 'available_through_pentafabric'].includes(normalized)) return 'pass';
    if (['hold', 'degraded', 'error', 'gated', 'readback_failed', 'unbound'].includes(normalized)) return 'hold';
    return 'pending';
  }

  function short(value, length = 14) {
    const text = String(value || '—');
    return text.length > length ? `${text.slice(0, length)}…` : text;
  }

  function formatTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
  }

  function injectSurface() {
    const nav = document.querySelector('.rail nav');
    if (nav && !nav.querySelector('[data-route="activity"]')) {
      const link = document.createElement('a');
      link.href = '#activity';
      link.dataset.route = 'activity';
      link.textContent = 'OS Activity';
      const releaseLink = nav.querySelector('[data-route="release-gates"]');
      nav.insertBefore(link, releaseLink || null);
    }

    if (document.querySelector('[data-page="activity"]')) return;
    const section = document.createElement('section');
    section.className = 'route os-activity-route';
    section.dataset.page = 'activity';
    section.setAttribute('aria-labelledby', 'activity-title');
    section.innerHTML = `
      <div class="section-head activity-head">
        <div><p class="eyebrow">Institutional telemetry</p><h2 id="activity-title">What CrownThrive OS is doing</h2></div>
        <p>Live instrumented operating picture from persisted Pentas, PentaFabric runtime assurance, CHLOM authority readback, and the Vercel execution fabric. Uninstrumented activity is never presented as observed.</p>
      </div>

      <div class="activity-summary" aria-live="polite">
        <article><span>Pentas · 24h</span><strong id="activity-events">—</strong><small id="activity-sample">reading ledger</small></article>
        <article><span>Protocols</span><strong id="activity-protocol-count">—</strong><small>active in observed window</small></article>
        <article><span>Routes</span><strong id="activity-route-count">—</strong><small>active in observed window</small></article>
        <article><span>Production planes</span><strong id="activity-planes">—</strong><small>provider readback</small></article>
      </div>

      <div class="activity-runtime-grid">
        <article class="activity-runtime-card">
          <div class="signal-head"><span>PentaFabric runtime</span><span id="activity-penta-state" class="state pending">PENDING</span></div>
          <dl class="activity-meta">
            <div><dt>Self-test</dt><dd id="activity-selftest">—</dd></div>
            <div><dt>Evidence sink</dt><dd id="activity-sink">—</dd></div>
            <div><dt>Sink mode</dt><dd id="activity-sink-mode">—</dd></div>
            <div><dt>Write auth</dt><dd id="activity-write-auth">—</dd></div>
          </dl>
        </article>
        <article class="activity-runtime-card">
          <div class="signal-head"><span>CHLOM authority</span><span id="activity-chlom-state" class="state pending">PENDING</span></div>
          <dl class="activity-meta">
            <div><dt>Readiness</dt><dd id="activity-chlom-readiness">—</dd></div>
            <div><dt>Mode</dt><dd id="activity-chlom-mode">—</dd></div>
            <div><dt>Rights / governance</dt><dd id="activity-chlom-rights">—</dd></div>
            <div><dt>Chain broadcast</dt><dd id="activity-chlom-broadcast">—</dd></div>
          </dl>
        </article>
        <article class="activity-runtime-card">
          <div class="signal-head"><span>Vercel execution fabric</span><span id="activity-fabric-state" class="state pending">PENDING</span></div>
          <dl class="activity-meta">
            <div><dt>Projects</dt><dd id="activity-fabric-projects">—</dd></div>
            <div><dt>MCP</dt><dd id="activity-mcp">—</dd></div>
            <div><dt>Provider writes</dt><dd id="activity-provider-writes">—</dd></div>
            <div><dt>Evidence</dt><dd id="activity-fabric-evidence">—</dd></div>
          </dl>
        </article>
        <article class="activity-runtime-card">
          <div class="signal-head"><span>Observability boundary</span><span id="activity-observability-state" class="state pending">PENDING</span></div>
          <dl class="activity-meta">
            <div><dt>Penta ledger</dt><dd id="activity-ledger-state">—</dd></div>
            <div><dt>Runtime logs</dt><dd id="activity-runtime-logs">—</dd></div>
            <div><dt>Agent Runs</dt><dd id="activity-agent-runs">—</dd></div>
            <div><dt>Observed</dt><dd id="activity-observed">—</dd></div>
          </dl>
        </article>
      </div>

      <div class="activity-distribution-grid">
        <article class="activity-panel"><div class="panel-head"><span>Protocol activity</span><small id="activity-distribution-scope">—</small></div><div id="activity-protocols" class="activity-bars"></div></article>
        <article class="activity-panel"><div class="panel-head"><span>Route activity</span><small>observed Pentas</small></div><div id="activity-routes" class="activity-bars"></div></article>
      </div>

      <div class="section-head compact activity-recent-head">
        <div><p class="eyebrow">PentaFabric ledger</p><h2>Recent governed activity</h2></div>
        <p>Public-safe metadata only: protocol, route, lane, receipt time, and shortened evidence identifiers.</p>
      </div>
      <div class="table-wrap">
        <table class="activity-table">
          <thead><tr><th>Received</th><th>Protocol</th><th>Route</th><th>Lane</th><th>Penta</th><th>Trace</th></tr></thead>
          <tbody id="activity-recent"><tr><td colspan="6">Reading live activity…</td></tr></tbody>
        </table>
      </div>
      <article id="activity-gap" class="callout"><strong>Evidence rule:</strong> only instrumented provider readback and persisted events are rendered as live OS activity.</article>
    `;

    const fabric = document.querySelector('[data-page="fabric"]');
    if (fabric) fabric.before(section);
    else document.querySelector('main')?.appendChild(section);
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
    const safeEntries = Array.isArray(entries) ? entries.slice(0, 10) : [];
    const max = Math.max(1, ...safeEntries.map((entry) => Number(entry.count) || 0));
    target.innerHTML = safeEntries.length
      ? safeEntries.map((entry) => {
          const count = Number(entry.count) || 0;
          const width = Math.max(4, Math.round((count / max) * 100));
          return `<div class="activity-bar-row"><div><strong>${escapeHtml(entry.name)}</strong><span>${count}</span></div><div class="activity-bar-track"><span style="width:${width}%"></span></div></div>`;
        }).join('')
      : '<p class="activity-empty">No persisted activity in the observed window.</p>';
  }

  function renderRecent(rows) {
    const target = document.querySelector('#activity-recent');
    if (!target) return;
    const recent = Array.isArray(rows) ? rows : [];
    target.innerHTML = recent.length
      ? recent.map((row) => `<tr>
          <td>${escapeHtml(formatTime(row.received_at))}</td>
          <td><strong>${escapeHtml(row.protocol)}</strong></td>
          <td>${escapeHtml(row.route)}</td>
          <td><span class="state ${row.lane === 'hot' ? 'pass' : 'pending'}">${escapeHtml(row.lane)}</span></td>
          <td class="mono" title="${escapeHtml(row.penta_id)}">${escapeHtml(short(row.penta_id))}</td>
          <td class="mono" title="${escapeHtml(row.trace_id)}">${escapeHtml(short(row.trace_id))}</td>
        </tr>`).join('')
      : '<tr><td colspan="6">No persisted Pentas in the observed window.</td></tr>';
  }

  async function readJson(path) {
    const response = await fetch(path, { cache: 'no-store' });
    let data = null;
    try { data = await response.json(); } catch { data = {}; }
    return { response, data };
  }

  async function readOperations() {
    const { response, data } = await readJson('/api/operations');
    const activity = data.activity || {};
    document.querySelector('#activity-events').textContent = activity.total_events ?? '—';
    document.querySelector('#activity-protocol-count').textContent = activity.active_protocols ?? '—';
    document.querySelector('#activity-route-count').textContent = activity.active_routes ?? '—';
    document.querySelector('#activity-sample').textContent = activity.distribution_scope || 'no sample';
    document.querySelector('#activity-distribution-scope').textContent = activity.distribution_scope || '—';
    document.querySelector('#activity-ledger-state').textContent = data.instrumentation?.pentafabric_event_ledger || data.source?.state || 'UNKNOWN';
    document.querySelector('#activity-runtime-logs').textContent = data.instrumentation?.vercel_runtime_management || 'UNKNOWN';
    document.querySelector('#activity-agent-runs').textContent = data.instrumentation?.vercel_agent_runs || 'UNKNOWN';
    document.querySelector('#activity-observed').textContent = formatTime(data.observed_at);
    const observability = document.querySelector('#activity-observability-state');
    observability.textContent = data.status || (response.ok ? 'OPERATIONAL' : 'DEGRADED');
    observability.className = `state ${stateClass(observability.textContent)}`;
    renderBars('#activity-protocols', activity.protocols);
    renderBars('#activity-routes', activity.routes);
    renderRecent(activity.recent);
    if (!response.ok) throw new Error(data.detail || `operations ${response.status}`);
  }

  async function readPenta() {
    const { response, data } = await readJson('/api/penta?selftest=1');
    const state = document.querySelector('#activity-penta-state');
    state.textContent = data.status || (response.ok ? 'OPERATIONAL' : 'DEGRADED');
    state.className = `state ${stateClass(state.textContent)}`;
    document.querySelector('#activity-selftest').textContent = data.self_test?.status || 'UNKNOWN';
    document.querySelector('#activity-sink').textContent = data.evidence_sink?.bound ? 'BOUND' : 'UNBOUND';
    document.querySelector('#activity-sink-mode').textContent = data.evidence_sink?.mode || 'UNKNOWN';
    document.querySelector('#activity-write-auth').textContent = data.write_authorization?.bound ? data.write_authorization.mode : 'FAIL-CLOSED';
  }

  async function readChlom() {
    const { data } = await readJson('/api/chlom');
    const health = data.health || data;
    const capabilities = health.capability_states || data.capability_states || {};
    const state = document.querySelector('#activity-chlom-state');
    state.textContent = health.status || data.status || 'UNKNOWN';
    state.className = `state ${stateClass(state.textContent)}`;
    document.querySelector('#activity-chlom-readiness').textContent = health.readiness_status || data.readiness_status || 'UNKNOWN';
    document.querySelector('#activity-chlom-mode').textContent = health.operating_mode || data.operating_mode || 'UNKNOWN';
    document.querySelector('#activity-chlom-rights').textContent = capabilities.governance_and_rights || 'UNKNOWN';
    document.querySelector('#activity-chlom-broadcast').textContent = capabilities.chain_broadcast || 'UNKNOWN';
  }

  async function readFabric() {
    const { data } = await readJson('/api/fabric');
    const state = document.querySelector('#activity-fabric-state');
    state.textContent = data.status || 'UNKNOWN';
    state.className = `state ${stateClass(state.textContent)}`;
    document.querySelector('#activity-planes').textContent = `${data.operational_project_count ?? '—'}/${data.required_project_count ?? '—'}`;
    document.querySelector('#activity-fabric-projects').textContent = `${data.operational_project_count ?? '—'}/${data.required_project_count ?? '—'} operational`;
    document.querySelector('#activity-mcp').textContent = data.mcp?.status || 'UNKNOWN';
    document.querySelector('#activity-provider-writes').textContent = data.provider_operations?.promote_and_rollback || 'UNKNOWN';
    document.querySelector('#activity-fabric-evidence').textContent = data.evidence?.sink_bound ? 'BOUND' : 'UNBOUND';
  }

  async function refreshActivity() {
    if (refreshing) return;
    refreshing = true;
    try {
      const results = await Promise.allSettled([readOperations(), readPenta(), readChlom(), readFabric()]);
      const failures = results.filter((entry) => entry.status === 'rejected');
      const gap = document.querySelector('#activity-gap');
      if (gap) {
        gap.innerHTML = failures.length
          ? `<strong>Partial readback:</strong> ${failures.length} activity source${failures.length === 1 ? '' : 's'} failed this refresh. No PASS was manufactured; retry with Refresh readback.`
          : '<strong>Evidence rule:</strong> persisted Pentas, runtime self-test, CHLOM authority, and Vercel fabric are live. Vercel Agent Runs remain explicitly NOT INSTRUMENTED until that observability feed is registered.';
      }
    } finally {
      refreshing = false;
    }
  }

  injectSurface();
  activateActivityRoute();
  refreshActivity();
  window.addEventListener('hashchange', activateActivityRoute);
  document.querySelector('#refresh')?.addEventListener('click', refreshActivity);
  window.setInterval(() => {
    if (document.visibilityState === 'visible') refreshActivity();
  }, 30000);
})();
