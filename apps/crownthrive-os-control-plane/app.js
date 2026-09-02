const routes = {
  overview: 'Command Center',
  ecosystem: 'Ecosystem',
  commerce: 'Commerce & Growth',
  fabric: 'Infrastructure',
  'release-gates': 'Trust & Release',
  interoperability: 'Integrations',
  receipts: 'Evidence & Lineage'
};

const lanes = [
  ['Build', 'Launch & operate', 'CrownThrive IO, ThriveTools, Thrive AI Studio, Kamora360, Collab Portal, App Factory, and production delivery turn ideas into working systems.'],
  ['Grow', 'Distribution & demand', 'CrownPulse, ThrivePush, CrownLytics, CrownFluence, AdLuxe Network, affiliates, ambassadors, and media distribution move attention into action.'],
  ['Serve', 'Community & experience', 'Locticians, FindCliques, ThrivePeer, ThriveGather, ThriveSeat, directories, events, and member experiences strengthen participation and retention.'],
  ['Monetize', 'Commerce & economic activation', 'PentaGreen, ThriveEvergreen, Stripe rails, tickets, loyalty, advertising, licensing, digital products, and partner economics activate durable revenue.'],
  ['Teach', 'Education & advancement', 'CrownThriveU, ThriveAlumni, CrownThrive Impact Institute, playbooks, training, and knowledge systems convert learning into capability.'],
  ['Tell', 'Media, culture & IP', 'Melanated Voices, Melanated TV, CrownThrive Studios, Virality Music, Melanated Stock, galleries, and publishing carry cultural IP across formats.'],
  ['Govern', 'Rights, trust & continuity', 'CHLOM, Cultural Imprint Engine, DAIL, PentaSecurity, PentaCertifier, licensing, evidence, recovery, and policy preserve institutional integrity.'],
  ['Compound', 'One connected flywheel', 'Identity, attribution, rewards, data, automation, reusable audiences, shared infrastructure, and institutional memory feed value back into the ecosystem.']
];

const ecosystem = [
  ['Core OS & Technology', 'Operate the ecosystem', 'Shared infrastructure, apps, APIs, analytics, automation, and execution surfaces.', ['CrownThrive.com', 'CrownThrive IO', 'ThriveApps', 'ThriveTools', 'Thrive AI Studio', 'CrownLytics', 'CrownPulse', 'Kamora360', 'Collab Portal']],
  ['Community & Directories', 'Connect people to opportunity', 'Discovery, service-provider networks, peer exchange, events, and community participation.', ['Locticians', 'FindCliques', 'ThrivePeer', 'ThriveGather', 'ThriveSeat', 'ThriveTickets', 'The Mane Experience']],
  ['Media & Culture', 'Distribute stories and cultural IP', 'Audio, video, publishing, stock, galleries, broadcast, and cultural storytelling.', ['Melanated Voices', 'Melanated Voices TV', 'Melanated TV', 'Melanated Stock', 'Melanated Vault', 'CrownThrive Studios', 'Virality Music', 'Locticians TV']],
  ['Commerce & Loyalty', 'Turn attention into durable economics', 'Advertising, loyalty, partner distribution, products, storefronts, licensing, and creator monetization.', ['AdLuxe Network', 'CrownRewards', 'CrownFluence', 'Crown Affiliates', 'Crown Ambassadors', 'Melanin Magic', 'Good Shit Only', 'MM Suites']],
  ['Education & Legacy', 'Build capability and institutional memory', 'Training, alumni, impact, certification, playbooks, documentation, and generational knowledge.', ['CrownThriveU', 'ThriveAlumni', 'CrownThrive Impact Institute', 'PentaDocs', 'Go Flipbooks', 'ThriveFunding']],
  ['Governance & Frameworks', 'Protect scale without losing identity', 'Rights, licensing, cultural alignment, evidence, policy, attribution, recovery, and governed automation.', ['CHLOM', 'Cultural Imprint Engine', 'Thrive Flywheel', 'DAIL', 'Penta families', 'CrownThrive ID']]
];

const commerce = [
  ['Advertising', 'AdLuxe Network + PentaAds', 'Publisher inventory, advertiser demand, placements, reporting, conversion evidence, and internal house inventory.', 'ADVERTISING LANE'],
  ['Loyalty', 'CrownRewards', 'Closed-loop rewards and engagement economics that can travel across participating ecosystem experiences.', 'LOYALTY LANE'],
  ['Influence', 'CrownFluence + Affiliates + Ambassadors', 'Partner distribution, referral economics, creator campaigns, and attributable audience growth.', 'DISTRIBUTION LANE'],
  ['Events', 'ThriveTickets + ThriveGather + ThriveSeat', 'Ticketing, gatherings, bookings, attendance, and event-driven commerce across the network.', 'EVENTS LANE'],
  ['Products', 'Melanin Magic + Good Shit Only', 'Retail, wholesale, digital goods, licensed assets, bundles, and brand-led storefront commerce.', 'PRODUCT LANE'],
  ['Licensing', 'CHLOM + rights rails', 'Machine-readable rights, license boundaries, entitlements, evidence, and downstream usage controls.', 'RIGHTS LANE'],
  ['Media', 'Studios + TV + Virality Music', 'Sponsorship, paid media, digital editions, licensing, memberships, and content-led monetization.', 'MEDIA LANE'],
  ['Platform', 'PentaGreen + ThriveEvergreen', 'Provider adapters, catalog activation, pricing, checkout, entitlement, fulfillment, tax, payout, and commercial readiness.', 'COMMERCE CONTROL']
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
  ['Governance', 'PentaGovernance', 'Ratification, authority boundaries, and founder-reserved actions.'],
  ['Policy', 'PentaPolice', 'Enforcement, exception handling, and fail-closed control.'],
  ['Control', 'PentaRG', 'Audit, recover, refactor, archive, restore, and orchestrate.'],
  ['Preflight', 'PentaGate', 'Deterministic repository and release checks.'],
  ['Recovery', 'PentaHeal', 'Rollback-bound repair packets and continuity.'],
  ['Awareness', 'PentaRanger', 'Exact-head watch, cadence, and escalation.'],
  ['Certification', 'PentaCertify', 'Independent evidence bound to the exact candidate.'],
  ['Release', 'PentaRelease', 'Technical, economic, cultural, and governance envelope.'],
  ['Delivery', 'PentaVercel', 'Preview, production, domains, logs, and rollback.'],
  ['Evidence', 'DAIL', 'Hash-chained institutional lineage.'],
  ['Rights', 'CHLOM', 'Identity, consent, licensing, provenance, and ownership evidence.'],
  ['Operations', 'PentaPM', 'Projects, milestones, development state, and ownership.']
];

const receipts = [
  ['OBSERVE', 'Read current source and provider state', 'Collect facts without converting repository intent, workflow dispatch, or written claims into provider truth.'],
  ['PLAN', 'Build the bounded change graph', 'Declare exact targets, authority, dependencies, reason, reversibility, and rollback before consequential mutation.'],
  ['APPLY', 'Execute the approved change', 'Only policy-enumerated actions execute; ambiguity remains held rather than becoming an inferred PASS.'],
  ['READBACK', 'Verify the resulting state', 'Provider and runtime readback confirm what actually changed before certification, activation, or release claims.']
];

const interop = [
  ['Identity', 'CrownThrive ID → ecosystem access', 'Shared identity progressively connects apps, attribution, permissions, rewards, and account-level context without pretending full SSO exists where it does not.'],
  ['Growth', 'Analytics → campaigns → rewards', 'CrownLytics, CrownPulse, ThrivePush, CrownFluence, CrownRewards, AdLuxe, affiliates, and ambassadors form an attributable growth loop.'],
  ['Commerce', 'Catalog → rights → checkout → entitlement', 'PentaGreen and ThriveEvergreen coordinate products and providers while CHLOM preserves rights and evidence boundaries.'],
  ['Media', 'Studios → distribution → audience → commerce', 'CrownThrive Studios, Melanated properties, Virality Music, stock, galleries, publishing, and advertising connect content to distribution and monetization.'],
  ['Community', 'Discovery → participation → retention', 'Locticians, FindCliques, ThrivePeer, events, tickets, loyalty, and education convert audience into durable community participation.'],
  ['Institutional', 'Everything → DAIL / PentaDocs', 'Decisions, execution, evidence, recovery, standards, and reusable knowledge converge into institutional memory and governed operating context.']
];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}

function stateClass(state) {
  const normalized = String(state || '').toLowerCase();
  if (['pass', 'operational', 'bound', 'production', 'ready'].includes(normalized)) return 'pass';
  if (['hold', 'degraded', 'error', 'gated', 'unbound'].includes(normalized)) return 'hold';
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
  renderAttention();
}

function renderAttention() {
  const target = document.querySelector('#attention-list');
  const count = document.querySelector('#attention-count');
  if (!target || !count) return;
  const items = gates.filter((entry) => entry[2] !== 'PASS');
  count.textContent = items.length ? `${items.length} OPEN` : 'CLEAR';
  target.innerHTML = (items.length ? items : [['No open release predicates', '', 'PASS', 'System']])
    .slice(0, 6)
    .map(([name, authority, state, route]) => `<div class="attention-item ${stateClass(state)}"><span><strong>${escapeHtml(name)}</strong><br><small>${escapeHtml(route)}${authority ? ` · ${escapeHtml(authority)}` : ''}</small></span><span class="state ${stateClass(state)}">${escapeHtml(state)}</span></div>`)
    .join('');
}

function render() {
  document.querySelector('#lane-grid').innerHTML = lanes
    .map(([lane, title, text]) => `<article class="lane-card"><span>${escapeHtml(lane)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p></article>`)
    .join('');

  document.querySelector('#ecosystem-grid').innerHTML = ecosystem
    .map(([corridor, title, text, tags]) => `<article class="ecosystem-card"><span>${escapeHtml(corridor)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p><div class="tag-list">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div></article>`)
    .join('');

  document.querySelector('#commerce-grid').innerHTML = commerce
    .map(([lane, title, text, label]) => `<article class="commerce-card"><span>${escapeHtml(lane)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p><strong>${escapeHtml(label)}</strong></article>`)
    .join('');

  renderGates();

  document.querySelector('#topology-map').innerHTML = nodes
    .map(([layer, name, text]) => `<article class="node" role="listitem"><span>${escapeHtml(layer)}</span><h3>${escapeHtml(name)}</h3><p>${escapeHtml(text)}</p></article>`)
    .join('');

  document.querySelector('#receipt-list').innerHTML = receipts
    .map(([kind, title, text], index) => `<article class="receipt"><code>${String(index + 1).padStart(2, '0')} · ${escapeHtml(kind)}</code><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div><span class="state pass">CHAIN</span></article>`)
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
    const status = data.status || 'UNKNOWN';
    badge.textContent = status;
    badge.className = `metric-state ${stateClass(status)}`;
    document.querySelector('#health-release').textContent = data.release || 'release unknown';
    document.querySelector('#health-vercel').textContent = data.vercel_provider_state || 'provider state unknown';
    const observed = data.observed_at ? new Date(data.observed_at) : null;
    document.querySelector('#health-time').textContent = observed && !Number.isNaN(observed.getTime()) ? observed.toLocaleString() : 'unknown';
    document.querySelector('#overview-observed').textContent = observed && !Number.isNaN(observed.getTime()) ? observed.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '—';
    document.querySelector('#rail-status').textContent = `OS ${String(status).toLowerCase()}`;
    document.querySelector('#footer-build').textContent = `Build ${String(data.build_sha || 'unknown').slice(0, 12)}`;
  } catch {
    badge.textContent = 'HOLD';
    badge.className = 'metric-state hold';
    document.querySelector('#rail-status').textContent = 'Production readback unavailable';
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
    const operational = Number(data.operational_project_count ?? 0);
    const required = Number(data.required_project_count ?? 0);

    badge.textContent = data.status || 'UNKNOWN';
    badge.className = `badge ${stateClass(data.status)}`;
    document.querySelector('#fabric-required').textContent = required || '—';
    document.querySelector('#fabric-operational').textContent = operational || '—';
    document.querySelector('#fabric-write-state').textContent = data.provider_operations?.promote_and_rollback || 'UNKNOWN';
    document.querySelector('#fabric-receipt').textContent = String(data.evidence?.digest || '—').slice(0, 16);
    document.querySelector('#provider-vercel-state').textContent = `${operational}/${required} production planes`;
    document.querySelector('#mcp-state').textContent = data.mcp?.status || 'UNKNOWN';
    document.querySelector('#mcp-state').className = `state ${stateClass(data.mcp?.status)}`;
    document.querySelector('#mcp-version').textContent = data.mcp?.protocol_version || '—';
    document.querySelector('#mcp-profile').textContent = data.mcp?.profile || '—';
    document.querySelector('#fabric-observed').textContent = data.observed_at ? new Date(data.observed_at).toLocaleString() : '—';
    document.querySelector('#overview-planes').textContent = required ? `${operational}/${required}` : '—';
    document.querySelector('#overview-mcp').textContent = data.mcp?.status || '—';

    renderFabricProjects(Array.isArray(data.projects) ? data.projects : []);

    setGate('Provider deployment readback', fabricPass ? 'PASS' : 'HOLD');
    setGate('Platform API / MCP exposure', data.mcp?.status === 'OPERATIONAL' ? 'PASS' : 'HOLD');
    setGate('Vercel provider write credential', data.provider_operations?.promote_and_rollback === 'BOUND_GOVERNED' ? 'PASS' : 'HOLD');
    renderGates();

    const gaps = document.querySelector('#fabric-gaps');
    if (data.provider_operations?.promote_and_rollback === 'BOUND_GOVERNED') {
      gaps.innerHTML = '<strong>Provider writes:</strong> governed promotion, rollback, domain, and environment mutation are credential-bound.';
    } else {
      gaps.innerHTML = '<strong>Provider-write boundary:</strong> Git-triggered deployments and provider readback are operational. Direct Vercel promotion, rollback, domain, and environment mutation remain fail-closed until the required automation credential is vaulted and bound.';
    }

    if (!response.ok || !fabricPass) document.querySelector('#rail-status').textContent = 'Vercel fabric degraded';
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
  button.textContent = 'Refreshing…';
  try {
    await Promise.allSettled([readHealth(), readFabric()]);
  } finally {
    button.disabled = false;
    button.textContent = 'Refresh';
  }
}

render();
activateRoute();
refreshAll();
window.addEventListener('hashchange', activateRoute);
document.querySelector('#refresh').addEventListener('click', refreshAll);
