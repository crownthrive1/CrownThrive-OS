import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.3";

const PROJECT_URL = Deno.env.get("SUPABASE_URL") ?? "https://tzajnzshmtzjenqulehq.supabase.co";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
let client: ReturnType<typeof postgres> | null = null;
function db(){ const url=Deno.env.get("SUPABASE_DB_URL")??""; if(!url) throw new Error("db_url_missing"); client ??= postgres(url,{max:2,idle_timeout:10,prepare:false}); return client; }
function j(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}})}
async function sha256(s:string){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s));return [...new Uint8Array(d)].map(b=>b.toString(16).padStart(2,"0")).join("");}
async function authorized(req:Request){
  const token=req.headers.get("x-ct-os-token")??"";
  if(!token) return false;
  const h=await sha256(token);
  const rows=await db()<Array<{token_sha256:string;active:boolean;expires_at:string|null}>>`select token_sha256,active,expires_at from os_v2.runtime_tokens where token_name='ct_os_v2_runtime_token' limit 1`;
  const r=rows[0];
  return !!r && r.active && (!r.expires_at || Date.parse(r.expires_at)>Date.now()) && r.token_sha256===h;
}
async function recordReceipt(taskId:string,kind:string,state:string,evidence:unknown,errorCode:string|null=null){
  const payload=JSON.stringify(evidence??{}); const digest=await sha256(`${taskId}|${kind}|${state}|${payload}`);
  await db()`insert into os_v2.run_receipts(task_id,task_kind,result_state,evidence,evidence_sha256,error_code) values(${taskId}::uuid,${kind},${state},${db().json(evidence as any)},${digest},${errorCode})`;
}
async function notify(subject:string,text:string,severity="info"){
  const sql=db();
  const rows=await sql<Array<{notification_id:string}>>`insert into os_v2.notifications(channel,recipient,subject,body,severity,state) values('email','jones.usmc.kj@gmail.com',${subject},${text},${severity},'queued') returning notification_id::text`;
  return rows[0]?.notification_id;
}
async function sendQueuedNotifications(limit=10){
  const sql=db();
  const rows=await sql<Array<{notification_id:string;recipient:string;subject:string;body:string;severity:string}>>`with c as (
    select notification_id from os_v2.notifications where state='queued' and available_at<=now() order by created_at limit ${limit} for update skip locked
  ) update os_v2.notifications n set state='sending',attempt_count=attempt_count+1,last_attempt_at=now() from c where n.notification_id=c.notification_id returning n.notification_id::text,n.recipient,n.subject,n.body,n.severity`;
  const out=[];
  for(const n of rows){
    try{
      const r=await fetch(`${PROJECT_URL}/functions/v1/mailgun-relay-control`,{method:'POST',headers:{authorization:`Bearer ${SERVICE_ROLE}`,'content-type':'application/json'},body:JSON.stringify({action:'send_internal',to:n.recipient,from_local:'notifications',subject:n.subject,text:n.body})});
      const t=await r.text(); let p:any={}; try{p=JSON.parse(t)}catch{p={raw:t.slice(0,500)}};
      await sql`update os_v2.notifications set state=${r.ok?'sent':'failed'},sent_at=${r.ok?new Date().toISOString():null},last_error=${r.ok?null:`mailgun_${r.status}`},provider_receipt=${sql.json(p)} where notification_id=${n.notification_id}::uuid`;
      out.push({id:n.notification_id,status:r.status,ok:r.ok});
    }catch(e){
      await sql`update os_v2.notifications set state='failed',last_error=${e instanceof Error?e.message:'send_error'} where notification_id=${n.notification_id}::uuid`;
      out.push({id:n.notification_id,ok:false});
    }
  }
  return out;
}
async function handleTask(task:any){
  const sql=db();
  const kind=String(task.task_kind);
  if(kind==='system_health'){
    const r=await sql`select now() as observed_at,(select count(*) from cron.job where active) as active_cron_jobs,(select count(*) from integration_control.services) as registered_services,(select count(*) from chlom_runtime.modules) as modules,(select count(*) from integration_control.thriveevergreen_mesh_work_queue_v1 where work_state in ('queued','running')) as open_mesh_work`;
    return {state:'pass',evidence:r[0]};
  }
  if(kind==='commerce_mesh'){
    const r=await sql`select integration_control.thriveevergreen_commerce_mesh_cycle_v1() as result`;
    return {state:'pass',evidence:r[0]?.result??{}};
  }
  if(kind==='scheduler_reconcile'){
    const r=await sql`select jobid,jobname,schedule,active from cron.job where jobname like 'ct-%' or jobname like 'crownthrive%' or jobname like 'chlom%' order by jobid`;
    const critical=['ct-crownthrive-os-v2-dispatch','ct-crownthrive-os-v2-watchdog'];
    const criticalState=critical.map(name=>({name,active:r.some((x:any)=>x.jobname===name&&x.active)}));
    const missing=criticalState.filter(x=>!x.active);
    if(missing.length) await notify('CrownThrive OS V2 scheduler fault',`OS V2 detected inactive critical scheduler(s): ${missing.map(x=>x.name).join(', ')}. Runtime remained fail-closed and did not manufacture recovery authority.`,'critical');
    return {state:missing.length?'hold':'pass',evidence:{critical:criticalState,observed_jobs:r.length}};
  }
  if(kind==='self_repair'){
    const stale=await sql`update os_v2.tasks set state='queued',claimed_at=null,claimed_by=null,available_at=now(),last_error='recovered_stale_lease' where state='running' and claimed_at<now()-interval '15 minutes' and risk_class in ('D0','D1','D2') returning task_id::text`;
    return {state:'pass',evidence:{stale_requeued:stale.length}};
  }
  if(kind==='notification_flush'){
    const sent=await sendQueuedNotifications(10); return {state:'pass',evidence:{processed:sent.length,results:sent}};
  }
  if(kind==='knowledge_projection'){
    const r=await sql`select (select count(*) from chlom_runtime.dail_events) as dail_events,(select count(*) from chlom_runtime.project_portfolio_projects) as projects,(select count(*) from integration_control.site_mesh_bindings) as site_bindings`;
    return {state:'pass',evidence:r[0]};
  }
  return {state:'hold',evidence:{reason:'unsupported_task_kind',task_kind:kind}};
}
async function processTasks(limit=12){
  const sql=db();
  const claimed=await sql<Array<any>>`with c as (
    select task_id from os_v2.tasks where state='queued' and available_at<=now() order by priority desc,created_at limit ${limit} for update skip locked
  ) update os_v2.tasks t set state='running',claimed_at=now(),claimed_by='ct.os.v2.runtime',attempt_count=attempt_count+1 from c where t.task_id=c.task_id returning t.*`;
  const results=[];
  for(const task of claimed){
    try{
      if(task.risk_class==='D3'){
        await sql`update os_v2.tasks set state='hold',completed_at=now(),last_error='D3_HUMAN_RESERVED' where task_id=${task.task_id}`;
        await recordReceipt(task.task_id,task.task_kind,'hold',{reason:'D3_HUMAN_RESERVED'},'D3_HUMAN_RESERVED');
        results.push({task_id:task.task_id,state:'hold'}); continue;
      }
      const rr=await handleTask(task);
      await sql`update os_v2.tasks set state=${rr.state==='pass'?'completed':rr.state},completed_at=now(),result=${sql.json(rr.evidence)},last_error=${rr.state==='pass'?null:'TASK_HOLD'} where task_id=${task.task_id}`;
      await recordReceipt(task.task_id,task.task_kind,rr.state,rr.evidence,rr.state==='pass'?null:'TASK_HOLD');
      results.push({task_id:task.task_id,kind:task.task_kind,state:rr.state});
    }catch(e){
      const msg=e instanceof Error?e.message:'task_error';
      const terminal=Number(task.attempt_count)>=Number(task.max_attempts);
      await sql`update os_v2.tasks set state=${terminal?'failed':'queued'},available_at=now()+interval '5 minutes',completed_at=${terminal?new Date().toISOString():null},last_error=${msg} where task_id=${task.task_id}`;
      await recordReceipt(task.task_id,task.task_kind,'failed',{error:msg,terminal},msg);
      if(terminal) await notify('CrownThrive OS V2 task failure',`Task ${task.task_kind} (${task.task_id}) exhausted retries. Error: ${msg}`,'critical');
      results.push({task_id:task.task_id,state:terminal?'failed':'retry',error:msg});
    }
  }
  return results;
}
Deno.serve(async(req:Request)=>{
  try{
    if(req.method==='GET'){
      const rows=await db()`select version,state,last_heartbeat_at,release_state from os_v2.runtime_state where singleton=true`;
      return j({service:'crownthrive-os-v2-runtime',...rows[0]});
    }
    if(req.method!=='POST') return j({error:'method_not_allowed'},405);
    if(!(await authorized(req))) return j({error:'runtime_auth_required'},403);
    const body=await req.json().catch(()=>({})) as any;
    const action=String(body.action??'tick');
    if(action==='tick'){
      const processed=await processTasks(Math.min(25,Math.max(1,Number(body.limit??12))));
      await db()`update os_v2.runtime_state set state='hot',last_heartbeat_at=now(),last_tick_at=now(),updated_at=now() where singleton=true`;
      return j({service:'crownthrive-os-v2-runtime',version:'2.0.0',state:'hot',processed});
    }
    if(action==='flush_notifications') return j({state:'complete',results:await sendQueuedNotifications(20)});
    return j({error:'unsupported_action'},400);
  }catch(e){return j({error:'runtime_error',detail:e instanceof Error?e.message:'unknown'},500)}
});
