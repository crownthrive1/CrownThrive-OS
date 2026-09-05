const CANONICAL_SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const CATALOG_SCHEMA = 'ct.crownthrive.marketplace-catalog.v2';

const CATEGORY_MAP = Object.freeze({
  Education: 'education',
  Infrastructure: 'infrastructure',
  'Live Experience': 'event-production',
  Licensing: 'rights-kit',
  Merchandise: 'merchandise',
  'Scripted audio': 'scripted-audio',
  'Full-length stage/screen': 'stage-screen',
});

function setHeaders(response, payload = null) {
  response.setHeader('Cache-Control', 'public, max-age=0, s-maxage=60, stale-while-revalidate=300');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  response.setHeader('X-CrownThrive-Catalog-State', payload?.status || 'UNKNOWN');
}

function send(response, status, payload, head = false) {
  setHeaders(response, payload);
  if (head) return response.status(status).end();
  return response.status(status).json(payload);
}

function canonicalSupabaseOrigin(value) {
  const raw = String(value || '');
  if (raw !== CANONICAL_SUPABASE_ORIGIN && raw !== `${CANONICAL_SUPABASE_ORIGIN}/`) return null;
  try {
    const parsed = new URL(raw);
    if (
      parsed.protocol !== 'https:' || parsed.origin !== CANONICAL_SUPABASE_ORIGIN ||
      parsed.username || parsed.password || parsed.port || parsed.pathname !== '/' ||
      parsed.search || parsed.hash
    ) return null;
    return CANONICAL_SUPABASE_ORIGIN;
  } catch {
    return null;
  }
}

function bindingState() {
  const suppliedUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!suppliedUrl || !serviceRoleKey) return { state: 'UNBOUND', origin: null, serviceRoleKey: null };
  const origin = canonicalSupabaseOrigin(suppliedUrl);
  if (!origin) return { state: 'CONFIGURATION_HOLD', origin: null, serviceRoleKey: null };
  return { state: 'BOUND', origin, serviceRoleKey };
}

function slugCategory(value) {
  const source = String(value || 'Digital product').trim();
  return CATEGORY_MAP[source] || source.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'digital-product';
}

function normalizeProduct(row) {
  const features = [
    row.product_format,
    row.corridor,
    row.audience,
    Number.isFinite(Number(row.credits)) ? `${Number(row.credits)} Crown Credits equivalent` : null,
  ].filter(Boolean);

  return {
    sku: row.sku,
    name: row.title,
    subtitle: row.subtitle || null,
    category: slugCategory(row.category),
    source_category: row.category,
    summary: row.subtitle || row.product_format || 'Governed CrownThrive digital product.',
    features,
    audience: row.audience || null,
    corridor: row.corridor || null,
    price_minor: Number(row.price_cents || 0),
    credits: Number(row.credits || 0),
    currency: 'USD',
    edition: row.edition,
    checkout_state: 'active',
    checkout_url: row.stripe_payment_link_url,
    product_url: row.public_url,
    preview_url: row.preview_url,
    delivery_mode: 'Payment-verified tokenized digital delivery',
    rights_model: 'CHLOM purchaser-use license',
    rights_state: row.rights_state,
    public_state: row.public_state,
    asset_sha256: row.package_sha256,
    package_bytes: Number(row.package_bytes || 0),
    provider_product_id: row.stripe_product_id,
    provider_price_id: row.stripe_price_id,
    provider_payment_link_id: row.stripe_payment_link_id,
    updated_at: row.updated_at,
  };
}

async function readProducts(binding) {
  const target = new URL('/rest/v1/go_flipbooks_pentabooks_products_v1', binding.origin);
  target.searchParams.set('select', [
    'sku','title','subtitle','category','product_format','audience','corridor','edition','price_cents','credits',
    'stripe_product_id','stripe_price_id','stripe_payment_link_id','stripe_payment_link_url',
    'public_url','preview_url','rights_state','delivery_state','public_state','active',
    'package_sha256','package_bytes','updated_at'
  ].join(','));
  target.searchParams.set('active', 'eq.true');
  target.searchParams.set('public_state', 'eq.PUBLISHED_CONTROLLED_PREVIEW');
  target.searchParams.set('stripe_payment_link_url', 'like.https://buy.stripe.com/%');
  target.searchParams.set('order', 'category.asc,title.asc');
  target.searchParams.set('limit', '500');

  const upstream = await fetch(target, {
    method: 'GET',
    redirect: 'error',
    cache: 'no-store',
    headers: {
      apikey: binding.serviceRoleKey,
      Authorization: `Bearer ${binding.serviceRoleKey}`,
      Accept: 'application/json',
    },
  });

  if (!upstream.ok) {
    const error = new Error('catalog_readback_failed');
    error.status = upstream.status;
    throw error;
  }

  const rows = await upstream.json();
  if (!Array.isArray(rows)) throw new Error('catalog_readback_invalid');
  return rows.map(normalizeProduct);
}

function categoryCounts(products) {
  return products.reduce((counts, product) => {
    counts[product.category] = (counts[product.category] || 0) + 1;
    return counts;
  }, {});
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: CATALOG_SCHEMA,
      status: 'REJECTED',
      error: 'method_not_allowed',
      products: [],
      pass_manufactured: false,
    });
  }

  const binding = bindingState();
  if (binding.state !== 'BOUND') {
    return send(response, binding.state === 'UNBOUND' ? 200 : 503, {
      schema: CATALOG_SCHEMA,
      status: binding.state === 'UNBOUND' ? 'PARTIAL' : 'DEGRADED',
      source: { provider: 'supabase', state: binding.state, mode: 'SERVER_ONLY_ACTIVE_PUBLICATION_READBACK' },
      active_checkout_count: 0,
      category_counts: {},
      products: [],
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }

  try {
    const products = await readProducts(binding);
    const payload = {
      schema: CATALOG_SCHEMA,
      catalog_id: 'ct.catalog.cos-marketplace.v2',
      catalog_name: 'CrownThrive OS Marketplace',
      status: products.length > 0 ? 'LIVE' : 'PARTIAL',
      source: {
        provider: 'supabase',
        state: 'BOUND',
        relation: 'public.go_flipbooks_pentabooks_products_v1',
        mode: 'SERVER_ONLY_ACTIVE_PUBLICATION_READBACK',
        selection: 'active + PUBLISHED_CONTROLLED_PREVIEW + Stripe Payment Link',
        secret_material_exposed: false,
      },
      economic_owner: 'PentaGreen',
      rights_framework: 'CHLOM',
      currency: 'USD',
      active_checkout_count: products.length,
      category_counts: categoryCounts(products),
      products,
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    };
    return send(response, 200, payload, head);
  } catch (error) {
    return send(response, 503, {
      schema: CATALOG_SCHEMA,
      status: 'DEGRADED',
      source: { provider: 'supabase', state: 'READBACK_FAILED', mode: 'SERVER_ONLY_ACTIVE_PUBLICATION_READBACK' },
      active_checkout_count: 0,
      category_counts: {},
      products: [],
      error: String(error?.message || error),
      upstream_status: Number(error?.status || 0) || null,
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }
}
