-- Emergency authority-reducing containment for the 2026-08-26 provider drain.
-- This preserves every job and branch while blocking new claims until the
-- PentaQueue flow-control gate is deployed and independently verified.

update public.ct_factory_provider_adapters
set enabled = false,
    configuration = coalesce(configuration, '{}'::jsonb) || jsonb_build_object(
      'containment_state', 'fail_closed',
      'containment_reason', 'exact_head_gate_and_promotion_continuation_failed',
      'contained_at', clock_timestamp(),
      're_enable_requires', 'certified_penta_queue_admission_fencing_and_promotion_readback'
    ),
    updated_at = clock_timestamp()
where adapter_key = 'ct.adapter.github.actions.v1';

update public.ct_factory_provider_jobs
set state = 'hold',
    completed_at = coalesce(completed_at, clock_timestamp()),
    last_error = case
      when coalesce(last_error, '') like '%PENTAQUEUE_EMERGENCY_CONTAINMENT_20260826%'
        then last_error
      else concat_ws(' | ', nullif(last_error, ''), 'PENTAQUEUE_EMERGENCY_CONTAINMENT_20260826')
    end,
    updated_at = clock_timestamp()
where adapter_key = 'ct.adapter.github.actions.v1'
  and state in ('queued', 'claimed');

create or replace function public.ct_factory_claim_provider_job(p_adapter_key text)
returns table(job_id uuid, build_run_id uuid, target_id uuid, operation text, request jsonb)
language plpgsql
security definer
set search_path = 'pg_catalog', 'public'
as $$
begin
  if not exists (
    select 1
    from public.ct_factory_provider_adapters a
    where a.adapter_key = p_adapter_key
      and a.enabled
      and a.verification_state = 'verified'
  ) then
    return;
  end if;

  return query
  with candidate as (
    select j.id
    from public.ct_factory_provider_jobs j
    where j.adapter_key = p_adapter_key
      and j.state = 'queued'
      and j.available_at <= clock_timestamp()
    order by j.created_at, j.id
    for update skip locked
    limit 1
  )
  update public.ct_factory_provider_jobs j
  set state = 'claimed',
      claimed_at = clock_timestamp(),
      attempt_count = j.attempt_count + 1,
      updated_at = clock_timestamp()
  from candidate c
  where j.id = c.id
  returning j.id, j.build_run_id, j.target_id, j.operation, j.request;
end;
$$;

revoke all on function public.ct_factory_claim_provider_job(text) from public, anon, authenticated;
grant execute on function public.ct_factory_claim_provider_job(text) to service_role;

insert into integration_control.penta_certify_receipts_v3(event_type, state, evidence)
values (
  'penta.provider.emergency_containment',
  'hold',
  jsonb_build_object(
    'adapter_key', 'ct.adapter.github.actions.v1',
    'workflow_commit', '7a4f4ce5d82b97efd297e85b07565ccdada1cac6',
    'containment_branch_commit', '180a8cc0c3c32b89e11fc46315be665676d3cc32',
    'jobs_preserved', true,
    'branches_preserved', true,
    'authority_reducing', true,
    'authority_manufactured', false,
    'at', clock_timestamp()
  )
);
