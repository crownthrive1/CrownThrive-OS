import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const url = Deno.env.get("SUPABASE_URL")!;
const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(url, serviceKey, { auth: { persistSession: false } });
const COOKIE = "ct_penta_nurture";

const json = (body: unknown, status = 200, cookie?: string) => {
  const headers = new Headers({"content-type":"application/json","cache-control":"no-store","x-content-type-options":"nosniff"});
  if (cookie) headers.append("set-cookie", `${COOKIE}=${cookie}; Path=/; Max-Age=2592000; Secure; HttpOnly; SameSite=Lax`);
  return new Response(JSON.stringify(body), { status, headers });
};
const cookieValue = (req: Request) => {
  const raw=req.headers.get("cookie")??"";
  return raw.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([0-9a-fA-F-]{36})(?:;|$)`))?.[1] ?? crypto.randomUUID();
};
const sha256 = async (value: string) => {
  const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,"0")).join("");
};
const serviceRole = (req: Request) => {
  try { const token=(req.headers.get("authorization")??"").replace(/^Bearer\s+/i,""); const part=token.split(".")[1]; if(!part)return false; const padded=part.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(part.length/4)*4,"="); return JSON.parse(atob(padded))?.role==="service_role"; } catch { return false; }
};

Deno.serve(async(req)=>{
  const session=cookieValue(req), sessionHash=await sha256(session);
  try {
    if(!serviceRole(req)) return json({ok:false,error:"service_role_required"},403,session);
    if(req.method!=="GET"&&req.method!=="POST") return json({ok:false,error:"GET_or_POST_required"},405,session);
    let body:Record<string,unknown>={}; if(req.method==="POST"){try{body=await req.json()}catch{}}
    const action=String(body.action??new URL(req.url).searchParams.get("action")??"status");
    if(!new Set(["status","nurture","reconcile","heartbeat"]).has(action)) return json({ok:false,error:"unsupported_action"},400,session);
    const rpc=action==="nurture"||action==="reconcile"?"penta_nurture_tick_v1":"penta_nurture_status_v1";
    const {data,error}=await db.rpc(rpc); if(error) throw error;
    const {error:telemetryError}=await db.rpc("penta_nurture_record_cookie_event_v1",{p_cookie_sha256:sessionHash,p_event_type:`penta.nurture.${action}`,p_surface_id:body.surface_id?String(body.surface_id):null,p_provider_system:body.provider_system?String(body.provider_system):null,p_consent_state:"necessary",p_actor_class:"software",p_metadata:{action,method:req.method,runtime:"penta-nurture.edge.v1",software_priority:true,secret_material_exposed:false}}); if(telemetryError) throw telemetryError;
    return json({ok:true,service:"PentaNurture",action,result:data,telemetry:{cookie_value_stored:false,server_hash:"SHA-256"}},200,session);
  } catch(e) { return json({ok:false,service:"PentaNurture",error:e instanceof Error?e.message:String(e)},500,session); }
});
