const CANONICAL_SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const CATALOG_SCHEMA = 'ct.crownthrive.marketplace-catalog.v3';
const CATALOG_RPC = 'crownthrive_marketplace_catalog_v3';

function setHeaders(response, payload = null) {
  response.setHeader('Cache-Control', 'public, max-age=0, s-maxage=60, stale-while-revalidate=300');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  response.setHeader('X-CrownThrive-Catalog-State', String(payload?.status || 'UNKNOWN'));
  response.setHeader('X-CrownThrive-Product-Count', String(payload?.active_product_count || 0));
  response.setHeader('X-CrownThrive-Checkout-Count', String(payload?.active_checkout_count || 0));
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

function normalizeRpcPayload(value) {
  if (Array.isArray(value) && value.length === 1 && value[0] && typeof value[0] === 'object') return value[0];
  return value;
}

function validCheckoutUrl(value) {
  try {
    const parsed = new URL(String(value || ''));
    return parsed.protocol === 'https:' && parsed.hostname === 'buy.stripe.com';
  } catch {
    return false;
  }
}

function validateCatalog(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('catalog_payload_invalid');
  if (payload.schema !== CATALOG_SCHEMA) throw new Error('catalog_schema_mismatch');
  if (!Array.isArray(payload.products)) throw new Error('catalog_products_missing');

  let checkoutCount = 0;
  const productKeys = new Set();
  const offerSignatures = new Set();

  for (const product of payload.products) {
    const productKey = String(product?.provider_product_id || product?.catalog_key || product?.sku || '');
    if (!productKey || productKeys.has(productKey)) throw new Error('catalog_product_identity_invalid');
    productKeys.add(productKey);

    if (product?.checkout_state !== 'active' || !Array.isArray(product?.offers) || product.offers.length < 1) {
      throw new Error('catalog_active_offer_missing');
    }

    for (const offer of product.offers) {
      if (offer?.checkout_state !== 'active' || !validCheckoutUrl(offer?.checkout_url)) {
        throw new Error('catalog_checkout_url_invalid');
      }
      const signature = [
        productKey,
        offer?.amount_minor,
        offer?.currency,
        offer?.billing_type,
        offer?.recurring_interval || '',
      ].join('|');
      if (offerSignatures.has(signature)) throw new Error('catalog_duplicate_offer_signature');
      offerSignatures.add(signature);
      checkoutCount += 1;
    }
  }

  if (Number(payload.active_product_count) !== payload.products.length) throw new Error('catalog_product_count_mismatch');
  if (Number(payload.active_checkout_count) !== checkoutCount) throw new Error('catalog_checkout_count_mismatch');
  if (Number(payload.physical_products_excluded || 0) < 0) throw new Error('catalog_physical_exclusion_invalid');

  return payload;
}

async function readCatalog(binding) {
  const target = new URL(`/rest/v1/rpc/${CATALOG_RPC}`, binding.origin);
  const upstream = await fetch(target, {
    method: 'POST',
    redirect: 'error',
    cache: 'no-store',
    headers: {
      apikey: binding.serviceRoleKey,
      Authorization: `Bearer ${binding.serviceRoleKey}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: '{}',
  });

  if (!upstream.ok) {
    const error = new Error('catalog_readback_failed');
    error.status = upstream.status;
    throw error;
  }

  const payload = normalizeRpcPayload(await upstream.json());
  return validateCatalog(payload);
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: CATALOG_SCHEMA,
      status: 'REJECTED',
      error: 'method_not_allowed',
      active_product_count: 0,
      active_checkout_count: 0,
      category_count: 0,
      category_counts: {},
      products: [],
      pass_manufactured: false,
    });
  }

  const binding = bindingState();
  if (binding.state !== 'BOUND') {
    return send(response, binding.state === 'UNBOUND' ? 200 : 503, {
      schema: CATALOG_SCHEMA,
      status: binding.state === 'UNBOUND' ? 'PARTIAL' : 'DEGRADED',
      source: {
        provider: 'supabase',
        state: binding.state,
        rpc: `public.${CATALOG_RPC}()`,
        mode: 'SERVER_ONLY_ACTIVE_DIGITAL_COMMERCE_READBACK',
        secret_material_exposed: false,
      },
      active_product_count: 0,
      active_checkout_count: 0,
      category_count: 0,
      category_counts: {},
      products: [],
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }

  try {
    const payload = await readCatalog(binding);
    return send(response, 200, payload, head);
  } catch (error) {
    return send(response, 503, {
      schema: CATALOG_SCHEMA,
      status: 'DEGRADED',
      source: {
        provider: 'supabase',
        state: 'READBACK_FAILED',
        rpc: `public.${CATALOG_RPC}()`,
        mode: 'SERVER_ONLY_ACTIVE_DIGITAL_COMMERCE_READBACK',
        secret_material_exposed: false,
      },
      active_product_count: 0,
      active_checkout_count: 0,
      category_count: 0,
      category_counts: {},
      products: [],
      error: String(error?.message || error),
      upstream_status: Number(error?.status || 0) || null,
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }
}
