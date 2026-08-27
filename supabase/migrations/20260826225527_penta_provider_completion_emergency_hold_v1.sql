-- Close the provider completion side of the 2026-08-26 emergency containment.
-- Held or adapter-disabled work cannot be promoted by a stale workflow run.

create or replace function public.ct_factory_provider_job_implemented(
  p_job_id uuid,
  p_response jsonb,
  p_readback jsonb,
  p_rollback_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'public'
as $$
declare
  v_job public.ct_factory_provider_jobs%rowtype;
  v_adapter public.ct_factory_provider_adapters%rowtype;
  v_assurance uuid;
  v_ready boolean;
  v_commit text := coalesce(p_response->>'commit_sha', '');
  v_gate_run text := coalesce(p_readback->>'governance_gate_run_id', '');
begin
  select * into v_job
  from public.ct_factory_provider_jobs
  where id = p_job_id
  for update;

  if not found then
    raise exception 'provider_job_not_found';
  end if;

  select * into v_adapter
  from public.ct_factory_provider_adapters
  where adapter_key = v_job.adapter_key;

  if v_job.state <> 'claimed' then
    raise exception 'provider_job_not_claimed';
  end if;
  if not coalesce(v_adapter.enabled, false) or v_adapter.verification_state <> 'verified' then
    raise exception 'provider_adapter_not_execution_enabled';
  end if;
  if v_commit !~ '^[0-9a-f]{40}$' then
    raise exception 'provider_commit_sha_invalid';
  end if;
  if v_gate_run = '' then
    raise exception 'governance_gate_readback_required';
  end if;
  if nullif(p_rollback_ref, '') is null then
    raise exception 'provider_rollback_ref_required';
  end if;

  update public.ct_factory_provider_jobs
  set state = 'implemented',
      response = coalesce(p_response, '{}'::jsonb),
      readback = coalesce(p_readback, '{}'::jsonb),
      rollback_ref = p_rollback_ref,
      completed_at = clock_timestamp(),
      updated_at = clock_timestamp(),
      last_error = null
  where id = p_job_id;

  if v_job.target_id is not null then
    insert into public.ct_factory_deployments(build_run_id, target_id, state, evidence)
    values (
      v_job.build_run_id,
      v_job.target_id,
      'implemented',
      jsonb_build_object(
        'provider_job_id', p_job_id,
        'response', coalesce(p_response, '{}'::jsonb),
        'readback', coalesce(p_readback, '{}'::jsonb),
        'rollback_ref', p_rollback_ref,
        'implemented_at', clock_timestamp()
      )
    )
    on conflict(build_run_id, target_id) do update
    set state = 'implemented',
        evidence = excluded.evidence,
        updated_at = clock_timestamp();
  end if;

  v_ready := public.ct_factory_required_deployments_satisfied(v_job.build_run_id);

  select id into v_assurance
  from public.ct_factory_work_units
  where build_run_id = v_job.build_run_id
    and lane = 'assurance'
  limit 1;

  if v_assurance is not null and v_ready then
    update public.ct_factory_release_packages
    set status = 'candidate', implemented_at = null
    where build_run_id = v_job.build_run_id
      and status = 'hold';

    update public.ct_factory_work_units
    set status = 'ready',
        completed_at = null,
        started_at = null,
        lease_until = null,
        output = '{}'::jsonb
    where id = v_assurance
      and status in ('hold', 'failed', 'queued');

    update public.ct_factory_build_runs
    set status = 'deploying', completed_at = null
    where id = v_job.build_run_id
      and status in ('hold', 'failed', 'deploying', 'assuring');

    perform public.ct_factory_tick();
  end if;

  return jsonb_build_object(
    'job_id', p_job_id,
    'build_run_id', v_job.build_run_id,
    'target_id', v_job.target_id,
    'state', 'implemented',
    'required_deployments_satisfied', v_ready,
    'assurance_reopened', coalesce(v_assurance is not null and v_ready, false)
  );
end;
$$;

create or replace function public.ct_factory_complete_provider_job(
  p_job_id uuid,
  p_state text,
  p_response jsonb default '{}'::jsonb,
  p_readback jsonb default '{}'::jsonb,
  p_rollback_ref text default null,
  p_error text default null
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog', 'public'
as $$
declare
  v_job public.ct_factory_provider_jobs%rowtype;
  v_enabled boolean;
  v_verified boolean;
begin
  if p_state not in ('implemented', 'failed', 'hold', 'rolled_back') then
    raise exception 'invalid_provider_job_state';
  end if;

  select * into v_job
  from public.ct_factory_provider_jobs
  where id = p_job_id
  for update;

  if not found then
    raise exception 'provider_job_not_found';
  end if;

  select a.enabled, a.verification_state = 'verified'
  into v_enabled, v_verified
  from public.ct_factory_provider_adapters a
  where a.adapter_key = v_job.adapter_key;

  if p_state = 'implemented' then
    if v_job.state <> 'claimed' then raise exception 'provider_job_not_claimed'; end if;
    if not coalesce(v_enabled, false) or not coalesce(v_verified, false) then
      raise exception 'provider_adapter_not_execution_enabled';
    end if;
  end if;

  update public.ct_factory_provider_jobs
  set state = p_state,
      response = coalesce(p_response, '{}'::jsonb),
      readback = coalesce(p_readback, '{}'::jsonb),
      rollback_ref = p_rollback_ref,
      last_error = p_error,
      completed_at = clock_timestamp(),
      updated_at = clock_timestamp()
  where id = p_job_id;

  return jsonb_build_object('job_id', p_job_id, 'state', p_state);
end;
$$;

revoke all on function public.ct_factory_provider_job_implemented(uuid, jsonb, jsonb, text) from public, anon, authenticated;
revoke all on function public.ct_factory_complete_provider_job(uuid, text, jsonb, jsonb, text, text) from public, anon, authenticated;
grant execute on function public.ct_factory_provider_job_implemented(uuid, jsonb, jsonb, text) to service_role;
grant execute on function public.ct_factory_complete_provider_job(uuid, text, jsonb, jsonb, text, text) to service_role;

insert into integration_control.penta_certify_receipts_v3(event_type, state, evidence)
values (
  'penta.provider.completion_containment',
  'hold',
  jsonb_build_object(
    'adapter_key', 'ct.adapter.github.actions.v1',
    'completion_requires_exact_claimed_state', true,
    'completion_requires_enabled_verified_adapter', true,
    'completion_requires_gate_readback', true,
    'promotion_workflow_containment_commit', '1c7b030797d0f4433446a4a4817170c606ef1ba8',
    'authority_reducing', true,
    'authority_manufactured', false,
    'at', clock_timestamp()
  )
);
