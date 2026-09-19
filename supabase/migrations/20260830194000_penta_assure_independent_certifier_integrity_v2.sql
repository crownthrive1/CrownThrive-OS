-- PentaAssure independent-certifier integrity v2
--
-- Scope: repair separation-of-duties truth for public.penta_assure_certify_v1.
-- This migration does not create a new authority, grant D3 authority, expand provider
-- write scope, rotate credentials, move money, or create CHLOM rights. It only prevents
-- a certification from being marked certified when independent certifier identity is
-- absent or conflicts with the originator/builder/producer identities supplied by the
-- governed service-role caller. The entrypoint is explicitly service-role only.

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
declare
  v_id text;
  v_all boolean := false;
  v_disp text := 'hold';
  v_ind text := 'not_satisfied';
  v_reason text := 'independence_unproven';
  v_certifier text;
  v_originator text;
  v_builders jsonb := '[]'::jsonb;
  v_producers jsonb := '[]'::jsonb;
  v_identity_shape_valid boolean := true;
  v_independence_proven boolean := false;
begin
  if p_risk_class not in ('D0','D1','D2','D3') then
    raise exception 'INVALID_RISK_CLASS';
  end if;

  if jsonb_typeof(coalesce(p_evidence_refs,'[]'::jsonb)) <> 'array'
     or jsonb_typeof(coalesce(p_checks,'[]'::jsonb)) <> 'array' then
    raise exception 'ASSURE_ARRAY_EVIDENCE_REQUIRED';
  end if;

  if jsonb_typeof(coalesce(p_metadata,'{}'::jsonb)) <> 'object' then
    raise exception 'ASSURE_METADATA_OBJECT_REQUIRED';
  end if;

  v_all :=
    jsonb_array_length(coalesce(p_evidence_refs,'[]'::jsonb)) > 0
    and jsonb_array_length(coalesce(p_checks,'[]'::jsonb)) > 0
    and not exists (
      select 1
      from jsonb_array_elements(coalesce(p_checks,'[]'::jsonb)) x
      where jsonb_typeof(x) <> 'object'
         or coalesce(x->>'passed','false') <> 'true'
    );

  v_certifier := nullif(btrim(coalesce(p_metadata->>'certifier_id','')), '');
  v_originator := nullif(btrim(coalesce(p_metadata->>'originator_id','')), '');

  if p_metadata ? 'builder_ids' then
    if jsonb_typeof(p_metadata->'builder_ids') <> 'array' then
      v_identity_shape_valid := false;
      v_reason := 'invalid_builder_identity_shape';
    else
      v_builders := p_metadata->'builder_ids';
      if exists (
        select 1 from jsonb_array_elements(v_builders) e
        where jsonb_typeof(e) <> 'string' or nullif(btrim(e #>> '{}'), '') is null
      ) then
        v_identity_shape_valid := false;
        v_reason := 'invalid_builder_identity_shape';
      end if;
    end if;
  end if;

  if p_metadata ? 'producer_ids' then
    if jsonb_typeof(p_metadata->'producer_ids') <> 'array' then
      v_identity_shape_valid := false;
      v_reason := 'invalid_producer_identity_shape';
    else
      v_producers := p_metadata->'producer_ids';
      if exists (
        select 1 from jsonb_array_elements(v_producers) e
        where jsonb_typeof(e) <> 'string' or nullif(btrim(e #>> '{}'), '') is null
      ) then
        v_identity_shape_valid := false;
        v_reason := 'invalid_producer_identity_shape';
      end if;
    end if;
  end if;

  if v_certifier is null or v_originator is null then
    v_reason := 'missing_certifier_or_originator_identity';
  elsif lower(v_certifier) = lower(v_originator) then
    v_reason := 'self_certification_detected';
  elsif v_identity_shape_valid and exists (
    select 1 from jsonb_array_elements_text(v_builders) b(value)
    where lower(btrim(value)) = lower(v_certifier)
  ) then
    v_reason := 'certifier_is_builder';
  elsif v_identity_shape_valid and exists (
    select 1 from jsonb_array_elements_text(v_producers) p(value)
    where lower(btrim(value)) = lower(v_certifier)
  ) then
    v_reason := 'certifier_is_producer';
  elsif v_identity_shape_valid then
    v_independence_proven := true;
    v_reason := 'separation_of_duties_satisfied';
  end if;

  if p_risk_class = 'D3' then
    v_disp := 'hold';
    v_ind := 'not_satisfied';
    v_reason := 'd3_human_reserved';
  elsif v_all and v_independence_proven then
    v_disp := 'certified';
    v_ind := 'separation_of_duties_satisfied';
  else
    v_disp := 'hold';
    v_ind := 'not_satisfied';
  end if;

  v_id := 'ct.assure.' || md5(p_subject_ref || '|' || p_standard_ref || '|' || clock_timestamp()::text);

  insert into public.penta_assure_certifications(
    certification_id, subject_ref, standard_ref, risk_class, evidence_refs,
    independence_state, checks, disposition, certified_at, expires_at, metadata
  ) values (
    v_id, p_subject_ref, p_standard_ref, p_risk_class,
    coalesce(p_evidence_refs,'[]'::jsonb), v_ind,
    coalesce(p_checks,'[]'::jsonb), v_disp,
    case when v_disp = 'certified' then now() else null end,
    p_expires_at,
    coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'd3_human_reserved', true,
      'authority_expansion', false,
      'independence_reason', v_reason,
      'independence_contract_version', '2.0.0'
    )
  );

  return jsonb_build_object(
    'certification_id', v_id,
    'disposition', v_disp,
    'independence_state', v_ind,
    'independence_reason', v_reason,
    'risk_class', p_risk_class,
    'd3_auto', false,
    'authority_expansion', false,
    'at', now()
  );
end
$function$;

revoke all on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)
  from public, anon, authenticated;
grant execute on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)
  to service_role;

comment on function public.penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)
is 'PentaAssure certification entrypoint with fail-closed independent-certifier identity enforcement. Service-role only. D3 remains human-reserved; this function does not create authority.';