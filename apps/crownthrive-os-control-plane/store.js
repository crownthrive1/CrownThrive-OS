const CATEGORY_META = Object.freeze({
  all: { label: 'All products', mark: 'CT', order: 0 },
  education: { label: 'Education', mark: 'ED', order: 1 },
  infrastructure: { label: 'Infrastructure', mark: 'IN', order: 2 },
  'event-production': { label: 'Live experiences', mark: 'EV', order: 3 },
  'rights-kit': { label: 'Licensing', mark: 'RX', order: 4 },
  merchandise: { label: 'Merchandise', mark: 'MX', order: 5 },
  'scripted-audio': { label: 'Scripted audio', mark: 'AU', order: 6 },
  'stage-screen': { label: 'Stage & screen', mark: 'SC', order: 7 },
});

const ALLOWED_EXTERNAL_HOSTS = new Set([
  'buy.stripe.com',
  'go-flipbooks.vercel.app',
  'tzajnzshmtzjenqulehq.supabase.co',
  'www.crownthrive.com',
  'crownthrive.com',
]);

const systems = [
  { mark: 'MCP', name: 'CrownThrive MCP', state: 'LIVE ENDPOINT', description: 'Public-safe model context and interoperability surface for discovering CrownThrive OS capabilities.', action: 'Probe MCP', href: '#developers', probe: '/api/mcp' },
  { mark: 'CW', name: 'CHLOM Wallet', state: 'PRODUCTION ENFORCED', description: 'Mandatory verified internal-ledger gate for authenticated economic mutations across registered CrownThrive systems.', action: 'Open wallet command', href: '/wallet' },
  { mark: '3D', name: 'Three DAIL', state: 'ACTIVE LANES', description: 'DAIL Machine, DAIL Human, and DAIL Hybrid Crossover preserve typed institutional history and authority boundaries.', action: 'Inspect Three DAIL', href: '/dail' },
  { mark: 'CH', name: 'CHLOM Protocol', state: 'LIVE READBACK', description: 'Compliance Hybrid Licensing and Ownership Model controls for rights, provenance, consent, and scope.', action: 'Inspect CHLOM', href: '/api/chlom' },
  { mark: 'PF', name: 'PentaFabric', state: 'LIVE HEALTH', description: 'Runtime routing, execution lanes, provider posture, and public-safe evidence for the Penta operating fabric.', action: 'Read fabric health', href: '/api/pentafabric-health' },
  { mark: 'PG', name: 'PentaGreen', state: 'COMMERCIAL LAYER', description: 'Catalog, pricing, checkout, entitlement, fulfillment, and provider-bound commercialization control.', action: 'Request license', href: 'mailto:contact@crownthrive.com?subject=PentaGreen%20Commercial%20License' },
  { mark: 'GF', name: 'Go Flipbooks', state: 'LIVE CATALOG', description: 'Publishing, interactive reading, digital delivery, marketplace, and licensing infrastructure.', action: 'Open Go Flipbooks', href: 'https://go-flipbooks.vercel.app/' },
  { mark: 'PA', name: 'PentaAds', state: 'LICENSE INTAKE', description: 'Placement, inventory, campaign, publisher, measurement, and ad-governance operating system.', action: 'Request evaluation', href: 'mailto:contact@crownthrive.com?subject=PentaAds%20Evaluation' },
  { mark: 'TE', name: 'ThriveEvergreen', state: 'LICENSE INTAKE', description: 'Durable commerce fabric for recurring value, lifecycle monetization, and economic continuity.', action: 'Request scope', href: 'mailto:contact@crownthrive.com?subject=ThriveEvergreen%20Commercial%20Scope' },
  { mark: 'PP', name: 'PentaPersonas', state: 'LICENSE INTAKE', description: 'Governed persona, role, skill, workflow, and machine-readable operating packages.', action: 'Request catalog', href: 'mailto:contact@crownthrive.com?subject=PentaPersonas%20Catalog%20Request' },
  { mark: 'CR', name: 'Crown Credits', state: 'INTERNAL ECONOMIC RAIL', description: 'Closed-loop value, entitlement, accounting, and interoperable ecosystem credit controls attached to CHLOM Wallet.', action: 'Request integration', href: 'mailto:contact@crownthrive.com?subject=Crown%20Credits%20Integration' },
  { mark: 'RS', name: 'Reseller Control Plane', state: 'PARTNER LANE', description: 'Managed and white-label operations for agencies, operators, partners, and client portfolios.', action: 'Open partner intake', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20OS%20Reseller%20Partner%20Intake' },
  { mark: 'CF', name: 'Production Factories', state: 'COMMERCIAL LAYER', description: 'Governed factories for software, contracts, media, books, assets, packages, and release evidence.', action: 'Request factory access', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20Production%20Factory%20Access' },
];

const probes = [
  { endpoint: '/api/health', label: 'OS production health' },
  { endpoint: '/api/command?limit=6', label: 'CHLOM Wallet + Three DAIL aggregate' },
  { endpoint: '/api/catalog', label: 'Complete governed product catalog' },
  { endpoint: '/api/mcp', label: 'MCP capability surface' },
  { endpoint: '/api/chlom', label: 'CHLOM rights posture' },
  { endpoint: '/api/penta', label: 'Penta public inventory' },
];

let catalog = [];
let activeFilter = 'all';
let searchTerm = '';
let catalogSource = 'READING';

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}

function safeUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  if (raw.startsWith('/') && !raw.startsWith('//')) return raw;
  if (raw.startsWith('mailto:')) return raw;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'https:' || !ALLOWED_EXTERNAL_HOSTS.has(parsed.hostname)) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

function formatPrice(amountMinor, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amountMinor || 0) / 100);
}

function categoryLabel(category) {
  return CATEGORY_META[category]?.label || String(category || 'Digital product').replaceAll('-', ' ');
}

function productMark(category) {
  return CATEGORY_META[category]?.mark || 'CT';
}

function productMatches(product) {
  const filterMatch = activeFilter === 'all' || product.category === activeFilter;
  const haystack = [
    product.name, product.subtitle, product.sku, product.category, product.source_category,
    product.summary, product.audience, product.corridor, ...(product.features || [])
  ].join(' ').toLowerCase();
  return filterMatch && (!searchTerm || haystack.includes(searchTerm));
}

function orderedProducts(products) {
  return [...products].sort((left, right) => {
    const categoryDifference = (CATEGORY_META[left.category]?.order ?? 99) - (CATEGORY_META[right.category]?.order ?? 99);
    if (categoryDifference) return categoryDifference;
    return String(left.name || '').localeCompare(String(right.name || ''));
  });
}

function productFeatures(product) {
  const values = [];
  if (Array.isArray(product.features) && product.features[0]) values.push(product.features[0]);
  if (product.corridor) values.push(product.corridor);
  if (Number(product.credits) > 0) values.push(`${Number(product.credits)} Crown Credits equivalent`);
  return values.slice(0, 3);
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  const empty = document.querySelector('#empty-state');
  const count = document.querySelector('#result-count');
  const visible = orderedProducts(catalog.filter(productMatches));
  count.textContent = `${visible.length} OF ${catalog.length} OFFERS · ${catalogSource}`;
  empty.hidden = visible.length > 0;
  grid.hidden = visible.length === 0;
  grid.innerHTML = visible.map((product) => {
    const previewUrl = safeUrl(product.preview_url || product.product_url);
    const productUrl = safeUrl(product.product_url);
    const checkoutUrl = safeUrl(product.checkout_url);
    const detailsUrl = productUrl && productUrl !== previewUrl ? productUrl : null;
    const actions = [
      previewUrl ? `<a class="preview" href="${escapeHtml(previewUrl)}" target="_blank" rel="noreferrer">Open preview ↗</a>` : '',
      detailsUrl ? `<a class="preview" href="${escapeHtml(detailsUrl)}" target="_blank" rel="noreferrer">Product page ↗</a>` : '',
      checkoutUrl ? `<a class="checkout" href="${escapeHtml(checkoutUrl)}" target="_blank" rel="noreferrer">Buy securely ↗</a>` : '<span class="rights-chip">Checkout unavailable</span>',
    ].filter(Boolean).join('');
    const actionCount = [previewUrl, detailsUrl, checkoutUrl].filter(Boolean).length;
    const releaseState = product.public_state === 'PUBLISHED_CONTROLLED_PREVIEW' ? 'Controlled preview' : 'Live checkout';

    return `
      <article class="product-card">
        <div class="product-art" data-mark="${escapeHtml(productMark(product.category))}">
          <span class="product-category">${escapeHtml(categoryLabel(product.category))}</span>
          <span class="product-status">${escapeHtml(releaseState)}</span>
        </div>
        <div class="product-body">
          <p class="product-sku">${escapeHtml(product.sku)} · ${escapeHtml(product.edition)}</p>
          <h3>${escapeHtml(product.name)}</h3>
          <p class="product-description">${escapeHtml(product.summary || product.subtitle)}</p>
          <div class="product-features">${productFeatures(product).map((feature) => `<span>${escapeHtml(feature)}</span>`).join('')}</div>
          <div class="product-meta">
            <span class="price"><small>One-time</small><strong>${escapeHtml(formatPrice(product.price_minor, product.currency))}</strong></span>
            <span class="rights-chip">CHLOM purchaser-use<br>Tokenized delivery</span>
          </div>
          <div class="product-actions" data-actions="${actionCount}">${actions}</div>
        </div>
      </article>`;
  }).join('');
}

function categoryCounts() {
  return catalog.reduce((counts, product) => {
    counts[product.category] = (counts[product.category] || 0) + 1;
    return counts;
  }, {});
}

function renderFilters() {
  const container = document.querySelector('.filters');
  if (!container) return;
  const counts = categoryCounts();
  const categories = Object.keys(CATEGORY_META)
    .filter((category) => category === 'all' || counts[category])
    .sort((a, b) => CATEGORY_META[a].order - CATEGORY_META[b].order);
  container.innerHTML = categories.map((category) => {
    const amount = category === 'all' ? catalog.length : counts[category];
    return `<button type="button" data-filter="${escapeHtml(category)}">${escapeHtml(CATEGORY_META[category].label)} <span>${amount}</span></button>`;
  }).join('');
  bindFilterButtons();
  syncFilterButtons();
}

function renderSystems() {
  document.querySelector('#system-grid').innerHTML = systems.map((system) => {
    const href = safeUrl(system.href) || '#developers';
    return `
      <article class="system-card">
        <div class="system-top"><span class="system-icon">${escapeHtml(system.mark)}</span><span class="system-state">${escapeHtml(system.state)}</span></div>
        <h3>${escapeHtml(system.name)}</h3>
        <p>${escapeHtml(system.description)}</p>
        <a href="${escapeHtml(href)}" ${href.startsWith('https:') ? 'target="_blank" rel="noreferrer"' : ''}>${escapeHtml(system.action)} →</a>
      </article>`;
  }).join('');
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
    output.textContent = JSON.stringify(receipt, null, 2).slice(0, 20000);
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

function syncUrl() {
  const params = new URLSearchParams();
  if (activeFilter !== 'all') params.set('category', activeFilter);
  if (searchTerm) params.set('q', searchTerm);
  const next = `${location.pathname}${params.size ? `?${params}` : ''}${location.hash}`;
  history.replaceState(null, '', next);
}

function bindFilterButtons() {
  document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    syncFilterButtons();
    syncUrl();
    renderProducts();
  }));
}

function readInitialState() {
  const params = new URLSearchParams(location.search);
  const filter = params.get('category');
  const query = params.get('q');
  if (filter && CATEGORY_META[filter]) activeFilter = filter;
  if (query) {
    searchTerm = query.trim().toLowerCase();
    document.querySelector('#catalog-search').value = query;
  }
}

async function fetchCatalog(url) {
  const response = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  const data = await response.json();
  if (!Array.isArray(data.products)) throw new Error(`${url} products missing`);
  return { data, products: data.products.filter((product) => product.checkout_state === 'active') };
}

async function loadCatalog() {
  try {
    const live = await fetchCatalog('/api/catalog');
    if (!live.products.length) throw new Error('live catalog empty');
    catalog = live.products;
    catalogSource = 'LIVE THRIVEBASE';
    document.querySelector('#catalog-state').textContent = `${catalog.length} ACTIVE · LIVE`;
  } catch (liveError) {
    try {
      const fallback = await fetchCatalog('/store-catalog.v1.json');
      catalog = fallback.products;
      catalogSource = `RECOVERY SNAPSHOT (${catalog.length})`;
      document.querySelector('#catalog-state').textContent = `${catalog.length} RECOVERY`;
    } catch (fallbackError) {
      throw new Error(`${liveError?.message || liveError}; ${fallbackError?.message || fallbackError}`);
    }
  }

  document.querySelector('#live-product-count').textContent = String(catalog.length);
  renderFilters();
  renderProducts();
}

function bindEvents() {
  document.querySelector('#catalog-search').addEventListener('input', (event) => {
    searchTerm = event.target.value.trim().toLowerCase();
    syncUrl();
    renderProducts();
  });
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
loadCatalog().catch((error) => {
  document.querySelector('#catalog-state').textContent = 'READBACK HOLD';
  document.querySelector('#result-count').textContent = 'CATALOG UNAVAILABLE';
  document.querySelector('#product-grid').innerHTML = `<article class="empty-state"><strong>Catalog readback failed.</strong><p>${escapeHtml(error?.message || error)}</p></article>`;
});
