(() => {
  const CATEGORY_LABELS = Object.freeze({
    education: 'Education',
    infrastructure: 'Infrastructure',
    'event-production': 'Live experience',
    'rights-kit': 'Licensing',
    merchandise: 'Merchandise',
    'scripted-audio': 'Scripted audio',
    'stage-screen': 'Stage & screen',
  });

  function money(amountMinor, currency = 'USD') {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amountMinor || 0) / 100);
  }

  function addMarketplaceNavigation() {
    const nav = document.querySelector('#nav');
    if (!nav || nav.querySelector('[data-marketplace-link]')) return;
    const link = document.createElement('a');
    link.href = '/store';
    link.dataset.marketplaceLink = '';
    link.innerHTML = '<b>10</b>Marketplace';
    nav.append(link);
  }

  function createMarketplaceButton(label = 'Open Marketplace') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'primary';
    button.textContent = label;
    button.addEventListener('click', () => window.location.assign('/store'));
    return button;
  }

  function addOverviewAction() {
    const actions = document.querySelector('[data-page="overview"] .intro .actions');
    if (!actions || actions.querySelector('[data-marketplace-action]')) return;
    const button = createMarketplaceButton('Browse Digital Products');
    button.dataset.marketplaceAction = '';
    actions.append(button);
  }

  function addCommercePanel() {
    const page = document.querySelector('[data-page="commerce"]');
    if (!page || page.querySelector('#marketplaceCatalogPanel')) return null;
    const grid = page.querySelector('#commerceGrid') || page.querySelector('.grid');
    if (!grid) return null;

    const panel = document.createElement('article');
    panel.className = 'panel';
    panel.id = 'marketplaceCatalogPanel';
    panel.innerHTML = `
      <div class="panel-head">
        <div><span class="kicker">Digital product estate</span><h3>Marketplace catalog</h3></div>
        <span class="badge pending" id="marketplaceCatalogState">READING</span>
      </div>
      <div class="facts">
        <div class="fact"><span>Active products</span><strong id="marketplaceProductCount">—</strong></div>
        <div class="fact"><span>Categories</span><strong id="marketplaceCategoryCount">—</strong></div>
        <div class="fact"><span>Price range</span><strong id="marketplacePriceRange">—</strong></div>
        <div class="fact"><span>Governance</span><strong>CHLOM + PentaGreen</strong></div>
      </div>
      <div class="rows" id="marketplaceCategoryRows">
        <div class="row"><span><strong>Reading governed catalog</strong><small>Active publication, checkout, rights, and delivery evidence only</small></span><span class="badge pending">READING</span></div>
      </div>`;
    const actions = document.createElement('div');
    actions.className = 'actions';
    actions.append(createMarketplaceButton('Open All Digital Products'));
    panel.append(actions);
    grid.insertAdjacentElement('afterend', panel);
    return panel;
  }

  function setCatalogHold(message) {
    const state = document.querySelector('#marketplaceCatalogState');
    if (state) {
      state.className = 'badge hold';
      state.textContent = 'READBACK HOLD';
    }
    const rows = document.querySelector('#marketplaceCategoryRows');
    if (rows) rows.innerHTML = `<div class="row"><span><strong>Catalog unavailable</strong><small>${String(message || 'Live readback failed')}</small></span><span class="badge hold">HOLD</span></div>`;
  }

  async function hydrateCatalog() {
    const response = await fetch('/api/catalog', { cache: 'no-store', headers: { Accept: 'application/json' } });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || !Array.isArray(payload.products)) throw new Error(`catalog_${response.status}`);

    const products = payload.products.filter((product) => product.checkout_state === 'active');
    if (!products.length) throw new Error('catalog_empty');
    const counts = products.reduce((result, product) => {
      result[product.category] = (result[product.category] || 0) + 1;
      return result;
    }, {});
    const prices = products.map((product) => Number(product.price_minor || 0)).filter(Number.isFinite);

    const state = document.querySelector('#marketplaceCatalogState');
    if (state) {
      state.className = 'badge pass';
      state.textContent = `${products.length} LIVE`;
    }
    const productCount = document.querySelector('#marketplaceProductCount');
    if (productCount) productCount.textContent = new Intl.NumberFormat('en-US').format(products.length);
    const categoryCount = document.querySelector('#marketplaceCategoryCount');
    if (categoryCount) categoryCount.textContent = String(Object.keys(counts).length);
    const priceRange = document.querySelector('#marketplacePriceRange');
    if (priceRange) priceRange.textContent = prices.length ? `${money(Math.min(...prices))}–${money(Math.max(...prices))}` : '—';

    const rows = document.querySelector('#marketplaceCategoryRows');
    if (rows) {
      rows.innerHTML = Object.entries(counts)
        .sort(([a], [b]) => (CATEGORY_LABELS[a] || a).localeCompare(CATEGORY_LABELS[b] || b))
        .map(([category, count]) => `<div class="row"><span><strong>${CATEGORY_LABELS[category] || category}</strong><small>Published controlled-preview products with active checkout</small></span><span class="badge pass">${count}</span></div>`)
        .join('');
    }
  }

  function init() {
    addMarketplaceNavigation();
    addOverviewAction();
    addCommercePanel();
    hydrateCatalog().catch((error) => setCatalogHold(error?.message || error));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
