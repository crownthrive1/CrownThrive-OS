const routes = {
  overview: 'Institutional Now',
  fabric: 'Vercel Execution Fabric',
  'release-gates': 'Release Gates',
  topology: 'Convergent Topology',
  receipts: 'DAIL Receipts',
  interoperability: 'Interoperability',
  providers: 'Provider Delivery'
};

const lanes = [
  ['Governance', 'PentaRG + PentaGovernance', 'Ratification, policy leases, bounded autonomy, exception routing, and irreversible-action control.'],
  ['Rights', 'CHLOM + PentaPolice', 'Identity, consent, licensing, provenance, cultural alignment, and enforceable policy constraints.'],
  ['Nervous system', 'PentaRanger + PentaFlows', 'System awareness, cadence, semantic routing, remediation ownership, and escalation.'],
  ['Release', 'PentaGate + PentaRelease', 'Exact-head evidence, certification envelopes, economics, culture, lineage, and deployment eligibility.'],
  ['Delivery', 'PentaDeploy + PentaVercel', 'Preview, production, domains, runtime telemetry, rollback, and provider readback.'],
  ['Evidence', 'DAIL + PentaAudit', 'Hash-chained observations, decisions, actions, identities, receipts, and immutable lineage.'],
  ['Economic', 'PentaCosts + SmartTreasury', 'Execution cost, rates, release cost, routing economics, and auditable allocation evidence.'],
  ['Experience', 'CrownThrive OS Control Plane', 'A single operational surface for ecosystem health, gates, work, receipts, and interoperability.']
];

const gates = [
  ['Repository contract', 'D1', 'PASS', 'PentaGate → PentaHeal'],
  ['Exact-head required checks', 'D2', 'PENDING', 'PentaRanger → PentaCertify'],
  ['Provider deployment readback', 'D2', 'PENDING', 'PentaDeploy → PentaVercel'],
  ['Platform API / MCP exposure', 'D1', 'PENDING', 'CrownThrive IO → PentaVercel'],
  ['Vercel provider write credential', 'D2', 'HOLD', 'PentaVault → PentaCredentials'],
  ['DAIL receipt chain', 'D1', 'PASS', 'PentaRG → DAIL'],
  ['CHLOM rights and consent', 'D2', 'PENDING', 'CHLOM → PentaPolice'],
  ['D3 founder authority lease', 'D3', 'PASS', 'PentaGovernance'],
  ['Release economics', 'D2', 'PENDING', 'SmartTreasury → PentaCosts'],
  ['Cultural imprint evidence', 'D2', 'PENDING', 'CIE → PentaRelease']
];

const nodes = [
  ['Governance', 'PentaGovernance', 'Ratification and founder-authority lease.'],
  ['Policy', 'PentaPolice', 'Enforcement, exception handling, and fail-closed control.'],
  ['Control', 'PentaRG', 'Audit, recover, refactor, archive, restore, and orchestrate.'],
  ['Preflight', 'PentaGate', 'Deterministic repository and release checks.'],
  ['Recovery', 'PentaHeal', 'Rollback-bound repair packets.'],
  ['Awareness', 'PentaRanger', 'Exact-head watch, cadence, and escalation.'],
  ['Certification', 'PentaCertify', 'Independent evidence on the exact candidate.'],
  ['Release', 'PentaRelease', 'Technical, economic, cultural, and governance envelope.'],
  ['Delivery', 'PentaVercel', 'Preview, production, domains, logs, and rollback.'],
  ['Evidence', 'DAIL', 'Hash-chained institutional lineage.'],
  ['Rights', 'CHLOM', 'Identity, consent, licensing, provenance, and ownership.'],
  ['Operations', 'PentaPM', 'Projects, milestones, development state, and ownership.']
];

const receipts = [
  ['AUDIT', 'Repository + provider inventory', 'Observations are collected without treating a source claim as provider truth.'],
  ['PLAN', 'Bounded repair graph', 'Every action declares authority, exact target, reason, reversibility, and rollback.'],
  ['APPLY', 'Idempotent mutation', 'Only policy-enumerated actions execute; ambiguous work remains HOLD.'],
  ['READBACK', 'Independent verification', 'The provider confirms the resulting state before certification or release.']
];

const interop = [
  ['Upstream', 'Policy → Control', 'PentaGovernance ratifies policy; CHLOM and PentaPolice constrain execution before PentaRG acts.'],
  ['Lateral', 'Control → Nervous System', 'PentaRG coordinates PentaGate, PentaHeal, PentaRanger, PentaCrawler, PentaFlows, and PentaHelper.'],
  ['Downstream', 'Release → Delivery', 'PentaCertify feeds PentaRelease; PentaDeploy invokes PentaVercel; readback returns to PentaRG.'],
  ['Evidence', 'Everything → DAIL', 'Audit, plan, apply, deployment, rollback, and governance events become hash-chained institutional evidence.']
];

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
  if (['pass', 'operational', 'bound', 'production'].includes(normalized)) return 'pass';
  if (['hold', 'degraded', 'error', 'gated'].includes(normalized)) return 'hold';
  return 'pending';
}

function setGate(name, state) {
  const gate = gates.find((entry) => entry[0] === name);
  if (gate) gate[2] = state;
}

function renderGates() {
  document.querySelector('#gate-table').innerHTML = gates
    .map(([gate, authority, state, route]) => `<tr><td><strong>${escapeHtml(gate)}</strong></td><td>${escapeHtml(authority)}</td><td><span class="state ${stateClass(state)}">${escapeHtml(state)}</span></td><td>${escapeHtml(route)}</td></tr>`)
    .join('');
}

function render() {
  document.querySelector('#lane-grid').innerHTML = lanes
    .map(([lane, title, text]) => `<article class="lane-card"><span>${escapeHtml(lane)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p></article>`)
    .join('');
  renderGates();
  document.querySelector('#topology-map').innerHTML = nodes
    .map(([layer, name, text]) => `<article class="node" role="listitem"><span>${escapeHtml(layer)}</span><h3>${escapeHtml(name)}</h3><p>${escapeHtml(text)}</p></article>`)
    .join('');
  document.querySelector('#receipt-list').innerHTML = receipts
    .map(([kind, title, text], index) => `<article class="receipt"><code>${String(index + 1).padStart(2, '0')} · ${escapeHtml(kind)}</code><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div><span class="state pass">CHAINED</span></article>`)
    .join('');
  document.querySelector('#interop-grid').innerHTML = interop
    .map(([lane, title, text]) => `<article class="interop-card"><span>${escapeHtml(lane)}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></article>`)
    .join('');
}

function activateRoute() {
  const route = location.hash.slice(1) || 'overview';
  const safe = routes[route] ? route : 'overview';
  document.querySelectorAll('[data-page]').forEach((element) => element.classList.toggle('active', element.dataset.page === safe));
  document.querySelectorAll('[data-route]').forEach((element) => element.classList.toggle('active', element.dataset.route === safe));
  document.querySelector('#page-title').textContent = routes[safe];
  document.title = `${routes[safe]} · CrownThrive OS`;
}

async function readHealth() {
  const badge = document.querySelector('#health-badge');
  try {
    const response = await fetch('/api/health', { cache: 'no-store' });
    if (!response.ok) throw new Error(`health ${response.status}`);
    const data = await response.json();
    badge.textContent = data.status;
    badge.className = `badge ${stateClass(data.status)}`;
    document.querySelector('#health-release').textContent = data.release;
    document.querySelector('#health-vercel').textContent = data.vercel_provider_state;
    document.querySelector('#health-time').textContent = new Date(data.observed_at).toLocaleString();
    document.querySelector('#rail-status').textContent = `Control plane ${String(data.status).toLowerCase()}`;
    document.querySelector('#footer-build').textContent = `Build ${String(data.build_sha).slice(0, 12)}`;
  } catch {
    badge.textContent = 'HOLD';
    badge.className = 'badge hold';
    document.querySelector('#rail-status').textContent = 'Provider readback unavailable';
    document.querySelector('#health-time').textContent = 'readback failed';
  }
}

function renderFabricProjects(projects) {
  const target = document.querySelector('#fabric-projects');
  target.innerHTML = projects
    .map((project) => {
      const health = project.health || {};
      const capabilities = Array.isArray(health.capabilities) && health.capabilities.length
        ? health.capabilities.slice(0, 3).join(' · ')
        : 'Provider health and deployment evidence';
      return `<article class="fabric-project">
        <div class="signal-head">
          <span>${escapeHtml(project.service)}</span>
          <span class="state ${stateClass(project.state)}">${escapeHtml(project.state)}</span>
        </div>
        <strong>${escapeHtml(project.project_id)}</strong>
        <p>${escapeHtml(capabilities)}</p>
        <dl class="fabric-meta">
          <div><dt>Release</dt><dd>${escapeHtml(health.release || 'unknown')}</dd></div>
          <div><dt>Provider</dt><dd>${escapeHtml(health.provider_state || 'unknown')}</dd></div>
          <div><dt>Latency</dt><dd>${escapeHtml(project.latency_ms)} ms</dd></div>
          <div><dt>Build</dt><dd class="mono">${escapeHtml(String(health.build_sha || '—').slice(0, 12))}</dd></div>
        </dl>
      </article>`;
    })
    .join('');
}

async function readFabric() {
  const badge = document.querySelector('#fabric-badge');
  try {
    const response = await fetch('/api/fabric', { cache: 'no-store' });
    const data = await response.json();
    const fabricPass = data.status === 'OPERATIONAL';

    badge.textContent = data.status;
    badge.className = `badge ${stateClass(data.status)}`;
    document.querySelector('#fabric-required').textContent = data.required_project_count;
    document.querySelector('#fabric-operational').textContent = data.operational_project_count;
    document.querySelector('#fabric-write-state').textContent = data.provider_operations?.promote_and_rollback || 'UNKNOWN';
    document.querySelector('#fabric-receipt').textContent = String(data.evidence?.digest || '—').slice(0, 16);
    document.querySelector('#provider-vercel-state').textContent = `${data.operational_project_count}/${data.required_project_count} production planes`;
    document.querySelector('#mcp-state').textContent = data.mcp?.status || 'UNKNOWN';
    document.querySelector('#mcp-version').textContent = data.mcp?.protocol_version || '—';
    document.querySelector('#mcp-profile').textContent = data.mcp?.profile || '—';
    document.querySelector('#fabric-observed').textContent = new Date(data.observed_at).toLocaleString();

    renderFabricProjects(Array.isArray(data.projects) ? data.projects : []);

    setGate('Provider deployment readback', fabricPass ? 'PASS' : 'HOLD');
    setGate('Platform API / MCP exposure', data.mcp?.status === 'OPERATIONAL' ? 'PASS' : 'HOLD');
    setGate(
      'Vercel provider write credential',
      data.provider_operations?.promote_and_rollback === 'BOUND_GOVERNED' ? 'PASS' : 'HOLD'
    );
    renderGates();

    const gaps = document.querySelector('#fabric-gaps');
    if (data.provider_operations?.promote_and_rollback === 'BOUND_GOVERNED') {
      gaps.innerHTML = '<strong>Provider writes:</strong> governed promotion, rollback, domain, and environment mutation are credential-bound.';
    } else {
      gaps.innerHTML = '<strong>Provider-write boundary:</strong> Git-triggered deployments and provider readback are operational. Direct Vercel promotion, rollback, domain, and environment mutation remain fail-closed until <code>VERCEL_AUTOMATION_TOKEN</code> is vaulted and bound.';
    }

    if (!response.ok || !fabricPass) {
      document.querySelector('#rail-status').textContent = 'Vercel fabric degraded';
    }
  } catch {
    badge.textContent = 'HOLD';
    badge.className = 'badge hold';
    document.querySelector('#fabric-observed').textContent = 'readback failed';
    document.querySelector('#fabric-projects').innerHTML = '<article class="callout"><strong>HOLD:</strong> aggregate provider readback is unavailable.</article>';
    setGate('Provider deployment readback', 'HOLD');
    setGate('Platform API / MCP exposure', 'HOLD');
    renderGates();
  }
}

async function refreshAll() {
  const button = document.querySelector('#refresh');
  button.disabled = true;
  try {
    await Promise.allSettled([readHealth(), readFabric()]);
  } finally {
    button.disabled = false;
  }
}

render();
activateRoute();
refreshAll();
window.addEventListener('hashchange', activateRoute);
document.querySelector('#refresh').addEventListener('click', refreshAll);
