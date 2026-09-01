-- CrownThrive COS — PentaSecurity PM qualification semantics v1
-- Fixes a real roster defect: PentaSecurity had no named PentaPM worker role.
-- This migration adds ONLY the bounded `security_review` role and human-readable
-- execution labels. It does not make PentaSecurity executable by itself.
-- PentaPM assignment still requires production maturity + active node + current cookie.
-- D3 remains Founder/Human-only and is never granted by this migration.

create or replace function penta_pm.pr_roles_for_v1(
  p_name text,
  p_category text default null,
  p_capability_text text default null
)
returns text[]
language plpgsql
immutable
as $function$
declare n text:=lower(coalesce(p_name,'')); r text[]:='{}';
begin
  if n ~ '(sink|registry)' then return '{}'::text[]; end if;
  if n ~ 'pentabuild|penta build|pentafactory|penta factory' then r:=array_append(r,'build'); end if;
  if n ~ 'pentatest|penta test' then r:=array_append(r,'test'); end if;
  if n ~ 'pentacertif|penta certif' then r:=array_append(r,'certify'); end if;
  if n ~ 'pentaassure|penta assure' then r:=array_append(r,'review'); end if;
  if n ~ 'pentasecurity|penta security' then r:=array_append(r,'security_review'); end if;
  if n ~ '^pentapr$|^penta pr$|pentapr agent|penta pr agent' then r:=array_append(r,'pr_classify'); end if;
  if n ~ 'pentamerge|penta merge' then r:=array_append(r,'merge'); end if;
  if n ~ 'pentacloser|penta closer' then r:=array_append(r,'close'); end if;
  if n ~ 'pentatagger|penta tagger' then r:=array_append(r,'tag'); end if;
  if n ~ 'pentarelease|penta release' then r:=array_append(r,'release'); end if;
  return coalesce((select array_agg(distinct x order by x) from unnest(r) x),'{}'::text[]);
end $function$;

create or replace function public.penta_execution_semantics_v1(p_system_key text)
returns jsonb
language sql
stable
security definer
set search_path='pg_catalog','public','penta_pm'
as $function$
with r as (
  select * from public.penta_system_registry where system_key=p_system_key
), pm as (
  select
    coalesce(bool_or(ep.pr_eligible),false) as has_pm_role,
    coalesce(bool_or(ep.pr_eligible and ep.execution_state='active' and ep.cookie_current),false) as pm_assignment_eligible,
    coalesce(bool_or(ep.cookie_current),false) as cookie_current,
    coalesce(jsonb_agg(distinct ep.execution_state) filter (where ep.execution_state is not null),'[]'::jsonb) as execution_states
  from r
  left join penta_pm.executable_pentas_v1 ep
    on ep.current and lower(ep.canonical_name)=lower(r.canonical_name)
), roles as (
  select coalesce(jsonb_agg(distinct role order by role),'[]'::jsonb) as role_list
  from r
  join penta_pm.executable_pentas_v1 ep on ep.current and lower(ep.canonical_name)=lower(r.canonical_name)
  cross join lateral unnest(ep.pr_roles) role
)
select jsonb_build_object(
  'system_key',r.system_key,
  'canonical_name',r.canonical_name,
  'maturity',r.maturity,
  'runtime_ref',r.runtime_ref,
  'native_execution_eligible',r.runtime_ref is not null,
  'native_execution_label',case when r.runtime_ref is not null
      then 'NATIVE-EXECUTABLE (can run its own built-in runtime)'
      else 'NO-NATIVE-RUNTIME (no built-in runtime currently registered)' end,
  'pm_assignment_eligible',pm.pm_assignment_eligible,
  'pm_assignment_roles',roles.role_list,
  'pm_execution_states',pm.execution_states,
  'pm_cookie_current',pm.cookie_current,
  'pm_assignment_label',case
      when pm.pm_assignment_eligible then 'PM-ASSIGNABLE (PentaPM may assign only its approved worker role)'
      when pm.has_pm_role then 'PM-QUALIFICATION-PENDING (worker role exists; certification/node/cookie gates are not all satisfied)'
      else 'PM-NONASSIGNABLE (PentaPM will not assign it general work)'
    end,
  'authority_ceiling',r.risk_ceiling,
  'authority_ceiling_label',case upper(coalesce(r.risk_ceiling,'D0'))
      when 'D0' then 'D0 (read/observe only)'
      when 'D1' then 'D1 (low-risk bounded change)'
      when 'D2' then 'D2 (production change with guardrails)'
      when 'D3' then 'D3 (Founder/Human only — never autonomous)'
      else coalesce(r.risk_ceiling,'UNKNOWN')||' (unclassified authority ceiling)'
    end,
  'd3_human_reserved',coalesce((r.metadata->>'d3_human_reserved')::boolean,false),
  'd3_label',case when coalesce((r.metadata->>'d3_human_reserved')::boolean,false)
      then 'D3 HUMAN-RESERVED (Founder/Human only — never autonomous)'
      else 'D3 POLICY NOT DECLARED HERE (check governing authority contract)' end,
  'autonomous_authority_ceiling',case
      when upper(coalesce(r.risk_ceiling,'D0'))='D3' and coalesce((r.metadata->>'d3_human_reserved')::boolean,false) then 'D2'
      else upper(coalesce(r.risk_ceiling,'D0')) end,
  'self_certification_allowed',false,
  'self_certification_label','SEPARATE CERTIFIER REQUIRED (this Penta cannot certify itself)',
  'machine_vs_human_note','Machine fields remain canonical; parenthetical labels are operator explanations only and create no authority.'
)
from r cross join pm cross join roles;
$function$;

revoke all on function public.penta_execution_semantics_v1(text) from public,anon,authenticated;
grant execute on function public.penta_execution_semantics_v1(text) to service_role;

-- Refresh the derived roster. PentaSecurity should enter certification_required,
-- not the active execution pool, until the independent certification + node/cookie
-- predicates are independently satisfied.
select penta_pm.refresh_executable_pentas_v1();

do $verify$
declare
  v_security_roles text[];
  v_dnd_roles text[];
  v_status jsonb;
begin
  v_security_roles:=penta_pm.pr_roles_for_v1('PentaSecurity','system','security posture review');
  if not ('security_review'=any(v_security_roles)) then raise exception 'PENTASECURITY_PM_ROLE_MISSING'; end if;

  v_dnd_roles:=penta_pm.pr_roles_for_v1('PentaDND','system','continuity');
  if cardinality(v_dnd_roles)<>0 then raise exception 'PENTADND_MUST_REMAIN_PM_NONASSIGNABLE:%',v_dnd_roles; end if;

  v_status:=public.penta_execution_semantics_v1('penta.security');
  if coalesce((v_status->>'pm_assignment_eligible')::boolean,false) then
    raise exception 'PENTASECURITY_PRECERT_ASSIGNMENT_NOT_ALLOWED:%',v_status;
  end if;
  if v_status->>'pm_assignment_label' not like 'PM-QUALIFICATION-PENDING%' then
    raise exception 'PENTASECURITY_EXPECTED_QUALIFICATION_PENDING:%',v_status;
  end if;
  if v_status->>'d3_label'<>'D3 HUMAN-RESERVED (Founder/Human only — never autonomous)' then
    raise exception 'D3_HUMAN_LABEL_MISSING:%',v_status;
  end if;
end $verify$;