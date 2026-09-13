import { createSign } from 'node:crypto';

const DEFAULT_SUPABASE_URL = 'https://tzajnzshmtzjenqulehq.supabase.co';
const DEFAULT_TTL_SECONDS = 600;
const MIN_TTL_SECONDS = 300;
const MAX_TTL_SECONDS = 900;

const AI_PERMISSIONS = Object.freeze([
  'ai:conversations:read',
  'ai:conversations:write',
  'ai:models:agent',
  'ai:actions:system:*',
  'ai:reviews:system:*',
]);

function getHeader(req, name) {
  const headers = req?.headers || {};
  const value = headers[name.toLowerCase()] ?? headers[name] ?? headers[name.toUpperCase()];
  return Array.isArray(value) ? value[0] : value;
}

function json(res, status, body) {
  res.status(status).json(body);
}

function normalizePrivateKey(value) {
  return String(value || '').replace(/\\n/g, '\n').trim();
}

function parseTtl() {
  const configured = Number.parseInt(process.env.TINYMCE_JWT_TTL_SECONDS || '', 10);
  if (!Number.isFinite(configured)) return DEFAULT_TTL_SECONDS;
  return Math.min(MAX_TTL_SECONDS, Math.max(MIN_TTL_SECONDS, configured));
}

function base64urlJson(value) {
  return Buffer.from(JSON.stringify(value), 'utf8').toString('base64url');
}

function signTinyJwt(payload, privateKey) {
  const header = base64urlJson({ alg: 'RS256', typ: 'JWT' });
  const body = base64urlJson(payload);
  const signingInput = `${header}.${body}`;
  const signer = createSign('RSA-SHA256');
  signer.update(signingInput);
  signer.end();
  const signature = signer.sign(privateKey).toString('base64url');
  return `${signingInput}.${signature}`;
}

function allowedOrigins() {
  const configured = String(process.env.TINYMCE_ALLOWED_ORIGINS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return new Set([
    'https://crownthrive.com',
    'https://www.crownthrive.com',
    'https://crown-thrive-os.vercel.app',
    ...configured,
  ]);
}

function applyCors(req, res) {
  const origin = String(getHeader(req, 'origin') || '').trim();
  if (!origin) return true;
  if (!allowedOrigins().has(origin)) return false;

  res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Vary', 'Origin');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  return true;
}

function bearerToken(req) {
  const authorization = String(getHeader(req, 'authorization') || '');
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  return match?.[1] || null;
}

async function authenticateUser(req) {
  const accessToken = bearerToken(req);
  if (!accessToken) return { ok: false, status: 401, code: 'AUTH_REQUIRED' };

  const supabaseUrl = String(process.env.CROWNTHRIVE_SUPABASE_URL || DEFAULT_SUPABASE_URL).replace(/\/$/, '');
  const anonKey = process.env.CROWNTHRIVE_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  if (!anonKey) return { ok: false, status: 503, code: 'SUPABASE_AUTH_UNBOUND' };

  let response;
  try {
    response = await fetch(`${supabaseUrl}/auth/v1/user`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        apikey: anonKey,
        Accept: 'application/json',
      },
      cache: 'no-store',
    });
  } catch {
    return { ok: false, status: 503, code: 'IDENTITY_PROVIDER_UNAVAILABLE' };
  }

  if (!response.ok) return { ok: false, status: 401, code: 'INVALID_SESSION' };

  const user = await response.json();
  if (!user?.id) return { ok: false, status: 401, code: 'INVALID_SESSION' };

  return { ok: true, user };
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');

  if (!applyCors(req, res)) {
    json(res, 403, { error: 'ORIGIN_NOT_ALLOWED' });
    return;
  }

  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST, OPTIONS');
    json(res, 405, { error: 'METHOD_NOT_ALLOWED' });
    return;
  }

  const tinyApiKey = String(process.env.TINYMCE_API_KEY || '').trim();
  const privateKey = normalizePrivateKey(process.env.TINYMCE_JWT_PRIVATE_KEY);
  if (!tinyApiKey || !privateKey) {
    json(res, 503, { error: 'TINYMCE_JWT_UNBOUND' });
    return;
  }

  const auth = await authenticateUser(req);
  if (!auth.ok) {
    json(res, auth.status, { error: auth.code });
    return;
  }

  const now = Math.floor(Date.now() / 1000);
  const ttl = parseTtl();
  const payload = {
    aud: tinyApiKey,
    sub: String(auth.user.id),
    iat: now,
    exp: now + ttl,
    auth: {
      ai: {
        permissions: AI_PERMISSIONS,
      },
    },
  };

  let token;
  try {
    token = signTinyJwt(payload, privateKey);
  } catch {
    json(res, 503, { error: 'TINYMCE_SIGNING_FAILED' });
    return;
  }

  json(res, 200, {
    token,
    expires_in: ttl,
  });
}
