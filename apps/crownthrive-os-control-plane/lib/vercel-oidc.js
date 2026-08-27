/**
 * Resolve Vercel's request-scoped OIDC token without importing a runtime helper.
 *
 * Vercel injects the token in `x-vercel-oidc-token` and may also expose the
 * `VERCEL_OIDC_TOKEN` environment variable. The value is never logged,
 * serialized, persisted, or returned to callers.
 */
export function requestHeader(request, name) {
  const value = request?.headers?.[String(name).toLowerCase()];
  if (Array.isArray(value)) return value[0] || null;
  return typeof value === 'string' && value.length > 0 ? value : null;
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
