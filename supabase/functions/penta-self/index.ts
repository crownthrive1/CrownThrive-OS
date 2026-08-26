import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store", "x-content-type-options": "nosniff" } });
}
function jwtRole(req: Request) {
  try {
    const token=(req.headers.get("authorization")??"").replace(/^Bearer\s+/i,"");
    const p=token.split(".")[1]; if(!p) return "";
    const s=p.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(p.length/4)*4,"=");
    return String(JSON.parse(atob(s))?.role??"");
  } catch { return ""; }
}
async function rpc(name:string) {
  const r=await fetch(`${BASE}/rest/v1/rpc/${name}`,{method:"POST",headers:{apikey:SERVICE_KEY,authorization:`Bearer ${SERVICE_KEY}`,"content-type":"application/json"},body:"{}"});
  const text=await r.text(); let data:unknown=text; try{data=JSON.parse(text)}catch{}
  if(!r.ok) throw new Error(`rpc_${name}_${r.status}:${typeof data==="string"?data:JSON.stringify(data)}`);
  return data;
}
Deno.serve(async(req:Request)=>{
  if(jwtRole(req)!=="service_role") return json({ok:false,error:"service_role_required"},403);
  if(req.method!=="GET"&&req.method!=="POST") return json({ok:false,error:"GET_or_POST_required"},405);
  let body:Record<string,unknown>={}; if(req.method==="POST"){try{body=await req.json()}catch{}}
  const action=String(body.action??new URL(req.url).searchParams.get("action")??"status");
  try{
    if(action==="status"||action==="health") return json({ok:true,service:"PentaSELF",phase:3,production:true,result:await rpc("penta_self_status_v1")});
    if(action==="tick"||action==="heal"||action==="reconcile") return json({ok:true,service:"PentaSELF",phase:3,production:true,result:await rpc("penta_self_tick_v1")});
    return json({ok:false,error:"unsupported_action",allowed:["status","health","tick","heal","reconcile"]},400);
  }catch(e){return json({ok:false,service:"PentaSELF",error:e instanceof Error?e.message:String(e)},500)}
});
