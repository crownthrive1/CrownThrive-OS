-- PentaSuper task-runtime hardening v2
-- Additive, fail-closed implementation candidate. This migration does not certify production.

create table if not exists penta_task_runtime.acceptance_runs_v1 (
  run_id uuid primary key default gen_random_uuid(),
  run_kind text not null default 'task_runtime_canary',
  state text not null check (state in ('running','pass','fail','hold')),
  actor_ref text not null,
  source_ref text not null,
  snapshot_id uuid references penta_task_runtime.snapshots_v1(snapshot_id),
  dnd_lease_id uuid,
  decision_dail_event_id uuid,
  execution_dail_event_id uuid,
  evidence jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default clock_timestamp(),
  completed_at timestamptz,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_task_runtime.acceptance_assertions_v1 (
  assertion_id uuid primary key default gen_random_uuid(),
  run_id uuid not null references penta_task_runtime.acceptance_runs_v1(run_id),
  assertion_key text not null,
  passed boolean not null,
  observed jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  unique(run_id,assertion_key)
);

create table if not exists penta_task_runtime.restore_canary_v1 (
  canary_key text primary key,
  canary_value text not null,
  generation bigint not null default 1,
  updated_at timestamptz not null default clock_timestamp()
);
insert into penta_task_runtime.restore_canary_v1(canary_key,canary_value,generation)
values('task-runtime','baseline',1)
on conflict(canary_key) do nothing;

create or replace function penta_task_runtime.guard_acceptance_run_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog'
as $$
begin
  if tg_op='DELETE' then raise exception 'acceptance_history_append_only'; end if;
  if old.state in ('pass','fail','hold') then raise exception 'terminal_acceptance_run_immutable'; end if;
  if new.run_id<>old.run_id or new.actor_ref<>old.actor_ref or new.source_ref<>old.source_ref or new.started_at<>old.started_at or new.created_at<>old.created_at then
    raise exception 'acceptance_run_identity_immutable';
  end if;
  if new.state='running' then raise exception 'invalid_acceptance_transition'; end if;
  new.updated_at:=clock_timestamp();
  if new.completed_at is null then new.completed_at:=clock_timestamp(); end if;
  return new;
end;
$$;

create or replace function penta_task_runtime.reject_acceptance_assertion_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog'
as $$
begin
  raise exception 'acceptance_assertion_append_only';
end;
$$;

drop trigger if exists penta_task_runtime_acceptance_run_guard_v1 on penta_task_runtime.acceptance_runs_v1;
create trigger penta_task_runtime_acceptance_run_guard_v1
before update or delete on penta_task_runtime.acceptance_runs_v1
for each row execute function penta_task_runtime.guard_acceptance_run_v1();

drop trigger if exists penta_task_runtime_acceptance_assertion_guard_v1 on penta_task_runtime.acceptance_assertions_v1;
create trigger penta_task_runtime_acceptance_assertion_guard_v1
before update or delete on penta_task_runtime.acceptance_assertions_v1
for each row execute function penta_task_runtime.reject_acceptance_assertion_mutation_v1();

alter table penta_task_runtime.acceptance_runs_v1 enable row level security;
alter table penta_task_runtime.acceptance_runs_v1 force row level security;
alter table penta_task_runtime.acceptance_assertions_v1 enable row level security;
alter table penta_task_runtime.acceptance_assertions_v1 force row level security;
alter table penta_task_runtime.restore_canary_v1 enable row level security;
alter table penta_task_runtime.restore_canary_v1 force row level security;

revoke all on penta_task_runtime.acceptance_runs_v1 from public,anon,authenticated;
revoke all on penta_task_runtime.acceptance_assertions_v1 from public,anon,authenticated;
revoke all on penta_task_runtime.restore_canary_v1 from public,anon,authenticated;
grant select,insert,update on penta_task_runtime.acceptance_runs_v1 to service_role;
grant select,insert on penta_task_runtime.acceptance_assertions_v1 to service_role;
grant select,insert,update on penta_task_runtime.restore_canary_v1 to service_role;

create policy penta_task_runtime_acceptance_runs_service_v1 on penta_task_runtime.acceptance_runs_v1 for all to service_role using(true) with check(true);
create policy penta_task_runtime_acceptance_assertions_select_v1 on penta_task_runtime.acceptance_assertions_v1 for select to service_role using(true);
create policy penta_task_runtime_acceptance_assertions_insert_v1 on penta_task_runtime.acceptance_assertions_v1 for insert to service_role with check(true);
create policy penta_task_runtime_restore_canary_service_v1 on penta_task_runtime.restore_canary_v1 for all to service_role using(true) with check(true);

create or replace function penta_task_runtime.verify_snapshot_v1(p_snapshot_id uuid,p_current_state jsonb)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_task_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_row penta_task_runtime.snapshots_v1%rowtype;
  v_hash text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_row from penta_task_runtime.snapshots_v1 where snapshot_id=p_snapshot_id;
  if not found then return jsonb_build_object('ok',false,'state','snapshot_not_found'); end if;
  v_hash:=encode(extensions.digest(convert_to(p_current_state::text,'UTF8'),'sha256'),'hex');
  return jsonb_build_object('ok',true,'snapshot_id',p_snapshot_id,'current_sha256',v_hash,'snapshot_sha256',v_row.source_sha256,'matches_snapshot',v_hash=v_row.source_sha256,'rollback_sha256',v_row.rollback_sha256);
end;
$$;

-- Safe transport codec for machine-readable archives. This is NOT encryption and creates no secrecy claim.
create or replace function penta_translate.encode_transport_v1(p_source_text text)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_hash text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_source_text is null then raise exception 'source_text_required'; end if;
  v_hash:=encode(extensions.digest(convert_to(p_source_text,'UTF8'),'sha256'),'hex');
  return jsonb_build_object('codec','ct.penta.translate.utf8-base64.v1','confidentiality',false,'source_sha256',v_hash,'body_b64',encode(convert_to(p_source_text,'UTF8'),'base64'));
end;
$$;

create or replace function penta_translate.decode_transport_v1(p_envelope jsonb)
returns text
language plpgsql
security definer
set search_path='pg_catalog','extensions'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_text text;
  v_hash text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if coalesce(p_envelope->>'codec','')<>'ct.penta.translate.utf8-base64.v1' then raise exception 'unsupported_transport_codec'; end if;
  if coalesce(p_envelope->>'source_sha256','') !~ '^[0-9a-f]{64}$' then raise exception 'invalid_source_sha256'; end if;
  v_text:=convert_from(decode(coalesce(p_envelope->>'body_b64',''),'base64'),'UTF8');
  v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  if v_hash<>p_envelope->>'source_sha256' then raise exception 'transport_integrity_mismatch'; end if;
  return v_text;
end;
$$;

create or replace function penta_translate.run_round_trip_canary_v1(p_actor_ref text default 'ct.relay.agent-c')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_translate'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_source text:='CrownThrive PentaTranslate deterministic canary v1';
  v_envelope jsonb;
  v_decoded text;
  v_source_hash text;
  v_projection_hash text;
  v_record jsonb;
  v_idem text;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  v_envelope:=penta_translate.encode_transport_v1(v_source);
  v_decoded:=penta_translate.decode_transport_v1(v_envelope);
  if v_decoded<>v_source then raise exception 'round_trip_failed'; end if;
  v_source_hash:=v_envelope->>'source_sha256';
  v_projection_hash:=encode(extensions.digest(convert_to(v_envelope::text,'UTF8'),'sha256'),'hex');
  v_idem:='ct.penta.translate.canary.v1:'||v_source_hash;
  v_record:=penta_translate.record_projection_v1(v_idem,'internal://penta-translate/canary/source',v_source_hash,'internal://penta-translate/canary/projection',v_projection_hash,'en','penta-machine','machine','ct.penta.translate.encode.v1','ct.penta.translate.utf8-base64.v1',true,1.0000,'internal',jsonb_build_object('canary',true,'confidentiality',false,'protected_mapping_exposed',false),p_actor_ref,'ctcorr:penta-translate:canary-v1');
  return jsonb_build_object('ok',true,'round_trip_verified',true,'source_sha256',v_source_hash,'projection_sha256',v_projection_hash,'record',v_record,'confidentiality',false);
end;
$$;

insert into penta_dnd.programs_v1(program_id,canonical_name,semantic_version,state,enabled,cron_expression,recipient,scope_kind,scope_ref,current_phase_key,next_phase_key,pass_counter,dnd_ttl_seconds,redundancy_profile,auto_renew,authority_ceiling,d3_human_reserved,no_silent_delete,metadata)
values('ct.program.penta-super-build-dnd','PentaSuper Scoped Build DND','1.0.0','active',true,'0 0 31 2 *','contact@crownthrive.com','penta_super_build','ct.penta.super.v1','source_discovery','certify_hold_classify',0,1800,'hot-warm-dual-cold-v1',false,'D2',true,true,jsonb_build_object('scheduler_created',false,'cron_expression_inert_metadata_only',true,'global_maintenance',false,'priority_required',true,'ttl_required',true,'snapshot_required',true,'no_self_certification',true,'source_ref','PR#1388/supabase/migrations/20260830083000_penta_super_runtime_controls_v2.sql'))
on conflict(program_id) do update set
  canonical_name=excluded.canonical_name,
  semantic_version=excluded.semantic_version,
  state=excluded.state,
  enabled=excluded.enabled,
  cron_expression=excluded.cron_expression,
  recipient=excluded.recipient,
  scope_kind=excluded.scope_kind,
  scope_ref=excluded.scope_ref,
  current_phase_key=excluded.current_phase_key,
  next_phase_key=excluded.next_phase_key,
  dnd_ttl_seconds=excluded.dnd_ttl_seconds,
  auto_renew=excluded.auto_renew,
  authority_ceiling=excluded.authority_ceiling,
  d3_human_reserved=excluded.d3_human_reserved,
  no_silent_delete=excluded.no_silent_delete,
  metadata=penta_dnd.programs_v1.metadata||excluded.metadata,
  updated_at=clock_timestamp();

create or replace function penta_task_runtime.run_acceptance_canary_v2(p_actor_ref text default 'ct.relay.agent-c')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_task_runtime','penta_dnd','penta_translate','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_run uuid:=gen_random_uuid();
  v_scope text:='ct.penta.super.v1:acceptance:'||v_run::text;
  v_scope_other text:=v_scope||':unrelated';
  v_dnd jsonb;
  v_conflict jsonb;
  v_unrelated jsonb;
  v_snapshot jsonb;
  v_snapshot_id uuid;
  v_drift jsonb;
  v_restored jsonb;
  v_translate jsonb;
  v_decision jsonb;
  v_execution jsonb;
  v_pass boolean;
  v_before jsonb;
  v_after jsonb;
  v_assertions integer;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  insert into penta_task_runtime.acceptance_runs_v1(run_id,state,actor_ref,source_ref)
  values(v_run,'running',p_actor_ref,'PR#1388/supabase/migrations/20260830083000_penta_super_runtime_controls_v2.sql');

  v_decision:=chlom_runtime.append_dail_event('penta.super.task-runtime.acceptance.started','penta_super_acceptance',v_run::text,jsonb_build_object('scope',v_scope,'three_dail_logical_phase','DAIL-DECISION','production_certification',false),p_actor_ref,null,'PentaSuper','1.0.0','ctcorr:penta-super:acceptance:'||v_run::text,null,'D2',null,'internal');

  v_dnd:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','acceptance_canary',v_scope,p_actor_ref,'task runtime acceptance',60,900,'acceptance_canary','independent_verification');
  if coalesce((v_dnd->>'ok')::boolean,false)=false then raise exception 'acceptance_dnd_unavailable: %',v_dnd; end if;

  v_conflict:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','acceptance_canary',v_scope,'ct.relay.agent-b','collision canary',40,900,'acceptance_canary','release');
  v_unrelated:=penta_dnd.open_lease_v2('ct.program.penta-super-build-dnd','acceptance_canary',v_scope_other,'ct.relay.agent-b','unrelated continuity canary',40,900,'acceptance_canary','release');

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'dnd_exact_scope_acquired',coalesce((v_dnd->>'ok')::boolean,false),v_dnd),
    (v_run,'dnd_conflicting_owner_blocked',coalesce((v_conflict->>'ok')::boolean,false)=false and v_conflict->>'state'='held_by_active_owner',v_conflict),
    (v_run,'dnd_unrelated_scope_continues',coalesce((v_unrelated->>'ok')::boolean,false),v_unrelated),
    (v_run,'dnd_ttl_bounded',(v_dnd->>'expires_at')::timestamptz<=clock_timestamp()+interval '16 minutes',jsonb_build_object('expires_at',v_dnd->>'expires_at','requested_seconds',900)),
    (v_run,'dnd_priority_attached',coalesce((v_dnd->>'priority')::integer,-1)=60,jsonb_build_object('priority',v_dnd->>'priority','preemption',false));

  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation) into v_before from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';
  v_snapshot:=penta_task_runtime.capture_snapshot_v1('restore_canary','penta_task_runtime.restore_canary_v1:task-runtime',v_before,jsonb_build_object('restore_to',v_before),'PentaSnapshot','D1','ctcorr:penta-super:restore-canary:'||v_run::text);
  v_snapshot_id:=(v_snapshot->>'snapshot_id')::uuid;
  update penta_task_runtime.restore_canary_v1 set canary_value='mutated:'||v_run::text,generation=generation+1,updated_at=clock_timestamp() where canary_key='task-runtime';
  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation) into v_after from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';
  v_drift:=penta_task_runtime.verify_snapshot_v1(v_snapshot_id,v_after);
  update penta_task_runtime.restore_canary_v1 set canary_value=v_before->>'canary_value',generation=(v_before->>'generation')::bigint,updated_at=clock_timestamp() where canary_key='task-runtime';
  select jsonb_build_object('canary_key',canary_key,'canary_value',canary_value,'generation',generation) into v_after from penta_task_runtime.restore_canary_v1 where canary_key='task-runtime';
  v_restored:=penta_task_runtime.verify_snapshot_v1(v_snapshot_id,v_after);

  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'snapshot_captured',coalesce((v_snapshot->>'ok')::boolean,false),v_snapshot-'dail'),
    (v_run,'snapshot_drift_detected',coalesce((v_drift->>'matches_snapshot')::boolean,true)=false,v_drift),
    (v_run,'restore_canary_exact',coalesce((v_restored->>'matches_snapshot')::boolean,false),v_restored);

  v_translate:=penta_translate.run_round_trip_canary_v1(p_actor_ref);
  insert into penta_task_runtime.acceptance_assertions_v1(run_id,assertion_key,passed,observed) values
    (v_run,'translate_transport_round_trip',coalesce((v_translate->>'round_trip_verified')::boolean,false),v_translate-'record'),
    (v_run,'translate_transport_no_confidentiality_claim',coalesce((v_translate->>'confidentiality')::boolean,true)=false,jsonb_build_object('confidentiality',v_translate->'confidentiality'));

  if coalesce(v_unrelated->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_unrelated->>'lease_id')::uuid,'acceptance_unrelated_complete'); end if;
  if coalesce(v_dnd->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'acceptance_complete'); end if;

  select bool_and(passed),count(*) into v_pass,v_assertions from penta_task_runtime.acceptance_assertions_v1 where run_id=v_run;
  v_execution:=chlom_runtime.append_dail_event('penta.super.task-runtime.acceptance.completed','penta_super_acceptance',v_run::text,jsonb_build_object('passed',coalesce(v_pass,false),'assertion_count',v_assertions,'snapshot_id',v_snapshot_id,'three_dail_logical_phase','DAIL-EXECUTION','production_certification',false),p_actor_ref,null,'PentaSuper','1.0.0','ctcorr:penta-super:acceptance:'||v_run::text,v_decision->>'event_id','D2',null,'internal');
  update penta_task_runtime.acceptance_runs_v1 set state=case when v_pass then 'pass' else 'fail' end,snapshot_id=v_snapshot_id,dnd_lease_id=(v_dnd->>'lease_id')::uuid,decision_dail_event_id=(v_decision->>'event_id')::uuid,execution_dail_event_id=(v_execution->>'event_id')::uuid,evidence=jsonb_build_object('translation_projection_id',v_translate#>>'{record,projection_id}','independent_certification_required',true,'production_certified',false) where run_id=v_run;
  return jsonb_build_object('ok',coalesce(v_pass,false),'run_id',v_run,'assertion_count',v_assertions,'state',case when v_pass then 'pass' else 'fail' end,'snapshot_id',v_snapshot_id,'dail_decision',v_decision,'dail_execution',v_execution,'production_certified',false);
exception when others then
  begin
    if coalesce(v_unrelated->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_unrelated->>'lease_id')::uuid,'acceptance_exception'); end if;
    if coalesce(v_dnd->>'lease_id','')<>'' then perform penta_dnd.close_lease_v1((v_dnd->>'lease_id')::uuid,'acceptance_exception'); end if;
  exception when others then null; end;
  update penta_task_runtime.acceptance_runs_v1 set state='fail',evidence=jsonb_build_object('error_class',sqlstate,'error_message',left(sqlerrm,400),'production_certified',false) where run_id=v_run and state='running';
  raise;
end;
$$;

create or replace function penta_task_runtime.status_v2()
returns jsonb
language sql
security definer
set search_path='pg_catalog','penta_task_runtime','penta_translate','penta_dnd','institutional_federation'
as $$
select penta_task_runtime.status_v1() || jsonb_build_object(
  'acceptance_latest',(select to_jsonb(r) from penta_task_runtime.acceptance_runs_v1 r order by started_at desc limit 1),
  'acceptance_pass_count',(select count(*) from penta_task_runtime.acceptance_runs_v1 where state='pass'),
  'translation_round_trip_verified_count',(select count(*) from penta_translate.projections_v1 where round_trip_verified=true),
  'penta_super_dnd_program_registered',exists(select 1 from penta_dnd.programs_v1 where program_id='ct.program.penta-super-build-dnd' and enabled=true),
  'production_certified',false
); $$;

revoke all on function penta_task_runtime.verify_snapshot_v1(uuid,jsonb) from public,anon,authenticated;
revoke all on function penta_translate.encode_transport_v1(text) from public,anon,authenticated;
revoke all on function penta_translate.decode_transport_v1(jsonb) from public,anon,authenticated;
revoke all on function penta_translate.run_round_trip_canary_v1(text) from public,anon,authenticated;
revoke all on function penta_task_runtime.run_acceptance_canary_v2(text) from public,anon,authenticated;
revoke all on function penta_task_runtime.status_v2() from public,anon,authenticated;
grant execute on function penta_task_runtime.verify_snapshot_v1(uuid,jsonb) to service_role;
grant execute on function penta_translate.encode_transport_v1(text) to service_role;
grant execute on function penta_translate.decode_transport_v1(jsonb) to service_role;
grant execute on function penta_translate.run_round_trip_canary_v1(text) to service_role;
grant execute on function penta_task_runtime.run_acceptance_canary_v2(text) to service_role;
grant execute on function penta_task_runtime.status_v2() to service_role;

update penta_task_runtime.components_v1 set metadata=metadata||jsonb_build_object('runtime_controls_v2',true,'acceptance_canary','penta_task_runtime.run_acceptance_canary_v2'),updated_at=clock_timestamp()
where component_id in ('ct.penta.dnd.v1','ct.penta.snapshot.v1','ct.penta.lease.v1','ct.penta.collision.v1');
update penta_task_runtime.components_v1 set metadata=metadata||jsonb_build_object('runtime_controls_v2',true,'transport_codec','ct.penta.translate.utf8-base64.v1','transport_confidentiality',false,'round_trip_canary','penta_translate.run_round_trip_canary_v1'),updated_at=clock_timestamp()
where component_id='ct.penta.translate.v1';

select chlom_runtime.append_dail_event('penta.super.runtime-controls.v2.installed','penta_super_runtime','ct.penta.task-runtime-family.v1',jsonb_build_object('dnd_program','ct.program.penta-super-build-dnd','acceptance_runtime','penta_task_runtime.run_acceptance_canary_v2','translation_transport','ct.penta.translate.utf8-base64.v1','translation_transport_confidentiality',false,'three_dail_logical_phase','DAIL-EXECUTION','independent_certification_required',true,'production_certified',false),'ct.relay.agent-c',null,'ct.relay.agent-c','2.0.0','ctcorr:penta-super:runtime-controls-v2',null,'D2',null,'internal');