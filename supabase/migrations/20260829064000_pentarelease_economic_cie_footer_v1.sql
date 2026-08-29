-- PentaRelease governed economic + CIE footer.
-- Production migration was applied to ThriveBase before this source projection.
-- Internal Penta units are not currency. USD values derive only from certified
-- provider-cost minor units and explicit PentaPay USD obligations.

create or replace function public.penta_release_footer_v1(p_release_version text)
returns jsonb
language plpgsql
stable security definer
set search_path='pg_catalog','public','penta_runtime','penta_os20','extensions'
as $$
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
  if coalesce(trim(p_release_version),'')='' then raise exception 'release_version_required'; end if;
  v_econ:=public.penta_release_economic_envelope_v2(p_release_version);
  select * into v_cie from penta_os20.cie_evidence where release_version=p_release_version order by created_at desc limit 1;
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
        'status','HOLD_INSUFFICIENT_EVIDENCE','score',null,'source',null,'evidence_hash',null,
        'reason','no release-specific governed CIE evidence has been recorded'
      ) else jsonb_build_object(
        'status',v_cie.status,'score',v_cie.score,'source',v_cie.source,'evidence_hash',v_cie.evidence_hash,'evidence',v_cie.evidence
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
end $$;

create or replace function penta_os20.resolve_release_evidence_bundle_v1(
  p_release_version text,
  p_payload_bytes bigint default 0,
  p_cie_subject jsonb default null
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_os20','public','extensions'
as $$
declare
  v_eval jsonb;
  v_cie jsonb;
  v_subject jsonb;
  v_hash text;
  v_status text;
  v_score numeric;
  v_footer jsonb;
begin
  if coalesce(trim(p_release_version),'')='' then raise exception 'release_version_required'; end if;
  v_eval:=penta_os20.evaluate_release(p_release_version,greatest(coalesce(p_payload_bytes,0),0));
  if p_cie_subject is not null then
    v_subject:=p_cie_subject||jsonb_build_object('subject_id',coalesce(p_cie_subject->>'subject_id',p_release_version),'subject_type',coalesce(p_cie_subject->>'subject_type','release'));
    v_cie:=public.ct_cie_score('crownthrive1/CrownThrive-CIE',1341314455,'ct.framework-agent.cie',v_subject);
    v_status:=coalesce(v_cie->>'verdict','HOLD_INSUFFICIENT_EVIDENCE');
    begin v_score:=nullif(v_cie->>'score','')::numeric; exception when others then v_score:=null; end;
    v_hash:=encode(extensions.digest(convert_to(v_cie::text,'UTF8'),'sha256'),'hex');
    insert into penta_os20.cie_evidence(release_version,score,status,source,evidence,evidence_hash)
    values(p_release_version,v_score,v_status,'public.ct_cie_score / ct.framework-package.cie',v_cie,v_hash);
  end if;
  v_footer:=public.penta_release_footer_v1(p_release_version);
  return jsonb_build_object('release_version',p_release_version,'evaluation',v_eval,'footer',v_footer,'resolved_at',now());
end $$;

create or replace function penta_os20.dispatch_release_footer_to_github_v1(
  p_release_version text,
  p_release_tag text default null,
  p_pr_number integer default null
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','penta_os20','public','vault','net'
as $$
declare
  v_token text;
  v_footer jsonb;
  v_request_id bigint;
  v_payload jsonb;
begin
  if coalesce(trim(p_release_version),'')='' then raise exception 'release_version_required'; end if;
  if p_pr_number is null and coalesce(trim(p_release_tag),'')='' then raise exception 'release_tag_or_pr_number_required'; end if;
  select decrypted_secret into v_token from vault.decrypted_secrets where name='PENTA_PM_GITHUB_TOKEN' limit 1;
  if coalesce(v_token,'')='' then raise exception 'PENTA_PM_GITHUB_TOKEN unavailable: fail closed'; end if;
  v_footer:=public.penta_release_footer_v1(p_release_version);
  v_payload:=jsonb_build_object(
    'schema','ct.pentarelease.github-footer-dispatch.v1',
    'release_version',p_release_version,
    'release_tag',p_release_tag,
    'pr_number',p_pr_number,
    'footer_markdown',v_footer->>'footer_markdown',
    'footer',v_footer,
    'evidence_sha256',v_footer->>'evidence_sha256'
  );
  select net.http_post(
    url:='https://api.github.com/repos/crownthrive1/CrownThrive-OS/dispatches',
    body:=jsonb_build_object('event_type','penta-release-evidence-footer','client_payload',v_payload),
    headers:=jsonb_build_object(
      'Authorization','Bearer '||v_token,
      'Accept','application/vnd.github+json',
      'X-GitHub-Api-Version','2022-11-28',
      'Content-Type','application/json',
      'User-Agent','CrownThrive-PentaRelease/3'
    ),
    timeout_milliseconds:=15000
  ) into v_request_id;
  perform penta_os20.record_receipt('release_footer_github_dispatch','PentaRelease','release_projection',null,
    jsonb_build_object('release_version',p_release_version,'release_tag',p_release_tag,'pr_number',p_pr_number,'request_id',v_request_id,'evidence_sha256',v_footer->>'evidence_sha256'));
  return jsonb_build_object('state','DISPATCHING','request_id',v_request_id,'release_version',p_release_version,'release_tag',p_release_tag,'pr_number',p_pr_number,'evidence_sha256',v_footer->>'evidence_sha256');
end $$;

create or replace function penta_os20.enqueue_release_projection(p_release_version text,p_external_release_tag text,p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
set search_path='penta_os20','public','extensions','pg_temp'
as $$
declare
  v_target penta_os20.release_projection_targets%rowtype;
  v_hash text;
  v_count integer:=0;
  v_footer jsonb;
  v_payload jsonb;
  v_dispatch jsonb;
begin
  if coalesce(trim(p_release_version),'')='' then raise exception 'release_version_required'; end if;
  v_footer:=public.penta_release_footer_v1(p_release_version);
  v_payload:=coalesce(p_payload,'{}'::jsonb)||jsonb_build_object('penta_release_footer',v_footer,'footer_markdown',v_footer->>'footer_markdown');
  v_hash:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
  for v_target in select * from penta_os20.release_projection_targets where status='active' loop
    insert into penta_os20.release_projection_queue(release_version,external_release_tag,target_id,payload,payload_hash,status)
    values(p_release_version,p_external_release_tag,v_target.id,v_payload,v_hash,'queued')
    on conflict (release_version,target_id,payload_hash) do update set external_release_tag=excluded.external_release_tag,updated_at=now();
    v_count:=v_count+1;
  end loop;
  if coalesce(trim(p_external_release_tag),'')<>'' then
    v_dispatch:=penta_os20.dispatch_release_footer_to_github_v1(p_release_version,p_external_release_tag,null);
  else
    v_dispatch:=jsonb_build_object('state','SKIPPED_NO_RELEASE_TAG');
  end if;
  perform penta_os20.record_receipt('release_projection_enqueued','PentaRelease','release_projection',null,
    jsonb_build_object('release_version',p_release_version,'external_release_tag',p_external_release_tag,'target_count',v_count,'payload_hash',v_hash,'footer_evidence_sha256',v_footer->>'evidence_sha256','github_footer_dispatch',v_dispatch));
  return jsonb_build_object('release_version',p_release_version,'external_release_tag',p_external_release_tag,'target_count',v_count,'payload_hash',v_hash,'footer',v_footer,'github_footer_dispatch',v_dispatch);
end $$;

create or replace function public.penta_pr_status_v1()
returns jsonb
language sql stable security definer
set search_path='pg_catalog','penta_pr'
as $$
select jsonb_build_object(
 'service','ct.penta.pr-lifecycle.v1',
 'phase',3,
 'hard_deadline_hours',12,
 'systems',(select jsonb_agg(to_jsonb(s) order by execution_order) from penta_pr.systems s),
 'open_tracked',(select count(*) from penta_pr.lifecycle where terminal_state is null),
 'overdue',(select count(*) from penta_pr.lifecycle where terminal_state is null and deadline_at <= now()),
 'terminal',(select count(*) from penta_pr.lifecycle where terminal_state is not null),
 'release_footer_contract',jsonb_build_object(
   'schema','ct.pentarelease.evidence-footer.v1',
   'resolver','public.penta_release_footer_v1(text)',
   'required_on_pr_merge_and_release',true,
   'fields',jsonb_build_array('PentaCosts','PentaPay','USD summary','CIE score/verdict','evidence SHA256'),
   'internal_units_are_not_currency',true
 )
);
$$;

grant execute on function public.penta_release_footer_v1(text) to authenticated,service_role;
grant execute on function penta_os20.resolve_release_evidence_bundle_v1(text,bigint,jsonb) to service_role;
grant execute on function penta_os20.dispatch_release_footer_to_github_v1(text,text,integer) to service_role;
grant execute on function penta_os20.enqueue_release_projection(text,text,jsonb) to service_role;
