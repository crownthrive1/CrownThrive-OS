-- CrownThrive OS Phase 3.5
-- PentaSELF continuous problem ownership, universal institutional-message intake,
-- bounded detect->heal->verify continuity, and hourly healing reports.

create schema if not exists penta_self;

create table if not exists penta_self.continuity_policy_v1 (
  policy_key text primary key,
  enabled boolean not null default true,
  intake_schedule text not null,
  healing_schedule text not null,
  hourly_report_schedule text not null,
  recipient text not null,
  persistent_ownership boolean not null default true,
  retry_until_verified boolean not null default true,
  d3_human_reserved boolean not null default true,
  authority_manufacture boolean not null default false,
  credential_manufacture boolean not null default false,
  uncertified_provider_write boolean not null default false,
  money_movement_without_authority boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.problem_handler_registry_v1 (
  handler_key text primary key,
  category text not null,
  owner_penta text not null,
  action_mode text not null check (action_mode in ('direct_bounded','delegated','external_recheck','d3_reserved')),
  max_risk_class text not null check (max_risk_class in ('D0','D1','D2','D3')),
  function_ref text,
  retry_base_seconds integer not null default 60 check (retry_base_seconds between 5 and 86400),
  retry_max_seconds integer not null default 3600 check (retry_max_seconds between 60 and 604800),
  enabled boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.message_scan_state_v1 (
  source_name text primary key,
  last_occurred_at timestamptz not null default '1970-01-01 00:00:00+00'::timestamptz,
  last_uuid uuid,
  last_bigint bigint,
  total_messages_scanned bigint not null default 0 check (total_messages_scanned >= 0),
  total_problem_candidates bigint not null default 0 check (total_problem_candidates >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.message_scan_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  cycle_id uuid not null,
  source_name text not null,
  window_start timestamptz,
  window_end timestamptz,
  first_cursor jsonb not null default '{}'::jsonb,
  last_cursor jsonb not null default '{}'::jsonb,
  message_count integer not null default 0 check (message_count >= 0),
  problem_count integer not null default 0 check (problem_count >= 0),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists penta_self.problem_ledger_v1 (
  problem_id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique check (fingerprint ~ '^[0-9a-f]{64}$'),
  source_kind text not null,
  source_system text not null,
  source_ref text not null,
  category text not null,
  severity text not null check (severity in ('info','watch','degraded','critical')),
  priority text not null check (priority in ('P0','P1','P2','P3')),
  state text not null check (state in ('detected','routed','healing','verification','blocked_external','blocked_d3','resolved','false_positive','retired')),
  title text not null,
  summary text not null,
  owner_penta text not null,
  handler_key text not null references penta_self.problem_handler_registry_v1(handler_key),
  authority_class text not null check (authority_class in ('D0','D1','D2','D3')),
  auto_heal_allowed boolean not null default true,
  persistent boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  next_attempt_at timestamptz not null default now(),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_attempt_at timestamptz,
  last_error text,
  blocked_reason text,
  evidence jsonb not null default '{}'::jsonb,
  verification_evidence jsonb not null default '{}'::jsonb,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.problem_attempts_v1 (
  attempt_id uuid primary key default gen_random_uuid(),
  cycle_id uuid not null,
  problem_id uuid not null references penta_self.problem_ledger_v1(problem_id),
  attempt_no integer not null check (attempt_no > 0),
  handler_key text not null,
  owner_penta text not null,
  authority_class text not null check (authority_class in ('D0','D1','D2','D3')),
  result_state text not null check (result_state in ('applied','no_change','delegated','blocked','failed','verified')),
  reversible boolean not null default true,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null default now(),
  completed_at timestamptz not null default now()
);

create index if not exists problem_ledger_due_idx
  on penta_self.problem_ledger_v1(next_attempt_at, priority, first_seen_at)
  where state not in ('resolved','false_positive','retired');
create index if not exists problem_ledger_state_idx on penta_self.problem_ledger_v1(state,priority,category);
create index if not exists problem_ledger_source_idx on penta_self.problem_ledger_v1(source_system,source_ref);
create index if not exists problem_attempts_problem_idx on penta_self.problem_attempts_v1(problem_id,completed_at desc);
create index if not exists message_scan_receipts_source_idx on penta_self.message_scan_receipts_v1(source_name,created_at desc);

alter table penta_self.continuity_policy_v1 enable row level security;
alter table penta_self.problem_handler_registry_v1 enable row level security;
alter table penta_self.message_scan_state_v1 enable row level security;
alter table penta_self.message_scan_receipts_v1 enable row level security;
alter table penta_self.problem_ledger_v1 enable row level security;
alter table penta_self.problem_attempts_v1 enable row level security;

do $$
declare v_table text;
begin
  foreach v_table in array array[
    'continuity_policy_v1','problem_handler_registry_v1','message_scan_state_v1',
    'message_scan_receipts_v1','problem_ledger_v1','problem_attempts_v1'
  ] loop
    execute format('drop policy if exists ct_explicit_client_deny_v1 on penta_self.%I',v_table);
    execute format('create policy ct_explicit_client_deny_v1 on penta_self.%I for all to anon, authenticated using (false) with check (false)',v_table);
    execute format('revoke all on table penta_self.%I from public, anon, authenticated',v_table);
    execute format('grant all on table penta_self.%I to postgres, service_role',v_table);
  end loop;
end $$;

create or replace function penta_self.reject_append_only_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','penta_self'
as $$
begin
  raise exception 'PENTASELF_APPEND_ONLY_EVIDENCE';
end $$;

drop trigger if exists message_scan_receipts_append_only_v1 on penta_self.message_scan_receipts_v1;
create trigger message_scan_receipts_append_only_v1
before update or delete on penta_self.message_scan_receipts_v1
for each row execute function penta_self.reject_append_only_mutation_v1();

drop trigger if exists problem_attempts_append_only_v1 on penta_self.problem_attempts_v1;
create trigger problem_attempts_append_only_v1
before update or delete on penta_self.problem_attempts_v1
for each row execute function penta_self.reject_append_only_mutation_v1();

drop trigger if exists problem_ledger_no_delete_v1 on penta_self.problem_ledger_v1;
create trigger problem_ledger_no_delete_v1
before delete on penta_self.problem_ledger_v1
for each row execute function penta_self.reject_append_only_mutation_v1();

insert into penta_self.continuity_policy_v1(
  policy_key,enabled,intake_schedule,healing_schedule,hourly_report_schedule,recipient,
  persistent_ownership,retry_until_verified,d3_human_reserved,authority_manufacture,
  credential_manufacture,uncertified_provider_write,money_movement_without_authority,metadata
) values (
  'ct.penta.self.continuous-healing.v1',true,'1-59/2 * * * *','1-59/2 * * * *','7 * * * *',
  'jones.usmc.kj@gmail.com',true,true,true,false,false,false,false,
  jsonb_build_object(
    'contract','ct.penta.self.problem-ownership.v1',
    'operating_rule','every institutional message is inspected; every detected problem remains owned until independently verified resolved or explicitly dispositioned under D3',
    'force_semantics','persistent retry, repair, verification, quarantine and escalation without bypassing CHLOM, DAIL, provider permissions, credential custody or fail-closed controls',
    'message_sources',jsonb_build_array('os_v2.system_change_events','public.pentafabric_events','integration_control.penta_mail_provider_incidents_v1','cron.job_run_details','public.penta_incidents_v1','penta_self.cycle_receipts_v1'),
    'authority_ceiling','D2_AUTONOMOUS_D3_HUMAN_RESERVED'
  )
) on conflict(policy_key) do update set
  enabled=excluded.enabled,
  intake_schedule=excluded.intake_schedule,
  healing_schedule=excluded.healing_schedule,
  hourly_report_schedule=excluded.hourly_report_schedule,
  recipient=excluded.recipient,
  persistent_ownership=true,
  retry_until_verified=true,
  d3_human_reserved=true,
  authority_manufacture=false,
  credential_manufacture=false,
  uncertified_provider_write=false,
  money_movement_without_authority=false,
  metadata=penta_self.continuity_policy_v1.metadata||excluded.metadata,
  updated_at=now();

insert into penta_self.problem_handler_registry_v1(
  handler_key,category,owner_penta,action_mode,max_risk_class,function_ref,retry_base_seconds,retry_max_seconds,metadata
) values
 ('repair.commercial_packager_schedule.v1','concurrency','PentaSELF/PentaTime','direct_bounded','D1','cron.alter_job + production readback',300,3600,jsonb_build_object('certified_change','stagger minute 27 collision to minute 33','money_movement',false)),
 ('recover.required_cron.v1','scheduler','PentaSELF/PentaTime','direct_bounded','D1','penta_self.scheduler_reconcile_v1 + penta_self.failed_job_recovery_v1',120,1800,'{}'::jsonb),
 ('repair.pentaself_discovery.v1','concurrency','PentaSELF/PentaDiscover','direct_bounded','D1','public.ct_phase3_self_discovery_tick_v3',120,1800,'{}'::jsonb),
 ('repair.pentamail.v1','mail','PentaSELF/PentaMail','direct_bounded','D1','public.penta_mail_outage_watch_v1 + public.penta_mail_outbox_dispatch_v1',300,3600,'{}'::jsonb),
 ('reconcile.provider_evidence.v1','provider_evidence','PentaCertify/PentaNurture','delegated','D2','integration_control.penta_certify_activate_control_evidence_v1',300,3600,'{}'::jsonb),
 ('repair.software.via_pentabuild.v1','software','PentaBuild/PentaCertify','delegated','D2','integration_control.penta_build_quality_sweep_v1',300,3600,'{}'::jsonb),
 ('reconcile.release.via_pentarelease.v1','release','PentaRelease/PentaBuild/PentaCertify','delegated','D2','PentaRelease governed repair lane',300,3600,jsonb_build_object('gate_bypass',false)),
 ('reconcile.projection.v1','projection','PentaStatus/PentaScribe/PentaDocs','delegated','D2','PentaStatus/PentaScribe projection reconciliation',900,3600,'{}'::jsonb),
 ('reconcile.source_custody.v1','source_custody','PentaSerialized/PentaBuild/PentaCertify','delegated','D2','PentaSerialized source-custody reconciliation',900,3600,'{}'::jsonb),
 ('external.provider_recheck.v1','external_provider','PentaLiaisn/PentaCredentials/PentaCertify','external_recheck','D2',null,900,3600,jsonb_build_object('provider_write',false,''requires_independent_readback',true)),
 ('external.human_action.v1','human_action','PentaLiaison/Founder','d3_reserved','D3',null,1800,3600,jsonb_build_object('d3_human_reserved',true)),
 ('diagnose.generic.v1','operational','PentaSELF/PentaNurture','direct_bounded','D1','public.thrivebase_safe_self_heal_run_v1',300,3600,'{}'::jsonb)
on conflict(handler_key) do update set
  category=excluded.category,
  owner_penta=excluded.owner_penta,
  action_mode=excluded.action_mode,
  max_risk_class=excluded.max_risk_class,
  function_ref=excluded.function_ref,
  retry_base_seconds=excluded.retry_base_seconds,
  retry_max_seconds=excluded.retry_max_seconds,
  enabled=true,
  metadata=penta_self.problem_handler_registry_v1.metadata||excluded.metadata,
  updated_at=now();

create or replace function penta_self.problem_fingerprint_v1(
  p_source_kind text,
  p_source_system text,
  p_source_ref text,
  p_category text,
  p_title text
) returns text
language sql
immutable
set search_path='pg_catalog','extensions'
as $$
  select encode(extensions.digest(convert_to(
    lower(coalesce(p_source_kind,'unknown'))||'|'||
    lower(coalesce(p_source_system,'unknown'))||'|'||
    lower(coalesce(nullif(p_source_ref,''),left(coalesce(p_title,'unknown'),160)))||'|'||
    lower(coalesce(p_category,'operational')),
    'UTF8'),'sha256'),'hex');
$$;

create or replace function penta_self.problem_category_v1(
  p_source_system text,
  p_source_ref text,
  p_title text,
  p_summary text,
  p_event_type text default null
) returns text
language plpgsql
immutable
set search_path='pg_catalog'
as $$
declare v text:=lower(concat_ws(' ',p_source_system,p_source_ref,p_title,p_summary,p_event_type));
begin
  if v ~ '(webhook|stripe event|paypal event)' then return 'provider_webhook'; end if;
  if v ~ '(payout|settlement rail|bank rail)' then return 'payout'; end if;
  if v ~ '(secret|credential|gitguardian|token)' then return 'security'; end if;
  if v ~ '(domain|dns|icann|registrant)' then return 'domain'; end if;
  if v ~ '(deadlock|waiting lock|lock contention|collision)' then return 'concurrency'; end if;
  if v ~ '(cron|scheduler|scheduled job)' then return 'scheduler'; end if;
  if v ~ '(release|pentarelease|tag|version)' then return 'release'; end if;
  if v ~ '(migration|source custody|lineage|replay)' then return 'source_custody'; end if;
  if v ~ '(projection|mirror|public phase|documentation drift|sheet|drive)' then return 'projection'; end if;
  if v ~ '(mail|gmail|outlook|mailgun|inbox|spam)' then return 'mail'; end if;
  if v ~ '(timeout|timed out|429|503|502|504)' then return 'timeout'; end if;
  if v ~ '(adapter|build|software|workflow|github actions)' then return 'software'; end if;
  if v ~ '(provider|stripe|paypal|vercel|github|google drive|supabase)' then return 'external_provider'; end if;
  return 'operational';
end $$;

create or replace function penta_self.problem_handler_for_v1(
  p_category text,
  p_source_system text,
  p_source_ref text,
  p_title text,
  p_summary text
) returns text
language plpgsql
immutable
set search_path='pg_catalog'
as $$
declare v text:=lower(concat_ws(' ',p_source_system,p_source_ref,p_title,p_summary));
begin
  if v like '%crownthrive_commercial_release_packager_hourly%' then return 'repair.commercial_packager_schedule.v1'; end if;
  if v like '%ct-phase3-self-discovery-v3%' or v like '%self-discovery%' then return 'repair.pentaself_discovery.v1'; end if;
  if p_category='scheduler' or (p_source_ref like 'cron:%') then return 'recover.required_cron.v1'; end if;
  if p_category='mail' then return 'repair.pentamail.v1'; end if;
  if p_category='release' then return 'reconcile.release.via_pentarelease.v1'; end if;
  if p_category='source_custody' then return 'reconcile.source_custody.v1'; end if;
  if p_category='projection' then return 'reconcile.projection.v1'; end if;
  if p_category in ('provider_webhook','payout','security','domain','external_provider','timeout') then return 'external.provider_recheck.v1'; end if;
  if p_category='software' then return 'repair.software.via_pentabuild.v1'; end if;
  if p_category='provider_evidence' then return 'reconcile.provider_evidence.v1'; end if;
  return 'diagnose.generic.v1';
end $$;

create or replace function penta_self.message_is_problem_v1(
  p_severity text,
  p_title text,
  p_summary text,
  p_event_type text,
  p_details jsonb default '{}'::jsonb
) returns boolean
language plpgsql
immutable
set search_path='pg_catalog'
as $$
declare
  v text:=lower(concat_ws(' ',p_severity,p_title,p_summary,p_event_type,coalesce(p_details::text,'')));
  v_sev text:=lower(coalesce(p_severity,''));
begin
  if v ~ '(recovered|resolved|succeeded|successfully|healthy|passed|closed|applied|verified)'
     and v !~ '(unrecovered|not resolved|still (failed|failing|blocked|degraded)|remains (failed|failing|blocked|degraded)|deadlock detected|error[^a-z0-9]*(present|true|[1-9])|http [45][0-9][0-9])' then
    return false;
  end if;
  if v_sev in ('critical','fatal','error','high','severe') then return true; end if;
  if v ~ '(failed|failure|failing|error|critical|blocked|degraded|deadlock|timeout|timed out|unhealthy|unrecovered|incident|hold|http 403|http 404|http 429|http 500|http 502|http 503|http 504|secret detected|webhook failure|payout rail|collision|drift detected|missing required)' then
    return true;
  end if;
  return false;
end $$;

create or replace function penta_self.register_problem_v1(
  p_source_kind text,
  p_source_system text,
  p_source_ref text,
  p_category text,
  p_severity text,
  p_priority text,
  p_title text,
  p_summary text,
  p_owner_penta text,
  p_handler_key text,
  p_authority_class text default 'D1',
  p_initial_state text default 'detected',
  p_auto_heal_allowed boolean default true,
  p_blocked_reason text default null,
  p_evidence jsonb default '{}'::jsonb,
  p_fingerprint text default null
) returns uuid
language plpgsql
security definer
set search_path='pg_catalog','penta_self'
as $$
declare
  v_id uuid;
  v_fp text:=coalesce(p_fingerprint,penta_self.problem_fingerprint_v1(p_source_kind,p_source_system,p_source_ref,p_category,p_title));
  v_sev text:=case lower(coalesce(p_severity,'')) when 'critical' then 'critical' when 'fatal' then 'critical' when 'error' then 'critical' when 'high' then 'critical' when 'degraded' then 'degraded' when 'warning' then 'degraded' when 'warn' then 'degraded' when 'watch' then 'watch' else 'watch' end;
  v_priority text:=case upper(coalesce(p_priority,'')) when 'P0' then 'P0' when 'P1' then 'P1' when 'P2' then 'P2' else 'P3' end;
  v_state text:=case when p_initial_state in ('detected','routed','healing','verification','blocked_external','blocked_d3','resolved','false_positive','retired') then p_initial_state else 'detected' end;
begin
  insert into penta_self.problem_ledger_v1(
    fingerprint,source_kind,source_system,source_ref,category,severity,priority,state,title,summary,
    owner_penta,handler_key,authority_class,auto_heal_allowed,persistent,first_seen_at,last_seen_at,
    next_attempt_at,blocked_reason,evidence,resolved_at
  ) values (
    v_fp,left(coalesce(p_source_kind,'unknown'),80),left(coalesce(p_source_system,'unknown'),120),
    left(coalesce(p_source_ref,'unknown'),240),left(coalesce(p_category,'operational'),80),v_sev,v_priority,v_state,
    left(coalesce(p_title,'Untitled operational problem'),240),left(coalesce(p_summary,'No summary supplied'),2000),
    left(coalesce(p_owner_penta,'PentaSELF'),160),p_handler_key,p_authority_class,p_auto_heal_allowed,true,now(),now(),now(),
    left(p_blocked_reason,500),coalesce(p_evidence,'{}'::jsonb),case when v_state='resolved' then now() else null end
  )
  on conflict(fingerprint) do update set
    severity=case
      when penta_self.problem_ledger_v1.severity='critical' or excluded.severity='critical' then 'critical'
      when penta_self.problem_ledger_v1.severity='degraded' or excluded.severity='degraded' then 'degraded'
      when penta_self.problem_ledger_v1.severity='watch' or excluded.severity='watch' then 'watch'
      else 'info' end,
    priority=case
      when penta_self.problem_ledger_v1.priority='P0' or excluded.priority='P0' then 'P0'
      when penta_self.problem_ledger_v1.priority='P1' or excluded.priority='P1' then 'P1'
      when penta_self.problem_ledger_v1.priority='P2' or excluded.priority='P2' then 'P2'
      else 'P3' end,
    state=case when penta_self.problem_ledger_v1.state in ('resolved','false_positive','retired') then excluded.state else penta_self.problem_ledger_v1.state end,
    title=excluded.title,
    summary=excluded.summary,
    owner_penta=excluded.owner_penta,
    handler_key=excluded.handler_key,
    authority_class=excluded.authority_class,
    auto_heal_allowed=excluded.auto_heal_allowed,
    persistent=true,
    last_seen_at=now(),
    next_attempt_at=least(penta_self.problem_ledger_v1.next_attempt_at,now()),
    blocked_reason=coalesce(excluded.blocked_reason,penta_self.problem_ledger_v1.blocked_reason),
    evidence=penta_self.problem_ledger_v1.evidence||excluded.evidence,
    resolved_at=case when penta_self.problem_ledger_v1.state in ('resolved','false_positive','retired') then null else penta_self.problem_ledger_v1.resolved_at end,
    updated_at=now()
  returning problem_id into v_id;
  return v_id;
end $$;

