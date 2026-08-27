import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE=Deno.env.get("SUPABASE_URL")??"";
const SERVICE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
const REPORT_VERSION="1.1.0";
const SERVER={name:"PentaMail",service:"ct.penta.mail.v1",version:"1.2.0",phase:3,production:true};

function json(body:unknown,status=200){return new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store","x-content-type-options":"nosniff"}})}
function headers(extra:Record<string,string>={}){return{apikey:SERVICE,authorization:`Bearer ${SERVICE}`,"content-type":"application/json",...extra}}
async function rpc(name:string,body:Record<string,unknown>={}){const r=await fetch(`${BASE}/rest/v1/rpc/${name}`,{method:"POST",headers:headers(),body:JSON.stringify(body)});const t=await r.text();let d:any=t;try{d=t?JSON.parse(t):null}catch{}if(!r.ok)throw new Error(`${name}:${r.status}:${typeof d==="string"?d:JSON.stringify(d)}`);return d}
async function rest(path:string,init:RequestInit={}){const r=await fetch(`${BASE}/rest/v1/${path}`,{...init,headers:{...headers(),...(init.headers??{})}});const t=await r.text();let d:any=t;try{d=t?JSON.parse(t):null}catch{}if(!r.ok)throw new Error(`REST:${path}:${r.status}:${typeof d==="string"?d:JSON.stringify(d)}`);return d}
async function safe<T=any>(label:string,fn:()=>Promise<T>):Promise<T|{state:"unavailable",error:string,label:string}>{try{return await fn()}catch(e){return{state:"unavailable",label,error:e instanceof Error?e.message:String(e)}}}
async function sha256(text:string){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return[...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,"0")).join("")}
function n(v:any,d=0){const x=Number(v);return Number.isFinite(x)?x:d}
function jstr(v:any){try{return JSON.stringify(v)}catch{return String(v)}}
function countBy(rows:any[],key:string){const out:Record<string,number>={};for(const r of rows??[]){const k=String(r?.[key]??"unknown");out[k]=(out[k]??0)+1}return out}
function fmtMap(x:any){return Object.entries(x??{}).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))).map(([k,v])=>`${k}=${v}`).join(", ")||"none"}
function lineList(items:any[],render:(x:any)=>string,limit=30){if(!items?.length)return"- none";const visible=items.slice(0,limit).map(x=>`- ${render(x)}`);if(items.length>limit)visible.push(`- ... ${items.length-limit} additional records retained in the machine snapshot`);return visible.join("\n")}
async function authorized(req:Request){const token=req.headers.get("x-penta-mail-token")??"";if(!token)return false;try{return await rpc("penta_state_report_authorize_v1",{p_token:token})===true}catch{return false}}
async function relay(action:string,payload:Record<string,unknown>={}){const r=await fetch(`${BASE}/functions/v1/mailgun-relay-control`,{method:"POST",headers:headers(),body:JSON.stringify({action,...payload})});const t=await r.text();let d:any={};try{d=t?JSON.parse(t):{}}catch{d={message:t.slice(0,400)}}return{ok:r.ok,http_status:r.status,body:d}}
async function sendMail(subject:string,text:string,to:string,triggerRef:string,requestKey:string){return relay("send_internal",{to,from_local:"pentamail",subject,text,trigger_ref:triggerRef,request_key:requestKey})}
async function ownerRecipient(){const value=await rpc("penta_mail_notification_recipient_v1");const recipient=String(value??"").trim().toLowerCase();if(!recipient)throw new Error("notification_recipient_unavailable");return recipient}

async function processOutbox(){let control:any=await rpc("penta_mail_provider_status_v1",{p_trigger_ref:null});let health:any=null;if(control?.route_state==="awaiting_provider_readback"){health=await relay("provider_health");control=await rpc("penta_mail_provider_status_v1",{p_trigger_ref:null})}if(!["closed","controlled_release"].includes(String(control?.route_state))){return{ok:true,service:"PentaMail",action:"process_outbox",processed:0,queue_state:"held",control,provider_health:health?.body??null,at:new Date().toISOString()}}const rows:any[]=await rpc("penta_mail_claim_outbox_v3",{p_limit:2});const results:any[]=[];for(const m of rows??[]){const delivery=await sendMail(String(m.subject),String(m.body_text),String(m.recipient),String(m.trigger_ref),`penta-outbox:${m.message_id}`);const ok=delivery.ok&&delivery.body?.ok===true;const providerCallMade=delivery.body?.provider_call_made===true;const providerStatus=delivery.body?.provider_status??null;const completion:any=await rpc("penta_mail_complete_outbox_v3",{p_message_id:m.message_id,p_lease_id:m.lease_id,p_ok:ok,p_provider_call_made:providerCallMade,p_provider_http_status:providerStatus,p_provider_message_id:delivery.body?.id??null,p_error:ok?null:jstr(delivery.body).slice(0,1000),p_retry_after_seconds:300});const reportId=String(m.metadata?.report_id??"");if(reportId){const reportPatch:any={delivery_state:completion?.state==="sent"?"sent":completion?.state==="failed"?"failed":"queued",provider_message_id:delivery.body?.id??null,provider_http_status:providerStatus,provider_response_message:delivery.body?.provider_reason_code??delivery.body?.error??null,sent_at:completion?.state==="sent"?new Date().toISOString():null,last_error:completion?.state==="sent"?null:jstr(delivery.body).slice(0,1000)};await rest(`penta_state_architecture_reports_v1?report_id=eq.${encodeURIComponent(reportId)}`,{method:"PATCH",headers:{Prefer:"return=minimal"},body:JSON.stringify(reportPatch)})}results.push({message_id:m.message_id,type:m.message_type,severity:m.severity,ok,provider_call_made:providerCallMade,provider_status:providerStatus,provider_message_id:delivery.body?.id??null,state:completion?.state,trigger_ref:m.trigger_ref});if(delivery.body?.provider_probation_detected===true)break}control=await rpc("penta_mail_provider_status_v1",{p_trigger_ref:null});return{ok:true,service:"PentaMail",action:"process_outbox",processed:results.length,queue_state:["closed","controlled_release"].includes(String(control?.route_state))?"controlled_release":"held",control,results,at:new Date().toISOString()}}

async function buildReport(){const owner=await ownerRecipient();const generatedAt=new Date();const generatedIso=generatedAt.toISOString();const previous:any[]=await rest(`penta_state_architecture_reports_v1?select=report_id,report_version,window_end,overall_state,severity,snapshot&order=window_end.desc&limit=1`);const prev=previous?.[0]??null;const since=prev?.window_end??new Date(Date.now()-3600_000).toISOString();
 const [self,phase,help,privateSubs,ofac,pentaPr,systems,providerQueue,factoryStatuses,systemChanges,providerChanges,factoryChanges,releaseChanges,releases,incidents]=await Promise.all([
  safe("penta_self",()=>rpc("penta_self_status_v1")),
  safe("phase_model",()=>rpc("penta_phase_model_status_v1")),
  safe("penta_help",()=>rpc("penta_help_report_snapshot_v1")),
  safe("private_subsystems",()=>rpc("penta_state_report_private_subsystems_v1")),
  safe("ofac",()=>rpc("penta_ofac_status_v1")),
  safe("penta_pr",()=>rpc("penta_state_report_penta_pr_status_v1")),
  safe("systems",()=>rest(`penta_system_registry?select=system_key,canonical_name,category,maturity,version,runtime_ref,authority_boundary,risk_ceiling,metadata,last_verified_at,updated_at&order=canonical_name.asc`)),
  safe("provider_queue",()=>rest(`ct_factory_adapter_certification_queue?select=surface_id,provider_system,candidate_adapter_key,runtime_adapter_key,certification_state,missing_requirements,priority_score,last_checked_at,certified_at,updated_at&order=provider_system.asc,surface_id.asc`)),
  safe("factory_statuses",()=>rest(`ct_factory_build_requests?select=status`)),
  safe("system_changes",()=>rest(`penta_system_registry?select=system_key,canonical_name,maturity,version,updated_at&updated_at=gte.${encodeURIComponent(since)}&order=updated_at.asc`)),
  safe("provider_changes",()=>rest(`ct_factory_adapter_certification_queue?select=surface_id,provider_system,certification_state,missing_requirements,updated_at&updated_at=gte.${encodeURIComponent(since)}&order=updated_at.asc`)),
  safe("factory_changes",()=>rest(`ct_factory_build_requests?select=id,request_key,source_type,source_ref,objective,status,governance_class,updated_at&updated_at=gte.${encodeURIComponent(since)}&order=updated_at.asc&limit=200`)),
  safe("release_changes",()=>rest(`ct_factory_release_packages?select=id,release_version,channel,status,package_uri,sha256,implemented_at,created_at&created_at=gte.${encodeURIComponent(since)}&order=created_at.asc&limit=200`)),
  safe("releases",()=>rest(`penta_report_release_state_v1?select=*&order=published_at.desc`)),
  safe("incidents",()=>rest(`penta_mail_incident_state_v1?select=condition_key,severity,active,first_seen_at,last_seen_at,last_notified_at,fingerprint,details&active=eq.true&order=severity.asc,condition_key.asc`))
 ]);
 const selfHealth=(self as any)?.health??{};const latestCycle=(self as any)?.latest_cycle??{};const latestEvidence=latestCycle?.evidence??{};const helpSnap=help as any;const subs=privateSubs as any;const sysRows=Array.isArray(systems)?systems:[];const queueRows=Array.isArray(providerQueue)?providerQueue:[];const factoryRows=Array.isArray(factoryStatuses)?factoryStatuses:[];const nonProd=sysRows.filter((x:any)=>x.maturity!=="production");const systemMaturity=countBy(sysRows,"maturity");const providerStates=countBy(queueRows,"certification_state");const factoryCounts=countBy(factoryRows,"status");const failedCert=n(selfHealth.failed_certification_tasks);const blockedCert=n(selfHealth.blocked_certification_tasks);const schedulerGaps=n(selfHealth.scheduler_gaps);const unrecovered=n(selfHealth.unrecovered_required_job_failures_30m);const authorityManufacture=selfHealth.authority_manufacture===true;const production=selfHealth.production===true;const green=subs?.pentagreen??{};const nurture=subs?.penta_nurture??latestEvidence?.nurture??{};const diagnostic=latestEvidence?.legacy_heal?.diagnostic?.diagnostic_state??latestEvidence?.legacy_heal?.diagnostic?.cron?.state??null;const helpReq=helpSnap?.request_counts??{};const waitingHuman=n(helpReq.waiting_human);const waitingExternal=n(helpReq.waiting_external);const providerRunnable=n(helpSnap?.provider_job_counts?.queued)+n(helpSnap?.provider_job_counts?.claimed);const activeIncidents=Array.isArray(incidents)?incidents:[];
 const critical=!production||schedulerGaps>0||unrecovered>0||authorityManufacture||activeIncidents.some((x:any)=>x.severity==="CRITICAL");const actualFailure=failedCert>0||green?.run_state==="failed"||String(diagnostic??"").toUpperCase()==="CRITICAL";const governedHolds=blockedCert>0||nonProd.length>0||waitingHuman>0||waitingExternal>0||providerRunnable>0||green?.economic_verdict==="HOLD"||activeIncidents.length>0;
 const overall=critical?"CRITICAL":actualFailure?"PRODUCTION_DEGRADED_EXECUTION":governedHolds?"PRODUCTION_HEALTHY_GOVERNED_HOLDS":"PRODUCTION_HEALTHY";const severity=critical?"CRITICAL":actualFailure?"HIGH":"INFO";
 const changes={since,baseline:!prev,system_registry_changes:Array.isArray(systemChanges)?systemChanges:[],provider_certification_changes:Array.isArray(providerChanges)?providerChanges:[],factory_request_changes:Array.isArray(factoryChanges)?factoryChanges:[],release_changes:Array.isArray(releaseChanges)?releaseChanges:[],current_state_changed_from_previous:prev?prev.overall_state!==overall:true};
 const snapshot={contract:"ct.penta.state-architecture-report.v1.1",report_version:REPORT_VERSION,generated_at:generatedIso,window_start:since,window_end:generatedIso,overall_state:overall,severity,phase_model:phase,penta_self:self,penta_help:helpSnap,penta_systems:{total:sysRows.length,by_maturity:systemMaturity,systems:sysRows,nonproduction:nonProd},provider_certification:{counts:providerStates,queue:queueRows,current_failed_tasks:failedCert,current_blocked_tasks:blockedCert,history_projection:selfHealth.certification_task_projection??null,historical_failed_attempts:selfHealth.historical_failed_certification_attempts??null},factory:{request_counts:factoryCounts,runnable_provider_jobs:providerRunnable,provider_job_counts:helpSnap?.provider_job_counts??{}},subsystems:subs,ofac,penta_pr:pentaPr,releases,active_incidents:activeIncidents,changes,guardrails:{d3_human_reserved:selfHealth.d3_human_reserved!==false,authority_manufacture:authorityManufacture,universal_delete:false,raw_secret_exposure:false,websites_deferred:true,source_of_truth:"CrownThrive OS / ThriveBase evidence",self_help_rule:"No generic idle WAITING: test, build, credential-reconcile, route, human-reserve, retire, or resolve."}};
 const prodNames=sysRows.filter((x:any)=>x.maturity==="production").map((x:any)=>x.canonical_name);const nonProdLines=nonProd.map((x:any)=>`${x.canonical_name} ${x.version} — ${x.metadata?.operational_state??x.maturity}; route=${x.metadata?.workflow??x.runtime_ref??"n/a"}; evidence pending=${x.metadata?.production_promotion_requires??"production receipt"}`);const helpOpen=Array.isArray(helpSnap?.open_requests)?helpSnap.open_requests:[];const queueLines=queueRows.map((q:any)=>`${q.provider_system} / ${q.surface_id}: ${q.certification_state}${Array.isArray(q.missing_requirements)&&q.missing_requirements.length?` — needs ${q.missing_requirements.join(", ")}`:""}`);const releaseRows=Array.isArray(releases)?releases:[];const greenBlockers=Array.isArray(green?.blockers)?green.blockers:[];const media=Array.isArray(subs?.penta_media)?subs.penta_media[0]:subs?.penta_media;const gen=Array.isArray(subs?.penta_generation)?subs.penta_generation[0]:subs?.penta_generation;
 const subject=`State Architecture Report v${REPORT_VERSION} — ${overall} — ${generatedAt.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})}`;
 const text=[
  `CROWNTHRIVE — STATE ARCHITECTURE REPORT`,
  `Report version: ${REPORT_VERSION}`,
  `Generated: ${generatedAt.toLocaleString("en-US",{timeZone:"America/New_York",dateStyle:"full",timeStyle:"long"})}`,
  `Window: ${since} → ${generatedIso}`,
  `Classification: ${severity} / ${overall}`,
  `Canonical evidence: CrownThrive OS + ThriveBase + CHLOM/provider readback. Websites remain downstream/deferred.`,
  ``,
  `1. EXECUTIVE STATE`,
  `Phase: ${(phase as any)?.current_name??"Phase 3 — Execute"}`,
  `Core production: ${production}`,
  `PentaSELF latest cycle: ${latestCycle?.state??(self as any)?.state??"unknown"}`,
  `PentaFabric: ${selfHealth.fabric_state??"unknown"}; PentaMesh: ${selfHealth.mesh_state??"unknown"}`,
  `Required schedulers: ${n(selfHealth.healthy_required_jobs)}/${n(selfHealth.required_jobs)}; gaps=${schedulerGaps}; unrecovered failures 30m=${unrecovered}`,
  `Database diagnostic: ${diagnostic??"unknown"}`,
  `Authority manufacture: ${authorityManufacture}; D3 human reserved: ${selfHealth.d3_human_reserved!==false}`,
  `PENTA systems: ${sysRows.length} (${fmtMap(systemMaturity)})`,
  `Current certification tasks: failed=${failedCert}, blocked/expected-hold=${blockedCert}`,
  ``,
  `2. PENTAHELP METAPROTOCOL`,
  `PentaHelper: ${helpSnap?.helper?.state??"unknown"}; PentaLiaison: ${helpSnap?.liaison?.state??"unknown"}`,
  `All Pentas can ask: ${helpSnap?.invariants?.all_pentas_can_ask===true}; generic idle WAIT prohibited: ${helpSnap?.invariants?.generic_idle_wait_prohibited===true}`,
  `Help requests: ${fmtMap(helpReq)}`,
  `Active typed classes: ${fmtMap(helpSnap?.active_class_counts)}`,
  `Liaison threads: ${fmtMap(helpSnap?.liaison_counts)}`,
  `TTL/TTYL: enabled; open routes=${helpSnap?.liaison?.open_threads??0}`,
  `Latest signed Help receipt: ${helpSnap?.helper?.latest_receipt?.evidence_sha256??"none"}`,
  `Separation of duties: ${helpSnap?.invariants?.separation_of_duties??"PentaHelper evidence / PentaBuild software / PentaCertify independent evaluation"}`,
  ``,
  `Top active help/dependency routes:`,
  lineList(helpOpen,(r:any)=>`${r.risk_class} ${r.requester_system_key} — ${r.state}/${r.resolution_mode}: ${r.blocker_code}; destination=${r.destination_ref??"internal next action"}; TTL=${r.expires_at}; TTYL=${r.ttyl_at??r.liaison_due_at}`,28),
  ``,
  `3. PENTA MATURITY`,
  `Production (${prodNames.length}): ${prodNames.join(", ")||"none"}`,
  `Non-production (${nonProd.length}):`,
  nonProdLines.length?nonProdLines.map((x:string)=>`- ${x}`).join("\n"):"- none",
  ``,
  `4. PROVIDER CERTIFICATION`,
  `Provider surfaces: ${queueRows.length}; states: ${fmtMap(providerStates)}`,
  `Current failures=${failedCert}; current blocked/expected holds=${blockedCert}; historical failed attempts=${selfHealth.historical_failed_certification_attempts??"n/a"}`,
  lineList(queueLines,(x:any)=>String(x),30),
  ``,
  `5. FACTORY / SOURCE CUSTODY`,
  `Factory request history: ${fmtMap(factoryCounts)}`,
  `Provider jobs: ${fmtMap(helpSnap?.provider_job_counts)}`,
  `Runnable provider jobs: ${providerRunnable}`,
  `Provider route is actively owned by PentaHelper/PentaLiaison; historical/deferred/superseded jobs remain preserved as HOLD evidence.`,
  ``,
  `6. PENTAGREEN / ECONOMIC ACTIVATION`,
  `Run state=${green?.run_state??"unknown"}; error=${green?.error_code??"none"}; economic verdict=${green?.economic_verdict??"unknown"}; publication=${green?.publication_decision??"unknown"}; count=${green?.publication_count??0}`,
  `Blockers: ${greenBlockers.length?greenBlockers.map((b:any)=>`${b.dimension}:${(b.reason_codes??[]).join("|")}`).join("; "):"none"}`,
  `PentaNurture: ${nurture?.state??"unknown"}; checked=${nurture?.summary?.checked??nurture?.checked??"n/a"}; healthy=${nurture?.summary?.healthy??nurture?.healthy??"n/a"}; watch=${nurture?.summary?.watch??nurture?.watch??"n/a"}; blocked=${nurture?.summary?.blocked??nurture?.blocked??"n/a"}; remediate=${nurture?.summary?.remediate??nurture?.remediate??"n/a"}`,
  ``,
  `7. OTHER SUBSYSTEMS`,
  `PentaOFAC: ${(ofac as any)?.state??"unknown"}; last_error=${(ofac as any)?.last_error??"none"}; last_success=${(ofac as any)?.last_success_at??"n/a"}`,
  `PentaMedia: ${media?.state??"unknown"}; assets=${media?.asset_count??"n/a"}; public=${media?.public_asset_count??"n/a"}; monetization-bound=${media?.monetization_bound_count??"n/a"}`,
  `PentaGeneration: ${gen?.status??"unknown"}; horizon=${gen?.horizon_generations??"n/a"}`,
  `PentaFederation: ${Array.isArray(subs?.penta_federation)?subs.penta_federation.map((x:any)=>`${x.name}:${x.status}`).join(", "):"n/a"}`,
  `PentaStudios provider bindings: ${subs?.penta_studios_provider_binding_count??"n/a"}; PentaSuite active leases: ${subs?.penta_suite_lease_count??"n/a"}`,
  `PentaPR: open_tracked=${(pentaPr as any)?.open_tracked??"n/a"}; overdue=${(pentaPr as any)?.overdue??"n/a"}; terminal=${(pentaPr as any)?.terminal??"n/a"}`,
  ``,
  `8. RELEASES`,
  lineList(releaseRows,(r:any)=>`${r.repo??r.repository??"repo"}: ${r.tag??r.version??"n/a"} — ${r.name??r.state??""} — ${r.published_at??""}`,10),
  ``,
  `9. CHANGES SINCE PRIOR REPORT`,
  `System registry changes: ${Array.isArray(systemChanges)?systemChanges.length:0}`,
  `Provider certification changes: ${Array.isArray(providerChanges)?providerChanges.length:0}`,
  `Factory request changes: ${Array.isArray(factoryChanges)?factoryChanges.length:0}`,
  `Release/package changes: ${Array.isArray(releaseChanges)?releaseChanges.length:0}`,
  `Overall state changed from previous: ${changes.current_state_changed_from_previous}`,
  ``,
  `10. ACTIVE INCIDENTS / OWNER ATTENTION`,
  activeIncidents.length?lineList(activeIncidents,(x:any)=>`${x.severity} ${x.condition_key}: ${jstr(x.details)}`,20):"- none",
  `Human-reserved Help routes: ${waitingHuman}; external/provider routes: ${waitingExternal}`,
  ``,
  `11. EVIDENCE`,
  `The full machine snapshot, complete provider queue, Help routes, change arrays, release data and subsystem evidence are retained in ThriveBase under this report ID.`,
  `Raw secrets are never included. PentaMail reports state; it does not manufacture authority, certification, money movement or D3 approval.`
 ].join("\n");
 const emailSha=await sha256(text);const insert:any[]=await rest(`penta_state_architecture_reports_v1`,{method:"POST",headers:{Prefer:"return=representation"},body:JSON.stringify({report_version:REPORT_VERSION,phase:3,window_start:since,window_end:generatedIso,overall_state:overall,severity,recipient:owner,snapshot,change_summary:changes,email_subject:subject,email_text:text,email_sha256:emailSha,delivery_state:"pending"})});const report=insert?.[0];if(!report?.report_id)throw new Error("report_insert_failed");const triggerRef="scheduled:penta-mail-state-architecture-report-v1";const outboxId=await rpc("penta_mail_enqueue_v1",{p_message_type:"state_architecture_report",p_severity:severity,p_subject:subject,p_body_text:text,p_dedupe_key:`state-architecture-report:${report.report_id}`,p_metadata:{report_id:report.report_id,trigger_ref:triggerRef,report_version:REPORT_VERSION},p_recipient:owner});const patch={delivery_state:"queued",provider_message_id:null,provider_http_status:null,provider_response_message:"governed_outbox",sent_at:null,last_error:null};await rest(`penta_state_architecture_reports_v1?report_id=eq.${report.report_id}`,{method:"PATCH",headers:{Prefer:"return=minimal"},body:JSON.stringify(patch)});return{ok:true,service:"PentaMail",report:"State Architecture Report",report_version:REPORT_VERSION,report_id:report.report_id,overall_state:overall,severity,generated_at:generatedIso,window_start:since,email_sha256:emailSha,email_bytes:new TextEncoder().encode(text).length,delivery:{state:"queued",outbox_message_id:outboxId,provider:"Mailgun",domain:"relay.crownthrive.com",recipient_ref:"founder_primary",trigger_ref:triggerRef,raw_secret_exposed:false},summary:{penta_systems:sysRows.length,maturity:systemMaturity,schedulers:`${n(selfHealth.healthy_required_jobs)}/${n(selfHealth.required_jobs)}`,scheduler_gaps:schedulerGaps,failed_certification_tasks:failedCert,blocked_certification_tasks:blockedCert,provider_queue:providerStates,open_help_requests:helpSnap?.helper?.open_requests??0,help_request_states:helpReq,open_liaison_threads:helpSnap?.liaison?.open_threads??0,runnable_provider_jobs:providerRunnable,nonproduction_systems:nonProd.map((x:any)=>x.canonical_name),changes:{systems:Array.isArray(systemChanges)?systemChanges.length:0,providers:Array.isArray(providerChanges)?providerChanges.length:0,factory:Array.isArray(factoryChanges)?factoryChanges.length:0,releases:Array.isArray(releaseChanges)?releaseChanges.length:0}}}}

Deno.serve(async(req:Request)=>{try{if(req.method!=="POST")return json({ok:false,error:"POST_required",server:SERVER},405);if(!(await authorized(req)))return json({ok:false,error:"dispatch_token_required",server:SERVER},403);const body=await req.json().catch(()=>({}));const action=String(body.action??"process_outbox");if(action==="health"||action==="status"){const control=await rpc("penta_mail_provider_status_v1",{p_trigger_ref:null});return json({ok:true,server:{...SERVER,version:"1.2.0"},report_version:REPORT_VERSION,mail_provider:"Mailgun",provider_control:control,help_metaprotocol:true,raw_secret_exposed:false})}if(action==="process_outbox")return json(await processOutbox());if(action==="state_architecture_report")return json(await buildReport());return json({ok:false,error:"unsupported_action",allowed:["health","status","process_outbox","state_architecture_report"],server:SERVER},400)}catch(e){return json({ok:false,service:"PentaMail",error:e instanceof Error?e.message:String(e),raw_secret_exposed:false},500)}});
