create or replace function public.thriveevergreen_hourly_product_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog','integration_control','developer_commerce','chlom_runtime','cron'
as $function$
  with p as (
    select * from integration_control.thriveevergreen_hourly_policy_v1
    where policy_id='ct.policy.thriveevergreen-hourly-product-orchestration.v1'
  ), latest as (
    select * from integration_control.thriveevergreen_hourly_runs_v1
    where policy_id='ct.policy.thriveevergreen-hourly-product-orchestration.v1'
    order by started_at desc limit 1
  )
  select jsonb_build_object(
    'contract','ct.status.thriveevergreen-hourly-product-orchestration.v1.2',
    'component_runtime_state',case
      when p.policy_state='active' and exists(select 1 from cron.job where jobname='ct-thriveevergreen-hourly-product-cycle-v1' and active)
        then 'production_observer_active'
      when p.policy_state='paused' then coalesce(p.metadata->>'component_runtime_state','paused')
      else 'staged' end,
    'whole_platform_phase3_certified',false,
    'decision_mode',p.runtime_mode,
    'production_effects_enabled',false,
    'production_write_gate','DENY',
    'publication_code_path_present',false,
    'publication_target_per_window',0,
    'candidate_attempt_target_per_window',1,
    'shared_slot_enforced',true,
    'preview_is_read_only',true,
    'hold_consumes_window',true,
    'catch_up_burst_allowed',false,
    'service_principal_state','HOLD_PROVIDER_EXECUTION_NOT_VERIFIED',
    'latest_run',case when latest.run_id is null then null else jsonb_build_object(
      'run_id',latest.run_id,
      'window_start',latest.window_start,
      'run_scope',latest.run_scope,
      'run_state',latest.run_state,
      'error_code',latest.error_code,
      'economic_verdict',latest.economic_verdict,
      'publication_decision',latest.publication_decision,
      'candidate_type',latest.selected_candidate_type,
      'candidate_ref',latest.selected_candidate_ref,
      'candidate_sku',latest.selected_sku,
      'candidate_package_id',latest.selected_package_id,
      'candidate_release_id',latest.selected_release_id,
      'candidate_surface_id',latest.selected_surface_id,
      'candidate_exact_version_ref',latest.selected_exact_version_ref,
      'candidate_content_sha256',latest.selected_content_sha256,
      'candidate_attempt_count',latest.candidate_attempt_count,
      'publication_count',latest.publication_count,
      'evidence_sha256',latest.evidence_sha256,
      'completed_at',latest.completed_at
    ) end,
    'credit_program_live_authorized',false
  ) from p left join latest on true;
$function$;

revoke execute on function public.thriveevergreen_hourly_product_status_v1() from public,anon,authenticated;
grant execute on function public.thriveevergreen_hourly_product_status_v1() to service_role;

create or replace function public.pentagreen_hourly_product_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog','public'
as $function$
  select public.thriveevergreen_hourly_product_status_v1()
    || jsonb_build_object('canonical_system','PentaGreen','legacy_system','ThriveEvergreen');
$function$;

revoke execute on function public.pentagreen_hourly_product_status_v1() from public,anon,authenticated;
grant execute on function public.pentagreen_hourly_product_status_v1() to service_role;
