const SITE_URL = 'https://crownthrive-os-crownthrive-os.vercel.app';
const AUTH_BASE = 'https://tzajnzshmtzjenqulehq.supabase.co/auth/v1';

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function page(title, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>${esc(title)}</title><style>body{font-family:system-ui,-apple-system,sans-serif;background:#0b0d12;color:#f6f7fb;margin:0}main{max-width:720px;margin:7vh auto;padding:32px}.card{background:#151924;border:1px solid #2a3142;border-radius:18px;padding:28px}h1{margin-top:0}code{overflow-wrap:anywhere}.muted{color:#aab2c3}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}button,a.button{appearance:none;border:0;border-radius:10px;padding:12px 18px;font-weight:700;text-decoration:none;cursor:pointer}.approve{background:#f6f7fb;color:#11151d}.deny{background:#2a3142;color:#f6f7fb}.scope{padding:10px 12px;background:#0f131c;border-radius:9px;margin:8px 0}form{display:inline}</style></head><body><main>${body}</main></body></html>`;
}

function safeReturn(raw) {
  try {
    const u = new URL(raw);
    if (u.origin !== AUTH_BASE) return null;
    if (!u.pathname.startsWith('/auth/v1/oauth/')) return null;
    return u.toString();
  } catch { return null; }
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Content-Security-Policy', "default-src 'self'; style-src 'unsafe-inline'; form-action 'self' https://tzajnzshmtzjenqulehq.supabase.co; frame-ancestors 'none'; base-uri 'none'");
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');

  const q = req.query || {};
  if (req.method === 'GET') {
    const authorizationId = q.authorization_id || q.authorizationId || '';
    const clientId = q.client_id || '';
    const scope = q.scope || '';
    const redirectUri = q.redirect_uri || '';
    const returnTo = q.return_to || '';

    if (!authorizationId && !clientId) {
      res.status(200).send(page('CrownThrive OAuth', `<section class="card"><h1>CrownThrive OAuth 2.1</h1><p class="muted">The consent endpoint is online. Authorization requests must originate from the CrownThrive identity provider.</p><p><code>${esc(AUTH_BASE)}/oauth/authorize</code></p></section>`));
      return;
    }

    res.status(200).send(page('Authorize application', `<section class="card"><h1>Authorize application</h1><p>A third-party application is requesting bounded access through CrownThrive OAuth 2.1.</p>${clientId ? `<p><strong>Client:</strong> <code>${esc(clientId)}</code></p>` : ''}${redirectUri ? `<p><strong>Redirect:</strong> <code>${esc(redirectUri)}</code></p>` : ''}<h2>Requested scope</h2>${scope ? scope.split(/\s+/).filter(Boolean).map(s => `<div class="scope">${esc(s)}</div>`).join('') : '<div class="scope">No scope metadata supplied.</div>'}<p class="muted">Only approve clients and scopes you recognize. CrownThrive does not expose client secrets or signing keys on this page.</p><div class="actions"><form method="post"><input type="hidden" name="authorization_id" value="${esc(authorizationId)}"><input type="hidden" name="decision" value="approve"><input type="hidden" name="return_to" value="${esc(returnTo)}"><button class="approve" type="submit">Approve</button></form><form method="post"><input type="hidden" name="authorization_id" value="${esc(authorizationId)}"><input type="hidden" name="decision" value="deny"><input type="hidden" name="return_to" value="${esc(returnTo)}"><button class="deny" type="submit">Deny</button></form></div></section>`));
    return;
  }

  if (req.method === 'POST') {
    const body = req.body || {};
    const decision = body.decision === 'approve' ? 'approve' : 'deny';
    const authorizationId = body.authorization_id || '';
    const returnTo = safeReturn(body.return_to || '');

    // Supabase owns authorization issuance. Never mint codes/tokens locally.
    // If the authorization server supplies an explicit safe return URL, forward the
    // user's decision to that provider-owned continuation. Otherwise fail closed.
    if (returnTo && authorizationId) {
      const u = new URL(returnTo);
      u.searchParams.set('authorization_id', authorizationId);
      u.searchParams.set('decision', decision);
      res.redirect(303, u.toString());
      return;
    }

    res.status(400).send(page('Authorization not completed', `<section class="card"><h1>Authorization not completed</h1><p>The request did not include a provider-owned continuation that CrownThrive can verify. No authorization code or token was issued.</p><p class="muted">Fail-closed state: no authority was created.</p><div class="actions"><a class="button deny" href="${SITE_URL}/oauth/consent">Return</a></div></section>`));
    return;
  }

  res.setHeader('Allow', 'GET, POST');
  res.status(405).end('Method Not Allowed');
}
