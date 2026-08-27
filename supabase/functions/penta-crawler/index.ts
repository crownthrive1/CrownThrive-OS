import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VERSION = "1.1.1";
const SERVER = {
  name: "PentaCrawler Communications Research",
  service: "ct.penta.crawler.communications.v1",
  parent: "PentaMarketer",
  canonicalAgent: "ct.ops.agent.email-attention",
  version: VERSION,
  production: true,
};

type Row = Record<string, unknown>;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

function serviceHeaders() {
  return { apikey: SERVICE, authorization: `Bearer ${SERVICE}`, "content-type": "application/json" };
}

async function rpc(name: string, body: Row = {}) {
  const response = await fetch(`${BASE}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: serviceHeaders(),
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: any = text;
  try { data = text ? JSON.parse(text) : null; } catch { /* bounded text retained */ }
  if (!response.ok) throw new Error(`${name}:${response.status}:${typeof data === "string" ? data.slice(0, 500) : JSON.stringify(data).slice(0, 500)}`);
  return data;
}

async function hash(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((n) => n.toString(16).padStart(2, "0")).join("");
}

function privateV4(host: string) {
  const p = host.split(".").map(Number);
  if (p.length !== 4 || p.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return false;
  return p[0] === 10 || p[0] === 127 || p[0] === 0 || (p[0] === 169 && p[1] === 254) || (p[0] === 172 && p[1] >= 16 && p[1] <= 31) || (p[0] === 192 && p[1] === 168);
}

function privateV6(host: string) {
  const h = host.toLowerCase().replace(/^\[|\]$/g, "");
  return h === "::1" || h === "::" || h.startsWith("fc") || h.startsWith("fd") || /^fe[89ab]/.test(h);
}

async function checkedUrl(raw: string) {
  let url: URL;
  try { url = new URL(raw); } catch { throw new Error("invalid_url"); }
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("unsupported_protocol");
  if (url.username || url.password) throw new Error("url_credentials_forbidden");
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".local") || host.endsWith(".internal") || privateV4(host) || privateV6(host)) throw new Error("private_or_local_target_forbidden");
  const resolved: string[] = [];
  try { resolved.push(...await Deno.resolveDns(host, "A")); } catch { /* no IPv4 */ }
  try { resolved.push(...await Deno.resolveDns(host, "AAAA")); } catch { /* no IPv6 */ }
  if (resolved.some((ip) => privateV4(ip) || privateV6(ip))) throw new Error("resolved_private_target_forbidden");
  url.hash = "";
  return url;
}

async function readBody(response: Response, max = 1_000_000) {
  const reader = response.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > max) { await reader.cancel(); throw new Error("response_body_limit_exceeded"); }
    chunks.push(value);
  }
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { output.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder().decode(output);
}

async function fetchPage(raw: string, redirects = 3) {
  let url = await checkedUrl(raw);
  for (let i = 0; i <= redirects; i++) {
    const response = await fetch(url, {
      redirect: "manual",
      headers: {
        "user-agent": "CrownThrive-PentaCrawler/1.1 (+https://crownthrive.com)",
        accept: "text/html,text/plain;q=0.9",
      },
      signal: AbortSignal.timeout(12_000),
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      if (!location) throw new Error("redirect_without_location");
      url = await checkedUrl(new URL(location, url).toString());
      continue;
    }
    if (!response.ok) throw new Error(`http_${response.status}`);
    const type = (response.headers.get("content-type") ?? "").toLowerCase();
    if (type && !type.includes("text/html") && !type.includes("text/plain")) throw new Error("unsupported_content_type");
    return { url: url.toString(), html: await readBody(response) };
  }
  throw new Error("redirect_limit_exceeded");
}

function removeScripts(html: string) {
  return html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<template\b[^>]*>[\s\S]*?<\/template>/gi, " ")
    .replace(/<!--([\s\S]*?)-->/g, " ");
}

function visibleText(html: string) {
  return removeScripts(html).replace(/<[^>]+>/g, " ")
    .replace(/&amp;/gi, "&").replace(/&nbsp;/gi, " ")
    .replace(/&#64;|\[at\]|\(at\)/gi, "@").replace(/&#46;|\[dot\]|\(dot\)/gi, ".")
    .replace(/\s+/g, " ").trim();
}

function title(html: string) {
  const match = removeScripts(html).match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
  return match ? visibleText(match[1]).slice(0, 240) : null;
}

const BLOCKED_DOMAINS = /(wixpress|sentry|ndiscovered|example|domain\.com|w3\.org|cloudflare|schema\.org|wordpress|shopify|googleusercontent|gravatar|doubleclick|facebookmail)/i;
const BLOCKED_LOCAL = /^(user|example|test|name|email|yourname|someone|noreply|no-reply|donotreply|do-not-reply|webmaster)$/i;

function validEmail(raw: string) {
  const email = raw.toLowerCase().replace(/^mailto:/, "").split("?")[0].replace(/[),.;:]+$/, "");
  if (!/^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/.test(email) || email.length > 254) return null;
  const [local, domain] = email.split("@");
  if (BLOCKED_LOCAL.test(local) || BLOCKED_DOMAINS.test(domain) || /\.(png|jpg|jpeg|gif|svg|webp|css|js)$/i.test(email)) return null;
  return email;
}

function extractPublicEmails(html: string) {
  const clean = removeScripts(html);
  const candidates: string[] = [];
  for (const match of clean.matchAll(/href=["']mailto:([^"'#]+)["']/gi)) candidates.push(match[1]);
  const text = visibleText(clean);
  for (const match of text.matchAll(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/gi)) candidates.push(match[0]);
  const result: string[] = [];
  for (const raw of candidates) {
    const email = validEmail(raw);
    if (email && !result.includes(email)) result.push(email);
    if (result.length >= 8) break;
  }
  return result;
}

function contactLinks(html: string, base: URL) {
  const result: string[] = [];
  const clean = removeScripts(html);
  for (const match of clean.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    const href = match[1].trim();
    const label = visibleText(match[2]).toLowerCase();
    if (!/(contact|about|team|staff|book|booking|admission|connect|support)/i.test(`${href} ${label}`)) continue;
    try {
      const url = new URL(href, base);
      if (url.origin === base.origin && ["http:", "https:"].includes(url.protocol) && !result.includes(url.toString())) result.push(url.toString());
    } catch { /* ignore malformed links */ }
    if (result.length >= 2) break;
  }
  return result;
}

async function robotsAllows(url: URL) {
  try {
    const robots = await fetchPage(`${url.origin}/robots.txt`, 1);
    let applies = false;
    const blocked: string[] = [];
    for (const raw of robots.html.split(/\r?\n/)) {
      const line = raw.split("#")[0].trim();
      const [key, ...rest] = line.split(":");
      const value = rest.join(":").trim();
      if ((key ?? "").trim().toLowerCase() === "user-agent") applies = value === "*" || value.toLowerCase().includes("pentacrawler");
      if ((key ?? "").trim().toLowerCase() === "disallow" && applies && value) blocked.push(value);
    }
    return !blocked.some((path) => url.pathname.startsWith(path));
  } catch { return true; }
}

async function scan(item: Row) {
  const queueId = String(item.queue_id ?? "");
  const target = String(item.target_url ?? "");
  const sourceKind = String(item.source_kind ?? "official_business_site");
  try {
    const targetUrl = await checkedUrl(target);
    if (!(await robotsAllows(targetUrl))) throw new Error("robots_disallow");
    const primary = await fetchPage(targetUrl.toString());
    const pages = [primary];
    const origin = new URL(primary.url);
    for (const link of contactLinks(primary.html, origin).slice(0, 1)) {
      try {
        const linkUrl = await checkedUrl(link);
        if (await robotsAllows(linkUrl)) pages.push(await fetchPage(linkUrl.toString()));
      } catch { /* keep primary page */ }
    }
    const observations: Row[] = [];
    for (const page of pages) {
      const url = new URL(page.url);
      const sourceType = /(book|booking)/i.test(url.pathname) ? "official_booking_page" : /(contact|about|team|staff|admission|support)/i.test(url.pathname) ? "official_contact_page" : sourceKind;
      for (const email of extractPublicEmails(page.html)) {
        const confidence = sourceType === "official_contact_page" || sourceType === "official_booking_page" ? 97 : sourceType === "official_business_site" || sourceType === "email_evidence_page" ? 93 : 80;
        const evidence = { email, source_url: page.url, source_type: sourceType, confidence, page_title: title(page.html), extraction: "mailto_or_visible_text_only", body_archived: false, observed_at: new Date().toISOString() };
        observations.push({
          email,
          source_url: page.url,
          source_type: sourceType,
          contact_name: null,
          page_title: evidence.page_title,
          confidence,
          is_public_business_contact: true,
          evidence_sha256: await hash(JSON.stringify(evidence)),
          evidence: { extraction: evidence.extraction, body_archived: false, page_origin: url.origin },
          observed_at: evidence.observed_at,
        });
      }
    }
    const result = await rpc("penta_marketer_complete_research_v1", { p_queue_id: queueId, p_observations: observations, p_error: null });
    return { queue_id: queueId, ok: true, observations: observations.length, result };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = await rpc("penta_marketer_complete_research_v1", { p_queue_id: queueId, p_observations: [], p_error: message.slice(0, 1000) }).catch((completionError) => ({ state: "completion_failed", error: completionError instanceof Error ? completionError.message : String(completionError) }));
    return { queue_id: queueId, ok: false, error: message, result };
  }
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return json({ ok: false, error: "POST_required", server: SERVER }, 405);
    const token = req.headers.get("x-penta-marketer-token") ?? "";
    if (!token || await rpc("penta_marketer_edge_authorize_v1", { p_token: token }) !== true) return json({ ok: false, error: "penta_crawler_authorization_required", server: SERVER }, 403);
    const body = await req.json().catch(() => ({}));
    const action = String(body?.action ?? "tick").toLowerCase();
    if (!["scan", "tick"].includes(action)) return json({ ok: false, error: "unsupported_action", allowed: ["scan", "tick"], server: SERVER }, 400);
    const batch = Math.max(1, Math.min(Number(body?.batch ?? 10) || 10, 10));
    const claimed = await rpc("penta_marketer_claim_research_v1", { p_limit: batch });
    const items = Array.isArray(claimed) ? claimed : [];
    const results: unknown[] = [];
    for (const item of items) results.push(await scan(item));
    const plan = await rpc("penta_marketer_plan_v1");
    const scheduler = action === "tick" ? await rpc("penta_marketer_tick_v1") : null;
    return json({ ok: true, server: SERVER, action, claimed: items.length, processed: results.length, results, plan, scheduler, body_archived: false, raw_secret_exposed: false, at: new Date().toISOString() });
  } catch (error) {
    return json({ ok: false, service: SERVER.service, error: error instanceof Error ? error.message : String(error), raw_secret_exposed: false }, 500);
  }
});
