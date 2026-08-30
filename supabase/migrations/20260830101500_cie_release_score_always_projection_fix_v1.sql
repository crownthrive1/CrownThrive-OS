-- Correct PentaRelease CIE semantic drift.
-- Applicable releases must resolve a real CIE score through the governed CIE runtime.
-- Missing/failed scoring must fail closed as a scoring/runtime defect; it must not be relabeled as a CIE score/status.

create or replace function penta_os20.resolve_release_evidence_bundle_v1(
  p_release_version text,
  p_payload_bytes bigint default 0,
  p_cie_subject jsonb default null
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_os20','public','extensions'
as $$
declare
  v_eval jsonb;
  v_cie jsonb;
  v_subject jsonb;
  v_hash text;
  v_semantic_hash text;
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

  -- Releases are applicable CIE subjects. Build the minimum governed subject even when
  -- the caller did not supply optional dimensions; the protected score-always runtime
  -- owns how missing dimensions affect the numerical score/confidence.
  v_subject:=coalesce(p_cie_subject,'{}'::jsonb)||jsonb_build_object(
    'subject_id',coalesce(p_cie_subject->>'subject_id',p_release_version),
    'subject_type',coalesce(p_cie_subject->>'subject_type','release'),
    'release_version',p_release_version,
    'payload_bytes',greatest(coalesce(p_payload_bytes,0),0)
  );

  -- Canonical governed implementation repository. The prior literal omitted "-OS"
  -- and therefore could not bind the active CIE framework agent to the repository.
  v_cie:=public.ct_cie_score(
    'crownthrive1/CrownThrive-CIE-OS',
    1341314455,
    'ct.framework-agent.cie',
    v_subject
  );

  v_status:=coalesce(v_cie->>'verdict','UNSCORED_RUNTIME_UNAVAILABLE');
  begin
    v_score:=nullif(v_cie->>'score','')::numeric;
  exception when others then
    v_score:=null;
  end;

  if v_score is null then
    raise exception 'cie_score_missing_for_scorable_release:%',p_release_version;
  end if;

  v_hash:=encode(extensions.digest(convert_to(v_cie::text,'UTF8'),'sha256'),'hex');
  v_semantic_hash:=encode(
    extensions.digest(convert_to((v_cie-'chain_event_hash')::text,'UTF8'),'sha256'),
    'hex'
  );

  if not exists (
    select 1
    from penta_os20.cie_evidence e
    where e.release_version=p_release_version
      and encode(
        extensions.digest(convert_to((e.evidence-'chain_event_hash')::text,'UTF8'),'sha256'),
        'hex'
      )=v_semantic_hash
  ) then
    insert into penta_os20.cie_evidence(
      release_version,score,status,source,evidence,evidence_hash
    ) values (
      p_release_version,
      v_score,
      v_status,
      'public.ct_cie_score / ct.framework-package.cie / score-always-waiver-v1',
      v_cie,
      v_hash
    );
  end if;

  v_footer:=public.penta_release_footer_v1(p_release_version);
  return jsonb_build_object(
    'release_version',p_release_version,
    'evaluation',v_eval,
    'cie',v_cie,
    'footer',v_footer,
    'resolved_at',now()
  );
end
$$;

comment on function penta_os20.resolve_release_evidence_bundle_v1(text,bigint,jsonb) is
'Resolves PentaRelease economic + governed score-always CIE evidence. Scorable releases require a numerical CIE score; scoring/runtime failure is not represented as HOLD_INSUFFICIENT_EVIDENCE.';
