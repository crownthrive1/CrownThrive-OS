const systems = [
  { mark: 'MCP', name: 'CrownThrive MCP', state: 'LIVE ENDPOINT', description: 'Public-safe model context and interoperability surface for discovering CrownThrive OS capabilities.', action: 'Probe MCP', href: '#developers', probe: '/api/mcp' },
  { mark: 'CH', name: 'CHLOM Protocol', state: 'LIVE READBACK', description: 'Compliance Hybrid Licensing and Ownership Model controls for rights, provenance, consent, and scope.', action: 'Inspect CHLOM', href: '/api/chlom' },
  { mark: 'PF', name: 'PentaFabric', state: 'LIVE HEALTH', description: 'Runtime routing, execution lanes, provider posture, and public-safe evidence for the Penta operating fabric.', action: 'Read fabric health', href: '/api/pentafabric-health' },
  { mark: 'PG', name: 'PentaGreen', state: 'COMMERCIAL LAYER', description: 'Catalog, pricing, checkout, entitlement, fulfillment, and provider-bound commercialization control.', action: 'Request license', href: 'mailto:contact@crownthrive.com?subject=PentaGreen%20Commercial%20License' },
  { mark: 'GF', name: 'Go Flipbooks', state: 'LIVE CATALOG', description: 'Publishing, interactive reading, digital delivery, marketplace, and licensing infrastructure.', action: 'Open Go Flipbooks', href: 'https://go-flipbooks.vercel.app/' },
  { mark: 'PA', name: 'PentaAds', state: 'LICENSE INTAKE', description: 'Placement, inventory, campaign, publisher, measurement, and ad-governance operating system.', action: 'Request evaluation', href: 'mailto:contact@crownthrive.com?subject=PentaAds%20Evaluation' },
  { mark: 'TE', name: 'ThriveEvergreen', state: 'LICENSE INTAKE', description: 'Durable commerce fabric for recurring value, lifecycle monetization, and economic continuity.', action: 'Request scope', href: 'mailto:contact@crownthrive.com?subject=ThriveEvergreen%20Commercial%20Scope' },
  { mark: 'PP', name: 'PentaPersonas', state: 'LICENSE INTAKE', description: 'Governed persona, role, skill, workflow, and machine-readable operating packages.', action: 'Request catalog', href: 'mailto:contact@crownthrive.com?subject=PentaPersonas%20Catalog%20Request' },
  { mark: 'PC', name: 'PentaCredits', state: 'ECONOMIC RAIL', description: 'Closed-loop value, entitlement, accounting, and interoperable ecosystem credit controls.', action: 'Request integration', href: 'mailto:contact@crownthrive.com?subject=PentaCredits%20Integration' },
  { mark: 'DA', name: 'DAIL Evidence Fabric', state: 'GOVERNED', description: 'Append-only decision, action, identity, and lineage evidence for institutional continuity.', action: 'Request institutional scope', href: 'mailto:contact@crownthrive.com?subject=DAIL%20Institutional%20Scope' },
  { mark: 'RS', name: 'Reseller Control Plane', state: 'PARTNER LANE', description: 'Managed and white-label operations for agencies, operators, partners, and client portfolios.', action: 'Open partner intake', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20OS%20Reseller%20Partner%20Intake' },
  { mark: 'CF', name: 'Production Factories', state: 'COMMERCIAL LAYER', description: 'Governed factories for software, contracts, media, books, assets, packages, and release evidence.', action: 'Request factory access', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20Production%20Factory%20Access' }
];

const probes = [
  { endpoint: '/api/health', label: 'OS production health' },
  { endpoint: '/api/mcp', label: 'MCP capability surface' },
  { endpoint: '/api/chlom', label: 'CHLOM rights posture' },
  { endpoint: '/api/penta', label: 'Penta public inventory' }
];

let catalog = [];
let activeFilter = 'all';
let searchTerm = '';

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}

function formatPrice(amountMinor, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amountMinor || 0) / 100);
}

function categoryLabel(category) {
  return ({ merchandise: 'Merchandise system', 'event-production': 'Event production', 'rights-kit': 'Rights administration' })[category] || category;
}

function productMark(category) {
  return ({ merchandise: 'MX', 'event-production': 'EV', 'rights-kit': 'RX' })[category] || 'CT';
}

function productMatches(product) {
  const filterMatch = activeFilter === 'all' || product.category === activeFilter;
  const haystack = [product.name, product.sku, product.category, product.summary, ...(product.features || [])].join(' ').toLowerCase();
  return filterMatch && (!searchTerm || haystack.includes(searchTerm));
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  const empty = document.querySelector('#empty-state');
  const count = document.querySelector('#result-count');
  const visible = catalog.filter(productMatches);
  count.textContent = `${visible.length} OF ${catalog.length} OFFERS`;
  empty.hidden = visible.length > 0;
  grid.hidden = visible.length === 0;
  grid.innerHTML = visible.map((product) => `
    <article class="product-card">
      <div class="product-art" data-mark="${escapeHtml(productMark(product.category))}">
        <span class="product-category">${escapeHtml(categoryLabel(product.category))}</span>
        <span class="product-status">Live checkout</span>
      </div>
      <div class="product-body">
        <p class="product-sku">${escapeHtml(product.sku)} · ${escapeHtml(product.edition)}</p>
        <h3>${escapeHtml(product.name)}</h3>
        <p class="product-description">${escapeHtml(product.summary)}</p>
        <div class="product-features">${(product.features || []).slice(0, 4).map((feature) => `<span>${escapeHtml(feature)}</span>`).join('')}</div>
        <div class="product-meta">
          <span class="price"><small>One-time</small><strong>${escapeHtml(formatPrice(product.price_minor, product.currency))}</strong></span>
          <span class="rights-chip">${escapeHtml(product.rights_model)}<br>${escapeHtml(product.delivery_mode)}</span>
        </div>
        <div class="product-actions">
          <a class="preview" href="${escapeHtml(product.product_url)}" target="_blank" rel="noreferrer">Preview package ↗</a>
          <a class="checkout" href="${escapeHtml(product.checkout_url)}" target="_blank" rel="noreferrer">Buy securely ↗</a>
        </div>
      </div>
    </article>`).join('');
}

function renderSystems() {
  document.querySelector('#system-grid').innerHTML = systems.map((system) => `
    <article class="system-card">
      <div class="system-top"><span class="system-icon">${escapeHtml(system.mark)}</span><span class="system-state">${escapeHtml(system.state)}</span></div>
      <h3>${escapeHtml(system.name)}</h3>
      <p>${escapeHtml(system.description)}</p>
      <a href="${escapeHtml(system.href)}" ${system.href.startsWith('http') ? 'target="_blank" rel="noreferrer"' : ''}>${escapeHtml(system.action)} →</a>
    </article>`).join('');
}

function renderProbes() {
  document.querySelector('#probe-list').innerHTML = probes.map((probe) => `
    <button class="probe-button" type="button" data-probe="${escapeHtml(probe.endpoint)}">
      <span><code>GET ${escapeHtml(probe.endpoint)}</code><small>${escapeHtml(probe.label)}</small></span><b>RUN →</b>
    </button>`).join('');
}

async function runProbe(endpoint) {
  const output = document.querySelector('#terminal-output');
  output.classList.remove('error');
  output.textContent = `GET ${endpoint}\n\nReading production response…`;
  try {
    const started = performance.now();
    const response = await fetch(endpoint, { headers: { accept: 'application/json' }, cache: 'no-store' });
    const elapsed = Math.round(performance.now() - started);
    const raw = await response.text();
    let body;
    try { body = JSON.parse(raw); } catch { body = raw; }
    const receipt = {
      request: { method: 'GET', endpoint },
      response: { status: response.status, ok: response.ok, elapsed_ms: elapsed },
      observed_at: new Date().toISOString(),
      body
    };
    output.textContent = JSON.stringify(receipt, null, 2).slice(0, 12000);
    if (!response.ok) output.classList.add('error');
  } catch (error) {
    output.classList.add('error');
    output.textContent = JSON.stringify({ status: 'READBACK_FAILED', endpoint, error: String(error?.message || error), observed_at: new Date().toISOString() }, null, 2);
  }
}

function syncFilterButtons() {
  document.querySelectorAll('[data-filter]').forEach((button) => {
    const selected = button.dataset.filter === activeFilter;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
}

function readInitialState() {
  const params = new URLSearchParams(location.search);
  const filter = params.get('category');
  const query = params.get('q');
  if (['all', 'merchandise', 'event-production', 'rights-kit'].includes(filter)) activeFilter = filter;
  if (query) {
    searchTerm = query.trim().toLowerCase();
    document.querySelector('#catalog-search').value = query;
  }
  syncFilterButtons();
}

async function loadCatalog() {
  try {
    const response = await fetch('/store-catalog.v1.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`catalog ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.products)) throw new Error('catalog products missing');
    catalog = data.products.filter((product) => product.checkout_state === 'active');
    document.querySelector('#live-product-count').textContent = String(catalog.length);
    document.querySelector('#catalog-state').textContent = `${catalog.length} ACTIVE`;
    renderProducts();
  } catch (error) {
    document.querySelector('#catalog-state').textContent = 'READBACK HOLD';
    document.querySelector('#result-count').textContent = 'CATALOG UNAVAILABLE';
    document.querySelector('#product-grid').innerHTML = `<article class="empty-state"><strong>Catalog readback failed.</strong><p>${escapeHtml(error?.message || error)}</p></article>`;
  }
}

function bindEvents() {
  document.querySelector('#catalog-search').addEventListener('input', (event) => {
    searchTerm = event.target.value.trim().toLowerCase();
    renderProducts();
  });
  document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    syncFilterButtons();
    renderProducts();
  }));
  document.querySelector('#probe-list').addEventListener('click', (event) => {
    const button = event.target.closest('[data-probe]');
    if (button) runProbe(button.dataset.probe);
  });
  document.querySelector('#clear-terminal').addEventListener('click', () => {
    const output = document.querySelector('#terminal-output');
    output.classList.remove('error');
    output.textContent = '{\n  "status": "READY",\n  "instruction": "Select an endpoint to run a live read-only probe."\n}';
  });
}

renderSystems();
renderProbes();
readInitialState();
bindEvents();
loadCatalog();
