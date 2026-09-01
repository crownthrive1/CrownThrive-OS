-- Transactional regression suite for PentaSecurity qualification semantics.
-- No persistent production effect: explicit ROLLBACK.

begin;

do $test$
declare
  v_security_roles text[];
  v_dnd_roles text[];
  v_security jsonb;
  v_dnd jsonb;
begin
  v_security_roles:=penta_pm.pr_roles_for_v1('PentaSecurity','system','security posture review');
  if not ('security_review'=any(v_security_roles)) then raise exception 'PENTASECURITY_SECURITY_REVIEW_ROLE_MISSING'; end if;
  if 'merge'=any(v_security_roles) or 'release'=any(v_security_roles) or 'certify'=any(v_security_roles) then
    raise exception 'PENTASECURITY_ROLE_OVEREXPANDED:%',v_security_roles;
  end if;

  v_dnd_roles:=penta_pm.pr_roles_for_v1('PentaDND','system','continuity');
  if cardinality(v_dnd_roles)<>0 then raise exception 'PENTADND_PM_GUARDRAIL_BROKEN:%',v_dnd_roles; end if;

  perform penta_pm.refresh_executable_pentas_v1();
  v_security:=public.penta_execution_semantics_v1('penta.security');
  v_dnd:=public.penta_execution_semantics_v1('penta.dnd');

  if v_security->>'native_execution_label'<>'NATIVE-EXECUTABLE (can run its own built-in runtime)' then
    raise exception 'PENTASECURITY_NATIVE_LABEL_BAD:%',v_security;
  end if;
  if coalesce((v_security->>'pm_assignment_eligible')::boolean,false) then
    raise exception 'PENTASECURITY_MUST_NOT_BYPASS_QUALIFICATION:%',v_security;
  end if;
  if v_security->>'pm_assignment_label' not like 'PM-QUALIFICATION-PENDING%' then
    raise exception 'PENTASECURITY_PENDING_LABEL_BAD:%',v_security;
  end if;
  if v_security->>'d3_label'<>'D3 HUMAN-RESERVED (Founder/Human only — never autonomous)' then
    raise exception 'PENTASECURITY_D3_LABEL_BAD:%',v_security;
  end if;

  if coalesce((v_dnd->>'pm_assignment_eligible')::boolean,false) then
    raise exception 'PENTADND_MUST_REMAIN_PM_NONASSIGNABLE:%',v_dnd;
  end if;
  if v_dnd->>'pm_assignment_label'<>'PM-NONASSIGNABLE (PentaPM will not assign it general work)' then
    raise exception 'PENTADND_HUMAN_LABEL_BAD:%',v_dnd;
  end if;
end
$test$;

rollback;