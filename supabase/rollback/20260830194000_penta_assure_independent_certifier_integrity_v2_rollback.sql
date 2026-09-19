-- Guarded rollback for 20260830194000_penta_assure_independent_certifier_integrity_v2.
-- Restores the exact production function contract observed before the v2 hardening.
-- Historical certification rows are preserved. This rollback does not create provider,
-- credential, money, rights, D3, vote/quorum, or authority expansion.

begin;

do $preflight$
declare
  v_def text;
begin
  if to_regprocedure('public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)') is null then
    raise exception 'rollback_refuses_missing_penta_assure_certify_v1';
  end if;

  select pg_get_functiondef('public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)'::regprocedure)
    into v_def;

  -- Refuse to roll back an unknown successor. These literals bind this rollback to the
  -- independently reviewed v2 poststate rather than to any future function version.
  if position('missing_certifier_or_originator_identity' in v_def) = 0
     or position('self_certification_detected' in v_def) = 0
     or position('certifier_is_builder' in v_def) = 0
     or position('certifier_is_producer' in v_def) = 0
     or position('independence_contract_version' in v_def) = 0
     or position('2.0.0' in v_def) = 0 then
    raise exception 'rollback_refuses_unknown_penta_assure_poststate';
  end if;

  if has_function_privilege('anon','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE')
     or has_function_privilege('authenticated','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE')
     or not has_function_privilege('service_role','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE') then
    raise exception 'rollback_refuses_acl_drift';
  end if;
end
$preflight$;

create or replace function public.penta_assure_certify_v1(
  p_subject_ref text,
  p_standard_ref text,
  p_risk_class text,
  p_evidence_refs jsonb,
  p_checks jsonb,
  p_expires_at timestamptz default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_id text; v_all boolean:=false; v_disp text; v_ind text;
begin
 if p_risk_class not in ('D0','D1','D2','D3') then raise exception 'INVALID_RISK_CLASS'; end if;
 if jsonb_typeof(coalesce(p_evidence_refs,'[]'::jsonb))<>'array' or jsonb_typeof(coalesce(p_checks,'[]'::jsonb))<>'array' then raise exception 'ASSURE_ARRAY_EVIDENCE_REQUIRED'; end if;
 v_all:=jsonb_array_length(coalesce(p_evidence_refs,'[]'::jsonb))>0 and jsonb_array_length(coalesce(p_checks,'[]'::jsonb))>0 and not exists(select 1 from jsonb_array_elements(p_checks) x where coalesce((x->>'passed')::boolean,false)=false);
 if p_risk_class='D3' then v_disp:='hold';v_ind:='not_satisfied'; else v_disp:=case when v_all then 'certified' else 'hold' end;v_ind:=case when v_all then 'separation_of_duties_satisfied' else 'not_satisfied' end; end if;
 v_id:='ct.assure.'||md5(p_subject_ref||'|'||p_standard_ref||'|'||clock_timestamp()::text);
 insert into public.penta_assure_certifications(certification_id,subject_ref,standard_ref,risk_class,evidence_refs,independence_state,checks,disposition,certified_at,expires_at,metadata)
 values(v_id,p_subject_ref,p_standard_ref,p_risk_class,coalesce(p_evidence_refs,'[]'::jsonb),v_ind,coalesce(p_checks,'[]'::jsonb),v_disp,case when v_disp='certified' then now() else null end,p_expires_at,coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('d3_human_reserved',true,'authority_expansion',false));
 return jsonb_build_object('certification_id',v_id,'disposition',v_disp,'independence_state',v_ind,'risk_class',p_risk_class,'d3_auto',false,'authority_expansion',false,'at',now());
end
$function$;

revoke all on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)
  from public, anon, authenticated;
grant execute on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)
  to service_role;

do $verify$
declare
  v_def text;
begin
  select pg_get_functiondef('public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)'::regprocedure)
    into v_def;

  if position('missing_certifier_or_originator_identity' in v_def) <> 0
     or position('independence_contract_version' in v_def) <> 0 then
    raise exception 'rollback_postcondition_function_not_restored';
  end if;

  if has_function_privilege('anon','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE')
     or has_function_privilege('authenticated','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE')
     or not has_function_privilege('service_role','public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)','EXECUTE') then
    raise exception 'rollback_postcondition_acl_mismatch';
  end if;
end
$verify$;

commit;
