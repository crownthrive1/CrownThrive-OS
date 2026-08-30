-- CrownThrive PentaSuper task-runtime family v1
-- Additive runtime implementation candidate for PentaDND/PentaSnapshot/PentaLease/PentaCollision/PentaTranslate.
-- Production certification remains independent and exact-head bound.

create schema if not exists penta_task_runtime;
create schema if not exists penta_translate;

revoke all on schema penta_task_runtime from public, anon, authenticated;
revoke all on schema penta_translate from public, anon, authenticated;
grant usage on schema penta_task_runtime to service_role;
grant usage on schema penta_translate to service_role;

create table if not exists penta_task_runtime.components_v1 (
  component_id text primary key,
  canonical_name text not null,
  family_key text not null,
  runtime_binding text not null,
  implementation_state text not null check (implementation_state in ('candidate','runtime_active_unverified','certified','production','hold','superseded')),
  source_ref text not null,
  authority_ceiling text not null default 'D2',
  d3_human_reserved boolean not null default true,
  no_self_certification boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_task_runtime.snapshots_v1 (
  snapshot_id uuid primary key default gen_random_uuid(),
  scope_kind text not null,
  scope_ref text not null,
  source_state jsonb not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  rollback_plan jsonb not null,
  rollback_sha256 text not null check (rollback_sha256 ~ '^[0-9a-f]{64}$'),
  actor_ref text not null,
  authority_basis text not null default 'D2',
  correlation_id text not null,
  dail_event_id uuid,
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists penta_task_runtime_snapshots_scope_idx on penta_task_runtime.snapshots_v1(scope_kind,scope_ref,created_at desc);

create table if not exists penta_translate.projections_v1 (
  projection_id uuid primary key default gen_random_uuid(),
  idempotency_key text not null unique,
  source_ref text not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  projection_ref text not null,
  projection_sha256 text not null check (projection_sha256 ~ '^[0-9a-f]{64}$'),
  source_language text not null,
  target_language text not null,
  projection_kind text not null check (projection_kind in ('machine','human','hybrid')),
  translator_component text not null,
  translation_profile_ref text not null,
  round_trip_verified boolean not null default false,
  semantic_equivalence_score numeric(5,4) check (semantic_equivalence_score between 0 and 1),
  classification text not null default 'internal',
  provenance jsonb not null default '{}'::jsonb,
  dail_event_id uuid,
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists penta_translate_projections_source_idx on penta_translate.projections_v1(source_sha256,created_at desc);

create or replace function penta_task_runtime.guard_snapshot_pointer_bind_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog'
as $$
begin
  if tg_op='DELETE' then raise exception 'append_only_evidence_object'; end if;
  if old.dail_event_id is null and new.dail_event_id is not null and
     row(old.scope_kind,old.scope_ref,old.source_state,old.source_sha256,old.rollback_plan,old.rollback_sha256,old.actor_ref,old.authority_basis,old.correlation_id,old.created_at)
     is not distinct from
     row(new.scope_kind,new.scope_ref,new.source_state,new.source_sha256,new.rollback_plan,new.rollback_sha256,new.actor_ref,new.authority_basis,new.correlation_id,new.created_at)
  then return new; end if;
  raise exception 'append_only_evidence_object';
end;
$$;

create or replace function penta_translate.guard_projection_pointer_bind_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog'
as $$
begin
  if tg_op='DELETE' then raise exception 'append_only_evidence_object'; end if;
  if current_setting('penta_translate.pointer_bind',true)='on' and old.dail_event_id is null and new.dail_event_id is not null then return new; end if;
  raise exception 'append_only_evidence_object';
end;
$$;

alter table penta_task_runtime.components_v1 enable row level security;
alter table penta_task_runtime.components_v1 force row level security;
alter table penta_task_runtime.snapshots_v1 enable row level security;
alter table penta_task_runtime.snapshots_v1 force row level security;
alter table penta_translate.projections_v1 enable row level security;
alter table penta_translate.projections_v1 force row level security;

revoke all on penta_task_runtime.components_v1 from public, anon, authenticated;
revoke all on penta_task_runtime.snapshots_v1 from public, anon, authenticated;
revoke all on penta_translate.projections_v1 from public, anon, authenticated;
grant select,insert,update on penta_task_runtime.components_v1 to service_role;
grant select,insert on penta_task_runtime.snapshots_v1 to service_role;
grant select,insert on penta_translate.projections_v1 to service_role;

drop policy if exists penta_task_runtime_components_service_v1 on penta_task_runtime.components_v1;
create policy penta_task_runtime_components_service_v1 on penta_task_runtime.components_v1
  for all to service_role using (true) with check (true);
drop policy if exists penta_task_runtime_snapshots_service_v1 on penta_task_runtime.snapshots_v1;
create policy penta_task_runtime_snapshots_service_v1 on penta_task_runtime.snapshots_v1
  for select to service_role using (true);
drop policy if exists penta_task_runtime_snapshots_insert_service_v1 on penta_task_runtime.snapshots_v1;
create policy penta_task_runtime_snapshots_insert_service_v1 on penta_task_runtime.snapshots_v1
  for insert to service_role with check (true);
drop policy if exists penta_translate_projections_service_v1 on penta_translate.projections_v1;
create policy penta_translate_projections_service_v1 on penta_translate.projections_v1
  for select to service_role using (true);
drop policy if exists penta_translate_projections_insert_service_v1 on penta_translate.projections_v1;
create policy penta_translate_projections_insert_service_v1 on penta_translate.projections_v1
  for insert to service_role with check (true);

DROP TRIGGER IF EXISTS penta_task_runtime_snapshots_immutable_v1 ON penta_task_runtime.snapshots_v1;
create trigger penta_task_runtime_snapshots_immutable_v1
before update or delete on penta_task_runtime.snapshots_v1
for each row execute function penta_task_runtime.guard_snapshot_pointer_bind_v1();

DROP TRIGGER IF EXISTS penta_translate_projections_immutable_v1 ON penta_translate.projections_v1;
create trigger penta_translate_projections_immutable_v1
before update or delete on penta_translate.projections_v1
for each row execute function penta_translate.guard_projection_pointer_bind_v1();

create or replace function penta_task_runtime.capture_snapshot_v1(
  p_scope_kind text,
  p_scope_ref text,
  p_source_state jsonb,
  p_rollback_plan jsonb,
  p_actor_ref text,
  p_authority_basis text default 'D2',
  p_correlation_id text default null
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','extensions','penta_task_runtime','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_snapshot penta_task_runtime.snapshots_v1%rowtype;
  v_source_hash text;
  v_rollback_hash text;
  v_corr text:=coalesce(nullif(p_correlation_id,''),'ctcorr:snapshot:'||gen_random_uuid()::text);
  v_event jsonb;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if nullif(btrim(coalesce(p_scope_kind,'')),'') is null or nullif(btrim(coalesce(p_scope_ref,'')),'') is null then raise exception 'scope_required'; end if;
  if p_source_state::text ~* '"(password|secret|private[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token)"[[:space:]]*:' then raise exception 'protected_material_rejected'; end if;
  if p_rollback_plan::text ~* '"(password|secret|private[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token)"[[:space:]]*:' then raise exception 'protected_material_rejected'; end if;
  v_source_hash:=encode(extensions.digest(convert_to(p_source_state::text,'UTF8'),'sha256'),'hex');
  v_rollback_hash:=encode(extensions.digest(convert_to(p_rollback_plan::text,'UTF8'),'sha256'),'hex');
  insert into penta_task_runtime.snapshots_v1(scope_kind,scope_ref,source_state,source_sha256,rollback_plan,rollback_sha256,actor_ref,authority_basis,correlation_id)
  values(p_scope_kind,p_scope_ref,p_source_state,v_source_hash,p_rollback_plan,v_rollback_hash,p_actor_ref,coalesce(nullif(p_authority_basis,''),'D2'),v_corr)
  returning * into v_snapshot;
  v_event:=chlom_runtime.append_dail_event('penta.snapshot.captured','penta_snapshot',v_snapshot.snapshot_id::text,
    jsonb_build_object('scope_kind',p_scope_kind,'scope_ref',p_scope_ref,'source_sha256',v_source_hash,'rollback_sha256',v_rollback_hash,'three_dail_logical_phase','DAIL-EVIDENCE','protected_material_stored',false),
    p_actor_ref,null,'PentaSnapshot','1.0.0',v_corr,null,coalesce(nullif(p_authority_basis,''),'D2'),null,'internal');
  update penta_task_runtime.snapshots_v1 set dail_event_id=(v_event->>'event_id')::uuid where snapshot_id=v_snapshot.snapshot_id;
  return jsonb_build_object('ok',true,'snapshot_id',v_snapshot.snapshot_id,'source_sha256',v_source_hash,'rollback_sha256',v_rollback_hash,'dail',v_event);
end;
$$;

create or replace function penta_translate.record_projection_v1(
  p_idempotency_key text,
  p_source_ref text,
  p_source_sha256 text,
  p_projection_ref text,
  p_projection_sha256 text,
  p_source_language text,
  p_target_language text,
  p_projection_kind text,
  p_translator_component text,
  p_translation_profile_ref text,
  p_round_trip_verified boolean,
  p_semantic_equivalence_score numeric,
  p_classification text,
  p_provenance jsonb,
  p_actor_ref text,
  p_correlation_id text default null
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_translate','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_row penta_translate.projections_v1%rowtype;
  v_event jsonb;
  v_corr text:=coalesce(nullif(p_correlation_id,''),'ctcorr:translate:'||gen_random_uuid()::text);
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_source_sha256 !~ '^[0-9a-f]{64}$' or p_projection_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_sha256'; end if;
  if p_projection_kind not in ('machine','human','hybrid') then raise exception 'invalid_projection_kind'; end if;
  if p_semantic_equivalence_score is not null and (p_semantic_equivalence_score<0 or p_semantic_equivalence_score>1) then raise exception 'invalid_semantic_score'; end if;
  if coalesce(p_provenance,'{}'::jsonb)::text ~* '"(password|secret|private[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token|cipher[_-]?map|raw[_-]?mapping)"[[:space:]]*:' then raise exception 'protected_material_rejected'; end if;
  insert into penta_translate.projections_v1(idempotency_key,source_ref,source_sha256,projection_ref,projection_sha256,source_language,target_language,projection_kind,translator_component,translation_profile_ref,round_trip_verified,semantic_equivalence_score,classification,provenance)
  values(p_idempotency_key,p_source_ref,p_source_sha256,p_projection_ref,p_projection_sha256,p_source_language,p_target_language,p_projection_kind,p_translator_component,p_translation_profile_ref,coalesce(p_round_trip_verified,false),p_semantic_equivalence_score,coalesce(nullif(p_classification,''),'internal'),coalesce(p_provenance,'{}'::jsonb))
  on conflict(idempotency_key) do nothing;
  select * into v_row from penta_translate.projections_v1 where idempotency_key=p_idempotency_key;
  if v_row.source_sha256<>p_source_sha256 or v_row.projection_sha256<>p_projection_sha256 then raise exception 'idempotency_key_reuse_with_different_projection'; end if;
  if v_row.dail_event_id is null then
    v_event:=chlom_runtime.append_dail_event('penta.translate.projection.recorded','translation_projection',v_row.projection_id::text,
      jsonb_build_object('source_ref',p_source_ref,'source_sha256',p_source_sha256,'projection_ref',p_projection_ref,'projection_sha256',p_projection_sha256,'source_language',p_source_language,'target_language',p_target_language,'projection_kind',p_projection_kind,'round_trip_verified',coalesce(p_round_trip_verified,false),'semantic_equivalence_score',p_semantic_equivalence_score,'three_dail_logical_phase','DAIL-EVIDENCE','protected_translation_internals_exposed',false),
      p_actor_ref,null,'PentaTranslate','1.0.0',v_corr,null,'D1',null,'internal');
    perform set_config('penta_translate.pointer_bind','on',true);
    update penta_translate.projections_v1 set dail_event_id=(v_event->>'event_id')::uuid where projection_id=v_row.projection_id;
  else
    v_event:=jsonb_build_object('event_id',v_row.dail_event_id,'replayed',true);
  end if;
  return jsonb_build_object('ok',true,'projection_id',v_row.projection_id,'round_trip_verified',v_row.round_trip_verified,'dail',v_event);
end;
$$;

-- Upgrade PentaDND in-place with priority/heartbeat/max lifetime while retaining v1 compatibility.
alter table penta_dnd.leases_v1 add column if not exists priority smallint not null default 50 check (priority between 0 and 100);
alter table penta_dnd.leases_v1 add column if not exists heartbeat_at timestamptz;
alter table penta_dnd.leases_v1 add column if not exists max_expires_at timestamptz;
update penta_dnd.leases_v1 set heartbeat_at=coalesce(heartbeat_at,started_at), max_expires_at=coalesce(max_expires_at,started_at+interval '2 hours') where heartbeat_at is null or max_expires_at is null;
create index if not exists penta_dnd_active_priority_idx on penta_dnd.leases_v1(scope_kind,scope_ref,priority desc,expires_at) where state='active';

create or replace function penta_dnd.open_lease_v2(
  p_program_id text,
  p_scope_kind text,
  p_scope_ref text,
  p_owner_system_key text,
  p_reason text,
  p_priority smallint default 50,
  p_ttl_seconds integer default 3300,
  p_current_phase_key text default null,
  p_next_phase_key text default null,
  p_allowed_actor_system_keys text[] default array['penta.dnd','penta.self','penta.discovery','penta.census','penta.certify','penta.wire','penta.planner','penta.factory','penta.backup','penta.restore','penta.mail'],
  p_allowed_capabilities text[] default array['dnd.scope','penta.discovery','penta.census','penta.certify','penta.wire','penta.self','pentas.route','dail.append','backup.continuity','restore.readback','penta.mail']
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_dnd','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_existing penta_dnd.leases_v1%rowtype;
  v_open jsonb;
  v_id uuid;
  v_event jsonb;
  v_ttl integer:=greatest(300,least(coalesce(p_ttl_seconds,3300),7200));
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if p_priority<0 or p_priority>100 then raise exception 'priority_out_of_range'; end if;
  perform pg_advisory_xact_lock(hashtextextended(coalesce(p_scope_kind,'')||'|'||coalesce(p_scope_ref,''),0));
  update penta_dnd.leases_v1 set state='expired',closed_at=clock_timestamp(),close_reason='ttl_expired',updated_at=clock_timestamp() where state='active' and expires_at<=clock_timestamp();
  select * into v_existing from penta_dnd.leases_v1 where scope_kind=p_scope_kind and scope_ref=p_scope_ref and state='active' and expires_at>clock_timestamp() order by priority desc,started_at limit 1 for update;
  if found then
    if v_existing.owner_system_key=p_owner_system_key then
      update penta_dnd.leases_v1 set heartbeat_at=clock_timestamp(),priority=greatest(priority,p_priority),updated_at=clock_timestamp() where lease_id=v_existing.lease_id;
      return jsonb_build_object('ok',true,'state','idempotent_active','lease_id',v_existing.lease_id,'owner',v_existing.owner_system_key,'priority',greatest(v_existing.priority,p_priority),'expires_at',v_existing.expires_at,'preempted',false);
    end if;
    return jsonb_build_object('ok',false,'state','held_by_active_owner','lease_id',v_existing.lease_id,'owner',v_existing.owner_system_key,'existing_priority',v_existing.priority,'requested_priority',p_priority,'expires_at',v_existing.expires_at,'preempted',false);
  end if;
  v_open:=penta_dnd.open_lease_v1(p_program_id,p_scope_kind,p_scope_ref,p_owner_system_key,p_reason,v_ttl,p_current_phase_key,p_next_phase_key,p_allowed_actor_system_keys,p_allowed_capabilities);
  v_id:=(v_open->>'lease_id')::uuid;
  update penta_dnd.leases_v1 set priority=p_priority,heartbeat_at=clock_timestamp(),max_expires_at=started_at+interval '2 hours',metadata=metadata||jsonb_build_object('priority',p_priority,'priority_preemption',false,'ttl_bounded',true),updated_at=clock_timestamp() where lease_id=v_id;
  v_event:=chlom_runtime.append_dail_event('penta.dnd.priority.bound','dnd_scope',v_id::text,jsonb_build_object('priority',p_priority,'ttl_seconds',v_ttl,'preemption',false,'three_dail_logical_phase','DAIL-DECISION'),'PentaDND',null,'PentaDND','1.1.0',v_open->>'correlation_id',null,'D1',null,'internal');
  return v_open||jsonb_build_object('priority',p_priority,'max_expires_at',(select max_expires_at from penta_dnd.leases_v1 where lease_id=v_id),'priority_event',v_event);
end;
$$;

create or replace function penta_dnd.renew_lease_v2(p_lease_id uuid,p_owner_system_key text,p_ttl_seconds integer default 3300)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_dnd','chlom_runtime'
as $$
declare
  v_role text:=coalesce(current_setting('request.jwt.claim.role',true),'');
  v_row penta_dnd.leases_v1%rowtype;
  v_new_exp timestamptz;
  v_event jsonb;
begin
  if session_user<>'postgres' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  select * into v_row from penta_dnd.leases_v1 where lease_id=p_lease_id for update;
  if not found then return jsonb_build_object('ok',false,'state','unknown_lease'); end if;
  if v_row.state<>'active' or v_row.expires_at<=clock_timestamp() then return jsonb_build_object('ok',false,'state','inactive_or_expired'); end if;
  if v_row.owner_system_key<>p_owner_system_key then raise exception 'lease_owner_mismatch'; end if;
  v_new_exp:=least(clock_timestamp()+make_interval(secs=>greatest(300,least(coalesce(p_ttl_seconds,3300),7200))),coalesce(v_row.max_expires_at,v_row.started_at+interval '2 hours'));
  if v_new_exp<=clock_timestamp()+interval '60 seconds' then return jsonb_build_object('ok',false,'state','max_lifetime_reached','max_expires_at',v_row.max_expires_at); end if;
  update penta_dnd.leases_v1 set expires_at=v_new_exp,heartbeat_at=clock_timestamp(),updated_at=clock_timestamp() where lease_id=p_lease_id;
  v_event:=chlom_runtime.append_dail_event('penta.dnd.lease.renewed','dnd_scope',p_lease_id::text,jsonb_build_object('expires_at',v_new_exp,'max_expires_at',v_row.max_expires_at,'priority',v_row.priority,'three_dail_logical_phase','DAIL-EXECUTION'),'PentaDND',null,'PentaDND','1.1.0',v_row.correlation_id,null,'D1',null,'internal');
  return jsonb_build_object('ok',true,'state','renewed','lease_id',p_lease_id,'expires_at',v_new_exp,'heartbeat_at',clock_timestamp(),'priority',v_row.priority,'dail',v_event);
end;
$$;

create or replace function penta_task_runtime.status_v1()
returns jsonb
language sql
security definer
set search_path='pg_catalog','penta_task_runtime','penta_translate','penta_dnd','institutional_federation'
as $$
select jsonb_build_object(
  'service','ct.penta.task-runtime-family.v1',
  'observed_at',clock_timestamp(),
  'components',(select coalesce(jsonb_agg(to_jsonb(c) order by c.component_id),'[]'::jsonb) from penta_task_runtime.components_v1 c),
  'snapshots',(select count(*) from penta_task_runtime.snapshots_v1),
  'translation_projections',(select count(*) from penta_translate.projections_v1),
  'active_dnd_leases',(select count(*) from penta_dnd.leases_v1 where state='active' and expires_at>clock_timestamp()),
  'active_collision_leases',(select count(*) from institutional_federation.collision_domain_leases_v2 where state='active' and expires_at>clock_timestamp()),
  'authority_created',false,
  'd3_human_reserved',true,
  'production_certified',false
); $$;

revoke all on function penta_task_runtime.guard_snapshot_pointer_bind_v1() from public, anon, authenticated;
revoke all on function penta_translate.guard_projection_pointer_bind_v1() from public, anon, authenticated;
revoke all on function penta_task_runtime.capture_snapshot_v1(text,text,jsonb,jsonb,text,text,text) from public, anon, authenticated;
revoke all on function penta_translate.record_projection_v1(text,text,text,text,text,text,text,text,text,text,boolean,numeric,text,jsonb,text,text) from public, anon, authenticated;
revoke all on function penta_dnd.open_lease_v2(text,text,text,text,text,smallint,integer,text,text,text[],text[]) from public, anon, authenticated;
revoke all on function penta_dnd.renew_lease_v2(uuid,text,integer) from public, anon, authenticated;
revoke all on function penta_task_runtime.status_v1() from public, anon, authenticated;
grant execute on function penta_task_runtime.capture_snapshot_v1(text,text,jsonb,jsonb,text,text,text) to service_role;
grant execute on function penta_translate.record_projection_v1(text,text,text,text,text,text,text,text,text,text,boolean,numeric,text,jsonb,text,text) to service_role;
grant execute on function penta_dnd.open_lease_v2(text,text,text,text,text,smallint,integer,text,text,text[],text[]) to service_role;
grant execute on function penta_dnd.renew_lease_v2(uuid,text,integer) to service_role;
grant execute on function penta_task_runtime.status_v1() to service_role;

insert into penta_task_runtime.components_v1(component_id,canonical_name,family_key,runtime_binding,implementation_state,source_ref,metadata)
values
('ct.penta.dnd.v1','PentaDND','ct.penta.task-runtime-family.v1','penta_dnd.open_lease_v2 + penta_dnd.renew_lease_v2','runtime_active_unverified','PR#1388/supabase/migrations/20260830073000_penta_super_task_runtime_v1.sql',jsonb_build_object('compatibility','penta_dnd.open_lease_v1 preserved','priority',true,'ttl',true)),
('ct.penta.snapshot.v1','PentaSnapshot','ct.penta.task-runtime-family.v1','penta_task_runtime.capture_snapshot_v1','runtime_active_unverified','PR#1388/supabase/migrations/20260830073000_penta_super_task_runtime_v1.sql',jsonb_build_object('append_only',true,'rollback_evidence',true)),
('ct.penta.lease.v1','PentaLease','ct.penta.task-runtime-family.v1','institutional_federation.collision_domain_leases_v2 + acquire/renew/release_collision_domain_lease_v2','runtime_active_unverified','PR#1388/supabase/migrations/20260830073000_penta_super_task_runtime_v1.sql',jsonb_build_object('duplicate_runtime_created',false,'fencing',true,'cas',true)),
('ct.penta.collision.v1','PentaCollision','ct.penta.task-runtime-family.v1','institutional_federation.collision_events_v2 + run_collision_awareness_subroute_v2','runtime_active_unverified','PR#1388/supabase/migrations/20260830073000_penta_super_task_runtime_v1.sql',jsonb_build_object('duplicate_runtime_created',false,'rogue_counterwrite',false)),
('ct.penta.translate.v1','PentaTranslate','ct.penta.task-runtime-family.v1','penta_translate.record_projection_v1','runtime_active_unverified','PR#1388/supabase/migrations/20260830073000_penta_super_task_runtime_v1.sql',jsonb_build_object('source_body_stored',false,'protected_mapping_stored',false,'round_trip_evidence',true))
on conflict(component_id) do nothing;

insert into integration_control.penta_identity_registry_v1(identity_key,canonical_name,identity_class,docs_path,docs_namespace,family_key,family_name,role,axis,kind,maturity,registration_state,activation_state,runtime_state,labels,source_refs,current,active,metadata)
values
('ct.penta.super.v1','PentaSuper','CANDIDATE','penta/super/README.md','penta/super','ct.penta.family.supervision','Supervision','system supervisory intelligence','orchestration','penta','bootstrap','source_controlled','CANDIDATE','SOURCE_BOOTSTRAP',array['supervisor','non-sovereign'],jsonb_build_object('pr',1388,'source','penta/super/README.md'),true,true,jsonb_build_object('no_self_certification',true,'d3_human_reserved',true)),
('ct.penta.dnd.v1','PentaDND','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','scoped do-not-disturb lease control','runtime-control','penta','production_candidate','registered','ACTIVE','RUNTIME_ACTIVE_UNVERIFIED',array['dnd','ttl','priority'],jsonb_build_object('pr',1388,'runtime','penta_dnd.open_lease_v2'),true,true,jsonb_build_object('global_shutdown',false,'priority_preemption',false)),
('ct.penta.snapshot.v1','PentaSnapshot','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','bounded rollback snapshot evidence','continuity','penta','production_candidate','registered','ACTIVE','RUNTIME_ACTIVE_UNVERIFIED',array['snapshot','rollback'],jsonb_build_object('pr',1388,'runtime','penta_task_runtime.capture_snapshot_v1'),true,true,jsonb_build_object('append_only',true)),
('ct.penta.lease.v1','PentaLease','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','fenced resource ownership leases','coordination','penta','production_candidate','registered','ACTIVE','RUNTIME_ACTIVE_UNVERIFIED',array['lease','fencing','cas'],jsonb_build_object('pr',1388,'runtime','institutional_federation.collision_domain_leases_v2'),true,true,jsonb_build_object('duplicate_runtime_created',false)),
('ct.penta.collision.v1','PentaCollision','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','collision and rogue-writer detection','coordination','penta','production_candidate','registered','ACTIVE','RUNTIME_ACTIVE_UNVERIFIED',array['collision','incident'],jsonb_build_object('pr',1388,'runtime','institutional_federation.collision_events_v2'),true,true,jsonb_build_object('counter_mutation',false)),
('ct.penta.translate.v1','PentaTranslate','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','governed translation projection provenance','translation','penta','production_candidate','registered','ACTIVE','RUNTIME_ACTIVE_UNVERIFIED',array['translate','provenance','round-trip'],jsonb_build_object('pr',1388,'runtime','penta_translate.record_projection_v1'),true,true,jsonb_build_object('protected_mapping_public',false,'source_body_stored',false)),
('ct.penta.translate.encode.v1','PentaTranslate Encode','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','machine-projection encoding subcapability','translation','subcomponent','specified','registered','HOLD_PARENT','INSTITUTIONAL_ONLY',array['translate','encode'],jsonb_build_object('pr',1388,'parent','ct.penta.translate.v1'),true,true,jsonb_build_object('authority_created',false)),
('ct.penta.translate.decode.v1','PentaTranslate Decode','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','human-language projection decoding subcapability','translation','subcomponent','specified','registered','HOLD_PARENT','INSTITUTIONAL_ONLY',array['translate','decode'],jsonb_build_object('pr',1388,'parent','ct.penta.translate.v1'),true,true,jsonb_build_object('authority_created',false)),
('ct.penta.translate.project.v1','PentaTranslate Project','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','projection materialization subcapability','translation','subcomponent','specified','registered','HOLD_PARENT','INSTITUTIONAL_ONLY',array['translate','project'],jsonb_build_object('pr',1388,'parent','ct.penta.translate.v1'),true,true,jsonb_build_object('authority_created',false)),
('ct.penta.translate.verify.v1','PentaTranslate Verify','CANDIDATE','penta/super/task-runtime-acceptance-v1.md','penta/super','ct.penta.task-runtime-family.v1','Task Runtime','non-originating translation verification subcapability','translation','subcomponent','specified','registered','HOLD_PARENT','INSTITUTIONAL_ONLY',array['translate','verify'],jsonb_build_object('pr',1388,'parent','ct.penta.translate.v1','independent_verifier_required',true),true,true,jsonb_build_object('authority_created',false,'no_self_certification',true))
on conflict(identity_key) do nothing;

select chlom_runtime.append_dail_event('penta.super.task-runtime.runtime-installed','penta_super_runtime','ct.penta.task-runtime-family.v1',
  jsonb_build_object('components',array['ct.penta.dnd.v1','ct.penta.snapshot.v1','ct.penta.lease.v1','ct.penta.collision.v1','ct.penta.translate.v1'],'implementation_state','runtime_active_unverified','production_certified',false,'three_dail_logical_phase','DAIL-EXECUTION','physical_dail_views',array['human','machine','hybrid'],'authority_created',false,'d3_human_reserved',true),
  'ct.relay.agent-c',null,'ct.relay.agent-c','1.0.0','ctcorr:penta-super:task-runtime-v1',null,'D2',null,'internal');
