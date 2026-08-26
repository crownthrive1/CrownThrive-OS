import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const url=Deno.env.get("SUPABASE_URL")!, key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(url,key,{auth:{persistSession:false}});
const respond=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});

async function sha256(text:string){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,"0")).join("")}
function safePath(v:string){if(!/^[A-Za-z0-9._\/-]{1,220}$/.test(v)||v.includes("..")||v.startsWith("/"))throw new Error("invalid_path");return v}
function ident(v:string){if(!/^[A-Za-z_][A-Za-z0-9_]{0,62}$/.test(v))throw new Error("invalid_identifier");return v}
function envName(v:string){if(!/^[A-Z][A-Z0-9_]{1,79}$/.test(v))throw new Error("invalid_env_name");return v}
function json(v:unknown){return JSON.stringify(v,null,2)+"\n"}
function cleanText(v:unknown,max=5000){return String(v??"").slice(0,max).replace(/<script/gi,"&lt;script").replace(/^\s*(import|export)\s+/gm,"$1-disabled ")}
function safeRoute(v:string){if(!/^\/[A-Za-z0-9_{}\-\/]*$/.test(v)||v.includes(".."))throw new Error("invalid_route");return v}
function safeUrlPath(v:string){if(!/^\/[A-Za-z0-9._~!$&'()*+,;=:@%\-\/]*$/.test(v)||v.includes(".."))throw new Error("invalid_asset_url");return v}

function compile(component:any,pkg:string){
  const kind=String(component.kind??"");
  const path=safePath(String(component.path??""));
  let content="";
  if(kind==="typescript_module"){
    const name=ident(String(component.export_name??"serviceInfo"));
    content=`export const ${name} = ${JSON.stringify(component.value??{package:pkg},null,2)} as const;\n`;
  } else if(kind==="edge_api"){
    const service=String(component.service??pkg).slice(0,120), message=String(component.message??"CrownThrive generated service").slice(0,500);
    content=`import "jsr:@supabase/functions-js/edge-runtime.d.ts";\nconst SERVICE=${JSON.stringify(service)};\nDeno.serve(async(req:Request)=>{const u=new URL(req.url);if(req.method==="GET"&&u.pathname.endsWith("/health"))return Response.json({ok:true,service:SERVICE,generated_by:"ct-factory-compiler.v4"});if(req.method!=="GET")return Response.json({error:"method_not_allowed"},{status:405});return Response.json({service:SERVICE,message:${JSON.stringify(message)}});});\n`;
  } else if(kind==="static_site"){
    const title=cleanText(component.title??pkg,160).replace(/[<>&"]/g,""), headline=cleanText(component.headline??title,240).replace(/[<>&]/g,""), body=cleanText(component.body??"",4000).replace(/[<>]/g,m=>m==="<"?"&lt;":"&gt;");
    content=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="generator" content="CrownThrive Autonomous Software Factory v4"><title>${title}</title></head><body><main><h1>${headline}</h1><p>${body}</p></main></body></html>\n`;
  } else if(kind==="sql_table"){
    const schema=ident(String(component.schema??"ct_generated")), table=ident(String(component.table??"generated_service"));
    const cols=Array.isArray(component.columns)?component.columns:[]; if(!cols.length||cols.length>64)throw new Error("columns_required");
    const allowed=["text","uuid","integer","bigint","boolean","jsonb","timestamptz","date","numeric"];
    const defs=cols.map((x:any)=>`${ident(String(x.name))} ${allowed.includes(String(x.type))?String(x.type):"text"}${x.default==="gen_random_uuid()"?" default gen_random_uuid()":""}${x.nullable?"":" not null"}`).join(",\n  ");
    content=`create schema if not exists ${schema};\ncreate table if not exists ${schema}.${table} (\n  ${defs}\n);\n`;
  } else if(kind==="postgres_view"){
    const schema=ident(String(component.schema??"ct_generated")), view=ident(String(component.view??"generated_view")), sourceSchema=ident(String(component.source_schema??"public")), sourceTable=ident(String(component.source_table??"source"));
    const columns=(Array.isArray(component.columns)?component.columns:[]).map((x:any)=>ident(String(x))); if(!columns.length||columns.length>64)throw new Error("view_columns_required");
    content=`create schema if not exists ${schema};\ncreate or replace view ${schema}.${view} as select ${columns.join(", ")} from ${sourceSchema}.${sourceTable};\n`;
  } else if(kind==="deno_test"){
    const target=safePath(String(component.target??"index.ts"));
    content=`import { assert } from "jsr:@std/assert";\nDeno.test("generated source exists", async()=>{const text=await Deno.readTextFile(new URL(${JSON.stringify("../"+target)},import.meta.url));assert(text.length>0);});\n`;
  } else if(kind==="json_document"){
    content=json(component.value??{});
  } else if(kind==="openapi_spec"){
    const paths:any={}; for(const p of Array.isArray(component.paths)?component.paths:[]){const route=safeRoute(String(p.path));const method=String(p.method??"get").toLowerCase();if(!["get","post","put","patch","delete"].includes(method))throw new Error("invalid_http_method");const operationId=ident(String(p.operation_id??`${method}_operation`));paths[route]??={};paths[route][method]={operationId,summary:String(p.summary??operationId).slice(0,240),responses:{"200":{description:"Success",content:{"application/json":{schema:p.response_schema&&typeof p.response_schema==="object"?p.response_schema:{type:"object"}}}}}};}
    content=json({openapi:"3.1.0",info:{title:String(component.title??pkg).slice(0,160),version:String(component.version??"1.0.0").slice(0,40)},paths});
  } else if(kind==="mcp_tool_manifest"){
    const tools=(Array.isArray(component.tools)?component.tools:[]).slice(0,64).map((t:any)=>({name:ident(String(t.name)),description:String(t.description??"").slice(0,500),inputSchema:t.input_schema&&typeof t.input_schema==="object"?t.input_schema:{type:"object",properties:{}}}));
    content=json({contract:"ct.mcp.tools.v1",server:String(component.server??pkg).slice(0,120),tools});
  } else if(kind==="github_workflow"){
    const wfName=String(component.name??`${pkg} CI`).replace(/[\r\n:]/g," ").slice(0,120);const trigger=String(component.trigger??"push");if(!["push","pull_request","workflow_dispatch"].includes(trigger))throw new Error("invalid_workflow_trigger");const steps:any[]=Array.isArray(component.steps)?component.steps:[];const lines=[`name: ${wfName}`,"",`on: ${trigger}`,"","permissions:","  contents: read","","jobs:","  verify:","    runs-on: ubuntu-latest","    steps:"];
    for(const s of steps.slice(0,24)){const type=String(s.type);if(type==="checkout")lines.push("      - uses: actions/checkout@v4");else if(type==="deno_setup")lines.push("      - uses: denoland/setup-deno@v2","        with:",`          deno-version: ${String(s.version??"v2.x").replace(/[^A-Za-z0-9._-]/g,"")}`);else if(type==="deno_check")lines.push("      - name: Deno check",`        run: deno check ${safePath(String(s.path??"index.ts"))}`);else if(type==="deno_test")lines.push("      - name: Deno test",`        run: deno test ${safePath(String(s.path??"tests"))}`);else if(type==="upload_artifact")lines.push("      - uses: actions/upload-artifact@v4","        with:",`          name: ${String(s.name??"factory-artifact").replace(/[^A-Za-z0-9._-]/g,"-")}`,`          path: ${safePath(String(s.path??"artifacts"))}`);else throw new Error(`unsupported_workflow_step:${type}`)}
    content=lines.join("\n")+"\n";
  } else if(kind==="mdx_document"){
    const title=cleanText(component.title??pkg,180).replace(/[\r\n"]/g," "), description=cleanText(component.description??"",280).replace(/[\r\n"]/g," "), body=cleanText(component.body??"",12000);
    content=`---\ntitle: "${title}"\ndescription: "${description}"\ngeneratedBy: "CrownThrive Autonomous Software Factory v4"\n---\n\n${body}\n`;
  } else if(kind==="service_worker"){
    const assets=(Array.isArray(component.assets)?component.assets:[]).slice(0,128).map((x:any)=>safeUrlPath(String(x)));const cache=String(component.cache_name??`${pkg}-v1`).replace(/[^A-Za-z0-9._-]/g,"-");
    content=`const CACHE=${JSON.stringify(cache)},ASSETS=${JSON.stringify(assets)};\nself.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));\nself.addEventListener("fetch",e=>{const u=new URL(e.request.url);if(u.origin!==self.location.origin)return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});\n`;
  } else if(kind==="env_contract"){
    const vars=(Array.isArray(component.variables)?component.variables:[]).slice(0,128).map((x:any)=>({name:envName(String(x.name)),required:x.required!==false,secret:!!x.secret,description:String(x.description??"").slice(0,300)}));
    content=json({contract:"ct.env.v1",package:pkg,variables:vars,values_included:false});
  } else if(kind==="event_contract"){
    const name=ident(String(component.name??"factory_event")), props=component.properties&&typeof component.properties==="object"?component.properties:{};
    content=json({$schema:"https://json-schema.org/draft/2020-12/schema",$id:`urn:crownthrive:event:${name}`,title:name,type:"object",properties:props,required:Array.isArray(component.required)?component.required.map((x:any)=>ident(String(x))):[],additionalProperties:false});
  } else if(kind==="policy_manifest"){
    content=json({contract:"ct.policy.v1",policy_id:String(component.policy_id??`${pkg}.policy`).slice(0,160),risk_class:String(component.risk_class??"D1"),authority:String(component.authority??"CHLOM").slice(0,120),fail_closed:component.fail_closed!==false,required_evidence:Array.isArray(component.required_evidence)?component.required_evidence.slice(0,32):[],rules:Array.isArray(component.rules)?component.rules.slice(0,64):[]});
  } else if(kind==="route_manifest"){
    const routes=(Array.isArray(component.routes)?component.routes:[]).slice(0,256).map((r:any)=>({path:safeRoute(String(r.path)),surface:String(r.surface??"web").slice(0,80),access:String(r.access??"public").slice(0,40)}));content=json({contract:"ct.routes.v1",package:pkg,routes});
  } else if(kind==="asset_manifest"){
    const assets=(Array.isArray(component.assets)?component.assets:[]).slice(0,512).map((a:any)=>({key:String(a.key??"").slice(0,160),path:safePath(String(a.path)),type:String(a.type??"asset").slice(0,80),rights_owner:String(a.rights_owner??"CrownThrive, LLC").slice(0,160)}));content=json({contract:"ct.assets.v1",package:pkg,assets});
  } else throw new Error(`unsupported_component:${kind}`);
  return {kind,path,content};
}

Deno.serve(async req=>{try{
  if(req.method!=="POST")return respond({error:"POST required"},405);
  const p=await req.json(); if(!p?.build_run_id||!p?.project_id)throw new Error("build_context_required");
  const reqs=p.requirements??{}; const spec=(reqs&&typeof reqs==="object"&&!Array.isArray(reqs)?reqs.compiler_spec:null)??{package_name:"factory-generated-service",components:[{kind:"typescript_module",path:"src/generated.ts",export_name:"build",value:{objective:p.objective??"generated"}}]};
  const pkg=String(spec.package_name??"generated-package"); if(!/^[a-z0-9][a-z0-9._-]{2,80}$/i.test(pkg))throw new Error("invalid_package_name");
  const components=Array.isArray(spec.components)?spec.components:[]; if(!components.length||components.length>96)throw new Error("components_required");
  const {data:families,error:fe}=await db.from("ct_factory_component_families").select("kind,enabled,compiler_version").eq("enabled",true); if(fe)throw fe; const allowed=new Set((families??[]).map((x:any)=>x.kind));
  const files:any[]=[]; const seen=new Set<string>();
  for(const c of components){if(!allowed.has(String(c.kind)))throw new Error(`component_family_not_enabled:${String(c.kind)}`);const f=compile(c,pkg);if(seen.has(f.path))throw new Error(`duplicate_path:${f.path}`);seen.add(f.path);const bytes=new TextEncoder().encode(f.content).byteLength;if(bytes>262144)throw new Error(`artifact_too_large:${f.path}`);const digest=await sha256(f.content);const {error}=await db.from("ct_factory_artifacts").upsert({build_run_id:p.build_run_id,artifact_type:"source_file",asset_key:f.path,uri:`thrivebase://factory/${p.build_run_id}/source/${encodeURIComponent(f.path)}`,sha256:digest,metadata:{contract:"ct.compiler.file.v2",kind:f.kind,path:f.path,content:f.content,bytes,compiler:"ct-factory-compiler.v4"}},{onConflict:"build_run_id,artifact_type,asset_key"});if(error)throw error;files.push({path:f.path,kind:f.kind,sha256:digest,bytes});}
  const report={contract:"ct.compiler.v4",package_name:pkg,files,component_count:files.length,component_kinds:[...new Set(files.map(x=>x.kind))],deterministic:true,structured_blueprints:true,arbitrary_shell:false,arbitrary_sql:false,secret_values:false,generated_at:new Date().toISOString()};const reportSha=await sha256(JSON.stringify(report));
  await db.from("ct_factory_artifacts").upsert({build_run_id:p.build_run_id,artifact_type:"compiler_report",asset_key:`${pkg}-compiler-report.json`,uri:`thrivebase://factory/${p.build_run_id}/compiler-report`,sha256:reportSha,metadata:report},{onConflict:"build_run_id,artifact_type,asset_key"});
  return respond({ok:true,compiler:"ct-factory-compiler.v4",package_name:pkg,files,component_kinds:report.component_kinds,report_sha256:reportSha});
}catch(e){return respond({ok:false,error:e instanceof Error?e.message:String(e)},422)}});
