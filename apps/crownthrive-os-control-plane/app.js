const routes = {
  overview: 'Institutional Now',
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
  ['Provider deployment readback', 'D2', 'HOLD', 'PentaDeploy → PentaVercel'],
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

function render() {
  document.querySelector('#lane-grid').innerHTML = lanes.map(([lane, title, text]) => `<article class="lane-card"><span>${lane}</span><h3>${title}</h3><p>${text}</p></article>`).join('');
  document.querySelector('#gate-table').innerHTML = gates.map(([gate, authority, state, route]) => `<tr><td><strong>${gate}</strong></td><td>${authority}</td><td><span class="state ${state.toLowerCase()}">${state}</span></td><td>${route}</td></tr>`).join('');
  document.querySelector('#topology-map').innerHTML = nodes.map(([layer, name, text]) => `<article class="node" role="listitem"><span>${layer}</span><h3>${name}</h3><p>${text}</p></article>`).join('');
  document.querySelector('#receipt-list').innerHTML = receipts.map(([kind, title, text], index) => `<article class="receipt"><code>${String(index + 1).padStart(2, '0')} · ${kind}</code><div><strong>${title}</strong><p>${text}</p></div><span class="state pass">CHAINED</span></article>`).join('');
  document.querySelector('#interop-grid').innerHTML = interop.map(([lane, title, text]) => `<article class="interop-card"><span>${lane}</span><strong>${title}</strong><p>${text}</p></article>`).join('');
}

function activateRoute() {
  const route = location.hash.slice(1) || 'overview';
  const safe = routes[route] ? route : 'overview';
  document.querySelectorAll('[data-page]').forEach(el => el.classList.toggle('active', el.dataset.page === safe));
  document.querySelectorAll('[data-route]').forEach(el => el.classList.toggle('active', el.dataset.route === safe));
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
    badge.className = `badge ${String(data.status).toLowerCase() === 'operational' ? 'pass' : 'hold'}`;
    document.querySelector('#health-release').textContent = data.release;
    document.querySelector('#health-vercel').textContent = data.vercel_provider_state;
    document.querySelector('#health-time').textContent = new Date(data.observed_at).toLocaleString();
    document.querySelector('#rail-status').textContent = `Control plane ${data.status.toLowerCase()}`;
    document.querySelector('#provider-vercel-state').textContent = data.vercel_provider_state;
    document.querySelector('#footer-build').textContent = `Build ${data.build_sha.slice(0, 12)}`;
  } catch (error) {
    badge.textContent = 'HOLD';
    badge.className = 'badge hold';
    document.querySelector('#rail-status').textContent = 'Provider readback unavailable';
    document.querySelector('#health-time').textContent = 'readback failed';
  }
}

render();
activateRoute();
readHealth();
window.addEventListener('hashchange', activateRoute);
document.querySelector('#refresh').addEventListener('click', readHealth);
