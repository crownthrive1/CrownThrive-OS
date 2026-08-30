import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const U=Deno.env.get("SUPABASE_URL")??"";
const K=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
const TOKEN_SECRET="penta_drive_worker_internal_token_v2";
const SA_SECRET="google_cloud_service_account_thrivebase_v1";
const VERSION="1.0.0";

function out(status:number,body:unknown){return new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","x-crownthrive-contract":"ct.thrivebase.sheets-preprovision-bootstrap.v1","x-worker-version":VERSION}})}
async function rpc(name:string,body:Record<string,unknown>={}){const r=await fetch(`${U}/rest/v1/rpc/${name}`,{method:"POST",headers:{apikey:K,authorization:`Bearer ${K}`,"content-type":"application/json"},body:JSON.stringify(body)});const t=await r.text();let d:any=t;try{d=t?JSON.parse(t):null}catch{}if(!r.ok)throw new Error(`rpc:${name}:${r.status}:${t.slice(0,320)}`);return d}
async function secret(name:string){const v=await rpc("get_runtime_secret",{secret_name:name});if(typeof v!=="string"||v.length<16)throw new Error(`secret_unavailable:${name}`);return v}
function b64url(input:Uint8Array|string){const bytes=typeof input==="string"?new TextEncoder().encode(input):input;let b="";for(const x of bytes)b+=String.fromCharCode(x);return btoa(b).replaceAll("+","-").replaceAll("/","_").replace(/=+$/g,"")}
function pemToBytes(p:string){const c=p.replace(/-----BEGIN PRIVATE KEY-----/g,"").replace(/-----END PRIVATE KEY-----/g,"").replace(/\s+/g,"");const b=atob(c),o=new Uint8Array(b.length);for(let i=0;i<b.length;i++)o[i]=b.charCodeAt(i);return o}
function bytesHex(a:Uint8Array){return [...a].map(x=>x.toString(16).padStart(2,"0")).join("")}
async function sha(s:string){return bytesHex(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s))))}
function canonical(v:any):any{if(Array.isArray(v))return v.map(canonical);if(v&&typeof v==="object")return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));return v}
function stable(v:any){return JSON.stringify(canonical(v))}
async function mint(){const raw=await secret(SA_SECRET);const sa=JSON.parse(raw),now=Math.floor(Date.now()/1000);const hd=b64url(JSON.stringify({alg:"RS256",typ:"JWT"}));const cl=b64url(JSON.stringify({iss:sa.client_email,scope:"https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets",aud:sa.token_uri??"https://oauth2.googleapis.com/token",iat:now,exp:now+3600}));const input=`${hd}.${cl}`;const key=await crypto.subtle.importKey("pkcs8",pemToBytes(sa.private_key),{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["sign"]);const sig=await crypto.subtle.sign("RSASSA-PKCS1-v1_5",key,new TextEncoder().encode(input));const tr=await fetch(sa.token_uri??"https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({grant_type:"urn:ietf:params:oauth:grant-type:jwt-bearer",assertion:`${input}.${b64url(new Uint8Array(sig))}`})});const tt=await tr.text();if(!tr.ok)throw new Error(`google_token:${tr.status}:${tt.slice(0,240)}`);return{token:JSON.parse(tt).access_token,email:String(sa.client_email??"")}}
async function gj(url:string,token:string,init:RequestInit={}){const r=await fetch(url,{...init,headers:{authorization:`Bearer ${token}`,"content-type":"application/json",...(init.headers??{})}});const t=await r.text();let d:any=t;try{d=t?JSON.parse(t):null}catch{}if(!r.ok)throw new Error(`google:${r.status}:${typeof d==="string"?d.slice(0,320):stable(d).slice(0,320)}`);return d}
async function driveMeta(id:string,token:string){return gj(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}?supportsAllDrives=true&fields=id,name,mimeType,parents,version,modifiedTime,ownedByMe,capabilities(canEdit),owners(displayName,emailAddress)`,token)}
async function sheetGet(id:string,token:string){return gj(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}?fields=spreadsheetId,properties.title,sheets.properties`,token)}
async function sheetBatch(id:string,requests:any[],token:string){return gj(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}:batchUpdate`,token,{method:"POST",body:JSON.stringify({requests})})}
async function sheetPut(id:string,range:string,values:any[][],token:string){return gj(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values/${encodeURIComponent(range)}?valueInputOption=RAW`,token,{method:"PUT",body:JSON.stringify({majorDimension:"ROWS",values})})}
async function sheetRead(id:string,range:string,token:string){return gj(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values/${encodeURIComponent(range)}?majorDimension=ROWS&valueRenderOption=UNFORMATTED_VALUE`,token)}

async function bootstrap(task:any,id:string,snapshot:string,part:number,token:string){
  const meta=await driveMeta(id,token);
  if(meta.mimeType!=="application/vnd.google-apps.spreadsheet")return{ok:false,state:"HOLD_NOT_NATIVE_SHEET"};
  if(!meta.capabilities?.canEdit)return{ok:false,state:"HOLD_SERVICE_WRITER_NOT_AUTHORIZED"};
  if(meta.ownedByMe===true)return{ok:false,state:"HOLD_SERVICE_OWNED_SHEET_DISALLOWED"};
  if(meta.ownedByMe!==false)return{ok:false,state:"HOLD_OWNER_UNVERIFIED"};
  const owners=Array.isArray(meta.owners)?meta.owners:[];
  const ownerBasis=owners.map((x:any)=>String(x.emailAddress??x.displayName??"")).sort().join("|");
  const ownerSha=await sha(ownerBasis||"owner-present-unresolved");
  let ss=await sheetGet(id,token);
  let names=new Set((ss.sheets??[]).map((x:any)=>String(x.properties?.title??"")));
  const first=ss.sheets?.[0]?.properties;
  const req:any[]=[];
  if(!names.has("__PENTA_META__")&&first?.sheetId!==undefined){req.push({updateSheetProperties:{properties:{sheetId:first.sheetId,title:"__PENTA_META__"},fields:"title"}});names.add("__PENTA_META__");}
  for(const title of ["DATA","SCHEMA","PENTA","HISTORY"])if(!names.has(title))req.push({addSheet:{properties:{title}}});
  if(req.length)await sheetBatch(id,req,token);
  ss=await sheetGet(id,token);
  names=new Set((ss.sheets??[]).map((x:any)=>String(x.properties?.title??"")));
  const required=["__PENTA_META__","DATA","SCHEMA","PENTA","HISTORY"];
  if(!required.every(x=>names.has(x)))return{ok:false,state:"HOLD_TAB_BOOTSTRAP_INCOMPLETE",tabs:[...names]};
  const existing=await sheetRead(id,"__PENTA_META__!A1:B3",token).catch(()=>({values:[]}));
  const initialized=existing?.values?.[0]?.[0]==="Field"&&existing?.values?.some((r:any[])=>r?.[0]==="table_uuid"&&String(r?.[1]??"")===String(task.table_uuid));
  if(!initialized){
    const metaRows=[['Field','Value'],['table_uuid',task.table_uuid],['table_did',task.table_did],['schema_name',task.schema_name],['table_name',task.table_name],['source_schema_sha256',task.source_schema_sha256],['gm_fingerprint_sha256',task.gm_fingerprint_sha256],['mirror_mode',task.mirror_mode],['capacity_mode',task.capacity_mode],['sensitivity_class',task.sensitivity_class],['estimated_rows',String(task.estimated_rows??0)],['estimated_bytes',String(task.estimated_bytes??0)],['column_count',String(task.column_count??0)],['estimated_cells',String(task.estimated_cells??0)],['snapshot_generation',snapshot],['shard_index',String(part)],['penta_language','ct.penta.lang.tabular.v1'],['penta_code',task.penta_code],['authority','D2 mirror only; no D3/provider/financial/credential authority'],['raw_secret_export','FORBIDDEN']];
    const cols=Array.isArray(task.columns)?task.columns:[];
    const schemaRows=[['ordinal','column','data_type','udt_name','nullable','default','sensitivity','transform','column_fingerprint_sha256'],...cols.map((c:any)=>[c.ordinal_position,c.column_name,c.data_type,c.udt_name,c.is_nullable,c.column_default??'',c.sensitivity_class,c.mirror_transform,c.column_fingerprint_sha256])];
    const penta=[['Penta Encoding','Value'],['TABLE',task.penta_code],['DID',task.table_did],['UUID',task.table_uuid],['GM_FINGERPRINT',task.gm_fingerprint_sha256],['SOURCE_FINGERPRINT',task.source_schema_sha256],['LANG','ct.penta.lang.tabular.v1'],['TABLE_GRAMMAR','PENTA:TBL/1|did=<table_did>|uuid=<table_uuid>|src=<schema.table>|fp=<gm_fingerprint>|mode=<mirror_mode>|state=<sync_state>'],['ROW_GRAMMAR','PENTA:ROW/1|did=<row_did>|uuid=<row_uuid>|table=<table_did>|fp=<row_fingerprint>|ord=<ordinal>'],['COLUMN_GRAMMAR','PENTA:COL/1|table=<table_did>|ord=<ordinal>|name=<column>|type=<type>|xform=<transform>|fp=<column_fingerprint>']];
    const hist=[['At','Event','Snapshot','Shard','Evidence'],[new Date().toISOString(),'PREPROVISION_BOOTSTRAPPED',snapshot,String(part),task.gm_fingerprint_sha256]];
    await sheetPut(id,"__PENTA_META__!A1",metaRows,token);
    await sheetPut(id,"SCHEMA!A1",schemaRows,token);
    await sheetPut(id,"PENTA!A1",penta,token);
    await sheetPut(id,"HISTORY!A1",hist,token);
  }
  const rbMeta=await sheetRead(id,"__PENTA_META__!A1:B20",token);
  const rbSchema=await sheetRead(id,`SCHEMA!A1:I${Math.max(2,(task.columns?.length??0)+1)}`,token);
  const rbPenta=await sheetRead(id,"PENTA!A1:B10",token);
  const rbHistory=await sheetRead(id,"HISTORY!A1:E2",token);
  const readbackSha=await sha(stable({meta:rbMeta.values??[],schema:rbSchema.values??[],penta:rbPenta.values??[],history:rbHistory.values??[]}));
  const after=await driveMeta(id,token);
  const receipt=await rpc("thrivebase_sheet_mirror_record_bootstrap_v1",{p_table_uuid:task.table_uuid,p_snapshot_generation:snapshot,p_shard_index:part,p_spreadsheet_id:id,p_provider_revision_id:String(after.version??''),p_provider_readback_sha256:readbackSha,p_evidence:{worker_version:VERSION,ownership_model:"user_owned_native_sheet",service_identity_writer:true,service_owned:false,owner_identity_sha256:ownerSha,tabs_verified:required,initialized_before:initialized,raw_secret_material:false}});
  return{ok:true,state:initialized?"ALREADY_BOOTSTRAPPED":"BOOTSTRAPPED",spreadsheet_id:id,provider_revision_id:String(after.version??''),provider_readback_sha256:readbackSha,owner_identity_sha256:ownerSha,receipt,raw_secret_material:false};
}

Deno.serve(async req=>{try{
  if(req.method!=="POST")return out(405,{ok:false,error:"POST_required"});
  const expected=await secret(TOKEN_SECRET),supplied=req.headers.get("x-penta-drive-token")??"";
  if(!supplied||supplied!==expected)return out(404,{ok:false});
  const body=await req.json().catch(()=>({}));
  const tableUuid=String(body.table_uuid??""),snapshot=String(body.snapshot_generation??""),spreadsheetId=String(body.spreadsheet_id??""),part=Math.max(1,Number(body.shard_index??1));
  if(!/^[0-9a-f-]{36}$/i.test(tableUuid)||!/^[0-9a-f-]{36}$/i.test(snapshot)||spreadsheetId.length<10)return out(400,{ok:false,state:"HOLD_INPUT_INVALID"});
  const task=await rpc("thrivebase_sheet_mirror_bootstrap_payload_v1",{p_table_uuid:tableUuid});
  if(!task||String(task.table_uuid??"")!==tableUuid)return out(404,{ok:false,state:"HOLD_TABLE_NOT_FOUND"});
  if(String(task.primary_spreadsheet_id??"")!==spreadsheetId&&part===1)return out(409,{ok:false,state:"HOLD_SPREADSHEET_BINDING_MISMATCH"});
  const {token,email}=await mint();
  const result=await bootstrap(task,spreadsheetId,snapshot,part,token);
  return out(result.ok?200:409,{...result,service_identity_sha256:await sha(email),worker_version:VERSION});
}catch(e){const msg=e instanceof Error?e.message:String(e);return out(500,{ok:false,error_class:e instanceof Error?e.name:"unknown",error_sha256:await sha(msg),raw_error_returned:false,raw_secret_material:false,worker_version:VERSION})}});
