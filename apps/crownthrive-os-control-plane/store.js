const CATEGORY_META = Object.freeze({
  all: { label: 'All products', mark: 'CT', order: 0 },
  education: { label: 'Education', mark: 'ED', order: 1 },
  playbooks: { label: 'Playbooks', mark: 'PB', order: 2 },
  infrastructure: { label: 'Infrastructure', mark: 'IN', order: 3 },
  'api-platform': { label: 'API platform', mark: 'API', order: 4 },
  publishing: { label: 'Publishing', mark: 'GF', order: 5 },
  advertising: { label: 'Advertising', mark: 'AD', order: 6 },
  credits: { label: 'Crown Credits', mark: 'CR', order: 7 },
  'event-production': { label: 'Live experiences', mark: 'EV', order: 8 },
  'rights-kit': { label: 'Licensing', mark: 'RX', order: 9 },
  'scripted-audio': { label: 'Scripted audio', mark: 'AU', order: 10 },
  'stage-screen': { label: 'Stage & screen', mark: 'SC', order: 11 },
  'digital-art': { label: 'Digital art', mark: 'AR', order: 12 },
  'local-media': { label: 'Local media', mark: 'GJ', order: 13 },
  promotion: { label: 'Promotion', mark: 'LO', order: 14 },
  'creative-services': { label: 'Creative services', mark: 'VM', order: 15 },
  'managed-services': { label: 'Managed services', mark: 'MS', order: 16 },
  merchandise: { label: 'Digital merchandise', mark: 'MX', order: 17 },
  'digital-product': { label: 'Digital products', mark: 'DP', order: 98 },
});

const ALLOWED_EXTERNAL_HOSTS = new Set([
  'buy.stripe.com',
  'go-flipbooks.vercel.app',
  'tzajnzshmtzjenqulehq.supabase.co',
  'www.crownthrive.com',
  'crownthrive.com',
]);

const systems = [
  { mark: 'MCP', name: 'CrownThrive MCP', state: 'LIVE ENDPOINT', description: 'Public-safe model context and interoperability surface for discovering CrownThrive OS capabilities.', action: 'Probe MCP', href: '#developers' },
  { mark: 'CW', name: 'CHLOM Wallet', state: 'PRODUCTION ENFORCED', description: 'Mandatory verified internal-ledger gate for authenticated economic mutations across registered CrownThrive systems.', action: 'Open wallet command', href: '/wallet' },
  { mark: '3D', name: 'Three DAIL', state: 'ACTIVE LANES', description: 'DAIL Machine, DAIL Human, and DAIL Hybrid Crossover preserve typed institutional history and authority boundaries.', action: 'Inspect Three DAIL', href: '/dail' },
  { mark: 'CH', name: 'CHLOM Protocol', state: 'LIVE READBACK', description: 'Compliance Hybrid Licensing and Ownership Model controls for rights, provenance, consent, and scope.', action: 'Inspect CHLOM', href: '/api/chlom' },
  { mark: 'API', name: 'CrownThrive API Platform', state: 'ACTIVE OFFERS', description: 'Governed API access, metering, entitlements, and external developer lanes without exposing internal control-plane authority.', action: 'View API plans', href: '/store?category=api-platform' },
  { mark: 'GF', name: 'Go Flipbooks', state: 'ACTIVE OFFERS', description: 'Standard, PRO, managed services, publishing, interactive reading, delivery, and licensing infrastructure.', action: 'View publishing offers', href: '/store?category=publishing' },
  { mark: 'PA', name: 'PentaAds', state: 'ACTIVE OFFERS', description: 'Placement, inventory, publisher, campaign, MCP, source-license, and measurement operating products.', action: 'View PentaAds offers', href: '/store?category=advertising' },
  { mark: 'CR', name: 'Crown Credits', state: 'ACTIVE FUNDING OPTIONS', description: 'Closed-loop value and entitlement funding attached to CHLOM Wallet; non-cash-out, non-crypto, and nontransferable.', action: 'View credit options', href: '/store?category=credits' },
  { mark: 'VM', name: 'Virality Music', state: 'ACTIVE OFFERS', description: 'Digital companion art, printables, catalog discovery, consultation, stage/screen, audio, and story-world products.', action: 'Explore Virality offers', href: '/store?q=Virality%20Music' },
  { mark: 'GJ', name: 'Gretna Junction', state: 'ACTIVE OFFERS', description: 'Digital editions, archives, community publishing, and local business visibility through a governed local-media lane.', action: 'View local-media offers', href: '/store?category=local-media' },
  { mark: 'LO', name: 'Locticians', state: 'ACTIVE OFFERS', description: 'Featured content and elite visibility products for the beauty-professional community and directory.', action: 'View promotion offers', href: '/store?category=promotion' },
  { mark: 'PB', name: 'CrownThrive Skills', state: 'ACTIVE PLAYBOOK', description: 'Digital reference playbooks and machine-readable skill contracts across CrownThrive operating families.', action: 'View playbooks', href: '/store?category=playbooks' },
  { mark: 'PF', name: 'PentaFabric', state: 'PUBLIC READBACK', description: 'Runtime routing, execution lanes, provider posture, and evidence. Degraded provider planes remain visibly degraded.', action: 'Read fabric health', href: '/api/pentafabric-health' },
  { mark: 'PG', name: 'PentaGreen', state: 'COMMERCIAL AUTHORITY', description: 'Catalog, pricing, checkout, entitlement, fulfillment, and provider-bound commercialization control.', action: 'Open commerce command', href: '/commerce' },
  { mark: 'MS', name: 'Penta Service Fulfillment', state: 'ACTIVE OPTIONS', description: 'Scoped AI-assisted service fulfillment with explicit provider, billing, rollback, and evidence boundaries.', action: 'View managed services', href: '/store?category=managed-services' },
  { mark: 'RS', name: 'Reseller Control Plane', state: 'PARTNER LANE', description: 'Managed and white-label operations for agencies, operators, partners, and client portfolios.', action: 'Open partner intake', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20OS%20Reseller%20Partner%20Intake' },
  { mark: 'CF', name: 'Production Factories', state: 'COMMERCIAL LAYER', description: 'Governed factories for software, contracts, media, books, assets, packages, and release evidence.', action: 'Request factory access', href: 'mailto:contact@crownthrive.com?subject=CrownThrive%20Production%20Factory%20Access' },
];

const probes = [
  { endpoint: '/api/health', label: 'OS production health' },
  { endpoint: '/api/command?limit=6', label: 'CHLOM Wallet + Three DAIL aggregate' },
  { endpoint: '/api/catalog', label: 'Complete governed digital catalog' },
  { endpoint: '/api/operations', label: 'Operations and scheduler posture' },
  { endpoint: '/api/mcp', label: 'MCP capability surface' },
  { endpoint: '/api/chlom', label: 'CHLOM rights posture' },
  { endpoint: '/api/penta', label: 'Penta public inventory' },
  { endpoint: '/api/pentafabric-health', label: 'PentaFabric public health' },
  { endpoint: '/api/fabric', label: 'Provider-plane readback; may truthfully degrade' },
];

let catalog = [];
let catalogMeta = {};
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
  if (raw.startsWith('#')) return raw;
  if (raw.startsWith('/') && !raw.startsWith('//')) return raw;
  if (/^mailto:[^\s@]+@[^\s@]+/i.test(raw)) return raw;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'https:' || !ALLOWED_EXTERNAL_HOSTS.has(parsed.hostname)) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

function formatPrice(amountMinor, currency = 'USD') {
  const amount = Number(amountMinor || 0) / 100;
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: String(currency || 'USD').toUpperCase() }).format(amount);
  } catch {
    return `$${amount.toFixed(2)}`;
  }
}

function categoryLabel(category) {
  return CATEGORY_META[category]?.label || String(category || 'Digital product').replaceAll('-', ' ');
}

function productMark(category) {
  return CATEGORY_META[category]?.mark || 'CT';
}

function cadenceLabel(offer) {
  if (offer.billing_type === 'recurring') {
    if (offer.recurring_interval === 'month') return 'Monthly';
    if (offer.recurring_interval === 'year') return 'Annual';
    if (offer.recurring_interval) return `Per ${offer.recurring_interval}`;
    return 'Subscription';
  }
  return 'One-time';
}

function normalizeOffer(raw, product) {
  const checkoutUrl = safeUrl(raw?.checkout_url || raw?.payment_link_url || product?.checkout_url);
  if (!checkoutUrl || !checkoutUrl.startsWith('https://buy.stripe.com/')) return null;
  return {
    offer_id: String(raw?.offer_id || raw?.provider_price_id || raw?.price_id || `${product?.provider_product_id || product?.sku}-${raw?.amount_minor ?? product?.price_minor}`),
    provider_price_id: raw?.provider_price_id || raw?.price_id || product?.provider_price_id || null,
    provider_payment_link_id: raw?.provider_payment_link_id || raw?.payment_link_id || product?.provider_payment_link_id || null,
    checkout_url: checkoutUrl,
    amount_minor: Number(raw?.amount_minor ?? product?.price_minor ?? 0),
    currency: String(raw?.currency || product?.currency || 'USD').toUpperCase(),
    billing_type: String(raw?.billing_type || product?.billing_model || 'one_time'),
    recurring_interval: raw?.recurring_interval || null,
    checkout_state: 'active',
    observed_at: raw?.observed_at || product?.updated_at || null,
  };
}

function normalizeProduct(raw) {
  const product = { ...raw };
  const sourceOffers = Array.isArray(product.offers) && product.offers.length
    ? product.offers
    : [{
        offer_id: product.provider_price_id,
        provider_price_id: product.provider_price_id,
        provider_payment_link_id: product.provider_payment_link_id,
        checkout_url: product.checkout_url,
        amount_minor: product.price_minor,
        currency: product.currency,
        billing_type: product.billing_model || 'one_time',
        recurring_interval: null,
      }];

  const seen = new Set();
  const offers = sourceOffers
    .map((offer) => normalizeOffer(offer, product))
    .filter(Boolean)
    .filter((offer) => {
      const signature = [offer.amount_minor, offer.currency, offer.billing_type, offer.recurring_interval || ''].join('|');
      if (seen.has(signature)) return false;
      seen.add(signature);
      return true;
    })
    .sort((left, right) => left.amount_minor - right.amount_minor || cadenceLabel(left).localeCompare(cadenceLabel(right)));

  const category = CATEGORY_META[product.category] ? product.category : 'digital-product';
  const primaryOffer = offers[0] || null;
  return {
    ...product,
    catalog_key: String(product.catalog_key || product.provider_product_id || product.sku || product.slug || product.name),
    category,
    currency: String(product.currency || primaryOffer?.currency || 'USD').toUpperCase(),
    offers,
    variant_count: offers.length,
    price_minor: Number(product.price_minor ?? primaryOffer?.amount_minor ?? 0),
    max_price_minor: Number(product.max_price_minor ?? offers.at(-1)?.amount_minor ?? product.price_minor ?? 0),
    checkout_url: primaryOffer?.checkout_url || safeUrl(product.checkout_url),
    checkout_state: offers.length ? 'active' : 'unavailable',
    features: Array.isArray(product.features) ? product.features.filter(Boolean) : [],
  };
}

function productMatches(product) {
  const filterMatch = activeFilter === 'all' || product.category === activeFilter;
  const offerText = product.offers.map((offer) => `${formatPrice(offer.amount_minor, offer.currency)} ${cadenceLabel(offer)}`).join(' ');
  const haystack = [
    product.name, product.subtitle, product.sku, product.category, product.source_category,
    product.summary, product.audience, product.corridor, product.delivery_mode, product.rights_model,
    offerText, ...product.features,
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
  for (const feature of product.features || []) {
    if (feature && !values.includes(feature)) values.push(feature);
  }
  if (product.corridor && !values.includes(product.corridor)) values.push(product.corridor);
  if (product.audience && !values.includes(product.audience)) values.push(product.audience);
  return values.slice(0, 3);
}

function shortRights(product) {
  if (product.category === 'credits') return 'Closed-loop credits';
  if (product.category === 'digital-art') return 'Personal-use digital license';
  if (['creative-services', 'managed-services', 'promotion', 'local-media'].includes(product.category)) return 'Scoped service terms';
  if (['api-platform', 'advertising', 'publishing', 'infrastructure'].includes(product.category)) return 'CHLOM software scope';
  return 'CHLOM rights attached';
}

function pricePresentation(product, selectedOffer = null) {
  if (selectedOffer) {
    return {
      label: cadenceLabel(selectedOffer),
      value: formatPrice(selectedOffer.amount_minor, selectedOffer.currency),
    };
  }
  if (!product.offers.length) return { label: 'Checkout', value: 'Unavailable' };
  if (product.offers.length === 1) {
    const offer = product.offers[0];
    return { label: cadenceLabel(offer), value: formatPrice(offer.amount_minor, offer.currency) };
  }
  const minimum = Math.min(...product.offers.map((offer) => offer.amount_minor));
  const maximum = Math.max(...product.offers.map((offer) => offer.amount_minor));
  return {
    label: `${product.offers.length} checkout options`,
    value: minimum === maximum ? formatPrice(minimum, product.currency) : `From ${formatPrice(minimum, product.currency)}`,
  };
}

function offerOptionLabel(offer) {
  return `${formatPrice(offer.amount_minor, offer.currency)} · ${cadenceLabel(offer)}`;
}

function releaseState(product) {
  if (product.public_state === 'PUBLISHED_CONTROLLED_PREVIEW') return 'Controlled preview';
  if (product.billing_model === 'subscription') return 'Active subscription';
  return 'Active checkout';
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  const empty = document.querySelector('#empty-state');
  const count = document.querySelector('#result-count');
  const visible = orderedProducts(catalog.filter(productMatches));
  const visibleCheckoutCount = visible.reduce((sum, product) => sum + product.offers.length, 0);

  count.textContent = `${visible.length} OF ${catalog.length} PRODUCTS · ${visibleCheckoutCount} CHECKOUT OPTIONS · ${catalogSource}`;
  empty.hidden = visible.length > 0;
  grid.hidden = visible.length === 0;
  grid.innerHTML = visible.map((product) => {
    const previewUrl = safeUrl(product.preview_url || product.product_url);
    const productUrl = safeUrl(product.product_url);
    const detailsUrl = productUrl && productUrl !== previewUrl ? productUrl : null;
    const primaryOffer = product.offers[0] || null;
    const price = pricePresentation(product);
    const checkoutUrl = primaryOffer?.checkout_url || null;
    const picker = product.offers.length > 1 ? `
      <label class="offer-picker">
        <span>Choose checkout option</span>
        <select data-offer-select aria-label="Choose a checkout option for ${escapeHtml(product.name)}">
          ${product.offers.map((offer) => `<option value="${escapeHtml(offer.offer_id)}">${escapeHtml(offerOptionLabel(offer))}</option>`).join('')}
        </select>
      </label>` : '';
    const actions = [
      previewUrl ? `<a class="preview" href="${escapeHtml(previewUrl)}" target="_blank" rel="noreferrer">Open preview ↗</a>` : '',
      detailsUrl ? `<a class="preview" href="${escapeHtml(detailsUrl)}" target="_blank" rel="noreferrer">Product page ↗</a>` : '',
      checkoutUrl ? `<a class="checkout" data-checkout-link href="${escapeHtml(checkoutUrl)}" target="_blank" rel="noreferrer" aria-label="Buy ${escapeHtml(product.name)} securely">Buy securely ↗</a>` : '<span class="checkout-unavailable">Checkout unavailable</span>',
    ].filter(Boolean).join('');
    const actionCount = [previewUrl, detailsUrl, checkoutUrl].filter(Boolean).length;
    const edition = product.edition && product.edition !== 'Current' ? product.edition : 'Current edition';

    return `
      <article class="product-card" data-product-key="${escapeHtml(product.catalog_key)}">
        <div class="product-art" data-mark="${escapeHtml(productMark(product.category))}">
          <span class="product-category">${escapeHtml(categoryLabel(product.category))}</span>
          <span class="product-status">${escapeHtml(releaseState(product))}</span>
        </div>
        <div class="product-body">
          <p class="product-sku">${escapeHtml(product.sku || product.catalog_key)} · ${escapeHtml(edition)}</p>
          <h3>${escapeHtml(product.name)}</h3>
          <p class="product-description">${escapeHtml(product.summary || product.subtitle || 'Governed CrownThrive digital product or service.')}</p>
          <div class="product-features">${productFeatures(product).map((feature) => `<span>${escapeHtml(feature)}</span>`).join('')}</div>
          <div class="product-meta">
            <span class="price"><small data-price-label>${escapeHtml(price.label)}</small><strong data-price-value>${escapeHtml(price.value)}</strong></span>
            <span class="rights-chip" title="${escapeHtml(product.rights_model || '')}">${escapeHtml(shortRights(product))}<br>${escapeHtml(product.offers.length)} verified option${product.offers.length === 1 ? '' : 's'}</span>
          </div>
          ${picker}
          <div class="product-boundaries">
            <span><b>Delivery</b><small>${escapeHtml(product.delivery_mode || 'Payment-verified digital fulfillment')}</small></span>
            <span><b>Rights</b><small>${escapeHtml(product.rights_model || 'CHLOM-scoped rights attached')}</small></span>
          </div>
          <div class="product-actions" data-actions="${actionCount}">${actions}</div>
        </div>
      </article>`;
  }).join('');
}

function categoryCounts() {
  return catalog.reduce((counts, product) => {
    if (!counts[product.category]) counts[product.category] = { products: 0, checkouts: 0 };
    counts[product.category].products += 1;
    counts[product.category].checkouts += product.offers.length;
    return counts;
  }, {});
}

function renderFilters() {
  const container = document.querySelector('.filters');
  if (!container) return;
  const counts = categoryCounts();
  const categories = Object.keys(CATEGORY_META)
    .filter((category) => category === 'all' || counts[category])
    .sort((left, right) => CATEGORY_META[left].order - CATEGORY_META[right].order);

  container.innerHTML = categories.map((category) => {
    const amount = category === 'all' ? catalog.length : counts[category].products;
    const checkoutCount = category === 'all'
      ? catalog.reduce((sum, product) => sum + product.offers.length, 0)
      : counts[category].checkouts;
    return `<button type="button" data-filter="${escapeHtml(category)}" title="${escapeHtml(`${checkoutCount} active checkout option${checkoutCount === 1 ? '' : 's'}`)}">${escapeHtml(CATEGORY_META[category].label)} <span>${amount}</span></button>`;
  }).join('');
  bindFilterButtons();
  syncFilterButtons();
}

function renderSystems() {
  document.querySelector('#system-grid').innerHTML = systems.map((system) => {
    const href = safeUrl(system.href) || '#developers';
    const external = href.startsWith('https:');
    return `
      <article class="system-card">
        <div class="system-top"><span class="system-icon">${escapeHtml(system.mark)}</span><span class="system-state">${escapeHtml(system.state)}</span></div>
        <h3>${escapeHtml(system.name)}</h3>
        <p>${escapeHtml(system.description)}</p>
        <a href="${escapeHtml(href)}" ${external ? 'target="_blank" rel="noreferrer"' : ''}>${escapeHtml(system.action)} →</a>
      </article>`;
  }).join('');
}

function renderProbes() {
  document.querySelector('#probe-list').innerHTML = probes.map((probe) => `
    <button class="probe-button" type="button" data-probe="${escapeHtml(probe.endpoint)}">
      <span><code>GET ${escapeHtml(probe.endpoint)}</code><small>${escapeHtml(probe.label)}</small></span><b>RUN →</b>
    </button>`).join('');
  const probeCount = document.querySelector('#live-probe-count');
  if (probeCount) probeCount.textContent = String(probes.length);
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
      interpretation: response.ok ? 'REACHABLE' : 'REACHABLE_WITH_TRUTHFUL_NON_PASS_STATE',
      observed_at: new Date().toISOString(),
      body,
    };
    output.textContent = JSON.stringify(receipt, null, 2).slice(0, 30000);
    if (!response.ok) output.classList.add('error');
  } catch (error) {
    output.classList.add('error');
    output.textContent = JSON.stringify({
      status: 'READBACK_FAILED', endpoint, error: String(error?.message || error), observed_at: new Date().toISOString()
    }, null, 2);
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
  const products = data.products.map(normalizeProduct).filter((product) => product.checkout_state === 'active');
  return { data, products };
}

function updateCatalogMetrics(data) {
  const productCount = catalog.length;
  const checkoutCount = catalog.reduce((sum, product) => sum + product.offers.length, 0);
  const categoryCount = new Set(catalog.map((product) => product.category)).size;
  const assign = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = String(value);
  };
  assign('#live-product-count', productCount);
  assign('#live-checkout-count', checkoutCount);
  assign('#live-category-count', categoryCount);
  assign('#live-probe-count', probes.length);
  assign('#catalog-state', `${productCount} PRODUCTS · ${checkoutCount} CHECKOUTS`);

  const note = document.querySelector('#catalog-scope-note');
  if (note) {
    const excluded = Number(data?.physical_products_excluded || 0);
    const collapsed = Number(data?.duplicate_active_links_collapsed || 0);
    note.textContent = catalogSource.startsWith('LIVE')
      ? `${productCount} active digital products expose ${checkoutCount} canonical checkout options across ${categoryCount} categories. ${excluded} made-to-order physical products remain outside this digital catalog; ${collapsed} duplicate active links were collapsed.`
      : 'Recovery catalog in use. Live provider readback is unavailable, so this snapshot may not include the complete current digital-product estate.';
  }
}

async function loadCatalog() {
  try {
    const live = await fetchCatalog('/api/catalog');
    if (!live.products.length) throw new Error('live catalog empty');
    catalog = live.products;
    catalogMeta = live.data;
    catalogSource = 'LIVE THRIVEBASE';
  } catch (liveError) {
    try {
      const fallback = await fetchCatalog('/store-catalog.v1.json');
      catalog = fallback.products;
      catalogMeta = fallback.data;
      catalogSource = `RECOVERY SNAPSHOT (${catalog.length})`;
    } catch (fallbackError) {
      throw new Error(`${liveError?.message || liveError}; ${fallbackError?.message || fallbackError}`);
    }
  }

  updateCatalogMetrics(catalogMeta);
  renderFilters();
  renderProducts();
}

function handleOfferSelection(select) {
  const card = select.closest('[data-product-key]');
  if (!card) return;
  const product = catalog.find((candidate) => candidate.catalog_key === card.dataset.productKey);
  const offer = product?.offers.find((candidate) => candidate.offer_id === select.value);
  if (!product || !offer) return;

  const price = pricePresentation(product, offer);
  const label = card.querySelector('[data-price-label]');
  const value = card.querySelector('[data-price-value]');
  const checkout = card.querySelector('[data-checkout-link]');
  if (label) label.textContent = price.label;
  if (value) value.textContent = price.value;
  if (checkout) {
    checkout.href = offer.checkout_url;
    checkout.setAttribute('aria-label', `Buy ${product.name} — ${offerOptionLabel(offer)} securely`);
    checkout.textContent = `Buy ${cadenceLabel(offer).toLowerCase()} ↗`;
  }
}

function bindEvents() {
  document.querySelector('#catalog-search').addEventListener('input', (event) => {
    searchTerm = event.target.value.trim().toLowerCase();
    syncUrl();
    renderProducts();
  });
  document.querySelector('#product-grid').addEventListener('change', (event) => {
    const select = event.target.closest('[data-offer-select]');
    if (select) handleOfferSelection(select);
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
