-- Provider-applied migration: pentaself_current_truth_and_phase_reconciliation_v2_fix
-- Separates canonical phase, founder operating label, and lane-specific rollout;
-- resolves transient cron failures only after a later successful execution.

create table if not exists integration_control.institutional_phase_projection_v2 (
  projection_key text primary key,
  canonical_os_phase numeric(4,2) not null,
  founder_operating_label text not null,
  public_rollout_state text not null,
  authority_note text not null,
  source_refs jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.institutional_phase_projection_v2 enable row level security;
revoke all on integration_control.institutional_phase_projection_v2 from public, anon, authenticated;
grant select, insert, update on integration_control.institutional_phase_projection_v2 to service_role;

drop policy if exists institutional_phase_projection_service_role_v2
  on integration_control.institutional_phase_projection_v2;
create policy institutional_phase_projection_service_role_v2
  on integration_control.institutional_phase_projection_v2
  for all to service_role using (true) with check (true);

insert into integration_control.institutional_phase_projection_v2(
  projection_key, canonical_os_phase, founder_operating_label,
  public_rollout_state, authority_note, source_refs, evidence_sha256
) values (
  'ct.os.phase.current',
  3.00,
  'Phase 3.5 — convergence and hardening',
  'lane_specific',
  'Canonical institutional phase, founder operating label, and public rollout state are independent fields. Public rollout never promotes canonical phase or authority.',
  jsonb_build_object(
    'canonical', 'ThriveBase/CrownThrive-OS',
    'founder_label', 'founder directive',
    'public_rollout', 'per-lane provider evidence'
  ),
  encode(extensions.digest(convert_to(
    '3|Phase 3.5 — convergence and hardening|lane_specific|independent-fields',
    'UTF8'
  ), 'sha256'), 'hex')
)
on conflict (projection_key) do update set
  canonical_os_phase = excluded.canonical_os_phase,
  founder_operating_label = excluded.founder_operating_label,
  public_rollout_state = excluded.public_rollout_state,
  authority_note = excluded.authority_note,
  source_refs = excluded.source_refs,
  evidence_sha256 = excluded.evidence_sha256,
  updated_at = now();

create table if not exists penta_self.current_truth_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_kind text not null,
  subject_ref text not null,
  observed_state jsonb not null,
  disposition text not null,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);

alter table penta_self.current_truth_receipts_v2 enable row level security;
revoke all on penta_self.current_truth_receipts_v2 from public, anon, authenticated;
grant select, insert on penta_self.current_truth_receipts_v2 to service_role;

drop policy if exists current_truth_receipts_select_service_role_v2
  on penta_self.current_truth_receipts_v2;
create policy current_truth_receipts_select_service_role_v2
  on penta_self.current_truth_receipts_v2
  for select to service_role using (true);

drop policy if exists current_truth_receipts_insert_service_role_v2
  on penta_self.current_truth_receipts_v2;
create policy current_truth_receipts_insert_service_role_v2
  on penta_self.current_truth_receipts_v2
  for insert to service_role with check (true);

create or replace function penta_self.current_truth_receipts_immutable_v2()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, penta_self
as $$
begin
  raise exception 'current_truth_receipts_v2 is append-only';
end $$;

revoke all on function penta_self.current_truth_receipts_immutable_v2()
  from public, anon, authenticated;
grant execute on function penta_self.current_truth_receipts_immutable_v2()
  to service_role;

drop trigger if exists current_truth_receipts_immutable_v2
  on penta_self.current_truth_receipts_v2;
create trigger current_truth_receipts_immutable_v2
before update or delete on penta_self.current_truth_receipts_v2
for each row execute function penta_self.current_truth_receipts_immutable_v2();

create or replace function penta_self.reconcile_current_truth_v2()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_self, integration_control, cron, extensions, chlom_runtime, crm
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'), '');
  v_factory_status text;
  v_factory_started timestamptz;
  v_factory_end timestamptz;
  v_resolved int := 0;
  v_rows int := 0;
  v_marketer jsonb := '{}'::jsonb;
  v_payload jsonb;
  v_digest text;
begin
  if session_user not in ('postgres', 'supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select status, start_time, end_time
    into v_factory_status, v_factory_started, v_factory_end
  from cron.job_run_details
  where jobid = (
    select jobid from cron.job
    where jobname = 'ct-software-factory-continuity-v5'
    order by jobid desc limit 1
  )
  order by start_time desc
  limit 1;

  if v_factory_status = 'succeeded' then
    update penta_self.problem_ledger_v1
       set state = 'resolved',
           resolved_at = coalesce(resolved_at, now()),
           blocked_reason = null,
           last_error = null,
           verification_evidence = coalesce(verification_evidence, '{}'::jsonb) || jsonb_build_object(
             'verified_at', now(),
             'latest_status', v_factory_status,
             'latest_started_at', v_factory_started,
             'latest_completed_at', v_factory_end,
             'reconciler', 'penta_self.reconcile_current_truth_v2'
           ),
           updated_at = now()
     where title = 'Latest active cron execution failed: ct-software-factory-continuity-v5'
       and state <> 'resolved';
    get diagnostics v_rows = row_count;
    v_resolved := v_resolved + v_rows;
  end if;

  update penta_self.problem_ledger_v1
     set state = 'resolved',
         resolved_at = coalesce(resolved_at, now()),
         blocked_reason = null,
         last_error = null,
         verification_evidence = coalesce(verification_evidence, '{}'::jsonb) || jsonb_build_object(
           'verified_at', now(),
           'projection_key', 'ct.os.phase.current',
           'canonical_phase', 3,
           'founder_operating_label', 'Phase 3.5 — convergence and hardening',
           'public_rollout_state', 'lane_specific',
           'reconciler', 'penta_self.reconcile_current_truth_v2'
         ),
         updated_at = now()
   where title = 'Public rollout language and OS institutional phase remain conflated'
     and state <> 'resolved';
  get diagnostics v_rows = row_count;
  v_resolved := v_resolved + v_rows;

  if to_regprocedure('crm.penta_marketer_refresh_event_projection_v2(text)') is not null then
    begin
      v_marketer := crm.penta_marketer_refresh_event_projection_v2(
        'ct.pentamarketer.locticians.claim.20260827.v1'
      );
    exception when others then
      v_marketer := jsonb_build_object('state', 'degraded', 'error_class', sqlstate);
    end;
  end if;

  v_payload := jsonb_build_object(
    'factory_latest_status', v_factory_status,
    'factory_latest_started_at', v_factory_started,
    'factory_latest_completed_at', v_factory_end,
    'resolved_count', v_resolved,
    'phase_projection', 'ct.os.phase.current',
    'marketer_projection', v_marketer,
    'observed_at', now()
  );
  v_digest := encode(extensions.digest(convert_to(v_payload::text, 'UTF8'), 'sha256'), 'hex');

  insert into penta_self.current_truth_receipts_v2(
    receipt_kind, subject_ref, observed_state, disposition, evidence_sha256
  ) values (
    'current_truth_reconcile', 'ct.penta.self.v2', v_payload, 'APPLIED', v_digest
  );

  perform chlom_runtime.append_dail_event(
    'pentaself.current_truth.reconciled',
    'self_healing',
    'ct.penta.self.v2',
    v_payload,
    'PentaSELF/PentaAssure',
    null,
    'PentaSELF',
    '2.0.0',
    v_digest,
    null,
    'ct.pentaself.scheduler-permanence.v2',
    null,
    'internal'
  );
  return v_payload;
end $$;

revoke all on function penta_self.reconcile_current_truth_v2()
  from public, anon, authenticated;
grant execute on function penta_self.reconcile_current_truth_v2()
  to service_role;

select penta_self.reconcile_current_truth_v2();

select cron.unschedule(jobid)
from cron.job
where jobname = 'ct-pentaself-current-truth-v2';

select cron.schedule(
  'ct-pentaself-current-truth-v2',
  '4-59/5 * * * *',
  'select penta_self.reconcile_current_truth_v2();'
);

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-pentaself-current-truth-v2',
  '4-59/5 * * * *',
  'select penta_self.reconcile_current_truth_v2();',
  2026082902,
  'ct.pentaself.scheduler-permanence.v2',
  jsonb_build_object(
    'owner', 'PentaSELF/PentaAssure',
    'rollback_policy', 'monotonic'
  )
);

-- Capture all current critical clocks at one monotonic generation.
do $$
declare
  r record;
begin
  for r in
    select jobname, schedule, command
    from cron.job
    where active = true
      and jobname in (
        'ct-penta-self-v1',
        'ct-penta-self-continuous-healing-v1',
        'ct-software-factory-continuity-v5',
        'penta-persona-execution-v1',
        'pentafactory-daily-agent-fleet-10x100-v1',
        'ct-penta-census-native-due-v1',
        'ct-pentamarketer-intake-cycle-v1',
        'ct-pentamarketer-event-projection-v2',
        'ct-locticians-native-monitor-v1',
        'ct-locticians-article-live-verifier-v1',
        'ct-locticians-article-schedule-dispatch-v1',
        'ct-locticians-bd-reference-daily-v3',
        'ct-locticians-bd-failover-reconcile-v3',
        'ct-locticians-bd-failover-daily-v3',
        'locticians-bd-contract-watch-v1',
        'ct-pentaself-current-truth-v2'
      )
  loop
    perform integration_control.scheduler_desired_job_upsert_v2(
      r.jobname,
      r.schedule,
      r.command,
      2026082902,
      'ct.pentaself.scheduler-permanence.v2',
      jsonb_build_object(
        'owner', 'PentaSELF/PentaTime/PentaAssure',
        'captured_from_live', true,
        'rollback_policy', 'monotonic',
        'captured_at', now()
      )
    );
  end loop;
end $$;

select integration_control.scheduler_permanence_reconcile_v2();
