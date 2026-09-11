const EXPECTED_PRICE = 'price_1UEEa1CJFUeGxc8S9orC3f1L';
const EXPECTED_PRODUCT = 'prod_VEi0bR9iBTFOUJ';
const EXPECTED_ENTITLEMENT = 'creelpilot_pro';

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  return response.status(status).json(payload);
}

async function stripeGet(path, secret, params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) value.forEach(item => query.append(key, item));
    else if (value !== undefined && value !== null) query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query}` : '';
  const result = await fetch(`https://api.stripe.com${path}${suffix}`, {
    headers: { Authorization: `Bearer ${secret}` },
  });
  const body = await result.json().catch(() => ({}));
  if (!result.ok) {
    const error = new Error(body?.error?.message || 'Stripe verification failed');
    error.status = result.status;
    throw error;
  }
  return body;
}

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return send(response, 405, { verified: false, status: 'METHOD_NOT_ALLOWED' });
  }

  const sessionId = String(request.query?.session_id || '').trim();
  if (!/^cs_(test_|live_)?[A-Za-z0-9_]+$/.test(sessionId)) {
    return send(response, 400, { verified: false, status: 'INVALID_SESSION' });
  }

  const secret = process.env.CREELPILOT_STRIPE_SECRET_KEY || process.env.STRIPE_SECRET_KEY;
  if (!secret) {
    return send(response, 503, {
      verified: false,
      status: 'STRIPE_SERVER_BINDING_REQUIRED',
      entitlement: EXPECTED_ENTITLEMENT,
    });
  }

  try {
    const session = await stripeGet(`/v1/checkout/sessions/${encodeURIComponent(sessionId)}`, secret, {
      'expand[]': ['subscription', 'line_items.data.price'],
    });

    const lineItems = session?.line_items?.data || [];
    const hasExactPrice = lineItems.some(item =>
      item?.price?.id === EXPECTED_PRICE &&
      item?.price?.product === EXPECTED_PRODUCT &&
      item?.price?.currency === 'usd' &&
      Number(item?.price?.unit_amount) === 499 &&
      item?.price?.recurring?.interval === 'month'
    );
    const subscription = session?.subscription && typeof session.subscription === 'object'
      ? session.subscription
      : null;
    const entitlement = subscription?.metadata?.entitlement || session?.metadata?.entitlement || null;
    const subscriptionStatus = subscription?.status || 'unknown';
    const subscriptionActive = ['active', 'trialing'].includes(subscriptionStatus);
    const checkoutComplete = session?.status === 'complete';
    const paymentOk = ['paid', 'no_payment_required'].includes(session?.payment_status);
    const modeOk = session?.mode === 'subscription';
    const metadataOk = entitlement === EXPECTED_ENTITLEMENT || hasExactPrice;
    const verified = Boolean(hasExactPrice && modeOk && checkoutComplete && paymentOk && subscriptionActive && metadataOk);

    return send(response, verified ? 200 : 403, {
      verified,
      entitlement: EXPECTED_ENTITLEMENT,
      status: verified ? 'PRO_ACTIVE' : 'PRO_NOT_ACTIVE',
      subscription_status: subscriptionStatus,
      checked_at: new Date().toISOString(),
    });
  } catch (error) {
    const upstream = Number(error?.status) || 502;
    return send(response, upstream === 404 ? 404 : 502, {
      verified: false,
      entitlement: EXPECTED_ENTITLEMENT,
      status: upstream === 404 ? 'SESSION_NOT_FOUND' : 'VERIFICATION_UNAVAILABLE',
    });
  }
}
