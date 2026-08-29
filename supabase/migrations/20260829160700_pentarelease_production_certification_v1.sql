-- PentaRelease production certification hardening.
-- Persists the active production fixes proven during v3.49 release convergence:
-- 1) stable semantic CIE evidence across reconciliation executions;
-- 2) incomplete HOLD payloads cannot downgrade an existing governed PASS;
-- 3) release evidence SHA is stable when only chain_event_hash changes;
-- 4) projection targets point at the surfaces/providers that actually own release state.

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
  v_semantic_hash text;
  v_status text;
  v_score numeric;
  v_footer jsonb;
  v_existing_pass boolean;
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

    select exists(
      select 1
      from penta_os20.cie_evidence e
      where e.release_version=p_release_version
        and e.status='PASS'
        and e.score is not null
    ) into v_existing_pass;

    v_hash:=encode(extensions.digest(convert_to(v_cie::text,'UTF8'),'sha256'),'hex');
    v_semantic_hash:=encode(
      extensions.digest(convert_to((v_cie-'chain_event_hash')::text,'UTF8'),'sha256'),
      'hex'
    );

    -- A missing/incomplete reconciliation subject is not new governed evidence
    -- and cannot downgrade a release that already has a governed PASS.
    -- Genuine non-HOLD semantic changes, including a future governed FAIL,
    -- remain recordable.
    if not (v_status='HOLD_INSUFFICIENT_EVIDENCE' and v_existing_pass) then
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
          'public.ct_cie_score / ct.framework-package.cie',
          v_cie,
          v_hash
        );
      end if;
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

create or replace function public.penta_release_footer_v1(p_release_version text)
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','extensions'
as $function$
declare
  v_econ jsonb;
  v_cie penta_os20.cie_evidence%rowtype;
  v_provider_actual_minor bigint;
  v_provider_estimated_minor bigint;
  v_pay_gross_minor bigint;
  v_pay_settled_minor bigint;
  v_reserved_units bigint;
  v_accounted_units bigint;
  v_footer jsonb;
  v_hash text;
begin
  if coalesce(trim(p_release_version),'')='' then
    raise exception 'release_version_required';
  end if;

  v_econ:=public.penta_release_economic_envelope_v2(p_release_version);

  -- Select one row per semantic CIE state, ignoring per-execution
  -- chain_event_hash volatility, then choose the newest semantic state.
  select c.* into v_cie
  from penta_os20.cie_evidence c
  where c.release_version=p_release_version
    and c.created_at=(
      select min(c2.created_at)
      from penta_os20.cie_evidence c2
      where c2.release_version=c.release_version
        and (c2.evidence-'chain_event_hash')=(c.evidence-'chain_event_hash')
    )
  order by c.created_at desc
  limit 1;

  v_provider_actual_minor:=coalesce((v_econ#>>'{provider_cost,actual_minor}')::bigint,0);
  v_provider_estimated_minor:=coalesce((v_econ#>>'{provider_cost,estimated_minor}')::bigint,0);
  v_pay_gross_minor:=coalesce((v_econ#>>'{pay_obligations,gross_minor}')::bigint,0);
  v_pay_settled_minor:=coalesce((v_econ#>>'{pay_obligations,settled_minor}')::bigint,0);
  v_reserved_units:=coalesce((v_econ#>>'{internal_execution,reserved_units}')::bigint,0);
  v_accounted_units:=coalesce((v_econ#>>'{internal_execution,accounted_units}')::bigint,0);

  v_footer:=jsonb_build_object(
    'schema','ct.pentarelease.evidence-footer.v1',
    'release_version',p_release_version,
    'penta_costs',jsonb_build_object(
      'internal_reserved_units',v_reserved_units,
      'internal_accounted_units',v_accounted_units,
      'provider_estimated_minor',v_provider_estimated_minor,
      'provider_actual_minor',v_provider_actual_minor,
      'currency','USD',
      'provider_estimated_usd',round(v_provider_estimated_minor::numeric/100,2),
      'provider_actual_usd',round(v_provider_actual_minor::numeric/100,2),
      'internal_units_are_not_currency',true
    ),
    'penta_pay',jsonb_build_object(
      'obligation_count',coalesce((v_econ#>>'{pay_obligations,count}')::bigint,0),
      'gross_minor',v_pay_gross_minor,
      'settled_minor',v_pay_settled_minor,
      'currency','USD',
      'gross_usd',round(v_pay_gross_minor::numeric/100,2),
      'settled_usd',round(v_pay_settled_minor::numeric/100,2),
      'pay_obligation_is_not_dispatch_authority',true
    ),
    'usd_summary',jsonb_build_object(
      'currency','USD',
      'provider_actual_usd',round(v_provider_actual_minor::numeric/100,2),
      'penta_pay_gross_usd',round(v_pay_gross_minor::numeric/100,2),
      'penta_pay_settled_usd',round(v_pay_settled_minor::numeric/100,2),
      'recognized_release_exposure_usd',round((v_provider_actual_minor+v_pay_gross_minor)::numeric/100,2),
      'translation_basis','certified provider-cost minor units plus explicit PentaPay USD obligations; internal execution units are displayed separately and are not converted to currency'
    ),
    'cie',case when v_cie.id is null then jsonb_build_object(
        'status','HOLD_INSUFFICIENT_EVIDENCE',
        'score',null,
        'source',null,
        'evidence_hash',null,
        'reason','no release-specific governed CIE evidence has been recorded'
      ) else jsonb_build_object(
        'status',v_cie.status,
        'score',v_cie.score,
        'source',v_cie.source,
        'evidence_hash',v_cie.evidence_hash,
        'evidence',v_cie.evidence
      ) end,
    'settlement_finality',v_econ->'settlement_finality',
    'separation_invariant',v_econ->'separation_invariant'
  );

  v_hash:=encode(extensions.digest(convert_to(v_footer::text,'UTF8'),'sha256'),'hex');
  return v_footer||jsonb_build_object(
    'evidence_sha256',v_hash,
    'footer_markdown',format(E'---\n### PentaRelease Economic + CIE Evidence\n- PentaCosts: %s accounted internal units; provider actual **$%s USD** (estimated $%s).\n- PentaPay: %s obligation(s); gross **$%s USD**; settled **$%s USD**.\n- USD release exposure: **$%s USD** (provider actual + gross PentaPay obligations).\n- CIE: **%s**%s.\n- Evidence: `%s`\n> Internal Penta execution units are not currency and are never relabeled as USD.',
      v_accounted_units,
      to_char(round(v_provider_actual_minor::numeric/100,2),'FM999999999999990.00'),
      to_char(round(v_provider_estimated_minor::numeric/100,2),'FM999999999999990.00'),
      coalesce((v_econ#>>'{pay_obligations,count}')::bigint,0),
      to_char(round(v_pay_gross_minor::numeric/100,2),'FM999999999999990.00'),
      to_char(round(v_pay_settled_minor::numeric/100,2),'FM999999999999990.00'),
      to_char(round((v_provider_actual_minor+v_pay_gross_minor)::numeric/100,2),'FM999999999999990.00'),
      coalesce(v_cie.status,'HOLD_INSUFFICIENT_EVIDENCE'),
      case when v_cie.score is null then '' else format(' — score %s/100',v_cie.score) end,
      v_hash)
  );
end
$function$;

update penta_os20.release_projection_targets
set provider_ref='crownthrive1/CrownThrive-OS:README.md,ABOUT_ME.md,LICENSE,CODE_OF_CONDUCT.md,PARTNERS.md,FAQ.md,CHANGELOG.md',
    updated_at=now()
where target_key='github_visible_tabs';

update penta_os20.release_projection_targets
set provider_ref='16C3Y96Qv37oG0cnU9C-92CZ6jRadTyaL7tjbih-eyG0',
    updated_at=now()
where target_key='google_drive_release_mirror';

update penta_os20.release_projection_targets
set provider_ref='crown-thrive:pentarelease/latest,pentarelease/faq,pentarelease/changelog,pentarelease/costs,pentarelease/cie,pentarelease/data,pentarelease/evidence',
    updated_at=now()
where target_key='pentadocs_release_surface';

comment on function penta_os20.resolve_release_evidence_bundle_v1(text,bigint,jsonb) is
  'Canonical PentaRelease economics/CIE resolver; deduplicates semantic evidence ignoring per-execution chain_event_hash and prevents incomplete HOLD payloads from downgrading an existing governed PASS.';

comment on function public.penta_release_footer_v1(text) is
  'Canonical PentaRelease economics/CIE footer with stable semantic CIE selection across reconciliation executions.';
