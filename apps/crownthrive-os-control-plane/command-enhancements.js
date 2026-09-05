(() => {
  const CATEGORY_LABELS = Object.freeze({
    education: 'Education',
    playbooks: 'Playbooks',
    infrastructure: 'Infrastructure',
    'api-platform': 'API platform',
    publishing: 'Publishing',
    advertising: 'Advertising',
    credits: 'Crown Credits',
    'event-production': 'Live experiences',
    'rights-kit': 'Licensing',
    'scripted-audio': 'Scripted audio',
    'stage-screen': 'Stage & screen',
    'digital-art': 'Digital art',
    'local-media': 'Local media',
    promotion: 'Promotion',
    'creative-services': 'Creative services',
    'managed-services': 'Managed services',
    merchandise: 'Digital merchandise',
    'digital-product': 'Digital products',
  });

  function money(amountMinor, currency = 'USD') {
    try {
      return new Intl.NumberFormat('en-US', { style: 'currency', currency: String(currency || 'USD').toUpperCase() }).format(Number(amountMinor || 0) / 100);
    } catch {
      return `$${(Number(amountMinor || 0) / 100).toFixed(2)}`;
    }
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
    const button = createMarketplaceButton('Browse All Digital Products');
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
        <div class="fact"><span>Checkout options</span><strong id="marketplaceCheckoutCount">—</strong></div>
        <div class="fact"><span>Categories</span><strong id="marketplaceCategoryCount">—</strong></div>
        <div class="fact"><span>Price range</span><strong id="marketplacePriceRange">—</strong></div>
      </div>
      <div class="rows" id="marketplaceCategoryRows">
        <div class="row"><span><strong>Reading governed catalog</strong><small>Active product, price, Payment Link, digital fulfillment, and CHLOM boundary evidence only</small></span><span class="badge pending">READING</span></div>
      </div>`;
    const actions = document.createElement('div');
    actions.className = 'actions';
    actions.append(createMarketplaceButton('Open 59 Digital Products'));
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
    if (rows) {
      rows.innerHTML = `<div class="row"><span><strong>Catalog unavailable</strong><small>${String(message || 'Live readback failed')}</small></span><span class="badge hold">HOLD</span></div>`;
    }
  }

  async function hydrateCatalog() {
    const response = await fetch('/api/catalog', { cache: 'no-store', headers: { Accept: 'application/json' } });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || !Array.isArray(payload.products)) throw new Error(`catalog_${response.status}`);

    const products = payload.products.filter((product) => product.checkout_state === 'active');
    if (!products.length) throw new Error('catalog_empty');

    const counts = products.reduce((result, product) => {
      if (!result[product.category]) result[product.category] = { products: 0, checkouts: 0 };
      result[product.category].products += 1;
      result[product.category].checkouts += Array.isArray(product.offers) ? product.offers.length : 1;
      return result;
    }, {});
    const prices = products.flatMap((product) => Array.isArray(product.offers)
      ? product.offers.map((offer) => Number(offer.amount_minor || 0))
      : [Number(product.price_minor || 0)]).filter(Number.isFinite);
    const productCount = Number(payload.active_product_count || products.length);
    const checkoutCount = Number(payload.active_checkout_count || Object.values(counts).reduce((sum, entry) => sum + entry.checkouts, 0));
    const categoryCount = Number(payload.category_count || Object.keys(counts).length);

    const state = document.querySelector('#marketplaceCatalogState');
    if (state) {
      state.className = 'badge pass';
      state.textContent = `${productCount} PRODUCTS`;
    }
    const productNode = document.querySelector('#marketplaceProductCount');
    if (productNode) productNode.textContent = new Intl.NumberFormat('en-US').format(productCount);
    const checkoutNode = document.querySelector('#marketplaceCheckoutCount');
    if (checkoutNode) checkoutNode.textContent = new Intl.NumberFormat('en-US').format(checkoutCount);
    const categoryNode = document.querySelector('#marketplaceCategoryCount');
    if (categoryNode) categoryNode.textContent = String(categoryCount);
    const priceRange = document.querySelector('#marketplacePriceRange');
    if (priceRange) priceRange.textContent = prices.length ? `${money(Math.min(...prices))}–${money(Math.max(...prices))}` : '—';

    const rows = document.querySelector('#marketplaceCategoryRows');
    if (rows) {
      const categoryRows = Object.entries(counts)
        .sort(([left], [right]) => (CATEGORY_LABELS[left] || left).localeCompare(CATEGORY_LABELS[right] || right))
        .map(([category, entry]) => `<div class="row"><span><strong>${CATEGORY_LABELS[category] || category}</strong><small>${entry.products} product${entry.products === 1 ? '' : 's'} · ${entry.checkouts} active checkout option${entry.checkouts === 1 ? '' : 's'}</small></span><span class="badge pass">${entry.products}</span></div>`)
        .join('');
      const exclusions = Number(payload.physical_products_excluded || 0);
      const duplicates = Number(payload.duplicate_active_links_collapsed || 0);
      rows.innerHTML = `${categoryRows}<div class="row"><span><strong>Catalog boundary</strong><small>${exclusions} physical made-to-order products excluded · ${duplicates} duplicate active links collapsed · CHLOM + PentaGreen governed</small></span><span class="badge pass">VERIFIED</span></div>`;
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
