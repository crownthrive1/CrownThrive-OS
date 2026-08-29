-- Provider-applied migration: pentaself_monotonic_permanent_repair_fabric_v2
-- Permanent repairs are allowlisted, generation-monotonic, independently re-verified,
-- and protected from stale evidence reopening a resolved problem.

create table if not exists penta_self.permanent_repairs_v2 (
  repair_key text primary key,
  generation bigint not null,
  repair_class text not null,
  enabled boolean not null default true,
  authority_ref text not null,
  desired_state jsonb not null default '{}'::jsonb,
  last_state text,
  last_result jsonb not null default '{}'::jsonb,
  last_error_class text,
  last_attempt_at timestamptz,
  last_verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table penta_self.permanent_repairs_v2 enable row level security;
revoke all on penta_self.permanent_repairs_v2 from public, anon, authenticated;
grant select, insert, update on penta_self.permanent_repairs_v2 to service_role;
drop policy if exists permanent_repairs_service_role_v2 on penta_self.permanent_repairs_v2;
create policy permanent_repairs_service_role_v2
  on penta_self.permanent_repairs_v2
  for all to service_role using (true) with check (true);

create table if not exists penta_self.permanent_repair_events_v2 (
  event_id uuid primary key default gen_random_uuid(),
  repair_key text not null,
  generation bigint not null,
  event_type text not null,
  state text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);
create index if not exists permanent_repair_events_key_time_v2
  on penta_self.permanent_repair_events_v2(repair_key, observed_at desc);

alter table penta_self.permanent_repair_events_v2 enable row level security;
revoke all on penta_self.permanent_repair_events_v2 from public, anon, authenticated;
grant select, insert on penta_self.permanent_repair_events_v2 to service_role;
drop policy if exists permanent_repair_events_select_service_role_v2 on penta_self.permanent_repair_events_v2;
create policy permanent_repair_events_select_service_role_v2
  on penta_self.permanent_repair_events_v2 for select to service_role using (true);
drop policy if exists permanent_repair_events_insert_service_role_v2 on penta_self.permanent_repair_events_v2;
create policy permanent_repair_events_insert_service_role_v2
  on penta_self.permanent_repair_events_v2 for insert to service_role with check (true);

create table if not exists penta_self.problem_regression_blocks_v2 (
  block_id uuid primary key default gen_random_uuid(),
  problem_id uuid not null,
  fingerprint text,
  attempted_state text,
  prior_resolved_at timestamptz,
  attempted_last_seen_at timestamptz,
  reason text not null,
  attempted_evidence_sha256 text,
  observed_at timestamptz not null default now()
);
create index if not exists problem_regression_blocks_problem_time_v2
  on penta_self.problem_regression_blocks_v2(problem_id, observed_at desc);

alter table penta_self.problem_regression_blocks_v2 enable row level security;
revoke all on penta_self.problem_regression_blocks_v2 from public, anon, authenticated;
grant select, insert on penta_self.problem_regression_blocks_v2 to service_role;
drop policy if exists problem_regression_blocks_select_service_role_v2 on penta_self.problem_regression_blocks_v2;
create policy problem_regression_blocks_select_service_role_v2
  on penta_self.problem_regression_blocks_v2 for select to service_role using (true);
drop policy if exists problem_regression_blocks_insert_service_role_v2 on penta_self.problem_regression_blocks_v2;
create policy problem_regression_blocks_insert_service_role_v2
  on penta_self.problem_regression_blocks_v2 for insert to service_role with check (true);

create or replace function penta_self.permanent_repairs_generation_guard_v2()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, penta_self
as $$
begin
  if tg_op = 'UPDATE' then
    if new.repair_key <> old.repair_key then raise exception 'repair_key_immutable'; end if;
    if new.generation < old.generation then raise exception 'stale_repair_generation_rejected'; end if;
    if old.enabled and not new.enabled and coalesce(new.metadata ->> 'rollback_ticket', '') = '' then
      raise exception 'explicit_higher_generation_rollback_ticket_required';
    end if;
    new.updated_at := now();
  end if;
  return new;
end $$;

revoke all on function penta_self.permanent_repairs_generation_guard_v2()
  from public, anon, authenticated;
grant execute on function penta_self.permanent_repairs_generation_guard_v2()
  to service_role;

drop trigger if exists permanent_repairs_generation_guard_v2 on penta_self.permanent_repairs_v2;
create trigger permanent_repairs_generation_guard_v2
before update on penta_self.permanent_repairs_v2
for each row execute function penta_self.permanent_repairs_generation_guard_v2();

create or replace function penta_self.problem_resolved_regression_guard_v2()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, penta_self, extensions
as $$
declare
  v_digest text;
  v_genuinely_new boolean;
begin
  if old.state = 'resolved' and new.state <> 'resolved' then
    v_genuinely_new := coalesce(new.last_seen_at, 'epoch'::timestamptz) > coalesce(old.resolved_at, old.updated_at)
      and new.evidence is distinct from old.evidence;
    if not v_genuinely_new then
      v_digest := encode(extensions.digest(convert_to(coalesce(new.evidence, '{}'::jsonb)::text, 'UTF8'), 'sha256'), 'hex');
      insert into penta_self.problem_regression_blocks_v2(
        problem_id, fingerprint, attempted_state, prior_resolved_at,
        attempted_last_seen_at, reason, attempted_evidence_sha256
      ) values (
        old.problem_id, old.fingerprint, new.state, old.resolved_at,
        new.last_seen_at, 'stale_or_identical_evidence_cannot_reopen_resolved_problem', v_digest
      );
      return old;
    end if;
  end if;
  return new;
end $$;

revoke all on function penta_self.problem_resolved_regression_guard_v2()
  from public, anon, authenticated;
grant execute on function penta_self.problem_resolved_regression_guard_v2()
  to service_role;

drop trigger if exists problem_resolved_regression_guard_v2 on penta_self.problem_ledger_v1;
create trigger problem_resolved_regression_guard_v2
before update on penta_self.problem_ledger_v1
for each row execute function penta_self.problem_resolved_regression_guard_v2();

create or replace function penta_self.permanent_repair_events_immutable_v2()
returns trigger language plpgsql security definer set search_path = pg_catalog, penta_self
as $$ begin raise exception 'permanent_repair_events_v2 is append-only'; end $$;
revoke all on function penta_self.permanent_repair_events_immutable_v2() from public, anon, authenticated;
grant execute on function penta_self.permanent_repair_events_immutable_v2() to service_role;
drop trigger if exists permanent_repair_events_immutable_v2 on penta_self.permanent_repair_events_v2;
create trigger permanent_repair_events_immutable_v2
before update or delete on penta_self.permanent_repair_events_v2
for each row execute function penta_self.permanent_repair_events_immutable_v2();

create or replace function penta_self.problem_regression_blocks_immutable_v2()
returns trigger language plpgsql security definer set search_path = pg_catalog, penta_self
as $$ begin raise exception 'problem_regression_blocks_v2 is append-only'; end $$;
revoke all on function penta_self.problem_regression_blocks_immutable_v2() from public, anon, authenticated;
grant execute on function penta_self.problem_regression_blocks_immutable_v2() to service_role;
drop trigger if exists problem_regression_blocks_immutable_v2 on penta_self.problem_regression_blocks_v2;
create trigger problem_regression_blocks_immutable_v2
before update or delete on penta_self.problem_regression_blocks_v2
for each row execute function penta_self.problem_regression_blocks_immutable_v2();

create or replace function penta_self.register_permanent_repair_v2(
  p_repair_key text,
  p_generation bigint,
  p_repair_class text,
  p_authority_ref text,
  p_desired_state jsonb default '{}'::jsonb,
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_self
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'), '');
  v_existing bigint;
begin
  if session_user not in ('postgres', 'supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select generation into v_existing
  from penta_self.permanent_repairs_v2
  where repair_key = p_repair_key;

  if v_existing is not null and p_generation < v_existing then
    return jsonb_build_object('ok', false, 'reason', 'stale_generation_rejected', 'existing_generation', v_existing);
  end if;

  insert into penta_self.permanent_repairs_v2(
    repair_key, generation, repair_class, enabled, authority_ref, desired_state, metadata
  ) values (
    p_repair_key, p_generation, p_repair_class, true, p_authority_ref,
    coalesce(p_desired_state, '{}'::jsonb), coalesce(p_metadata, '{}'::jsonb)
  )
  on conflict (repair_key) do update set
    generation = excluded.generation,
    repair_class = excluded.repair_class,
    enabled = true,
    authority_ref = excluded.authority_ref,
    desired_state = excluded.desired_state,
    metadata = penta_self.permanent_repairs_v2.metadata || excluded.metadata,
    updated_at = now();

  return jsonb_build_object('ok', true, 'repair_key', p_repair_key, 'generation', p_generation);
end $$;

revoke all on function penta_self.register_permanent_repair_v2(text, bigint, text, text, jsonb, jsonb)
  from public, anon, authenticated;
grant execute on function penta_self.register_permanent_repair_v2(text, bigint, text, text, jsonb, jsonb)
  to service_role;

create or replace function penta_self.permanent_repair_tick_v2()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_self, integration_control, crm, extensions, chlom_runtime
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'), '');
  r record;
  v_result jsonb;
  v_state text;
  v_digest text;
  v_ok int := 0;
  v_failed int := 0;
begin
  if session_user not in ('postgres', 'supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  for r in select * from penta_self.permanent_repairs_v2 where enabled order by repair_key loop
    begin
      case r.repair_class
        when 'scheduler_permanence' then
          v_result := integration_control.scheduler_permanence_reconcile_v2();
        when 'current_truth' then
          v_result := penta_self.reconcile_current_truth_v2();
        when 'marketing_event_projection' then
          v_result := crm.penta_marketer_refresh_event_projection_v2(
            coalesce(r.desired_state ->> 'campaign_ref', 'ct.pentamarketer.locticians.claim.20260827.v1')
          );
        when 'bd_warm_failover' then
          v_result := integration_control.locticians_bd_warm_failover_reconcile_v3();
        else
          raise exception 'repair_class_not_allowlisted:%', r.repair_class;
      end case;

      v_state := 'verified';
      v_ok := v_ok + 1;
      update penta_self.permanent_repairs_v2
         set last_state = v_state,
             last_result = coalesce(v_result, '{}'::jsonb),
             last_error_class = null,
             last_attempt_at = now(),
             last_verified_at = now(),
             updated_at = now()
       where repair_key = r.repair_key;
    exception when others then
      v_state := 'degraded';
      v_failed := v_failed + 1;
      v_result := jsonb_build_object(
        'error_class', sqlstate,
        'error_message_sha256', encode(extensions.digest(convert_to(sqlerrm, 'UTF8'), 'sha256'), 'hex')
      );
      update penta_self.permanent_repairs_v2
         set last_state = v_state,
             last_result = v_result,
             last_error_class = sqlstate,
             last_attempt_at = now(),
             updated_at = now()
       where repair_key = r.repair_key;
    end;

    v_digest := encode(extensions.digest(convert_to(jsonb_build_object(
      'repair_key', r.repair_key,
      'generation', r.generation,
      'state', v_state,
      'result', v_result,
      'observed_at', now()
    )::text, 'UTF8'), 'sha256'), 'hex');

    insert into penta_self.permanent_repair_events_v2(
      repair_key, generation, event_type, state, evidence, evidence_sha256
    ) values (
      r.repair_key, r.generation, 'verification_tick', v_state,
      coalesce(v_result, '{}'::jsonb), v_digest
    );
  end loop;

  perform chlom_runtime.append_dail_event(
    'pentaself.permanent_repairs.tick',
    'self_healing',
    'ct.penta.self.permanent-repairs.v2',
    jsonb_build_object('verified', v_ok, 'degraded', v_failed, 'observed_at', now()),
    'PentaSELF/PentaAssure/PentaTime',
    null,
    'PentaSELF',
    '2.0.0',
    encode(extensions.digest(convert_to(v_ok::text || ':' || v_failed::text, 'UTF8'), 'sha256'), 'hex'),
    null,
    'ct.pentaself.scheduler-permanence.v2',
    null,
    'internal'
  );

  return jsonb_build_object('verified', v_ok, 'degraded', v_failed, 'observed_at', now());
end $$;

revoke all on function penta_self.permanent_repair_tick_v2()
  from public, anon, authenticated;
grant execute on function penta_self.permanent_repair_tick_v2()
  to service_role;

select penta_self.register_permanent_repair_v2(
  'ct.repair.scheduler-permanence', 2026082902, 'scheduler_permanence',
  'ct.pentaself.scheduler-permanence.v2', jsonb_build_object('mode', 'monotonic'),
  jsonb_build_object('rollback_policy', 'higher_generation_explicit_ticket_only')
);
select penta_self.register_permanent_repair_v2(
  'ct.repair.current-truth', 2026082902, 'current_truth', 'ct.penta.self.v2',
  jsonb_build_object('phase_projection', 'ct.os.phase.current'),
  jsonb_build_object('rollback_policy', 'higher_generation_explicit_ticket_only')
);
select penta_self.register_permanent_repair_v2(
  'ct.repair.pentamarketer-event-projection', 2026082902, 'marketing_event_projection',
  'ct.pentamarketer.locticians.dynamic-outreach.v3',
  jsonb_build_object('campaign_ref', 'ct.pentamarketer.locticians.claim.20260827.v1'),
  jsonb_build_object('event_ledger_authoritative', true)
);
select penta_self.register_permanent_repair_v2(
  'ct.repair.bd-warm-failover', 2026082902, 'bd_warm_failover',
  'ct.locticians.brilliant-directories.api-fabric.v3',
  jsonb_build_object('shared_provider_quota', true, 'switch_on_429', false),
  jsonb_build_object('credential_material_exposure', false)
);

select penta_self.permanent_repair_tick_v2();

select cron.unschedule(jobid)
from cron.job
where jobname = 'ct-pentaself-permanent-repairs-v2';

select cron.schedule(
  'ct-pentaself-permanent-repairs-v2',
  '2-59/3 * * * *',
  'select penta_self.permanent_repair_tick_v2();'
);

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-pentaself-permanent-repairs-v2',
  '2-59/3 * * * *',
  'select penta_self.permanent_repair_tick_v2();',
  2026082902,
  'ct.pentaself.scheduler-permanence.v2',
  jsonb_build_object(
    'owner', 'PentaSELF/PentaTime/PentaAssure',
    'rollback_policy', 'monotonic',
    'stale_problem_reopen_guard', true
  )
);

select integration_control.scheduler_permanence_reconcile_v2();
