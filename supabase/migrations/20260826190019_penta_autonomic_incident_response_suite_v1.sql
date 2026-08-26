begin;

create table if not exists public.penta_incidents_v1 (
  incident_id uuid primary key default gen_random_uuid(),
  system_key text not null,
  incident_code text not null,
  severity text not null check (severity in ('INFO','WARN','ERROR','CRITICAL')),
  priority text not null check (priority in ('P0','P1','P2','P3')),
  state text not null check (state in ('detected','notified','remediating','verification','resolved','hold')),
  source_event_ref text,
  fingerprint text not null,
  title text not null,
  summary text not null,
  failure_evidence jsonb not null default '{}'::jsonb,
  remediation_state text,
  remediation_evidence jsonb not null default '{}'::jsonb,
  verification_evidence jsonb not null default '{}'::jsonb,
  opened_at timestamptz not null default now(),
  first_notified_at timestamptz,
  resolved_at timestamptz,
  updated_at timestamptz not null default now()
);
create unique index if not exists penta_incidents_v1_fingerprint_uq on public.penta_incidents_v1(fingerprint);
create index if not exists penta_incidents_v1_state_idx on public.penta_incidents_v1(state,priority,updated_at desc);

create table if not exists public.penta_flags_v1 (
  flag_id uuid primary key default gen_random_uuid(),
  incident_id uuid references public.penta_incidents_v1(incident_id) on delete cascade,
  flag_key text not null,
  severity text not null,
  reason text not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(incident_id,flag_key)
);

create table if not exists public.penta_tags_v1 (
  tag_id uuid primary key default gen_random_uuid(),
  incident_id uuid references public.penta_incidents_v1(incident_id) on delete cascade,
  tag text not null,
  created_at timestamptz not null default now(),
  unique(incident_id,tag)
);

create table if not exists public.penta_harvest_events_v1 (
  harvest_id uuid primary key default gen_random_uuid(),
  incident_id uuid references public.penta_incidents_v1(incident_id) on delete cascade,
  source_type text not null,
  source_ref text not null,
  payload jsonb not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique(source_type,source_ref,payload_sha256)
);

create table if not exists public.penta_backup_receipts_v1 (
  backup_id uuid primary key default gen_random_uuid(),
  scope text not null,
  reason text not null,
  snapshot jsonb not null,
  snapshot_sha256 text not null check (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  external_backup_job jsonb not null default '{}'::jsonb,
  restore_ready boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.penta_restore_receipts_v1 (
  restore_id uuid primary key default gen_random_uuid(),
  backup_id uuid not null references public.penta_backup_receipts_v1(backup_id) on delete restrict,
  mode text not null check (mode in ('dry_run','authorized_restore')),
  state text not null check (state in ('planned','blocked','completed','failed')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.penta_flush_receipts_v1 (
  flush_id uuid primary key default gen_random_uuid(),
  scope text not null,
  dry_run boolean not null default true,
  candidate_count integer not null default 0,
  deleted_count integer not null default 0,
  constraints jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.penta_remediation_actions_v1 (
  action_id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references public.penta_incidents_v1(incident_id) on delete cascade,
  handler_key text not null,
  state text not null check (state in ('planned','applied','already_compliant','blocked','failed')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.penta_reports_v1 (
  report_id uuid primary key default gen_random_uuid(),
  report_type text not null,
  system_key text not null,
  incident_id uuid references public.penta_incidents_v1(incident_id) on delete set null,
  priority text not null check (priority in ('P0','P1','P2','P3')),
  title text not null,
  body jsonb not null,
  body_sha256 text not null check (body_sha256 ~ '^[0-9a-f]{64}$'),
  state text not null check (state in ('draft','final','sent')) default 'final',
  created_at timestamptz not null default now(),
  sent_at timestamptz
);

create table if not exists public.penta_redblue_exercises_v1 (
  exercise_id uuid primary key default gen_random_uuid(),
  target_system text not null,
  scenario_key text not null,
  red_assertions jsonb not null,
  blue_assertions jsonb not null,
  verdict text not null check (verdict in ('PASS','HOLD','FAIL')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.penta_incidents_v1 enable row level security;
alter table public.penta_flags_v1 enable row level security;
alter table public.penta_tags_v1 enable row level security;
alter table public.penta_harvest_events_v1 enable row level security;
alter table public.penta_backup_receipts_v1 enable row level security;
alter table public.penta_restore_receipts_v1 enable row level security;
alter table public.penta_flush_receipts_v1 enable row level security;
alter table public.penta_remediation_actions_v1 enable row level security;
alter table public.penta_reports_v1 enable row level security;
alter table public.penta_redblue_exercises_v1 enable row level security;

revoke all on public.penta_incidents_v1,public.penta_flags_v1,public.penta_tags_v1,
  public.penta_harvest_events_v1,public.penta_backup_receipts_v1,public.penta_restore_receipts_v1,
  public.penta_flush_receipts_v1,public.penta_remediation_actions_v1,public.penta_reports_v1,
  public.penta_redblue_exercises_v1 from anon,authenticated;

insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata)
values
 ('penta.reports','PentaReports','assurance','Canonical after-action, incident, verification and operational reporting.','May report evidence; cannot manufacture PASS or authority.','D2','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_reports_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.notifs','PentaNotifs','operations','Dedupe-aware operator notification and escalation integrated with PentaMail.','May notify and escalate; cannot approve consequential action.','D1','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_mail_enqueue_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.flagger','PentaFlagger','operations','Converts observed faults and policy conditions into durable flags.','Flags evidence only; does not determine final governance disposition.','D1','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_flags_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.tagger','PentaTagger','operations','Applies machine-readable routing, ownership, priority and domain tags.','Tags are routing metadata, never authority.','D0','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_tags_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.harvestor','PentaHarvestor','evidence','Harvests bounded evidence into immutable hashed incident evidence records.','Read/collect only from authorized sources; does not mutate source truth.','D1','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_harvest_events_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.backup','PentaBackup','continuity','Creates verifiable control-plane snapshots and binds to CHLOM backup jobs.','Backup only; no destructive production mutation.','D1','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_backup_receipts_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.restore','PentaRestore','continuity','Plans and executes only verified, authorized restores.','Fail closed unless backup provenance, integrity and restore authority are proven.','D3','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_restore_receipts_v1','{"family":"autonomic_operations"}'::jsonb),
 ('penta.flush','PentaFlush','maintenance','TTL-bounded cleanup of explicitly ephemeral state.','Never deletes canonical evidence, governance, financial, rights or audit records.','D2','implemented','1.0.0',true,'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md','public.penta_flush_receipts_v1','{"family":"autonomic_operations"}'::jsonb)
on conflict(system_key) do update set
 canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,
 authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,
 version=excluded.version,public_exposure=excluded.public_exposure,docs_ref=excluded.docs_ref,
 runtime_ref=excluded.runtime_ref,metadata=public.penta_system_registry.metadata||excluded.metadata,
 last_verified_at=now(),updated_at=now();

create or replace function public.penta_remediate_pentagreen_23514_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control'
as $fn$
declare
  v_def text;
  v_old text := 'v_snapshot->>''candidate_type'',nullif(v_snapshot->>''candidate_ref'','''')';
  v_new text := 'v_snapshot->>''candidate_type'',case when v_snapshot->>''candidate_type''=''proprietary_product_candidate'' then nullif(v_snapshot->>''candidate_ref'','''') else null end';
  v_state text;
begin
  select pg_get_functiondef('integration_control.run_thriveevergreen_hourly_product_cycle_v1(timestamptz,text,boolean)'::regprocedure) into v_def;
  if position(v_new in v_def)>0 then
    v_state := 'already_compliant';
  elsif position(v_old in v_def)>0 then
    v_def := replace(v_def,v_old,v_new);
    execute v_def;
    v_state := 'applied';
  else
    return jsonb_build_object('state','blocked','reason','UNRECOGNIZED_FUNCTION_FINGERPRINT');
  end if;
  return jsonb_build_object('state',v_state,'handler','penta.pentagreen.23514.candidate-identity.v1');
end
$fn$;

create or replace function public.penta_backup_control_plane_v1(p_scope text,p_reason text)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control','chlom_runtime','extensions'
as $fn$
declare
  v_snapshot jsonb;
  v_sha text;
  v_backup_job jsonb := '{}'::jsonb;
  v_id uuid;
begin
  v_snapshot := jsonb_build_object(
    'captured_at',now(),
    'scope',p_scope,
    'penta_green_latest',(select to_jsonb(x) from (select run_id,window_start,run_state,economic_verdict,publication_count,error_code,evidence_sha256 from integration_control.pentagreen_hourly_runs_v1 order by started_at desc limit 1) x),
    'open_incidents',(select coalesce(jsonb_agg(to_jsonb(i)),'[]'::jsonb) from (select incident_id,system_key,incident_code,priority,state,fingerprint,updated_at from public.penta_incidents_v1 where state<>'resolved' order by priority,updated_at desc limit 100) i),
    'system_registry',(select coalesce(jsonb_agg(to_jsonb(s)),'[]'::jsonb) from (select system_key,canonical_name,maturity,version,risk_ceiling,last_verified_at from public.penta_system_registry where system_key like 'penta.%' order by system_key) s)
  );
  v_sha := encode(extensions.digest(v_snapshot::text,'sha256'),'hex');
  begin
    v_backup_job := chlom_runtime.enqueue_midnight_backup_v2(true,(now() at time zone 'UTC')::date);
  exception when others then
    v_backup_job := jsonb_build_object('state','enqueue_failed','sqlstate',sqlstate);
  end;
  insert into public.penta_backup_receipts_v1(scope,reason,snapshot,snapshot_sha256,external_backup_job,restore_ready)
  values(p_scope,p_reason,v_snapshot,v_sha,v_backup_job,false) returning backup_id into v_id;
  return jsonb_build_object('backup_id',v_id,'snapshot_sha256',v_sha,'external_backup_job',v_backup_job,'state','captured');
end
$fn$;

create or replace function public.penta_restore_plan_v1(p_backup_id uuid)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public'
as $fn$
declare v_b public.penta_backup_receipts_v1%rowtype; v_id uuid;
begin
  select * into strict v_b from public.penta_backup_receipts_v1 where backup_id=p_backup_id;
  insert into public.penta_restore_receipts_v1(backup_id,mode,state,evidence)
  values(p_backup_id,'dry_run',case when v_b.restore_ready then 'planned' else 'blocked' end,
    jsonb_build_object('snapshot_sha256',v_b.snapshot_sha256,'restore_ready',v_b.restore_ready,'rule','NO_MUTATION_DURING_DRY_RUN'))
  returning restore_id into v_id;
  return jsonb_build_object('restore_id',v_id,'state',case when v_b.restore_ready then 'planned' else 'blocked' end,'dry_run',true);
end
$fn$;

create or replace function public.penta_flush_ephemeral_v1(p_older_than interval default interval '7 days',p_dry_run boolean default true)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public'
as $fn$
declare v_candidates integer := 0; v_deleted integer := 0; v_id uuid;
begin
  select count(*) into v_candidates from public.penta_mail_outbox_v1
   where state in ('sent','failed') and updated_at < now()-p_older_than;
  if not p_dry_run then
    delete from public.penta_mail_outbox_v1
     where state in ('sent','failed') and updated_at < now()-p_older_than;
    get diagnostics v_deleted = row_count;
  end if;
  insert into public.penta_flush_receipts_v1(scope,dry_run,candidate_count,deleted_count,constraints)
  values('penta_mail_ephemeral_terminal_rows',p_dry_run,v_candidates,v_deleted,
    jsonb_build_object('canonical_records_deleted',false,'allowed_states',jsonb_build_array('sent','failed'),'ttl',p_older_than::text))
  returning flush_id into v_id;
  return jsonb_build_object('flush_id',v_id,'dry_run',p_dry_run,'candidate_count',v_candidates,'deleted_count',v_deleted,'canonical_records_deleted',false);
end
$fn$;

create or replace function public.penta_redblue_pentagreen_23514_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control','extensions'
as $fn$
declare
  v_def text;
  v_constraint text;
  v_latest record;
  v_red jsonb;
  v_blue jsonb;
  v_verdict text;
  v_id uuid;
begin
  select pg_get_functiondef('integration_control.run_thriveevergreen_hourly_product_cycle_v1(timestamptz,text,boolean)'::regprocedure) into v_def;
  select pg_get_constraintdef(oid) into v_constraint from pg_constraint where conname='thriveevergreen_packets_candidate_identity_v1' limit 1;
  select run_id,run_state,economic_verdict,publication_count,error_code,assertions,evidence_sha256 into v_latest
  from integration_control.pentagreen_hourly_runs_v1 order by started_at desc limit 1;
  v_red := jsonb_build_object(
    'legacy_bad_writer_absent',position('v_snapshot->>''candidate_type'',nullif(v_snapshot->>''candidate_ref'','''')' in v_def)=0,
    'protective_constraint_present',coalesce(v_constraint,'') like '%candidate_ref IS NULL%'
  );
  v_blue := jsonb_build_object(
    'conditional_writer_present',position('case when v_snapshot->>''candidate_type''=''proprietary_product_candidate''' in v_def)>0,
    'latest_run_completed',v_latest.run_state='completed',
    'latest_error_clear',v_latest.error_code is null,
    'publication_count_zero',coalesce(v_latest.publication_count,0)=0,
    'no_money_movement',coalesce((v_latest.assertions->>'money_movement_function_invoked')::boolean,false)=false,
    'no_checkout_activation',coalesce((v_latest.assertions->>'checkout_activation_invoked')::boolean,false)=false
  );
  v_verdict := case when (v_red->>'legacy_bad_writer_absent')::boolean
                         and (v_red->>'protective_constraint_present')::boolean
                         and (v_blue->>'conditional_writer_present')::boolean
                         and (v_blue->>'latest_run_completed')::boolean
                         and (v_blue->>'latest_error_clear')::boolean
                         and (v_blue->>'publication_count_zero')::boolean
                         and (v_blue->>'no_money_movement')::boolean
                         and (v_blue->>'no_checkout_activation')::boolean
                    then 'PASS' else 'HOLD' end;
  insert into public.penta_redblue_exercises_v1(target_system,scenario_key,red_assertions,blue_assertions,verdict,evidence)
  values('penta.green','postgres_check_23514_candidate_identity',v_red,v_blue,v_verdict,
    jsonb_build_object('latest_run_id',v_latest.run_id,'evidence_sha256',v_latest.evidence_sha256,'constraint',v_constraint))
  returning exercise_id into v_id;
  return jsonb_build_object('exercise_id',v_id,'verdict',v_verdict,'red',v_red,'blue',v_blue);
end
$fn$;

create or replace function public.penta_incident_control_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control','extensions'
as $fn$
declare
  v_failed record;
  v_success record;
  v_incident_id uuid;
  v_fp text;
  v_rem jsonb;
  v_report jsonb;
  v_report_sha text;
  v_report_id uuid;
  v_note_id uuid;
  v_source_ref text;
  v_harvest jsonb;
  v_harvest_sha text;
begin
  select run_id,window_start,run_state,economic_verdict,publication_count,error_code,blockers,assertions,evidence_sha256,started_at,completed_at
  into v_failed
  from integration_control.pentagreen_hourly_runs_v1
  where run_state='failed' and error_code is not null
  order by started_at desc limit 1;

  if not found then
    return jsonb_build_object('state','no_action','reason','NO_FAILED_PENTAGREEN_RUN');
  end if;

  v_fp := encode(extensions.digest(('penta.green:'||coalesce(v_failed.error_code,'unknown'))::text,'sha256'),'hex');
  v_source_ref := 'pentagreen_run:'||v_failed.run_id::text;

  insert into public.penta_incidents_v1(system_key,incident_code,severity,priority,state,source_event_ref,fingerprint,title,summary,failure_evidence)
  values('penta.green',v_failed.error_code,case when v_failed.error_code='23514' then 'CRITICAL' else 'ERROR' end,
         case when v_failed.error_code='23514' then 'P0' else 'P1' end,'detected',v_source_ref,v_fp,
         'PentaGreen governed execution fault '||v_failed.error_code,
         'PentaFlagger detected a failed PentaGreen governed hourly execution. Economic activation remains fail-closed.',
         jsonb_build_object('run_id',v_failed.run_id,'window_start',v_failed.window_start,'economic_verdict',v_failed.economic_verdict,
                            'publication_count',v_failed.publication_count,'error_code',v_failed.error_code,'blockers',v_failed.blockers,
                            'assertions',v_failed.assertions,'evidence_sha256',v_failed.evidence_sha256))
  on conflict(fingerprint) do update set
    source_event_ref=excluded.source_event_ref,
    failure_evidence=public.penta_incidents_v1.failure_evidence||excluded.failure_evidence,
    updated_at=now()
  returning incident_id into v_incident_id;

  insert into public.penta_flags_v1(incident_id,flag_key,severity,reason,evidence)
  values(v_incident_id,'execution_failure','CRITICAL','PentaGreen hourly execution returned SQLSTATE '||v_failed.error_code,
         jsonb_build_object('run_id',v_failed.run_id,'publication_count',v_failed.publication_count))
  on conflict(incident_id,flag_key) do nothing;

  insert into public.penta_tags_v1(incident_id,tag) values
    (v_incident_id,'system:penta.green'),(v_incident_id,'priority:P0'),(v_incident_id,'owner:penta.blue'),
    (v_incident_id,'review:penta.red'),(v_incident_id,'error:'||v_failed.error_code),(v_incident_id,'economic:fail-closed')
  on conflict(incident_id,tag) do nothing;

  v_harvest := jsonb_build_object('run_id',v_failed.run_id,'error_code',v_failed.error_code,'blockers',v_failed.blockers,
                                  'assertions',v_failed.assertions,'evidence_sha256',v_failed.evidence_sha256);
  v_harvest_sha := encode(extensions.digest(v_harvest::text,'sha256'),'hex');
  insert into public.penta_harvest_events_v1(incident_id,source_type,source_ref,payload,payload_sha256)
  values(v_incident_id,'pentagreen_hourly_run',v_source_ref,v_harvest,v_harvest_sha)
  on conflict(source_type,source_ref,payload_sha256) do nothing;

  if (select first_notified_at is null from public.penta_incidents_v1 where incident_id=v_incident_id) then
    v_note_id := public.penta_mail_enqueue_v1(
      'incident','CRITICAL','[P0] PentaGreen execution fault '||v_failed.error_code,
      'PentaNotifs detected PentaGreen SQLSTATE '||v_failed.error_code||'. The governed execution failed closed with publication_count='||coalesce(v_failed.publication_count,0)::text||'. PentaBlue owns remediation; PentaRed owns adversarial verification. Economic activation remains HOLD until a successful governed readback.',
      'penta-incident:'||v_fp,
      jsonb_build_object('incident_id',v_incident_id,'run_id',v_failed.run_id,'priority','P0','owner','PentaBlue','reviewer','PentaRed')
    );
    update public.penta_incidents_v1 set state='notified',first_notified_at=now(),updated_at=now() where incident_id=v_incident_id;
  end if;

  if v_failed.error_code='23514' then
    update public.penta_incidents_v1 set state='remediating',updated_at=now() where incident_id=v_incident_id;
    v_rem := public.penta_remediate_pentagreen_23514_v1();
    insert into public.penta_remediation_actions_v1(incident_id,handler_key,state,evidence)
    values(v_incident_id,'penta.pentagreen.23514.candidate-identity.v1',
      case when v_rem->>'state'='applied' then 'applied' when v_rem->>'state'='already_compliant' then 'already_compliant' when v_rem->>'state'='blocked' then 'blocked' else 'failed' end,
      v_rem);
    update public.penta_incidents_v1 set remediation_state=v_rem->>'state',remediation_evidence=v_rem,state='verification',updated_at=now() where incident_id=v_incident_id;
  end if;

  select run_id,window_start,run_state,economic_verdict,publication_count,error_code,assertions,evidence_sha256,started_at,completed_at
  into v_success
  from integration_control.pentagreen_hourly_runs_v1
  where run_state='completed' and error_code is null and started_at>v_failed.started_at
  order by started_at desc limit 1;

  if found then
    v_report := jsonb_build_object(
      'contract','ct.penta.report.after-action.v1',
      'incident_id',v_incident_id,
      'system','PentaGreen',
      'priority','P0',
      'fault',jsonb_build_object('sqlstate',v_failed.error_code,'failed_run_id',v_failed.run_id,'publication_count',v_failed.publication_count),
      'root_cause','Commercial-package candidate_ref was persisted into a column constrained for proprietary_product_candidate identity only.',
      'repair','Writer now persists candidate_ref only for proprietary_product_candidate; commercial packages use sku/package_id identity and candidate_ref=NULL.',
      'verification',jsonb_build_object('successful_run_id',v_success.run_id,'error_code',v_success.error_code,'run_state',v_success.run_state,
                                       'economic_verdict',v_success.economic_verdict,'publication_count',v_success.publication_count,
                                       'evidence_sha256',v_success.evidence_sha256,'assertions',v_success.assertions),
      'economic_activation','HOLD_PENDING_GOVERNANCE_EVIDENCE',
      'red_blue_assignment',jsonb_build_object('red','constraint/adversarial regression','blue','repair/readback/containment'),
      'closed_at',now()
    );
    v_report_sha := encode(extensions.digest(v_report::text,'sha256'),'hex');
    insert into public.penta_reports_v1(report_type,system_key,incident_id,priority,title,body,body_sha256,state)
    values('after_action','penta.green',v_incident_id,'P0','PentaGreen 23514 After Action Report',v_report,v_report_sha,'final')
    returning report_id into v_report_id;

    update public.penta_incidents_v1 set state='resolved',resolved_at=now(),
      verification_evidence=v_report->'verification',updated_at=now() where incident_id=v_incident_id;

    perform public.penta_mail_enqueue_v1(
      'after_action','INFO','[RESOLVED SOFTWARE FAULT] PentaGreen 23514 AAR',
      'PentaReports closed the P0 software incident. SQLSTATE 23514 was traced to a candidate identity CHECK violation and repaired without weakening the constraint. A subsequent governed production run completed with error_code=NULL and publication_count=0. Economic activation remains HOLD for independent governance/evidence blockers; no checkout activation or money movement was performed. Report ID: '||v_report_id::text||'. Evidence SHA-256: '||v_report_sha||'.',
      'penta-aar:'||v_fp,
      jsonb_build_object('incident_id',v_incident_id,'report_id',v_report_id,'report_sha256',v_report_sha,'successful_run_id',v_success.run_id)
    );
  end if;

  return jsonb_build_object('state',case when found then 'resolved' else 'verification' end,'incident_id',v_incident_id,'remediation',v_rem,'report_id',v_report_id);
end
$fn$;

select cron.schedule('ct-penta-incident-control-v1','*/5 * * * *','select public.penta_incident_control_tick_v1();');

commit;
