import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const url=Deno.env.get("SUPABASE_URL")!;
const key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(url,key,{auth:{persistSession:false}});
const respond=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});

async function sha256(text:string){const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,"0")).join("")}
function safePath(path:string){if(!/^[A-Za-z0-9._\/-]{1,180}$/.test(path)||path.includes("..")||path.startsWith("/"))throw new Error("invalid_path");return path}
function identifier(value:string){if(!/^[A-Za-z_][A-Za-z0-9_]{0,62}$/.test(value))throw new Error("invalid_identifier");return value}
function quoted(value:unknown){return JSON.stringify(String(value??""))}

function compile(component:any,packageName:string){
  const kind=String(component.kind??"");
  const path=safePath(String(component.path??""));
  let content="";
  if(kind==="typescript_module"){
    const name=identifier(String(component.export_name??"serviceInfo"));
    content=`export const ${name} = ${JSON.stringify(component.value??{package:packageName},null,2)} as const;\n`;
  }else if(kind==="edge_api"){
    const service=String(component.service??packageName),message=String(component.message??"CrownThrive generated service");
    content=`import \"jsr:@supabase/functions-js/edge-runtime.d.ts\";\nconst SERVICE=${quoted(service)};\nDeno.serve(async(req:Request)=>{const u=new URL(req.url);if(req.method===\"GET\"&&u.pathname.endsWith(\"/health\"))return Response.json({ok:true,service:SERVICE,generated_by:\"ct-factory-compiler.v3\"});if(req.method!==\"GET\")return Response.json({error:\"method_not_allowed\"},{status:405});return Response.json({service:SERVICE,message:${quoted(message)}});});\n`;
  }else if(kind==="static_site"){
    const title=String(component.title??packageName).replace(/[<>&\"]/g,""),headline=String(component.headline??title).replace(/[<>&]/g,""),body=String(component.body??"").replace(/[<>&]/g,"");
    content=`<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>${title}</title></head><body><main><h1>${headline}</h1><p>${body}</p></main></body></html>\n`;
  }else if(kind==="sql_table"){
    const schema=identifier(String(component.schema??"ct_generated")),table=identifier(String(component.table??"generated_service")),cols=Array.isArray(component.columns)?component.columns:[];
    if(!cols.length)throw new Error("columns_required");
    const defs=cols.map((x:any)=>`${identifier(String(x.name))} ${["text","uuid","integer","boolean","jsonb","timestamptz"].includes(String(x.type))?String(x.type):"text"}${x.nullable?"":" not null"}`).join(",\n  ");
    content=`create schema if not exists ${schema};\ncreate table if not exists ${schema}.${table} (\n  ${defs}\n);\n`;
  }else if(kind==="deno_test"){
    const target=safePath(String(component.target??"index.ts"));
    content=`import { assert } from \"jsr:@std/assert\";\nDeno.test(\"generated source exists\", async()=>{const text=await Deno.readTextFile(new URL(${quoted("../"+target)},import.meta.url));assert(text.length>0);});\n`;
  }else throw new Error(`unsupported_component:${kind}`);
  return {kind,path,content};
}

Deno.serve(async req=>{try{
  if(req.method!=="POST")return respond({error:"POST required"},405);
  const payload=await req.json();
  if(!payload?.build_run_id||!payload?.project_id)throw new Error("build context required");
  const requirements=payload.requirements??{};
  const spec=(requirements&&typeof requirements==="object"&&!Array.isArray(requirements)?requirements.compiler_spec:null)??{package_name:"factory-generated-service",components:[{kind:"typescript_module",path:"src/generated.ts",export_name:"build",value:{objective:payload.objective??"generated"}}]};
  const packageName=String(spec.package_name??"generated-package");
  if(!/^[a-z0-9][a-z0-9._-]{2,80}$/i.test(packageName))throw new Error("invalid_package_name");
  const components=Array.isArray(spec.components)?spec.components:[];
  if(!components.length||components.length>32)throw new Error("components_required");
  const files=[];
  for(const component of components){
    const file=compile(component,packageName),digest=await sha256(file.content);
    const {error}=await db.from("ct_factory_artifacts").upsert({build_run_id:payload.build_run_id,artifact_type:"source_file",asset_key:file.path,uri:`thrivebase://factory/${payload.build_run_id}/source/${encodeURIComponent(file.path)}`,sha256:digest,metadata:{contract:"ct.compiler.file.v1",kind:file.kind,path:file.path,content:file.content,bytes:new TextEncoder().encode(file.content).byteLength,compiler:"ct-factory-compiler.v3"}},{onConflict:"build_run_id,artifact_type,asset_key"});
    if(error)throw error;
    files.push({path:file.path,kind:file.kind,sha256:digest,bytes:new TextEncoder().encode(file.content).byteLength});
  }
  const report={contract:"ct.compiler.v3",package_name:packageName,files,deterministic:true,template_compiler:true,arbitrary_shell:false,arbitrary_sql:false,generated_at:new Date().toISOString()};
  const reportSha=await sha256(JSON.stringify(report));
  await db.from("ct_factory_artifacts").upsert({build_run_id:payload.build_run_id,artifact_type:"compiler_report",asset_key:`${packageName}-compiler-report.json`,uri:`thrivebase://factory/${payload.build_run_id}/compiler-report`,sha256:reportSha,metadata:report},{onConflict:"build_run_id,artifact_type,asset_key"});
  return respond({ok:true,compiler:"ct-factory-compiler.v3",package_name:packageName,files,report_sha256:reportSha});
}catch(error){return respond({ok:false,error:error instanceof Error?error.message:String(error)},422)}});
