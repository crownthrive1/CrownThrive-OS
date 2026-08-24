-- Applied to the canonical ThriveBase Supabase project as migration
-- 20260824010127 normalize_integration_rate_check_zero_semantics_v9.
-- This changes the runtime-facing zero-limit label only; zero already denied requests.

create or replace function public.integration_rate_check(p_service_id text, p_actor text, p_window_seconds integer default 60, p_max_requests integer default 30)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  v_count bigint;
  v_limit integer := greatest(1,least(coalesce(p_max_requests,30),300));
  v_window integer := greatest(1,least(coalesce(p_window_seconds,60),3600));
  v_month_limit integer;
  v_month_count bigint;
  v_month_allowed boolean;
begin
  select count(*) into v_count from integration_control.request_audit
  where service_id=p_service_id and actor=p_actor and created_at>=now()-make_interval(secs=>v_window);

  select monthly_request_limit into v_month_limit from integration_control.services where service_id=p_service_id;
  select request_count into v_month_count from integration_control.request_budget where service_id=p_service_id;

  v_month_allowed := case
    when v_month_limit=-1 then true
    when v_month_limit=0 then false
    when v_month_limit is null then false
    else coalesce(v_month_count,0)<v_month_limit
  end;

  return jsonb_build_object(
    'allowed',v_count<v_limit and v_month_allowed,
    'window_seconds',v_window,
    'max_requests',v_limit,
    'window_count',v_count,
    'monthly_limit',v_month_limit,
    'monthly_count',coalesce(v_month_count,0),
    'monthly_limit_semantics',case when v_month_limit=-1 then 'unlimited_local_ceiling' when v_month_limit=0 then 'exactly_zero_requests' when v_month_limit is null then 'unresolved_fail_closed' else 'literal_positive_ceiling' end,
    'provider_throttles_still_apply',true
  );
end
$function$;