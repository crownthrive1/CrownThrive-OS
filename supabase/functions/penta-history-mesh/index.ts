import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.5";

const DB = Deno.env.get("SUPABASE_DB_URL")!;
const sql = postgres(DB, { max: 3, prepare: false });
const SLUG = "penta-history-mesh";
const BASE = `https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/${SLUG}`;
const VERSION = "2.0.0";
const SERVICE_ID = "penta_history_mesh";

function routeContext(url: URL) {
  const parts = url.pathname.split("/").filter(Boolean);
  const idx = parts.indexOf(SLUG);
  return idx >= 0 ? parts.slice(idx + 1) : parts;
}
function clampLimit(url: URL) {
  const n = Number(url.searchParams.get("limit") ?? "100");
  return Number.isFinite(n) ? Math.max(1, Math.min(100, Math.trunc(n))) : 100;
}
function esc(v: unknown) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}
function hex(bytes: Uint8Array) { return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join(""); }
async function sha256(text: string) { return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)))); }
function common(contentType: string, cache = "public,max-age=30,stale-while-revalidate=120") {
  return new Headers({
    "content-type": contentType,
    "cache-control": cache,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "x-frame-options": "DENY",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,HEAD,OPTIONS",
    "access-control-allow-headers": "accept,content-type,if-none-match,cache-control",
    "access-control-expose-headers": "etag,x-crownthrive-content-sha256,x-crownthrive-history-authority-effect,x-crownthrive-mesh-node,x-crownthrive-api-version",
    "x-crownthrive-history-authority-effect": "none",
    "x-crownthrive-mesh-node": "PentaHistory",
    "x-crownthrive-api-version": VERSION,
  });
}
async function respond(req: Request, body: string, contentType: string, status = 200, cache?: string) {
  const digest = await sha256(body);
  const etag = `"sha256:${digest}"`;
  const h = common(contentType, cache);
  h.set("etag", etag);
  h.set("x-crownthrive-content-sha256", digest);
  if (req.headers.get("if-none-match") === etag) return new Response(null, { status: 304, headers: h });
  return new Response(req.method === "HEAD" ? null : body, { status, headers: h });
}
async function json(req: Request, payload: unknown, status = 200, cache?: string) {
  return respond(req, JSON.stringify(payload), "application/json; charset=utf-8", status, cache);
}

async function listStories(limit: number) {
  return await sql`select story_id,supersession_receipt_id,control_family,historical_control_id,current_control_id,story_kind,title,narrative,story_sha256,current_authority_effect,recorded_by_agent_id,recorded_at from integration_control.penta_scribe_stories_v1 order by recorded_at desc limit ${limit}`;
}
async function getStory(id: string) {
  const rows = await sql`select story_id,supersession_receipt_id,control_family,historical_control_id,current_control_id,story_kind,title,narrative,factual_evidence,story_sha256,current_authority_effect,recorded_by_agent_id,recorded_at from integration_control.penta_scribe_stories_v1 where story_id=${id}::uuid limit 1`;
  return rows[0] ?? null;
}
async function listSupersessions(limit: number) {
  return await sql`select receipt_id,control_family,superseded_control_id,current_control_id,superseded_snapshot_sha256,current_snapshot_sha256,decision,reason,enforced_by_agent_id,archive_state,historian_state,scribe_state,evidence_sha256,observed_at from integration_control.penta_supersession_receipts_v1 order by observed_at desc limit ${limit}`;
}
async function getSupersession(id: string) {
  const rows = await sql`select receipt_id,control_family,superseded_control_id,current_control_id,superseded_snapshot_sha256,current_snapshot_sha256,decision,reason,enforced_by_agent_id,archive_state,historian_state,scribe_state,evidence_sha256,observed_at from integration_control.penta_supersession_receipts_v1 where receipt_id=${id}::uuid limit 1`;
  return rows[0] ?? null;
}
async function listArchives(limit: number) {
  return await sql`select archive_id,supersession_receipt_id,control_family,control_id,superseded_by_control_id,historical_state,archived_snapshot_sha256,restore_authority,archived_by_agent_id,archived_at from integration_control.penta_archiver_records_v1 order by archived_at desc limit ${limit}`;
}
async function getArchive(id: string) {
  const rows = await sql`select archive_id,supersession_receipt_id,control_family,control_id,superseded_by_control_id,historical_state,archived_snapshot_sha256,restore_authority,archived_by_agent_id,archived_at from integration_control.penta_archiver_records_v1 where archive_id=${id}::uuid limit 1`;
  return rows[0] ?? null;
}
async function listObservations(limit: number) {
  return await sql`select observation_id,source_id,observed_at,content_digest,prior_digest,change_state,current_truth_effect,evidence_ref,summary,scribe_handoff_state,metadata->>'supersession_receipt_id' as supersession_receipt_id,metadata->>'scribe_story_id' as scribe_story_id from integration_control.penta_historian_observations_v1 order by observed_at desc limit ${limit}`;
}
async function getObservation(id: string) {
  const rows = await sql`select observation_id,source_id,observed_at,content_digest,prior_digest,change_state,current_truth_effect,evidence_ref,summary,scribe_handoff_state,metadata->>'supersession_receipt_id' as supersession_receipt_id,metadata->>'scribe_story_id' as scribe_story_id from integration_control.penta_historian_observations_v1 where observation_id=${id}::uuid limit 1`;
  return rows[0] ?? null;
}
async function listControls(limit: number) {
  return await sql`select control_id,control_family,semantic_version,control_kind,authority_model,state,risk_ceiling,effective_at,supersedes_control_id,superseded_by_control_id,source_ref,control_sha256,registered_by_agent_id,created_at,updated_at from integration_control.penta_control_authority_registry_v1 order by control_family,effective_at desc limit ${limit}`;
}
async function getControl(id: string) {
  const rows = await sql`select control_id,control_family,semantic_version,control_kind,authority_model,state,risk_ceiling,effective_at,supersedes_control_id,superseded_by_control_id,source_ref,control_sha256,registered_by_agent_id,created_at,updated_at from integration_control.penta_control_authority_registry_v1 where control_id=${id} limit 1`;
  return rows[0] ?? null;
}
async function currentControl(family: string) {
  const rows = await sql`select control_id,control_family,semantic_version,control_kind,authority_model,state,risk_ceiling,effective_at,supersedes_control_id,superseded_by_control_id,source_ref,control_sha256,registered_by_agent_id from integration_control.penta_control_authority_registry_v1 where control_family=${family} and state='current' order by effective_at desc limit 1`;
  return rows[0] ?? null;
}
async function lineage(family: string) {
  const controls = await sql`select control_id,control_family,semantic_version,control_kind,authority_model,state,risk_ceiling,effective_at,supersedes_control_id,superseded_by_control_id,source_ref,control_sha256 from integration_control.penta_control_authority_registry_v1 where control_family=${family} order by effective_at asc`;
  const supersessions = await sql`select receipt_id,superseded_control_id,current_control_id,decision,reason,evidence_sha256,observed_at from integration_control.penta_supersession_receipts_v1 where control_family=${family} order by observed_at asc`;
  return { control_family: family, current: controls.find((x: any) => x.state === "current") ?? null, controls, supersessions };
}
async function chain(receiptId: string) {
  const rows = await sql`
    select jsonb_build_object(
      'supersession',jsonb_build_object('receipt_id',r.receipt_id,'control_family',r.control_family,'superseded_control_id',r.superseded_control_id,'current_control_id',r.current_control_id,'superseded_snapshot_sha256',r.superseded_snapshot_sha256,'current_snapshot_sha256',r.current_snapshot_sha256,'decision',r.decision,'reason',r.reason,'enforced_by_agent_id',r.enforced_by_agent_id,'archive_state',r.archive_state,'historian_state',r.historian_state,'scribe_state',r.scribe_state,'evidence_sha256',r.evidence_sha256,'observed_at',r.observed_at),
      'archive',case when a.archive_id is null then null else jsonb_build_object('archive_id',a.archive_id,'control_id',a.control_id,'superseded_by_control_id',a.superseded_by_control_id,'historical_state',a.historical_state,'archived_snapshot_sha256',a.archived_snapshot_sha256,'restore_authority',a.restore_authority,'archived_by_agent_id',a.archived_by_agent_id,'archived_at',a.archived_at) end,
      'historian',case when h.observation_id is null then null else jsonb_build_object('observation_id',h.observation_id,'source_id',h.source_id,'observed_at',h.observed_at,'content_digest',h.content_digest,'prior_digest',h.prior_digest,'change_state',h.change_state,'current_truth_effect',h.current_truth_effect,'evidence_ref',h.evidence_ref,'summary',h.summary,'scribe_handoff_state',h.scribe_handoff_state) end,
      'scribe',case when s.story_id is null then null else jsonb_build_object('story_id',s.story_id,'story_kind',s.story_kind,'title',s.title,'narrative',s.narrative,'story_sha256',s.story_sha256,'current_authority_effect',s.current_authority_effect,'recorded_by_agent_id',s.recorded_by_agent_id,'recorded_at',s.recorded_at) end,
      'historical_control',case when hc.control_id is null then null else jsonb_build_object('control_id',hc.control_id,'authority_model',hc.authority_model,'state',hc.state,'effective_at',hc.effective_at,'control_sha256',hc.control_sha256) end,
      'current_control',case when cc.control_id is null then null else jsonb_build_object('control_id',cc.control_id,'authority_model',cc.authority_model,'state',cc.state,'effective_at',cc.effective_at,'control_sha256',cc.control_sha256) end
    ) as chain
    from integration_control.penta_supersession_receipts_v1 r
    left join integration_control.penta_archiver_records_v1 a on a.supersession_receipt_id=r.receipt_id
    left join integration_control.penta_historian_observations_v1 h on h.metadata->>'supersession_receipt_id'=r.receipt_id::text
    left join integration_control.penta_scribe_stories_v1 s on s.supersession_receipt_id=r.receipt_id
    left join integration_control.penta_control_authority_registry_v1 hc on hc.control_id=r.superseded_control_id
    left join integration_control.penta_control_authority_registry_v1 cc on cc.control_id=r.current_control_id
    where r.receipt_id=${receiptId}::uuid limit 1`;
  return rows[0]?.chain ?? null;
}
function openapi() {
  const p = (summary: string) => ({ get: { summary, responses: { "200": { description: "Public read-only historical/control data" }, "404": { description: "Not found" } } } });
  return {
    openapi: "3.1.0",
    info: { title: "CrownThrive PentaHistory Mesh API", version: VERSION, description: "Public read-only history, supersession, archive, lineage, and current-control discovery. Historical records carry no execution authority." },
    servers: [{ url: BASE }],
    paths: {
      "/api/stories": p("List PentaScribe stories"),
      "/api/stories/{story_id}": p("Get a PentaScribe story"),
      "/api/supersessions": p("List PentaPolice supersession receipts"),
      "/api/supersessions/{receipt_id}": p("Get a PentaPolice supersession receipt"),
      "/api/archives": p("List PentaArchiver records"),
      "/api/archives/{archive_id}": p("Get a PentaArchiver record"),
      "/api/observations": p("List PentaHistorian observations"),
      "/api/observations/{observation_id}": p("Get a PentaHistorian observation"),
      "/api/controls": p("List public-safe authority controls"),
      "/api/controls/{control_id}": p("Get a control"),
      "/api/families/{control_family}/current": p("Get current control for a family"),
      "/api/families/{control_family}/lineage": p("Get full control lineage"),
      "/api/chains/{receipt_id}": p("Get supersession→archive→historian→scribe chain"),
      "/api/mesh": p("Discover mesh services"),
      "/health": p("Health and record counts"),
      "/manifest": p("Service manifest"),
      "/.well-known/penta-history-mesh": p("Well-known mesh discovery")
    }
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: common("text/plain") });
  if (!["GET", "HEAD"].includes(req.method)) return json(req, { error: "method_not_allowed", authority_effect: "none" }, 405, "no-store");
  const url = new URL(req.url);
  const tail = routeContext(url);
  const limit = clampLimit(url);
  try {
    if (tail[0] === "api" && tail[1] === "stories" && !tail[2]) return json(req, { schema: "ct.penta.history.stories.v1", authority_effect: "none", items: await listStories(limit) });
    if (tail[0] === "api" && tail[1] === "stories" && tail[2]) { const x = await getStory(tail[2]); return x ? json(req, { schema: "ct.penta.history.public-story.v2", authority_effect: "none", historical_fact: true, story: x, links: { human: `${BASE}/stories/${x.story_id}`, chain: `${BASE}/api/chains/${x.supersession_receipt_id}` } }) : json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "supersessions" && !tail[2]) return json(req,{schema:"ct.penta.history.supersessions.v1",authority_effect:"none",items:await listSupersessions(limit)});
    if (tail[0] === "api" && tail[1] === "supersessions" && tail[2]) { const x=await getSupersession(tail[2]); return x?json(req,{schema:"ct.penta.history.supersession.v1",authority_effect:"none",receipt:x,links:{chain:`${BASE}/api/chains/${x.receipt_id}`}}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "archives" && !tail[2]) return json(req,{schema:"ct.penta.history.archives.v1",authority_effect:"none",items:await listArchives(limit)});
    if (tail[0] === "api" && tail[1] === "archives" && tail[2]) { const x=await getArchive(tail[2]); return x?json(req,{schema:"ct.penta.history.archive.v1",authority_effect:"none",archive:x,links:{chain:`${BASE}/api/chains/${x.supersession_receipt_id}`}}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "observations" && !tail[2]) return json(req,{schema:"ct.penta.history.observations.v1",authority_effect:"none",items:await listObservations(limit)});
    if (tail[0] === "api" && tail[1] === "observations" && tail[2]) { const x=await getObservation(tail[2]); return x?json(req,{schema:"ct.penta.history.observation.v1",authority_effect:"none",observation:x,links:{story:x.scribe_story_id?`${BASE}/api/stories/${x.scribe_story_id}`:null,chain:x.supersession_receipt_id?`${BASE}/api/chains/${x.supersession_receipt_id}`:null}}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "controls" && !tail[2]) return json(req,{schema:"ct.penta.history.controls.v1",authority_effect:"none",items:await listControls(limit)});
    if (tail[0] === "api" && tail[1] === "controls" && tail[2]) { const id=decodeURIComponent(tail.slice(2).join("/")); const x=await getControl(id); return x?json(req,{schema:"ct.penta.history.control.v1",authority_effect:"none",control:x,links:{lineage:`${BASE}/api/families/${encodeURIComponent(x.control_family)}/lineage`,current:`${BASE}/api/families/${encodeURIComponent(x.control_family)}/current`}}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "families" && tail[2] && tail[3] === "current") { const family=decodeURIComponent(tail[2]); const x=await currentControl(family); return x?json(req,{schema:"ct.penta.history.current-control.v1",authority_effect:"current_control_registry_only",control:x}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "families" && tail[2] && tail[3] === "lineage") return json(req,{schema:"ct.penta.history.lineage.v1",authority_effect:"none",...(await lineage(decodeURIComponent(tail[2])))});
    if (tail[0] === "api" && tail[1] === "chains" && tail[2]) { const x=await chain(tail[2]); return x?json(req,{schema:"ct.penta.history.chain.v1",authority_effect:"none",historical_preservation:true,chain:x,links:{human:`${BASE}/chains/${tail[2]}`}}):json(req,{error:"not_found"},404); }
    if (tail[0] === "api" && tail[1] === "mesh") { const [sc,ac,hc,st,cc]=await Promise.all([sql`select count(*)::int n from integration_control.penta_supersession_receipts_v1`,sql`select count(*)::int n from integration_control.penta_archiver_records_v1`,sql`select count(*)::int n from integration_control.penta_historian_observations_v1`,sql`select count(*)::int n from integration_control.penta_scribe_stories_v1`,sql`select count(*)::int n from integration_control.penta_control_authority_registry_v1`]); return json(req,{schema:"ct.penta.history.mesh.v2",node:"PentaHistory",service_id:SERVICE_ID,version:VERSION,authority_effect:"none",counts:{supersessions:sc[0].n,archives:ac[0].n,observations:hc[0].n,stories:st[0].n,controls:cc[0].n},services:{human_index:`${BASE}/stories`,stories:`${BASE}/api/stories`,supersessions:`${BASE}/api/supersessions`,archives:`${BASE}/api/archives`,observations:`${BASE}/api/observations`,controls:`${BASE}/api/controls`,mesh:`${BASE}/api/mesh`,openapi:`${BASE}/openapi.json`,manifest:`${BASE}/manifest`,health:`${BASE}/health`,well_known:`${BASE}/.well-known/penta-history-mesh`}}); }
    if (tail[0] === "openapi.json") return json(req,openapi(),200,"public,max-age=300");
    if (tail[0] === ".well-known" && tail[1] === "penta-history-mesh") return json(req,{schema:"ct.penta.history.well-known.v1",service_id:SERVICE_ID,node:"PentaHistory",version:VERSION,authority_effect:"none",public_read_only:true,mesh_api:`${BASE}/api/mesh`,openapi:`${BASE}/openapi.json`,manifest:`${BASE}/manifest`,health:`${BASE}/health`},200,"public,max-age=300");
    if (tail[0] === "manifest") return json(req,{schema:"ct.penta.history.manifest.v2",service_id:SERVICE_ID,node:"PentaHistory",version:VERSION,public_read_only:true,authority_effect:"none",chain:"PentaPolice → PentaArchiver → PentaHistorian → PentaScribe",routes:Object.keys(openapi().paths),security:{public_projection_allowlist:true,archived_snapshot_public:false,internal_metadata_public:false,secrets_public:false}},200,"public,max-age=300");
    if (tail[0] === "health") { const [s,a,h,st,c]=await Promise.all([sql`select count(*)::int n,max(observed_at) latest from integration_control.penta_supersession_receipts_v1`,sql`select count(*)::int n,max(archived_at) latest from integration_control.penta_archiver_records_v1`,sql`select count(*)::int n,max(observed_at) latest from integration_control.penta_historian_observations_v1`,sql`select count(*)::int n,max(recorded_at) latest from integration_control.penta_scribe_stories_v1`,sql`select count(*)::int n,count(*) filter(where state='current')::int current_count from integration_control.penta_control_authority_registry_v1`]); return json(req,{ok:true,service_id:SERVICE_ID,node:"PentaHistory",version:VERSION,authority_effect:"none",counts:{supersessions:s[0].n,archives:a[0].n,observations:h[0].n,stories:st[0].n,controls:c[0].n,current_controls:c[0].current_count},latest:{supersession:s[0].latest,archive:a[0].latest,observation:h[0].latest,story:st[0].latest}},200,"no-store"); }
    if (tail[0] === "stories" && tail[1]) { const x=await getStory(tail[1]); if(!x)return respond(req,"Not found","text/plain",404); const body=`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${esc(x.title)}</title><style>body{font:16px system-ui;max-width:900px;margin:48px auto;padding:0 20px;line-height:1.6;background:#0b0d12;color:#f5f7fb}a{color:#a9c1ff}.card{border:1px solid #303746;border-radius:18px;padding:24px;background:#121620}.meta{color:#aeb8ca;font-size:14px}code{word-break:break-all}</style></head><body><p><a href="${BASE}/stories">← PentaHistory</a></p><main class="card"><p class="meta">PentaScribe · Historical Fact · Current authority effect: ${esc(x.current_authority_effect)}</p><h1>${esc(x.title)}</h1><p>${esc(x.narrative)}</p><hr><p><strong>Historical control:</strong> <code>${esc(x.historical_control_id)}</code></p><p><strong>Current control:</strong> <code>${esc(x.current_control_id)}</code></p><p><strong>Story SHA-256:</strong> <code>${esc(x.story_sha256)}</code></p><p><a href="${BASE}/api/stories/${x.story_id}">Story API</a> · <a href="${BASE}/api/chains/${x.supersession_receipt_id}">Full evidence chain API</a></p></main></body></html>`; return respond(req,body,"text/html; charset=utf-8"); }
    if (tail[0] === "chains" && tail[1]) { const x=await chain(tail[1]); if(!x)return respond(req,"Not found","text/plain",404); const body=`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>PentaHistory Evidence Chain</title><style>body{font:16px system-ui;max-width:1000px;margin:48px auto;padding:0 20px;background:#0b0d12;color:#f5f7fb;line-height:1.55}a{color:#a9c1ff}.card{border:1px solid #303746;border-radius:18px;padding:20px;margin:14px 0;background:#121620}code{word-break:break-all}.meta{color:#aeb8ca}</style></head><body><p><a href="${BASE}/stories">← PentaHistory</a></p><h1>Supersession Evidence Chain</h1><p class="meta">PentaPolice → PentaArchiver → PentaHistorian → PentaScribe. Historical records create no current authority.</p><section class="card"><h2>PentaPolice</h2><p>${esc(x.supersession?.superseded_control_id)} → ${esc(x.supersession?.current_control_id)}</p><code>${esc(x.supersession?.receipt_id)}</code></section><section class="card"><h2>PentaArchiver</h2><p>${esc(x.archive?.historical_state)}</p><code>${esc(x.archive?.archive_id)}</code></section><section class="card"><h2>PentaHistorian</h2><p>${esc(x.historian?.summary)}</p><code>${esc(x.historian?.observation_id)}</code></section><section class="card"><h2>PentaScribe</h2><p>${esc(x.scribe?.narrative)}</p><code>${esc(x.scribe?.story_id)}</code></section><p><a href="${BASE}/api/chains/${tail[1]}">Machine-readable chain</a></p></body></html>`; return respond(req,body,"text/html; charset=utf-8"); }
    const rows=await listStories(limit); const cards=rows.map((x:any)=>`<article class="card"><h2><a href="${BASE}/stories/${x.story_id}">${esc(x.title)}</a></h2><p><code>${esc(x.historical_control_id)}</code> → <code>${esc(x.current_control_id)}</code></p><p class="meta">${esc(x.recorded_at)}</p></article>`).join(""); const body=`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>PentaHistory</title><style>body{font:16px system-ui;max-width:1000px;margin:48px auto;padding:0 20px;background:#0b0d12;color:#f5f7fb}a{color:#a9c1ff}.card{border:1px solid #303746;border-radius:18px;padding:20px;margin:16px 0;background:#121620}.meta{color:#aeb8ca}code{word-break:break-all}</style></head><body><h1>PentaHistory</h1><p>Public historical facts preserved by PentaPolice → PentaArchiver → PentaHistorian → PentaScribe. Historical records have no current authority.</p>${cards}<p><a href="${BASE}/api/mesh">Mesh API</a> · <a href="${BASE}/openapi.json">OpenAPI</a> · <a href="${BASE}/manifest">Manifest</a></p></body></html>`; return respond(req,body,"text/html; charset=utf-8");
  } catch (error) {
    return json(req,{error:"history_mesh_unavailable",error_class:error instanceof Error?error.name:"unknown",authority_effect:"none"},503,"no-store");
  }
});
