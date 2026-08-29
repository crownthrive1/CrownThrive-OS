-- PentaRelease release-intelligence convergence hardening.
-- Tracks the production repairs applied during the v3.48.0.0 convergence incident:
-- 1. projection status must count configured required targets even before queue materialization;
-- 2. identical governed CIE results must be idempotent across hourly reconciliation passes.

create or replace function penta_os20.release_projection_status(p_release_version text)
returns jsonb
language sql
stable
set search_path to 'penta_os20','pg_temp'
as $function$
  select jsonb_build_object(
    'release_version',p_release_version,
    'required_targets',count(*) filter (where t.required),
    'synchronized_required',count(*) filter (where t.required and coalesce(q.status,'not_enqueued')='synchronized'),
    'open_required',count(*) filter (where t.required and coalesce(q.status,'not_enqueued')<>'synchronized'),
    'targets',coalesce(jsonb_agg(jsonb_build_object(
      'target_key',t.target_key,
      'target_type',t.target_type,
      'status',coalesce(q.status,'not_enqueued'),
      'provider_ref',t.provider_ref,
      'attempts',coalesce(q.attempts,0),
      'last_error',q.last_error,
      'payload_hash',q.payload_hash,
      'updated_at',q.updated_at
    ) order by t.target_key),'[]'::jsonb)
  )
  from penta_os20.release_projection_targets t
  left join lateral (
    select q1.*
    from penta_os20.release_projection_queue q1
    where q1.release_version=p_release_version and q1.target_id=t.id
    order by q1.updated_at desc, q1.created_at desc
    limit 1
  ) q on true
  where t.status='active';
$function$;

create or replace function penta_os20.resolve_release_evidence_bundle_v1(
  p_release_version text,
  p_payload_bytes bigint default 0,
  p_cie_subject jsonb default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_os20','public','extensions'
as $function$
declare
  v_eval jsonb;
  v_cie jsonb;
  v_subject jsonb;
  v_hash text;
  v_status text;
  v_score numeric;
  v_footer jsonb;
begin
  if coalesce(trim(p_release_version),'')='' then
    raise exception 'release_version_required';
  end if;

  v_eval:=penta_os20.evaluate_release(
    p_release_version,
    greatest(coalesce(p_payload_bytes,0),0)
  );

  if p_cie_subject is not null then
    v_subject:=p_cie_subject||jsonb_build_object(
      'subject_id',coalesce(p_cie_subject->>'subject_id',p_release_version),
      'subject_type',coalesce(p_cie_subject->>'subject_type','release')
    );

    v_cie:=public.ct_cie_score(
      'crownthrive1/CrownThrive-CIE',
      1341314455,
      'ct.framework-agent.cie',
      v_subject
    );
    v_status:=coalesce(v_cie->>'verdict','HOLD_INSUFFICIENT_EVIDENCE');
    begin
      v_score:=nullif(v_cie->>'score','')::numeric;
    exception when others then
      v_score:=null;
    end;
    v_hash:=encode(extensions.digest(convert_to(v_cie::text,'UTF8'),'sha256'),'hex');

    if not exists (
      select 1
      from penta_os20.cie_evidence
      where release_version=p_release_version
        and evidence_hash=v_hash
    ) then
      insert into penta_os20.cie_evidence(
        release_version,score,status,source,evidence,evidence_hash
      ) values (
        p_release_version,
        v_score,
        v_status,
        'public.ct_cie_score / ct.framework-package.cie',
        v_cie,
        v_hash
      );
    end if;
  end if;

  v_footer:=public.penta_release_footer_v1(p_release_version);
  return jsonb_build_object(
    'release_version',p_release_version,
    'evaluation',v_eval,
    'footer',v_footer,
    'resolved_at',now()
  );
end
$function$;

comment on function penta_os20.release_projection_status(text) is
  'PentaRelease projection status across every active configured target; unqueued required targets remain open rather than disappearing from the denominator.';

comment on function penta_os20.resolve_release_evidence_bundle_v1(text,bigint,jsonb) is
  'Canonical PentaRelease economics/CIE resolver; CIE scoring remains governed by public.ct_cie_score and identical evidence rows are idempotent.';
