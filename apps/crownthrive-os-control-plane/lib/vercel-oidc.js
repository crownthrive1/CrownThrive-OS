/**
 * Resolve request metadata with standards-based APIs.
 *
 * Vercel injects workload identity in `x-vercel-oidc-token` and may also expose
 * `VERCEL_OIDC_TOKEN`. Token material is never logged, serialized, or returned.
 */
export function requestHeader(request, name) {
  const value = request?.headers?.[String(name).toLowerCase()];
  if (Array.isArray(value)) return value[0] || null;
  return typeof value === 'string' && value.length > 0 ? value : null;
}

export function requestUrl(request) {
  const protocol = requestHeader(request, 'x-forwarded-proto') || 'https';
  const host =
    requestHeader(request, 'x-forwarded-host') ||
    requestHeader(request, 'host') ||
    'localhost';
  return new URL(request?.url || '/', `${protocol}://${host}`);
}

export function requestQueryParam(request, name) {
  return requestUrl(request).searchParams.get(String(name));
}

export function resolveVercelOidcToken(request) {
  const token =
    requestHeader(request, 'x-vercel-oidc-token') ||
    process.env.VERCEL_OIDC_TOKEN ||
    null;
  return typeof token === 'string' && token.length > 0 ? token : null;
}

export function hasVercelOidcToken(request) {
  return Boolean(resolveVercelOidcToken(request));
}
