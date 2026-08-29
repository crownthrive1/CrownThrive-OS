import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VERSION = "3.0.0";
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_RESPONSE_BYTES = 1_000_000;
const MAX_REDIRECTS = 3;
const HTTP_TIMEOUT_MS = 12_000;

const SERVER = Object.freeze({
  name: "PentaCrawler",
  service: "ct.penta.crawler.systemwide.v3",
  communicationsService: "ct.penta.crawler.communications.v1",
  protocol: "ct.penta.protocol.v1",
  packetProtocol: "ct.pentas.packet.v1",
  cookieProtocol: "ct.penta.cookie.v1",
  version: VERSION,
  productionCandidate: true,
  productionPromoted: false,
});

type Row = Record<string, unknown>;

class SafeError extends Error {
  readonly code: string;
  readonly status: number;
  readonly publicDetail?: Row;

  constructor(code: string, status = 400, publicDetail?: Row) {
    super(code);
    this.name = "SafeError";
    this.code = code;
    this.status = status;
    this.publicDetail = publicDetail;
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    },
  });
}

function serviceHeaders(): HeadersInit {
  return {
    apikey: SERVICE,
    authorization: `Bearer ${SERVICE}`,
    "content-type": "application/json",
  };
}

function requestId(): string {
  return crypto.randomUUID();
}

async function sha256Text(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((n) => n.toString(16).padStart(2, "0")).join("");
}

async function rpc(name: string, body: Row = {}): Promise<unknown> {
  if (!BASE || !SERVICE) throw new SafeError("runtime_configuration_unavailable", 503);

  const response = await fetch(`${BASE}/rest/v1/rpc/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: serviceHeaders(),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
  }).catch(() => {
    throw new SafeError("rpc_transport_error", 502, { rpc: name });
  });

  const providerRequestId = response.headers.get("x-request-id") ?? response.headers.get("sb-request-id");
  const text = await readLimitedBody(response, 256 * 1024).catch(() => "");
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    throw new SafeError("rpc_rejected", 502, {
      rpc: name,
      provider_status: response.status,
      ...(providerRequestId ? { provider_request_id: providerRequestId } : {}),
    });
  }
  return data;
}

async function authorize(req: Request): Promise<void> {
  const token = req.headers.get("x-penta-crawler-token")
    ?? req.headers.get("x-penta-marketer-token")
    ?? "";
  if (!token) throw new SafeError("penta_crawler_authorization_required", 403);

  const allowed = await rpc("penta_marketer_edge_authorize_v1", { p_token: token });
  if (allowed !== true) throw new SafeError("penta_crawler_authorization_required", 403);
}

async function readLimitedBody(response: Response, maxBytes = MAX_RESPONSE_BYTES): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw new SafeError("response_body_limit_exceeded", 413);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(output);
}

async function readJsonRequest(req: Request): Promise<Row> {
  const declaredLength = Number(req.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BYTES) {
    throw new SafeError("request_body_limit_exceeded", 413);
  }
  const text = await readLimitedBody(new Response(req.body), MAX_REQUEST_BYTES);
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new SafeError("request_json_object_required", 400);
    }
    return parsed as Row;
  } catch (error) {
    if (error instanceof SafeError) throw error;
    throw new SafeError("invalid_json", 400);
  }
}

function normalizeHost(raw: string): string {
  return raw.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
}

function parseV4(host: string): number[] | null {
  const parts = host.split(".");
  if (parts.length !== 4) return null;
  const numbers = parts.map((part) => Number(part));
  if (numbers.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return null;
  return numbers;
}

function isUnsafeV4(host: string): boolean {
  const p = parseV4(host);
  if (!p) return false;
  const [a, b] = p;
  return a === 0
    || a === 10
    || a === 127
    || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254)
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && b === 0)
    || (a === 192 && b === 168)
    || (a === 198 && (b === 18 || b === 19 || b === 51))
    || a === 203
    || a >= 224;
}

function isUnsafeV6(host: string): boolean {
  const h = normalizeHost(host);
  if (!h.includes(":")) return false;
  if (h === "::" || h === "::1") return true;
  if (h.startsWith("fc") || h.startsWith("fd")) return true;
  if (/^fe[89ab]/.test(h)) return true;
  if (h.startsWith("ff")) return true;
  if (h.startsWith("2001:db8:")) return true;
  if (h.startsWith("::ffff:")) {
    const v4 = h.slice("::ffff:".length);
    if (parseV4(v4)) return isUnsafeV4(v4);
  }
  return false;
}

const BLOCKED_HOSTS = new Set([
  "localhost",
  "localhost.localdomain",
  "metadata.google.internal",
  "metadata.google.com",
  "instance-data.ec2.internal",
  "169.254.169.254",
]);

async function checkedUrl(raw: string): Promise<URL> {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new SafeError("invalid_url", 400);
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new SafeError("unsupported_protocol", 400);
  }
  if (url.username || url.password) throw new SafeError("url_credentials_forbidden", 400);
  if (url.port && !["80", "443"].includes(url.port)) throw new SafeError("nonstandard_port_forbidden", 400);

  const host = normalizeHost(url.hostname);
  if (!host
    || BLOCKED_HOSTS.has(host)
    || host.endsWith(".local")
    || host.endsWith(".internal")
    || host.endsWith(".localhost")
    || isUnsafeV4(host)
    || isUnsafeV6(host)) {
    throw new SafeError("private_or_local_target_forbidden", 403);
  }

  const resolved = new Set<string>();
  try {
    for (const ip of await Deno.resolveDns(host, "A")) resolved.add(ip);
  } catch {
    // IPv4 absence alone is acceptable when a safe AAAA record exists.
  }
  try {
    for (const ip of await Deno.resolveDns(host, "AAAA")) resolved.add(ip);
  } catch {
    // IPv6 absence alone is acceptable when a safe A record exists.
  }
  if (resolved.size === 0) throw new SafeError("dns_resolution_unavailable", 502);
  for (const ip of resolved) {
    if (isUnsafeV4(ip) || isUnsafeV6(ip)) {
      throw new SafeError("resolved_private_target_forbidden", 403);
    }
  }

  url.hash = "";
  return url;
}

async function fetchPage(raw: string, redirects = MAX_REDIRECTS): Promise<{ url: string; html: string; contentType: string }> {
  let url = await checkedUrl(raw);
  for (let i = 0; i <= redirects; i++) {
    const response = await fetch(url, {
      redirect: "manual",
      headers: {
        "user-agent": "CrownThrive-PentaCrawler/3.0 (+https://crownthrive.com)",
        accept: "text/html,text/plain;q=0.9",
      },
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    }).catch(() => {
      throw new SafeError("target_fetch_failed", 502);
    });

    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      if (!location) throw new SafeError("redirect_without_location", 502);
      if (i >= redirects) throw new SafeError("redirect_limit_exceeded", 502);
      url = await checkedUrl(new URL(location, url).toString());
      continue;
    }

    if (!response.ok) {
      throw new SafeError("target_http_error", 502, { provider_status: response.status });
    }

    const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
    if (contentType
      && !contentType.includes("text/html")
      && !contentType.includes("text/plain")) {
      throw new SafeError("unsupported_content_type", 415);
    }

    return {
      url: url.toString(),
      html: await readLimitedBody(response, MAX_RESPONSE_BYTES),
      contentType,
    };
  }
  throw new SafeError("redirect_limit_exceeded", 502);
}

function decodeEntitiesOnce(value: string): string {
  const named: Record<string, string> = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: '"',
    apos: "'",
    nbsp: " ",
  };
  return value.replace(/&(#x[0-9a-f]{1,6}|#[0-9]{1,7}|amp|lt|gt|quot|apos|nbsp);/gi, (match, token: string) => {
    const lower = token.toLowerCase();
    if (lower.startsWith("#x")) {
      const code = Number.parseInt(lower.slice(2), 16);
      return Number.isFinite(code) && code <= 0x10ffff ? String.fromCodePoint(code) : match;
    }
    if (lower.startsWith("#")) {
      const code = Number.parseInt(lower.slice(1), 10);
      return Number.isFinite(code) && code <= 0x10ffff ? String.fromCodePoint(code) : match;
    }
    return named[lower] ?? match;
  });
}

function stripUnsafeMarkup(html: string): string {
  const lower = html.toLowerCase();
  const out: string[] = [];
  let i = 0;
  while (i < html.length) {
    if (lower.startsWith("<!--", i)) {
      const end = lower.indexOf("-->", i + 4);
      i = end === -1 ? html.length : end + 3;
      out.push(" ");
      continue;
    }
    if (html[i] === "<") {
      const tagEnd = html.indexOf(">", i + 1);
      if (tagEnd === -1) break;
      const open = lower.slice(i + 1, Math.min(tagEnd, i + 256)).trimStart();
      const nameMatch = open.match(/^\/?\s*([a-z0-9:-]+)/);
      const tagName = nameMatch?.[1] ?? "";
      if (["script", "style", "template", "noscript"].includes(tagName) && !open.startsWith("/")) {
        const closeStart = lower.indexOf(`</${tagName}`, tagEnd + 1);
        if (closeStart === -1) {
          i = html.length;
          out.push(" ");
          continue;
        }
        const closeEnd = html.indexOf(">", closeStart + tagName.length + 2);
        i = closeEnd === -1 ? html.length : closeEnd + 1;
        out.push(" ");
        continue;
      }
      out.push(" ");
      i = tagEnd + 1;
      continue;
    }
    out.push(html[i]);
    i += 1;
  }
  return out.join("");
}

function visibleText(html: string): string {
  return decodeEntitiesOnce(stripUnsafeMarkup(html))
    .replace(/\s+/g, " ")
    .trim();
}

function title(html: string): string | null {
  const lower = html.toLowerCase();
  const start = lower.indexOf("<title");
  if (start === -1) return null;
  const openEnd = html.indexOf(">", start + 6);
  if (openEnd === -1) return null;
  const closeStart = lower.indexOf("</title", openEnd + 1);
  if (closeStart === -1) return null;
  return visibleText(html.slice(openEnd + 1, closeStart)).slice(0, 240) || null;
}

function attributeValue(tag: string, name: string): string | null {
  const lower = tag.toLowerCase();
  let cursor = 0;
  while (cursor < lower.length) {
    const found = lower.indexOf(name.toLowerCase(), cursor);
    if (found === -1) return null;
    const before = found === 0 ? " " : lower[found - 1];
    const after = lower[found + name.length] ?? " ";
    const nameBoundaryBefore = !/[a-z0-9_:-]/i.test(before);
    const nameBoundaryAfter = !/[a-z0-9_:-]/i.test(after);
    if (!nameBoundaryBefore || !nameBoundaryAfter) {
      cursor = found + name.length;
      continue;
    }
    let i = found + name.length;
    while (/\s/.test(tag[i] ?? "")) i += 1;
    if (tag[i] !== "=") {
      cursor = i + 1;
      continue;
    }
    i += 1;
    while (/\s/.test(tag[i] ?? "")) i += 1;
    const quote = tag[i];
    if (quote === '"' || quote === "'") {
      const end = tag.indexOf(quote, i + 1);
      if (end === -1) return null;
      return decodeEntitiesOnce(tag.slice(i + 1, end));
    }
    let end = i;
    while (end < tag.length && !/[\s>]/.test(tag[end])) end += 1;
    return decodeEntitiesOnce(tag.slice(i, end));
  }
  return null;
}

const BLOCKED_DOMAINS = /(wixpress|sentry|ndiscovered|example|domain\.com|w3\.org|cloudflare|schema\.org|wordpress|shopify|googleusercontent|gravatar|doubleclick|facebookmail)/i;
const BLOCKED_LOCAL = /^(user|example|test|name|email|yourname|someone|noreply|no-reply|donotreply|do-not-reply|webmaster)$/i;

function validEmail(raw: string): string | null {
  const email = raw.toLowerCase().replace(/^mailto:/, "").split("?")[0].replace(/[),.;:]+$/, "");
  if (!/^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/.test(email) || email.length > 254) return null;
  const [local, domain] = email.split("@");
  if (BLOCKED_LOCAL.test(local)
    || BLOCKED_DOMAINS.test(domain)
    || /\.(png|jpg|jpeg|gif|svg|webp|css|js)$/i.test(email)) return null;
  return email;
}

function extractAnchorTags(html: string, max = 64): Array<{ tag: string; label: string }> {
  const lower = html.toLowerCase();
  const anchors: Array<{ tag: string; label: string }> = [];
  let cursor = 0;
  while (anchors.length < max) {
    const start = lower.indexOf("<a", cursor);
    if (start === -1) break;
    const boundary = lower[start + 2] ?? " ";
    if (/[a-z0-9:-]/.test(boundary)) {
      cursor = start + 2;
      continue;
    }
    const openEnd = html.indexOf(">", start + 2);
    if (openEnd === -1 || openEnd - start > 8192) {
      cursor = start + 2;
      continue;
    }
    const tag = html.slice(start, openEnd + 1);
    const closeStart = lower.indexOf("</a", openEnd + 1);
    const label = closeStart === -1
      ? ""
      : visibleText(html.slice(openEnd + 1, Math.min(closeStart, openEnd + 4096)));
    anchors.push({ tag, label });
    cursor = closeStart === -1 ? openEnd + 1 : closeStart + 3;
  }
  return anchors;
}

function extractPublicEmails(html: string): string[] {
  const candidates: string[] = [];
  for (const anchor of extractAnchorTags(html, 128)) {
    const href = attributeValue(anchor.tag, "href");
    if (href?.toLowerCase().startsWith("mailto:")) candidates.push(href);
  }

  const text = visibleText(html).slice(0, MAX_RESPONSE_BYTES);
  for (const match of text.matchAll(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/gi)) {
    candidates.push(match[0]);
    if (candidates.length >= 64) break;
  }

  const result: string[] = [];
  for (const raw of candidates) {
    const email = validEmail(raw);
    if (email && !result.includes(email)) result.push(email);
    if (result.length >= 8) break;
  }
  return result;
}

function contactLinks(html: string, base: URL): string[] {
  const result: string[] = [];
  for (const anchor of extractAnchorTags(html, 128)) {
    const href = attributeValue(anchor.tag, "href")?.trim() ?? "";
    if (!href) continue;
    const signal = `${href} ${anchor.label}`.toLowerCase();
    if (!/(contact|about|team|staff|book|booking|admission|connect|support)/i.test(signal)) continue;
    try {
      const url = new URL(href, base);
      if (url.origin === base.origin
        && (url.protocol === "http:" || url.protocol === "https:")
        && !result.includes(url.toString())) {
        result.push(url.toString());
      }
    } catch {
      // Ignore malformed hrefs.
    }
    if (result.length >= 2) break;
  }
  return result;
}

type RobotsRule = { kind: "allow" | "disallow"; path: string };

async function robotsAllows(url: URL): Promise<boolean> {
  try {
    const robotsUrl = new URL("/robots.txt", url.origin);
    const response = await fetch(robotsUrl, {
      redirect: "manual",
      headers: { "user-agent": "CrownThrive-PentaCrawler/3.0 (+https://crownthrive.com)" },
      signal: AbortSignal.timeout(6_000),
    });
    if (!response.ok) return true;
    const text = await readLimitedBody(response, 256 * 1024);
    let groupApplies = false;
    const rules: RobotsRule[] = [];
    for (const rawLine of text.split(/\r?\n/)) {
      const line = rawLine.split("#", 1)[0].trim();
      if (!line) continue;
      const colon = line.indexOf(":");
      if (colon === -1) continue;
      const key = line.slice(0, colon).trim().toLowerCase();
      const value = line.slice(colon + 1).trim();
      if (key === "user-agent") {
        const agent = value.toLowerCase();
        groupApplies = agent === "*" || agent.includes("pentacrawler") || agent.includes("crownthrive-pentacrawler");
        continue;
      }
      if (!groupApplies || !value) continue;
      if (key === "allow") rules.push({ kind: "allow", path: value });
      if (key === "disallow") rules.push({ kind: "disallow", path: value });
    }
    const matches = rules
      .filter((rule) => url.pathname.startsWith(rule.path))
      .sort((a, b) => b.path.length - a.path.length);
    if (matches.length === 0) return true;
    return matches[0].kind === "allow";
  } catch {
    return true;
  }
}

async function scanResearchItem(item: Row): Promise<Row> {
  const queueId = String(item.queue_id ?? "");
  const target = String(item.target_url ?? "");
  const sourceKind = String(item.source_kind ?? "official_business_site");
  if (!queueId || !target) {
    return { queue_id: queueId || null, ok: false, code: "invalid_research_item" };
  }

  try {
    const targetUrl = await checkedUrl(target);
    if (!(await robotsAllows(targetUrl))) throw new SafeError("robots_disallow", 403);

    const primary = await fetchPage(targetUrl.toString());
    const pages = [primary];
    const primaryUrl = new URL(primary.url);
    const links = contactLinks(primary.html, primaryUrl).slice(0, 1);
    for (const link of links) {
      try {
        const linkUrl = await checkedUrl(link);
        if (await robotsAllows(linkUrl)) pages.push(await fetchPage(linkUrl.toString()));
      } catch {
        // Primary page is retained even when optional contact-page enrichment fails.
      }
    }

    const observations: Row[] = [];
    for (const page of pages) {
      const pageUrl = new URL(page.url);
      const sourceType = /(book|booking)/i.test(pageUrl.pathname)
        ? "official_booking_page"
        : /(contact|about|team|staff|admission|support)/i.test(pageUrl.pathname)
          ? "official_contact_page"
          : sourceKind;

      for (const email of extractPublicEmails(page.html)) {
        const confidence = sourceType === "official_contact_page" || sourceType === "official_booking_page"
          ? 97
          : sourceType === "official_business_site" || sourceType === "email_evidence_page"
            ? 93
            : 80;
        const observedAt = new Date().toISOString();
        const pageTitle = title(page.html);
        const evidence = {
          email,
          source_url: page.url,
          source_type: sourceType,
          confidence,
          page_title: pageTitle,
          extraction: "mailto_or_visible_text_once_decoded",
          body_archived: false,
          observed_at: observedAt,
        };
        observations.push({
          email,
          source_url: page.url,
          source_type: sourceType,
          contact_name: null,
          page_title: pageTitle,
          confidence,
          is_public_business_contact: true,
          evidence_sha256: await sha256Text(JSON.stringify(evidence)),
          evidence: {
            extraction: evidence.extraction,
            body_archived: false,
            page_origin: pageUrl.origin,
            parser_version: VERSION,
          },
          observed_at: observedAt,
        });
      }
    }

    const completion = await rpc("penta_marketer_complete_research_v1", {
      p_queue_id: queueId,
      p_observations: observations,
      p_error: null,
    });
    return {
      queue_id: queueId,
      ok: true,
      observations: observations.length,
      result: completion,
    };
  } catch (error) {
    const code = error instanceof SafeError ? error.code : "research_scan_failed";
    const completion = await rpc("penta_marketer_complete_research_v1", {
      p_queue_id: queueId,
      p_observations: [],
      p_error: code,
    }).catch(() => ({ state: "completion_failed" }));
    return { queue_id: queueId, ok: false, code, result: completion };
  }
}

async function runCommunications(batch: number, schedule: boolean): Promise<Row> {
  const claimed = await rpc("penta_marketer_claim_research_v1", { p_limit: Math.min(batch, 10) });
  const items = Array.isArray(claimed) ? claimed as Row[] : [];
  const results: Row[] = [];
  for (const item of items) results.push(await scanResearchItem(item));
  const plan = await rpc("penta_marketer_plan_v1");
  const scheduler = schedule ? await rpc("penta_marketer_tick_v1") : null;
  return {
    lane: "communications",
    claimed: items.length,
    processed: results.length,
    results,
    plan,
    scheduler,
  };
}

async function runRoam(batch: number): Promise<Row> {
  const result = await rpc("penta_crawler_roam_v1", { p_limit: batch });
  return { lane: "registered_estate", result };
}

Deno.serve(async (req: Request) => {
  const requestIdValue = requestId();
  try {
    if (req.method !== "POST") {
      return json({ ok: false, code: "POST_required", request_id: requestIdValue, server: SERVER }, 405);
    }

    await authorize(req);
    const body = await readJsonRequest(req);
    const action = String(body.action ?? "tick").toLowerCase();
    const batch = Math.max(1, Math.min(Number(body.batch ?? 25) || 25, 100));

    if (!["tick", "roam", "communications", "status"].includes(action)) {
      throw new SafeError("unsupported_action", 400, {
        allowed: ["tick", "roam", "communications", "status"],
      });
    }

    let result: unknown;
    if (action === "status") {
      result = await rpc("penta_crawler_status_v3");
    } else if (action === "roam") {
      result = await runRoam(batch);
    } else if (action === "communications") {
      result = await runCommunications(Math.min(batch, 10), false);
    } else {
      // Tick composes registered-estate roaming and the legacy communications lane under the existing cadence; it creates no new clock.
      const roam = await runRoam(batch);
      const communications = await runCommunications(Math.min(batch, 10), true);
      result = { roam, communications };
    }

    return json({
      ok: true,
      request_id: requestIdValue,
      server: SERVER,
      action,
      result,
      controls: {
        raw_secret_exposed: false,
        raw_body_archived: false,
        arbitrary_internal_crawling: false,
        provider_write: false,
        authority_created: false,
        d3_execution: false,
      },
      at: new Date().toISOString(),
    });
  } catch (error) {
    const safe = error instanceof SafeError
      ? error
      : new SafeError("internal_error", 500);

    return json(
      {
        ok: false,
        code: safe.code,
        request_id: requestIdValue,
        ...(safe.publicDetail ? { detail: safe.publicDetail } : {}),
        server: SERVER,
        raw_secret_exposed: false,
        stack_exposed: false,
      },
      safe.status,
    );
  }
});
