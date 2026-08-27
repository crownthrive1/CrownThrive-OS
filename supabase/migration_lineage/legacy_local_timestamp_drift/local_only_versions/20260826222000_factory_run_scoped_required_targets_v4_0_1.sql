-- PentaFactory v4.0.1: evaluate release-required deployment targets in the
-- exact build-request scope. Globally registered targets remain visible but
-- cannot block an unrelated run after an explicit out-of-scope disposition.

create or replace function public.ct_factory_required_deployments_satisfied(p_run_id uuid)
returns boolean language sql stable security definer set search_path='public' as $$
with ctx as (
  select r.project_id,
         case when jsonb_typeof(r.requirements->'target_types')='array'
              then r.requirements->'target_types' else '[]'::jsonb end as target_types,
         case when jsonb_typeof(r.requirements->'target_surface_ids')='array'
              then r.requirements->'target_surface_ids' else '[]'::jsonb end as target_surface_ids
  from public.ct_factory_build_runs b
  join public.ct_factory_build_requests r on r.id=b.build_request_id
  where b.id=p_run_id
), required_targets as (
  select t.id
  from public.ct_factory_deployment_targets t
  join ctx on ctx.project_id=t.project_id
  where t.enabled
    and case when t.config ? 'required_for_release'
             then coalesce((t.config->>'required_for_release')::boolean,false)
             else t.target_type <> 'website_surface' end
    and (jsonb_array_length(ctx.target_types)=0 or ctx.target_types ? t.target_type)
    and (t.target_type <> 'website_surface'
         or jsonb_array_length(ctx.target_surface_ids)=0
         or ctx.target_surface_ids ? coalesce(t.config->>'surface_id',''))
)
select not exists (
  select 1 from required_targets rt
  left join public.ct_factory_deployments d
    on d.build_run_id=p_run_id and d.target_id=rt.id
  where d.id is null or d.state <> 'implemented'
);
$$;

revoke all on function public.ct_factory_required_deployments_satisfied(uuid) from public,anon,authenticated;
grant execute on function public.ct_factory_required_deployments_satisfied(uuid) to service_role;
