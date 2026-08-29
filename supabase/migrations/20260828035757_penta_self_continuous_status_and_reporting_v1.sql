create or replace function penta_self.continuous_status_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','penta_self'
as $$
declare v_states jsonb; v_priorities jsonb; v_categories jsonb; v_scans jsonb; v_oldest timestamptz; v_open int; v_due int; v_resolved_24h int;
begin
  select coalesce(jsonb_object_agg(state,cnt),'{}'::jsonb) into v_states from (select state,count(*) cnt from penta_self.problem_ledger_v1 group by state)s;
  select coalesce(jsonb_object_agg(priority,cnt),'{}'::jsonb) into v_priorities from (select priority,count(*) cnt from penta_self.problem_ledger_v1 where state not in ('resolved','false_positive','retired') group by priority)s;
  select coalesce(jsonb_object_agg(category,cnt),'{}'::jsonb) into v_categories from (select category,count(*) cnt from penta_self.problem_ledger_v1 where state not in ('resolved','false_positive','retired') group by category)s;
  select count(*),count(*) filter(where next_attempt_at<=now()),min(first_seen_at) into v_open,v_due,v_oldest from penta_self.problem_ledger_v1 where state not in ('resolved','false_positive','retired');
  select count(*) into v_resolved_24h from penta_self.problem_ledger_v1 where state='resolved' and resolved_at>=now()-interval '24 hours';
  select coalesce(jsonb_agg(jsonb_build_object('source',source_name,'last_occurred_at',last_occurred_at,'last_uuid',last_uuid,'last_bigint',last_bigint,'messages_scanned',total_messages_scanned,'problem_candidates',total_problem_candidates,'updated_at',updated_at) order by source_name),'[]'::jsonb)
    into v_scans from penta_self.message_scan_state_v1;
  return jsonb_build_object('service','ct.penta.self.continuous-healing.v1','state',case when coalesce((v_priorities->>'P0')::int,0)>0 then 'DEGRADED_P0' when v_open>0 then 'HEALING' else 'HEALTHY' end,
    'open_problems',v_open,'due_now',v_due,'oldest_opened_at',v_oldest,'resolved_24h',v_resolved_24h,'states',v_states,'priorities',v_priorities,'categories',v_categories,
    'message_scans',v_scans,'persistent_ownership',true,'retry_until_verified',true,'d3_human_reserved',true,'authority_manufactured',false,
    'credential_manufactured',false,'uncertified_provider_write',false,'money_movement_without_authority',false,'generated_at',now());
end $$;

create or replace function penta_self.continuous_healing_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_self','public'
as $$
declare v_cycle uuid:=gen_random_uuid(); v_started timestamptz:=clock_timestamp(); v_intake jsonb; v_heal jsonb; v_status jsonb; v_state text;
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.self.continuous-healing.v1',0)) then
    return jsonb_build_object('service','ct.penta.self.continuous-healing.v1','state','SKIPPED_LOCKED','at',now());
  end if;
  insert into penta_self.cycle_receipts_v1(cycle_id,state,started_at,summary,evidence) values(v_cycle,'running',v_started,'{}'::jsonb,jsonb_build_object('cycle_kind','continuous_healing'));
  begin v_intake:=penta_self.message_intake_v1(v_cycle,500); exception when others then v_intake:=jsonb_build_object('state','failed','sqlstate',sqlstate,'error',left(sqlerrm,500)); end;
  begin v_heal:=penta_self.problem_heal_cycle_v1(v_cycle,25); exception when others then v_heal:=jsonb_build_object('state','failed','sqlstate',sqlstate,'error',left(sqlerrm,500)); end;
  v_status:=penta_self.continuous_status_v1();
  v_state:=case when v_intake->>'state'='failed' or v_heal->>'state'='failed' then 'failed' when coalesce((v_status->>'open_problems')::int,0)>0 then 'degraded' else 'healthy' end;
  update penta_self.cycle_receipts_v1 set state=v_state,completed_at=clock_timestamp(),summary=jsonb_build_object('state',v_state,'continuous_status',v_status),
    evidence=jsonb_build_object('cycle_kind','continuous_healing','intake',v_intake,'healing',v_heal,'persistent_ownership',true,'d3_human_reserved',true,'authority_manufactured',false)
  where cycle_id=v_cycle;
  update public.penta_system_registry set last_verified_at=now(),updated_at=now(),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('continuous_healing_cycle_id',v_cycle,'continuous_healing_state',v_state,'continuous_healing_at',now())
  where system_key='penta.self';
  return jsonb_build_object('service','ct.penta.self.continuous-healing.v1','cycle_id',v_cycle,'state',upper(v_state),'intake',v_intake,'healing',v_heal,'status',v_status,
    'persistent_ownership',true,'retry_until_verified',true,'d3_human_reserved',true,'authority_manufactured',false,'at',now());
exception when others then
  update penta_self.cycle_receipts_v1 set state='failed',completed_at=clock_timestamp(),summary=jsonb_build_object('error',left(sqlerrm,500)),evidence=jsonb_build_object('cycle_kind','continuous_healing','sqlstate',sqlstate) where cycle_id=v_cycle;
  return jsonb_build_object('service','ct.penta.self.continuous-healing.v1','cycle_id',v_cycle,'state','FAILED','sqlstate',sqlstate,'error',left(sqlerrm,500),'persistent_retry',true,'at',now());
end $$;

create or replace function public.penta_self_continuous_healing_tick_v1()
returns jsonb
language sql
security definer
set search_path='pg_catalog','penta_self'
as $$ select penta_self.continuous_healing_tick_v1(); $$;

create or replace function public.penta_self_continuous_status_v1()
returns jsonb
language sql
stable
security definer
set search_path='pg_catalog','penta_self'
as $$ select penta_self.continuous_status_v1(); $$;

create or replace function public.penta_self_status_v1()
returns jsonb
language sql
stable
security definer
set search_path='pg_catalog','penta_self'
as $$ select penta_self.status_v1()||jsonb_build_object('continuous_healing',penta_self.continuous_status_v1()); $$;

create or replace function public.penta_self_hourly_report_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','penta_self','integration_control','extensions'
as $$
declare
  v_recipient text;
  v_status jsonb;
  v_open int;
  v_p0 int;
  v_p1 int;
  v_resolved int;
  v_attempts int;
  v_messages bigint;
  v_problem_candidates bigint;
  v_top text;
  v_subject text;
  v_body text;
  v_message uuid;
  v_report_id uuid;
  v_report jsonb;
  v_sha text;
  v_severity text;
begin
  select recipient into v_recipient from integration_control.penta_hourly_update_policy_v1 where enabled order by effective_at desc,created_at desc limit 1;
  v_recipient:=coalesce(v_recipient,'jones.usmc.kj@gmail.com');
  v_status:=penta_self.continuous_status_v1();
  v_open:=coalesce((v_status->>'open_problems')::int,0);
  v_p0:=coalesce((v_status->'priorities'->>'P0')::int,0);
  v_p1:=coalesce((v_status->'priorities'->>'P1')::int,0);
  select count(*) into v_resolved from penta_self.problem_ledger_v1 where state='resolved' and resolved_at>=now()-interval '1 hour';
  select count(*) into v_attempts from penta_self.problem_attempts_v1 where completed_at>=now()-interval '1 hour';
  select coalesce(sum(message_count),0),coalesce(sum(problem_count),0) into v_messages,v_problem_candidates from penta_self.message_scan_receipts_v1 where created_at>=now()-interval '1 hour';
  select string_agg(format('%s | %s | %s | owner=%s | attempts=%s | next=%s',priority,state,left(title,110),left(owner_penta,80),attempt_count,to_char(next_attempt_at at time zone 'America/New_York','HH24:MI:SS')),E'\n' order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,first_seen_at)
    into v_top from (select * from penta_self.problem_ledger_v1 where state not in ('resolved','false_positive','retired') order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,first_seen_at limit 20)x;
  v_severity:=case when v_p0>0 then 'CRITICAL' when v_open>0 then 'WARNING' else 'INFO' end;
  v_subject:=format('[PentaSELF Hourly Healing] %s open | %s resolved | %s messages inspected',v_open,v_resolved,v_messages);
  v_body:=format(E'CROWNTHRIVE OS — PENTASELF CONTINUOUS HEALING\n================================================\nObserved: %s ET\nCanonical phase: Phase 3 — Execute\nFounder operating label: Phase 3.5 — convergence and hardening\n\nHEALING STATE\n• Open problems: %s\n• P0: %s\n• P1: %s\n• Repair/verification attempts this hour: %s\n• Independently verified resolutions this hour: %s\n• Institutional messages inspected this hour: %s\n• Problem candidates routed this hour: %s\n\nTOP OWNED PROBLEMS\n%s\n\nCONTINUITY CONTRACT\n• Every message entering the CrownThrive institutional event fabric is inspected.\n• Every detected problem remains owned until verified resolution or explicit D3 disposition.\n• PentaSELF retries, repairs, verifies, quarantines, delegates, and escalates persistently.\n• “By force” means no silent abandonment: it does not bypass CHLOM, DAIL, provider permissions, credentials, release gates, or fail-closed economic controls.\n• D3 remains human-reserved. PentaSELF does not manufacture authority, credentials, provider evidence, or money-movement permission.\n\nThis report is an operational projection. ThriveBase, CHLOM, DAIL, GitHub, and independent provider readback retain their canonical roles.\n',
    to_char(now() at time zone 'America/New_York','YYYY-MM-DD HH24:MI:SS'),v_open,v_p0,v_p1,v_attempts,v_resolved,v_messages,v_problem_candidates,coalesce(v_top,'(none)'));
  v_report:=jsonb_build_object('contract','ct.penta.self.hourly-healing-report.v1','observed_at',now(),'recipient',v_recipient,'status',v_status,
    'messages_inspected_1h',v_messages,'problem_candidates_1h',v_problem_candidates,'attempts_1h',v_attempts,'resolved_1h',v_resolved,'d3_human_reserved',true,'authority_manufactured',false);
  v_sha:=encode(extensions.digest(convert_to(v_report::text,'UTF8'),'sha256'),'hex');
  insert into public.penta_reports_v1(report_type,system_key,priority,title,body,body_sha256,state)
  values('hourly_healing','penta.self',case when v_p0>0 then 'P0' when v_p1>0 then 'P1' else 'P2' end,v_subject,v_report,v_sha,'final') returning report_id into v_report_id;
  v_message:=public.penta_mail_enqueue_with_maker_v1('penta_self_hourly_healing',v_severity,v_subject,v_body,
    'penta-self-hourly-healing-'||to_char(now() at time zone 'UTC','YYYYMMDDHH24'),
    jsonb_build_object('trigger_ref','penta-self-hourly-healing-v1','report_id',v_report_id,'report_sha256',v_sha,'source_penta','PentaSELF','delivery_penta','PentaMail','d3_human_reserved',true,'authority_expansion',false),v_recipient);
  perform public.penta_mail_outbox_dispatch_v1();
  update public.penta_reports_v1 set sent_at=now() where report_id=v_report_id;
  return jsonb_build_object('ok',true,'state','queued','recipient',v_recipient,'message_id',v_message,'report_id',v_report_id,'report_sha256',v_sha,'status',v_status);
end $$;

