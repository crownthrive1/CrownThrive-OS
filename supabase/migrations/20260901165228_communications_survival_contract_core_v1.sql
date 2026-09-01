-- CrownThrive Communications Survival Contract core v1.
-- Forward-only policy, immutable cycle evidence, flow status, and bounded recovery executor.

create table integration_control.communications_survival_contract_versions_v1 (
  contract_key text not null,
  generation bigint not null,
  semantic_version text not null,
  policy jsonb not null,
  policy_sha256 text not null,
  predecessor_sha256 text,
  evidence_sha256 text not null,
  authority_ceiling text not null,
  successor_acceptance text not null,
  source_ref text not null,
  migration_version text not null,
  accepted_at timestamptz not null default clock_timestamp(),
  accepted_by text not null default current_user,
  primary key(contract_key,generation),
  unique(contract_key,policy_sha256),
  constraint communications_survival_contract_key_v1_chk check(contract_key='ct.communications.survival.v1'),
  constraint communications_survival_generation_v1_chk check(generation>0),
  constraint communications_survival_policy_sha_v1_chk check(policy_sha256 ~ '^[0-9a-f]{64}$'),
  constraint communications_survival_predecessor_sha_v1_chk check(predecessor_sha256 is null or predecessor_sha256 ~ '^[0-9a-f]{64}$'),
  constraint communications_survival_evidence_sha_v1_chk check(evidence_sha256 ~ '^[0-9a-f]{64}$'),
  constraint communications_survival_authority_v1_chk check(authority_ceiling in ('D0','D1','D2')),
  constraint communications_survival_acceptance_v1_chk check(successor_acceptance='PASS')
);

create or replace function integration_control.guard_communications_survival_contract_insert_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $function$
declare
  v_computed_sha text;
  v_prev integration_control.communications_survival_contract_versions_v1%rowtype;
  v_has_prev boolean:=false;
  v_key text;
  v_old_rank integer;
  v_new_rank integer;
  v_old_safety_rank bigint;
  v_new_safety_rank bigint;
  v_max_keys constant text[]:=array[
    'planner_max_silence_seconds','scheduler_max_silence_seconds',
    'provider_probe_max_age_seconds','capability_probe_max_age_seconds',
    'outbox_stale_seconds','terminal_projection_stale_seconds',
    'max_auth_failovers','max_cursor_resets','max_ambiguous_resends'
  ];
begin
  v_computed_sha:=encode(extensions.digest(convert_to(new.policy::text,'UTF8'),'sha256'),'hex');
  if new.contract_key<>'ct.communications.survival.v1' then
    raise exception using errcode='55000',message='communications_survival_contract_key_rejected';
  end if;
  if new.policy_sha256 is distinct from v_computed_sha then
    raise exception using errcode='55000',message='communications_survival_policy_sha_mismatch';
  end if;
  if jsonb_typeof(new.policy->'stages')<>'array'
     or jsonb_typeof(new.policy->'invariants')<>'object'
     or jsonb_typeof(new.policy->'thresholds')<>'object'
     or jsonb_typeof(new.policy->'tests')<>'object' then
    raise exception using errcode='55000',message='communications_survival_policy_shape_rejected';
  end if;

  foreach v_key in array array[
    'acquisition','research','promotion','eligibility','scheduling','outbox',
    'provider_transport','provider_readback','terminal_projection','reply_suppression'
  ] loop
    if not (new.policy->'stages' @> jsonb_build_array(v_key)) then
      raise exception using errcode='55000',message='communications_survival_required_stage_missing:'||v_key;
    end if;
  end loop;

  foreach v_key in array array[
    'penta_mail_is_sole_transport','penta_mailer_is_transport_subcomponent',
    'final_eligibility_required','suppression_required','authority_required',
    'provider_readback_required','ambiguous_outcome_no_blind_retry',
    'gmail_outlook_send_fallback_forbidden','credential_presence_not_health',
    'capability_specific_provider_health','credential_hopping_on_429_forbidden',
    'flow_health_required','no_silent_green','append_only_repair_evidence',
    'destructive_repair_forbidden','d3_human_reserved'
  ] loop
    if coalesce((new.policy->'invariants'->>v_key)::boolean,false) is not true then
      raise exception using errcode='55000',message='communications_survival_required_invariant_missing_or_false:'||v_key;
    end if;
  end loop;

  foreach v_key in array array[
    'scheduler_restore','stale_cursor_recovery','unsafe_ready_quarantine',
    'final_eligibility','mailgun_readback','terminal_projection',
    'ambiguous_outcome_no_blind_retry','no_direct_send'
  ] loop
    if coalesce((new.policy->'tests'->>v_key)::boolean,false) is not true then
      raise exception using errcode='55000',message='communications_survival_required_test_missing_or_false:'||v_key;
    end if;
  end loop;

  foreach v_key in array v_max_keys loop
    if nullif(new.policy->'thresholds'->>v_key,'') is null then
      raise exception using errcode='55000',message='communications_survival_threshold_missing:'||v_key;
    end if;
  end loop;

  if nullif(new.policy->'thresholds'->>'queue_low_watermark','') is null
     or nullif(new.policy->'thresholds'->>'queue_target_depth','') is null
     or nullif(new.policy->>'safety_rank','') is null then
    raise exception using errcode='55000',message='communications_survival_quality_fields_missing';
  end if;

  if (new.policy->'thresholds'->>'planner_max_silence_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'scheduler_max_silence_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'provider_probe_max_age_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'capability_probe_max_age_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'outbox_stale_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'terminal_projection_stale_seconds')::bigint<=0
     or (new.policy->'thresholds'->>'queue_low_watermark')::bigint<=0
     or (new.policy->'thresholds'->>'queue_target_depth')::bigint < (new.policy->'thresholds'->>'queue_low_watermark')::bigint
     or (new.policy->'thresholds'->>'max_auth_failovers')::bigint not between 0 and 1
     or (new.policy->'thresholds'->>'max_cursor_resets')::bigint not between 0 and 1
     or (new.policy->'thresholds'->>'max_ambiguous_resends')::bigint<>0
     or (new.policy->>'safety_rank')::bigint<=0 then
    raise exception using errcode='55000',message='communications_survival_thresholds_rejected';
  end if;

  select * into v_prev
  from integration_control.communications_survival_contract_versions_v1
  where contract_key=new.contract_key order by generation desc limit 1;
  v_has_prev:=found;

  if not v_has_prev then
    if new.generation<>1 or new.predecessor_sha256 is not null then
      raise exception using errcode='55000',message='communications_survival_initial_generation_rejected';
    end if;
  else
    if new.generation<=v_prev.generation then
      raise exception using errcode='55000',message='communications_survival_non_monotonic_generation_rejected';
    end if;
    if new.predecessor_sha256 is distinct from v_prev.policy_sha256 then
      raise exception using errcode='55000',message='communications_survival_predecessor_mismatch';
    end if;
    if not (v_prev.policy->'stages' <@ new.policy->'stages') then
      raise exception using errcode='55000',message='communications_survival_stage_regression_rejected';
    end if;
    for v_key in select key from jsonb_each(v_prev.policy->'invariants') where value='true'::jsonb loop
      if coalesce((new.policy->'invariants'->>v_key)::boolean,false) is not true then
        raise exception using errcode='55000',message='communications_survival_invariant_regression_rejected:'||v_key;
      end if;
    end loop;
    foreach v_key in array v_max_keys loop
      if (new.policy->'thresholds'->>v_key)::bigint > (v_prev.policy->'thresholds'->>v_key)::bigint then
        raise exception using errcode='55000',message='communications_survival_threshold_regression_rejected:'||v_key;
      end if;
    end loop;
    v_old_safety_rank:=(v_prev.policy->>'safety_rank')::bigint;
    v_new_safety_rank:=(new.policy->>'safety_rank')::bigint;
    if v_new_safety_rank<=v_old_safety_rank then
      raise exception using errcode='55000',message='communications_survival_safety_rank_must_increase';
    end if;
    v_old_rank:=case v_prev.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    v_new_rank:=case new.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    if v_new_rank>v_old_rank then
      raise exception using errcode='55000',message='communications_survival_authority_expansion_rejected';
    end if;
  end if;
  return new;
end;
$function$;

create or replace function integration_control.reject_communications_survival_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
begin
  raise exception using errcode='55000',message='communications_survival_history_is_append_only';
end;
$function$;

create trigger communications_survival_contract_insert_guard_v1
before insert on integration_control.communications_survival_contract_versions_v1
for each row execute function integration_control.guard_communications_survival_contract_insert_v1();
create trigger communications_survival_contract_immutable_v1
before update or delete on integration_control.communications_survival_contract_versions_v1
for each row execute function integration_control.reject_communications_survival_mutation_v1();
create trigger communications_survival_contract_no_truncate_v1
before truncate on integration_control.communications_survival_contract_versions_v1
for each statement execute function integration_control.reject_communications_survival_mutation_v1();

with policy_document as (
  select jsonb_build_object(
    'version','1.0.0','safety_rank',100,
    'stages',to_jsonb(array['acquisition','research','promotion','eligibility','scheduling','outbox','provider_transport','provider_readback','terminal_projection','reply_suppression']::text[]),
    'invariants',jsonb_build_object(
      'penta_mail_is_sole_transport',true,'penta_mailer_is_transport_subcomponent',true,
      'final_eligibility_required',true,'suppression_required',true,'authority_required',true,
      'provider_readback_required',true,'ambiguous_outcome_no_blind_retry',true,
      'gmail_outlook_send_fallback_forbidden',true,'credential_presence_not_health',true,
      'capability_specific_provider_health',true,'credential_hopping_on_429_forbidden',true,
      'flow_health_required',true,'no_silent_green',true,'append_only_repair_evidence',true,
      'destructive_repair_forbidden',true,'d3_human_reserved',true
    ),
    'thresholds',jsonb_build_object(
      'planner_max_silence_seconds',600,'scheduler_max_silence_seconds',600,
      'provider_probe_max_age_seconds',1200,'capability_probe_max_age_seconds',1200,
      'outbox_stale_seconds',600,'terminal_projection_stale_seconds',600,
      'queue_low_watermark',40,'queue_target_depth',80,
      'max_auth_failovers',1,'max_cursor_resets',1,'max_ambiguous_resends',0
    ),
    'tests',jsonb_build_object(
      'scheduler_restore',true,'stale_cursor_recovery',true,'unsafe_ready_quarantine',true,
      'final_eligibility',true,'mailgun_readback',true,'terminal_projection',true,
      'ambiguous_outcome_no_blind_retry',true,'no_direct_send',true
    ),
    'upgrade_rule','strictly_stronger_successor_only','diagnostic_owner','PentaSELF',
    'transport_owner','PentaMail','provider_component','PentaMailer',
    'direct_send_authority',false,'source_authority','ThriveBase migration ledger and governed GitHub source'
  ) policy
), evidence as (
  select policy,
    encode(extensions.digest(convert_to(policy::text,'UTF8'),'sha256'),'hex') policy_sha,
    encode(extensions.digest(convert_to(jsonb_build_object(
      'acquisition_pages_verified',2,'provider_http_status',200,'unsafe_ready_remaining',0,
      'mailgun_healthy_routes',3,'terminal_state','HEALTHY','missing_source_receipts',0,
      'unbound_terminal_receipts',0,'direct_send_performed',false
    )::text,'UTF8'),'sha256'),'hex') evidence_sha
  from policy_document
)
insert into integration_control.communications_survival_contract_versions_v1(
  contract_key,generation,semantic_version,policy,policy_sha256,predecessor_sha256,
  evidence_sha256,authority_ceiling,successor_acceptance,source_ref,migration_version
)
select 'ct.communications.survival.v1',1,'1.0.0',policy,policy_sha,null,evidence_sha,
  'D2','PASS','ct.communications.survival.v1@g1','communications_survival_contract_core_v1'
from evidence;

create table integration_control.communications_survival_cycles_v1 (
  cycle_id uuid primary key,
  contract_key text not null,
  contract_generation bigint not null,
  state_before text not null,
  state_after text not null,
  reasons jsonb not null default '[]'::jsonb,
  snapshot_before jsonb not null,
  snapshot_after jsonb not null,
  actions jsonb not null default '[]'::jsonb,
  dail_receipt jsonb not null,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint communications_survival_cycle_contract_fk_v1 foreign key(contract_key,contract_generation)
    references integration_control.communications_survival_contract_versions_v1(contract_key,generation),
  constraint communications_survival_cycle_time_v1_chk check(completed_at>=started_at),
  constraint communications_survival_cycle_reasons_v1_chk check(jsonb_typeof(reasons)='array'),
  constraint communications_survival_cycle_actions_v1_chk check(jsonb_typeof(actions)='array')
);
create index communications_survival_cycles_created_v1_idx on integration_control.communications_survival_cycles_v1(created_at desc);
create trigger communications_survival_cycles_immutable_v1
before update or delete on integration_control.communications_survival_cycles_v1
for each row execute function integration_control.reject_communications_survival_mutation_v1();
create trigger communications_survival_cycles_no_truncate_v1
before truncate on integration_control.communications_survival_cycles_v1
for each statement execute function integration_control.reject_communications_survival_mutation_v1();

alter table integration_control.communications_survival_contract_versions_v1 enable row level security;
alter table integration_control.communications_survival_cycles_v1 enable row level security;
revoke all on integration_control.communications_survival_contract_versions_v1 from public,anon,authenticated;
revoke all on integration_control.communications_survival_cycles_v1 from public,anon,authenticated;
grant select on integration_control.communications_survival_contract_versions_v1 to service_role;
grant select on integration_control.communications_survival_cycles_v1 to service_role;
create policy communications_survival_contract_service_read_v1 on integration_control.communications_survival_contract_versions_v1 for select to service_role using(true);
create policy communications_survival_cycles_service_read_v1 on integration_control.communications_survival_cycles_v1 for select to service_role using(true);

create or replace function integration_control.communications_survival_status_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','crm','public','pentatime','cron'
as $function$
declare
  v_campaign_id constant text:='ct.pentamarketer.locticians.claim.20260827.v1';
  v_contract integration_control.communications_survival_contract_versions_v1%rowtype;
  v_queue crm.penta_marketer_queue_policy_v1%rowtype;
  v_cap integration_control.provider_capability_health_v1%rowtype;
  v_desired integration_control.scheduler_desired_jobs_v2%rowtype;
  v_campaign jsonb:='{}'::jsonb; v_mailgun jsonb:='{}'::jsonb; v_terminal jsonb:='{}'::jsonb;
  v_reasons jsonb:='[]'::jsonb; v_state text; v_now timestamptz:=clock_timestamp();
  v_low integer:=40; v_target integer:=80; v_planner_max integer:=600; v_scheduler_max integer:=600;
  v_provider_probe_max integer:=1200; v_capability_probe_max integer:=1200; v_outbox_stale_seconds integer:=600;
  v_unsafe_ready integer:=0; v_eligible_now integer:=0; v_schedule_depth integer:=0;
  v_active_outbox integer:=0; v_stale_outbox integer:=0; v_discovery_active integer:=0; v_research_candidates integer:=0;
  v_provider_cursor_present boolean:=false; v_campaign_active boolean:=false;
  v_capability_unhealthy boolean:=true; v_transport_unhealthy boolean:=true; v_terminal_unhealthy boolean:=true;
  v_scheduler_drift boolean:=true; v_scheduler_stale boolean:=true; v_planner_stale boolean:=true;
  v_cron_jobid bigint; v_cron_schedule text; v_cron_command text; v_cron_active boolean; v_cron_last_success timestamptz;
  v_planner_jobid bigint; v_planner_last_success timestamptz; v_latest_mailgun_probe timestamptz; v_healthy_routes integer:=0;
begin
  select * into v_contract from integration_control.communications_survival_contract_versions_v1
  where contract_key='ct.communications.survival.v1' order by generation desc limit 1;
  if not found then
    return jsonb_build_object('service','ct.communications.survival.v1','state','HOLD_NO_CONTRACT',
      'reasons',jsonb_build_array('communications_survival_contract_missing'),'observed_at',v_now);
  end if;

  v_low:=(v_contract.policy->'thresholds'->>'queue_low_watermark')::integer;
  v_target:=(v_contract.policy->'thresholds'->>'queue_target_depth')::integer;
  v_planner_max:=(v_contract.policy->'thresholds'->>'planner_max_silence_seconds')::integer;
  v_scheduler_max:=(v_contract.policy->'thresholds'->>'scheduler_max_silence_seconds')::integer;
  v_provider_probe_max:=(v_contract.policy->'thresholds'->>'provider_probe_max_age_seconds')::integer;
  v_capability_probe_max:=(v_contract.policy->'thresholds'->>'capability_probe_max_age_seconds')::integer;
  v_outbox_stale_seconds:=(v_contract.policy->'thresholds'->>'outbox_stale_seconds')::integer;

  v_campaign:=crm.penta_marketer_campaign_status_v1(v_campaign_id);
  v_campaign_active:=coalesce((v_campaign->>'active')::boolean,false);
  select * into v_queue from crm.penta_marketer_queue_policy_v1 where campaign_id=v_campaign_id and active=true;
  if found then
    v_low:=greatest(v_low,v_queue.low_watermark); v_target:=greatest(v_target,v_queue.target_depth);
    v_provider_cursor_present:=nullif(v_queue.provider_page_cursor,'') is not null;
  else v_reasons:=v_reasons||jsonb_build_array('queue_policy_missing_or_inactive'); end if;

  select * into v_cap from integration_control.provider_capability_health_v1
  where service_id='locticians' and capability_key='member_find';
  v_capability_unhealthy:=not found or v_cap.health_state<>'HEALTHY'
    or v_cap.credential_verified is distinct from true or v_cap.capability_verified is distinct from true
    or v_cap.last_success_at is null or v_cap.last_success_at<v_now-make_interval(secs=>v_capability_probe_max);

  select count(*) into v_unsafe_ready from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect' and x.copy_state='ready' and not crm.public_business_email_safe_v2(x.email);
  select count(*) into v_eligible_now from crm.outreach_contacts_v1 x
  where x.relationship_state='prospect' and coalesce((crm.penta_marketer_eligibility_v1(x.contact_id,'cold')->>'eligible')::boolean,false);
  select count(*) into v_schedule_depth from crm.outreach_schedule_v1 s
  where s.campaign_ref=v_campaign_id and s.state in ('scheduled','enqueued','ready','claimed','queued');
  select count(*) into v_active_outbox from public.penta_mail_outbox_v1 o
  where o.state in ('pending','queued','retry','leased','claimed','sending');
  select count(*) into v_stale_outbox from public.penta_mail_outbox_v1 o
  where o.state in ('pending','queued','retry','leased','claimed','sending')
    and coalesce(o.lease_expires_at,o.available_at,o.created_at)<v_now-make_interval(secs=>v_outbox_stale_seconds);
  select count(*) into v_discovery_active from crm.contact_discovery_queue_v1 q where q.state in ('pending','retry','processing','leased');
  select count(*) into v_research_candidates from crm.prospects p where crm.locticians_research_candidate_v1(p);

  select * into v_desired from integration_control.scheduler_desired_jobs_v2 where jobname='ct-communications-survival-v1';
  if found then
    select j.jobid,j.schedule,j.command,j.active into v_cron_jobid,v_cron_schedule,v_cron_command,v_cron_active
    from cron.job j where j.jobname='ct-communications-survival-v1' order by j.jobid desc limit 1;
    v_scheduler_drift:=v_cron_jobid is null or v_cron_schedule is distinct from v_desired.schedule
      or v_cron_command is distinct from v_desired.command or v_cron_active is distinct from true
      or v_desired.active is distinct from true or v_desired.allow_auto_restore is distinct from true;
    if v_cron_jobid is not null then
      select max(d.start_time) filter(where d.status='succeeded') into v_cron_last_success
      from cron.job_run_details d where d.jobid=v_cron_jobid;
    end if;
    v_scheduler_stale:=case when v_cron_last_success is null
      then v_desired.created_at<v_now-make_interval(secs=>v_scheduler_max)
      else v_cron_last_success<v_now-make_interval(secs=>v_scheduler_max) end;
  end if;

  select j.jobid into v_planner_jobid from cron.job j
  where j.jobname='ct-outreach-daily-planner-v1' and j.active=true order by j.jobid desc limit 1;
  if v_planner_jobid is not null then
    select max(d.start_time) filter(where d.status='succeeded') into v_planner_last_success
    from cron.job_run_details d where d.jobid=v_planner_jobid;
  end if;
  v_planner_stale:=v_planner_jobid is null or v_planner_last_success is null
    or v_planner_last_success<v_now-make_interval(secs=>v_planner_max);

  v_mailgun:=public.penta_mail_mailgun_route_status_v1();
  v_healthy_routes:=coalesce((v_mailgun->>'healthy_routes')::integer,0);
  select max(r.last_checked_at) into v_latest_mailgun_probe from integration_control.penta_mail_mailgun_routes_v1 r
  where r.enabled=true and r.health_state='healthy';
  v_transport_unhealthy:=v_healthy_routes<1 or v_latest_mailgun_probe is null
    or v_latest_mailgun_probe<v_now-make_interval(secs=>v_provider_probe_max);

  v_terminal:=integration_control.penta_mail_terminal_projection_status_v1();
  v_terminal_unhealthy:=coalesce(v_terminal->>'state','UNKNOWN')<>'HEALTHY'
    or coalesce((v_terminal->>'missing_source_receipts')::integer,0)>0
    or coalesce((v_terminal->>'unbound_terminal_receipts')::integer,0)>0;

  if v_scheduler_drift or v_scheduler_stale then v_state:='HOLD_SCHEDULER_DRIFT'; v_reasons:=v_reasons||jsonb_build_array('survival_scheduler_missing_drifted_or_stale');
  elsif v_planner_stale then v_state:='HOLD_PLANNER_STALE'; v_reasons:=v_reasons||jsonb_build_array('penta_marketer_planner_missing_or_stale');
  elsif v_unsafe_ready>0 then v_state:='HOLD_UNSAFE_READY_STATE'; v_reasons:=v_reasons||jsonb_build_array('unsafe_recipient_retained_ready_state');
  elsif v_transport_unhealthy then v_state:='HOLD_TRANSPORT_UNHEALTHY'; v_reasons:=v_reasons||jsonb_build_array('no_fresh_healthy_mailgun_route');
  elsif v_stale_outbox>0 then v_state:='HOLD_OUTBOX_STALLED'; v_reasons:=v_reasons||jsonb_build_array('stale_pentamail_outbox_work');
  elsif v_terminal_unhealthy then v_state:='HOLD_TERMINAL_PROJECTION'; v_reasons:=v_reasons||jsonb_build_array('terminal_projection_or_dail_binding_unhealthy');
  elsif v_capability_unhealthy then v_state:='HOLD_ACQUISITION_CAPABILITY'; v_reasons:=v_reasons||jsonb_build_array('member_find_capability_missing_unhealthy_or_stale');
  elsif v_schedule_depth>0 or v_active_outbox>0 then v_state:='FLOWING'; v_reasons:=v_reasons||jsonb_build_array('eligible_work_advancing');
  elsif not v_campaign_active then v_state:='IDLE_NO_DEMAND'; v_reasons:=v_reasons||jsonb_build_array('campaign_not_active');
  elsif v_discovery_active>0 or v_eligible_now>0 or v_provider_cursor_present then v_state:='REPLENISHING'; v_reasons:=v_reasons||jsonb_build_array('bounded_acquisition_research_or_eligibility_work_available');
  else v_state:='INVENTORY_EXHAUSTED'; v_reasons:=v_reasons||jsonb_build_array('no_lawful_unattempted_cohort_or_due_acquisition_work'); end if;

  return jsonb_build_object(
    'service','ct.communications.survival.v1','state',v_state,'reasons',v_reasons,
    'contract',jsonb_build_object('generation',v_contract.generation,'semantic_version',v_contract.semantic_version,
      'policy_sha256',v_contract.policy_sha256,'evidence_sha256',v_contract.evidence_sha256,
      'authority_ceiling',v_contract.authority_ceiling,'safety_rank',(v_contract.policy->>'safety_rank')::bigint,
      'upgrade_rule',v_contract.policy->>'upgrade_rule'),
    'campaign',v_campaign,
    'flow',jsonb_build_object('eligible_now',v_eligible_now,'schedule_depth',v_schedule_depth,
      'active_outbox',v_active_outbox,'stale_outbox',v_stale_outbox,'unsafe_ready',v_unsafe_ready,
      'discovery_active',v_discovery_active,'research_candidates',v_research_candidates,
      'low_watermark',v_low,'target_depth',v_target),
    'acquisition',jsonb_build_object('provider_cursor_present',v_provider_cursor_present,
      'provider_current_page',v_queue.provider_current_page,'provider_total',v_queue.provider_total,
      'capability_state',v_cap.health_state,'capability_last_success_at',v_cap.last_success_at,
      'credential_verified',v_cap.credential_verified,'capability_verified',v_cap.capability_verified,
      'capability_unhealthy',v_capability_unhealthy,'raw_secret_exposed',false),
    'scheduler',jsonb_build_object('desired_present',v_desired.jobname is not null,'actual_jobid',v_cron_jobid,
      'drift',v_scheduler_drift,'stale',v_scheduler_stale,'last_success_at',v_cron_last_success,
      'planner_jobid',v_planner_jobid,'planner_last_success_at',v_planner_last_success,'planner_stale',v_planner_stale),
    'transport',jsonb_build_object('mailgun',v_mailgun,'healthy_routes',v_healthy_routes,
      'latest_route_probe',v_latest_mailgun_probe,'credential_presence_treated_as_health',false),
    'terminal_projection',v_terminal,'direct_send_authority',false,'gmail_outlook_send_fallback',false,
    'destructive_repair_authority',false,'observed_at',v_now
  );
end;
$function$;

create or replace function public.penta_mail_survival_status_v1()
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control'
as $function$
declare v_role text:=coalesce(nullif(current_setting('request.jwt.claim.role',true),''),coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''));
begin
  if session_user not in ('postgres','supabase_admin') and current_user not in ('postgres','service_role') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  return integration_control.communications_survival_status_v1();
end;
$function$;

create or replace function integration_control.communications_survival_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','crm','public','pentatime','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce(nullif(current_setting('request.jwt.claim.role',true),''),coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''));
  v_cycle_id uuid:=gen_random_uuid(); v_started_at timestamptz:=clock_timestamp(); v_completed_at timestamptz;
  v_contract_generation bigint; v_before jsonb; v_mid jsonb; v_after jsonb;
  v_scheduler jsonb:='{}'::jsonb; v_planner jsonb:='{}'::jsonb; v_actions jsonb:='[]'::jsonb;
  v_dail jsonb:='{}'::jsonb; v_dail_payload jsonb; v_quarantined integer:=0; v_should_plan boolean:=false;
  v_campaign_active boolean:=false; v_queue_depth integer:=0; v_discovery_active integer:=0; v_low integer:=40;
begin
  if session_user not in ('postgres','supabase_admin') and current_user not in ('postgres','service_role') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.communications.survival.v1',0)) then
    return jsonb_build_object('state','LOCKED','reason','another_survival_cycle_is_active','direct_send_authority',false);
  end if;
  select max(generation) into v_contract_generation from integration_control.communications_survival_contract_versions_v1 where contract_key='ct.communications.survival.v1';
  v_before:=integration_control.communications_survival_status_v1();

  update crm.outreach_contacts_v1
  set copy_state='hold',research_state='hold',claimable_profile=false,risk_hold_at=coalesce(risk_hold_at,clock_timestamp()),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('communications_safety_hold_v1',jsonb_build_object(
        'reason','public_business_email_unsafe','detected_at',clock_timestamp(),
        'email_domain',lower(split_part(coalesce(email,''),'@',2)),
        'email_sha256',encode(extensions.digest(convert_to(lower(btrim(coalesce(email,''))),'UTF8'),'sha256'),'hex'),
        'raw_email_copied',false,'auto_clear_forbidden',true,'survival_cycle',v_cycle_id))
  where relationship_state='prospect' and copy_state='ready' and not crm.public_business_email_safe_v2(email);
  get diagnostics v_quarantined=row_count;
  v_actions:=v_actions||jsonb_build_array(jsonb_build_object('action','unsafe_ready_quarantine','rows',v_quarantined,'destructive',false,'direct_send',false));

  v_scheduler:=integration_control.scheduler_permanence_reconcile_v2();
  v_actions:=v_actions||jsonb_build_array(jsonb_build_object('action','scheduler_permanence_reconcile','result',v_scheduler,'destructive',false,'direct_send',false));
  v_mid:=integration_control.communications_survival_status_v1();
  v_campaign_active:=coalesce((v_mid->'campaign'->>'active')::boolean,false);
  v_queue_depth:=coalesce((v_mid->'flow'->>'schedule_depth')::integer,0);
  v_discovery_active:=coalesce((v_mid->'flow'->>'discovery_active')::integer,0);
  v_low:=coalesce((v_mid->'flow'->>'low_watermark')::integer,40);
  v_should_plan:=v_campaign_active and v_queue_depth<v_low and (v_mid->>'state' in ('REPLENISHING','INVENTORY_EXHAUSTED','FLOWING') or v_discovery_active>0);
  if v_should_plan then v_planner:=pentatime.execute_guarded_v3('penta_marketer_plan');
  else v_planner:=jsonb_build_object('state','SKIPPED','reason','no_safe_bounded_planner_work_due','direct_send',false); end if;
  v_actions:=v_actions||jsonb_build_array(jsonb_build_object('action','bounded_penta_marketer_plan','invoked',v_should_plan,'result',v_planner,'direct_send',false));

  v_after:=integration_control.communications_survival_status_v1(); v_completed_at:=clock_timestamp();
  v_dail_payload:=jsonb_build_object('cycle_id',v_cycle_id,'contract_generation',v_contract_generation,
    'state_before',v_before->>'state','state_after',v_after->>'state','flow_before',v_before->'flow','flow_after',v_after->'flow',
    'actions',v_actions,'direct_send_authority',false,'gmail_outlook_send_fallback',false,
    'suppression_weakened',false,'credential_exposed',false,'destructive_repair',false,'authority_expanded',false,'observed_at',v_completed_at);
  v_dail:=chlom_runtime.append_dail_event('communications.survival.cycle.completed','communications_survival_cycle',v_cycle_id::text,
    v_dail_payload,'PentaSELF/PentaMail',null,'PentaSELF','1.0.0',v_cycle_id::text,'communications_survival',
    'ct.communications.survival.v1',null,'internal');
  insert into integration_control.communications_survival_cycles_v1(
    cycle_id,contract_key,contract_generation,state_before,state_after,reasons,snapshot_before,snapshot_after,actions,dail_receipt,started_at,completed_at
  ) values (v_cycle_id,'ct.communications.survival.v1',v_contract_generation,coalesce(v_before->>'state','UNKNOWN'),
    coalesce(v_after->>'state','UNKNOWN'),coalesce(v_after->'reasons','[]'::jsonb),v_before,v_after,v_actions,v_dail,v_started_at,v_completed_at);
  return jsonb_build_object('state','COMPLETE','cycle_id',v_cycle_id,'contract_generation',v_contract_generation,
    'state_before',v_before->>'state','state_after',v_after->>'state','actions',v_actions,'dail_receipt',v_dail,
    'direct_send_authority',false,'completed_at',v_completed_at);
end;
$function$;

create or replace function pentatime.executor_communications_survival_v1()
returns jsonb language sql security definer set search_path to 'pg_catalog','integration_control'
as $function$ select integration_control.communications_survival_cycle_v1(); $function$;

revoke all on function integration_control.communications_survival_status_v1() from public,anon,authenticated;
revoke all on function integration_control.communications_survival_cycle_v1() from public,anon,authenticated;
revoke all on function public.penta_mail_survival_status_v1() from public,anon,authenticated;
revoke all on function pentatime.executor_communications_survival_v1() from public,anon,authenticated;
grant execute on function integration_control.communications_survival_status_v1() to service_role;
grant execute on function integration_control.communications_survival_cycle_v1() to service_role;
grant execute on function public.penta_mail_survival_status_v1() to service_role;
grant execute on function pentatime.executor_communications_survival_v1() to service_role;