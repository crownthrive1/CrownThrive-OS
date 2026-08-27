import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

const SOFTWARE = "PentaCrawler Communications Research Runtime";
const VERSION = "1.0.0";
const USER_AGENT = "CrownThrive-PentaCrawler/1.0 (+public-business-research; contact@crownthrive.com)";
const MAX_BODY_BYTES = 1_500_000;
const MAX_REDIRECTS = 5;
const MAX_SAME_ORIGIN_FOLLOWS = 3;

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "x-pentacrawler-version": VERSION,
  },
});

const serviceRole = (req: Request) => {
  try {
    const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
    const part = token.split(".")[1];
    if (!part) return false;
    const padded = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return JSON.parse(atob(padded))?.role === "service_role";
  } catch {
    return false;
  }
};

const sha256 = async (value: string) => {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
};

const decodeBasicEntities = (value: string) => value
  .replace(/&commat;|&#64;|&#x40;/gi, "@")
  .replace(/&period;|&#46;|&#x2e;/gi, ".")
  .replace(/&amp;/gi, "&")
  .replace(/&nbsp;/gi, " ");

const isPrivateIpv4 = (host: string) => {
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const [a, b, c, d] = m.slice(1).map(Number);
  if ([a, b, c, d].some((n) => n < 0 || n > 255)) return true;
  return a === 10 || a === 127 || a === 0 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a === 198 && (b === 18 || b === 19)) ||
    (a >= 224);
};

const assertSafeUrl = (raw: string) => {
  const url = new URL(raw);
  if (!new Set(["http:", "https:"]).has(url.protocol)) throw new Error("unsupported_url_scheme");
  if (url.username || url.password) throw new Error("url_credentials_prohibited");
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (!host || host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local") || host.endsWith(".internal")) {
    throw new Error("private_hostname_prohibited");
  }
  if (isPrivateIpv4(host) || host === "::1" || host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80:")) {
    throw new Error("private_address_prohibited");
  }
  url.hash = "";
  return url;
};

const readBoundedText = async (response: Response) => {
  const length = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(length) && length > MAX_BODY_BYTES) throw new Error("page_too_large");
  if (!response.body) return "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let total = 0;
  let out = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) {
      await reader.cancel("bounded_read_limit");
      throw new Error("page_too_large");
    }
    out += decoder.decode(value, { stream: true });
  }
  return out + decoder.decode();
};

const fetchPublicPage = async (raw: string) => {
  let url = assertSafeUrl(raw);
  for (let redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
    const response = await fetch(url, {
      method: "GET",
      redirect: "manual",
      headers: {
        "user-agent": USER_AGENT,
        "accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.2",
      },
      signal: AbortSignal.timeout(12_000),
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      if (!location) throw new Error(`redirect_without_location:${response.status}`);
      url = assertSafeUrl(new URL(location, url).toString());
      continue;
    }
    if (!response.ok) throw new Error(`http_${response.status}`);
    const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
    if (!contentType.includes("text/html") && !contentType.includes("application/xhtml+xml") && !contentType.includes("text/plain")) {
      throw new Error(`unsupported_content_type:${contentType.slice(0, 80)}`);
    }
    return { url, html: await readBoundedText(response), contentType };
  }
  throw new Error("redirect_limit_exceeded");
};

const parseRobots = (text: string, path: string) => {
  let applies = false;
  const disallow: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*/, "").trim();
    if (!line) continue;
    const [key, ...rest] = line.split(":");
    const value = rest.join(":").trim();
    if (key.trim().toLowerCase() === "user-agent") applies = value === "*" || value.toLowerCase().includes("pentacrawler");
    if (applies && key.trim().toLowerCase() === "disallow" && value) disallow.push(value);
  }
  return !disallow.some((rule) => rule !== "/" && path.startsWith(rule)) && !disallow.includes("/");
};

const robotsAllows = async (url: URL) => {
  try {
    const robotsUrl = assertSafeUrl(new URL("/robots.txt", url.origin).toString());
    const response = await fetch(robotsUrl, {
      redirect: "manual",
      headers: { "user-agent": USER_AGENT, "accept": "text/plain,*/*;q=0.1" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return true;
    return parseRobots((await response.text()).slice(0, 250_000), url.pathname || "/");
  } catch {
    return true;
  }
};

const stripHtml = (html: string) => decodeBasicEntities(html)
  .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
  .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/\s+/g, " ")
  .trim();

const extractEmails = (html: string) => {
  const normalized = decodeBasicEntities(html);
  const found = normalized.match(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/gi) ?? [];
  return [...new Set(found.map((e) => e.toLowerCase()))]
    .filter((e) => !/(example\.(com|org|net)|email@|name@|user@|noreply@|no-reply@)/i.test(e))
    .filter((e) => !/\.(png|jpg|jpeg|gif|webp|svg)$/i.test(e));
};

const extractTitle = (html: string) => decodeBasicEntities(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? "")
  .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);

const extractSameOriginLinks = (html: string, base: URL) => {
  const links: string[] = [];
  const re = /<a\b[^>]*href\s*=\s*["']([^"']+)["'][^>]*>/gi;
  for (const match of html.matchAll(re)) {
    try {
      const url = assertSafeUrl(new URL(decodeBasicEntities(match[1]), base).toString());
      if (url.origin !== base.origin) continue;
      if (!/(contact|about|team|staff|admission|book|connect|reach|location)/i.test(url.pathname + url.search)) continue;
      links.push(url.toString());
    } catch { /* ignore malformed/non-http links */ }
  }
  return [...new Set(links)].slice(0, MAX_SAME_ORIGIN_FOLLOWS);
};

const sourceTypeFor = (sourceKind: string, url: URL, followed: boolean) => {
  if (sourceKind === "directory_listing") return "directory_listing";
  if (/square\.site|squareup\.com|styleseat\.com|vagaro\.com|glossgenius\.com/i.test(url.hostname)) return "official_booking_page";
  if (followed || /(contact|connect|reach)/i.test(url.pathname)) return "official_contact_page";
  if (sourceKind === "email_evidence_page") return "email_evidence_page";
  return "official_business_site";
};

type Observation = {
  source_url: string;
  source_type: string;
  email: string | null;
  page_title: string | null;
  contact_name: string | null;
  confidence: number;
  is_public_business_contact: boolean;
  evidence_sha256: string;
  observed_at: string;
  evidence: Record<string, unknown>;
};

const observationsFromPage = async (sourceKind: string, url: URL, html: string, followed: boolean): Promise<Observation[]> => {
  const emails = extractEmails(html);
  const title = extractTitle(html) || null;
  const text = stripHtml(html).slice(0, 20_000);
  const sourceType = sourceTypeFor(sourceKind, url, followed);
  const publicBusiness = sourceKind !== "directory_listing";
  const confidence = publicBusiness ? (followed ? 92 : 95) : 70;
  const observedAt = new Date().toISOString();
  const evidenceBase = {
    software: SOFTWARE,
    version: VERSION,
    public_page: true,
    source_kind: sourceKind,
    followed_same_origin: followed,
    title,
    content_length: html.length,
    signals: {
      claim_language: /claim\s+(listing|profile)|claimable|are you/i.test(text),
      contact_language: /contact|email|reach out|get in touch|connect/i.test(text),
      beauty_wellness_language: /(beauty|hair|salon|lash|skin|esthetic|wellness|spa|makeup|brow|massage|locs|locks)/i.test(text),
    },
  };
  if (!emails.length) {
    const digest = await sha256(`${url.toString()}|NO_EMAIL|${title ?? ""}|${text.slice(0, 1000)}`);
    return [{
      source_url: url.toString(), source_type: sourceType, email: null, page_title: title, contact_name: null,
      confidence: Math.min(confidence, 80), is_public_business_contact: false, evidence_sha256: digest, observed_at: observedAt,
      evidence: { ...evidenceBase, observed_email_count: 0 },
    }];
  }
  const out: Observation[] = [];
  for (const email of emails.slice(0, 10)) {
    const digest = await sha256(`${url.toString()}|${email}|${title ?? ""}|${text.slice(0, 1000)}`);
    out.push({
      source_url: url.toString(), source_type: sourceType, email, page_title: title, contact_name: null,
      confidence, is_public_business_contact: publicBusiness, evidence_sha256: digest, observed_at: observedAt,
      evidence: { ...evidenceBase, observed_email_count: emails.length },
    });
  }
  return out;
};

const scanJob = async (job: Record<string, unknown>) => {
  const queueId = String(job.queue_id);
  const target = assertSafeUrl(String(job.target_url));
  const sourceKind = String(job.source_kind);
  if (!(await robotsAllows(target))) throw new Error("robots_disallow");

  const first = await fetchPublicPage(target.toString());
  const observations = await observationsFromPage(sourceKind, first.url, first.html, false);

  if (sourceKind === "official_business_site") {
    const links = extractSameOriginLinks(first.html, first.url);
    for (const link of links) {
      const next = assertSafeUrl(link);
      if (!(await robotsAllows(next))) continue;
      try {
        const page = await fetchPublicPage(next.toString());
        observations.push(...await observationsFromPage(sourceKind, page.url, page.html, true));
      } catch { /* one optional contact page must not fail the root observation */ }
    }
  }

  const deduped = [...new Map(observations.map((o) => [`${o.source_url}|${o.email ?? "NO_EMAIL"}|${o.evidence_sha256}`, o])).values()];
  const { data, error } = await db.schema("crm").rpc("contact_discovery_complete_v1", {
    p_queue_id: queueId,
    p_observations: deduped,
    p_error: null,
  });
  if (error) throw error;
  return data;
};

const recordFailure = async (job: Record<string, unknown>, error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  const { data, error: completionError } = await db.schema("crm").rpc("contact_discovery_complete_v1", {
    p_queue_id: String(job.queue_id),
    p_observations: [],
    p_error: message.slice(0, 1800),
  });
  if (completionError) return { queue_id: job.queue_id, state: "FAILURE_RECORD_FAILED", error: message, completion_error: completionError.message };
  return { queue_id: job.queue_id, state: "RETRY_OR_HOLD", error: message, completion: data };
};

Deno.serve(async (req) => {
  try {
    if (!serviceRole(req)) return json({ ok: false, service: SOFTWARE, error: "service_role_required" }, 403);
    if (req.method !== "GET" && req.method !== "POST") return json({ ok: false, service: SOFTWARE, error: "GET_or_POST_required" }, 405);

    let body: Record<string, unknown> = {};
    if (req.method === "POST") { try { body = await req.json(); } catch { /* empty body */ } }
    const query = new URL(req.url).searchParams;
    const action = String(body.action ?? query.get("action") ?? "scan");
    const batch = Math.max(1, Math.min(Number(body.batch ?? query.get("batch") ?? 5) || 5, 10));
    if (!new Set(["scan", "tick", "status"]).has(action)) return json({ ok: false, service: SOFTWARE, error: "unsupported_action" }, 400);

    if (action === "status") {
      const [{ data: authority, error: aError }, { data: offer, error: oError }] = await Promise.all([
        db.schema("crm").rpc("commercial_send_authority_v1", { p_principal_id: "ct.ops.agent.email-attention" }),
        db.schema("crm").rpc("outreach_offer_ready_v1", { p_offer_ref: "locticians.claimmonth50.v1" }),
      ]);
      if (aError) throw aError;
      if (oError) throw oError;
      return json({ ok: true, service: SOFTWARE, version: VERSION, state: "PRODUCTION_FAIL_CLOSED", authority, offer });
    }

    const { data: control, error: controlError } = await db.schema("crm").rpc("outreach_control_plane_v1");
    if (controlError) throw controlError;

    const { data: jobs, error: claimError } = await db.schema("crm").rpc("contact_discovery_claim_v1", { p_limit: batch });
    if (claimError) throw claimError;
    const claimed = Array.isArray(jobs) ? jobs : [];
    const results: unknown[] = [];
    for (const job of claimed) {
      try { results.push(await scanJob(job)); }
      catch (error) { results.push(await recordFailure(job, error)); }
    }

    const { data: promotion, error: promotionError } = await db.schema("crm").rpc("promote_verified_prospects_v1", { p_limit: 100 });
    if (promotionError) throw promotionError;

    let scheduler: unknown = null;
    if (action === "tick") {
      const { data, error } = await db.schema("crm").rpc("outreach_scheduler_tick_v1");
      if (error) throw error;
      scheduler = data;
    }

    return json({
      ok: true,
      service: SOFTWARE,
      version: VERSION,
      state: "COMPLETE",
      action,
      control,
      claimed: claimed.length,
      results,
      promotion,
      scheduler,
      commercial_send_fail_closed: true,
    });
  } catch (error) {
    return json({ ok: false, service: SOFTWARE, version: VERSION, error: error instanceof Error ? error.message : String(error) }, 500);
  }
});
