-- PentaWire surface-contract classification v1.
-- Distinguishes intentionally zero-tool provider surfaces from genuine secure-read adapters.
-- Candidate classifications do not self-certify. PentaCertify must independently certify the
-- exact current service-semantics digest before an intentional zero-tool surface can resolve COMPLETE.
-- No provider write, credential value, money movement, rights grant, vote/quorum, or D3 authority.

create table if not exists integration_control.penta_wire_surface_contract_modes_v1 (
  service_id text primary key references integration_control.services(service_id) on delete cascade,
  contract_mode text not null check (contract_mode in (
    'CLIENT_TELEMETRY','CLIENT_SDK','AUTH_FLOW','SERVER_EXECUTION_GATED','SECURE_READ'
  )),
  expected_tool_policy text not null check (expected_tool_policy in ('ZERO_TOOL','SECURE_READ_REQUIRED')),
  source_semantics_sha256 text not null check (source_semantics_sha256 ~ '^[0-9a-f]{64}$'),
  external_evidence_refs jsonb not null default '[]'::jsonb check (jsonb_typeof(external_evidence_refs)='array'),
  required_checks jsonb not null default '[]'::jsonb check (jsonb_typeof(required_checks)='array'),
  classification_state text not null default 'candidate' check (classification_state in ('candidate','active','hold','superseded')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_wire_surface_mode_certifications_v1 (
  certification_id uuid primary key default gen_random_uuid(),
  service_id text not null references integration_control.services(service_id) on delete cascade,
  contract_mode text not null check (contract_mode in (
    'CLIENT_TELEMETRY','CLIENT_SDK','AUTH_FLOW','SERVER_EXECUTION_GATED','SECURE_READ'
  )),
  expected_tool_policy text not null check (expected_tool_policy in ('ZERO_TOOL','SECURE_READ_REQUIRED')),
  source_semantics_sha256 text not null check (source_semantics_sha256 ~ '^[0-9a-f]{64}$'),
  decision text not null check (decision in ('pass','hold')),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_refs jsonb not null check (jsonb_typeof(evidence_refs)='array'),
  checks jsonb not null check (jsonb_typeof(checks)='array'),
  originator_agent_id text not null,
  certified_by text not null check (certified_by='penta.certify'),
  certified_at timestamptz not null default now(),
  expires_at timestamptz not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists penta_wire_surface_mode_certifications_v1_lookup_idx
  on integration_control.penta_wire_surface_mode_certifications_v1(service_id,certified_at desc);

alter table integration_control.penta_wire_surface_contract_modes_v1 enable row level security;
alter table integration_control.penta_wire_surface_contract_modes_v1 force row level security;
alter table integration_control.penta_wire_surface_mode_certifications_v1 enable row level security;
alter table integration_control.penta_wire_surface_mode_certifications_v1 force row level security;

revoke all on integration_control.penta_wire_surface_contract_modes_v1 from public,anon,authenticated;
revoke all on integration_control.penta_wire_surface_mode_certifications_v1 from public,anon,authenticated;
grant select,insert,update on integration_control.penta_wire_surface_contract_modes_v1 to service_role;
grant select,insert on integration_control.penta_wire_surface_mode_certifications_v1 to service_role;

create or replace function integration_control.penta_wire_surface_mode_certification_immutable_v1()
returns trigger
language plpgsql
set search_path='pg_catalog'
as $function$
begin
  raise exception 'penta_wire_surface_mode_certification_is_append_only' using errcode='55000';
end
$function$;

drop trigger if exists penta_wire_surface_mode_certification_immutable_v1
  on integration_control.penta_wire_surface_mode_certifications_v1;
create trigger penta_wire_surface_mode_certification_immutable_v1
before update or delete on integration_control.penta_wire_surface_mode_certifications_v1
for each row execute function integration_control.penta_wire_surface_mode_certification_immutable_v1();

-- Seed classifications as CANDIDATES only. These rows describe intended PentaWire exposure,
-- not provider capability or independent certification.
with candidate(service_id,contract_mode,tool_policy,checks,evidence) as (
  values
  ('google_analytics_ga4','CLIENT_TELEMETRY','ZERO_TOOL',
    jsonb_build_array(
      'current service identity is the GA4 measurement/client telemetry surface',
      'client projection is explicitly allowed by current service metadata',
      'no Data API/OAuth read authority is inferred from a Measurement ID',
      'provider write remains false'
    ),
    jsonb_build_object('separate_read_service_required',true,'data_api_authority_inferred',false)),
  ('google_maps_javascript','CLIENT_SDK','ZERO_TOOL',
    jsonb_build_array(
      'current service identity is the browser Maps JavaScript client surface',
      'browser-key projection is explicitly allowed only under provider restrictions',
      'server web-service read authority is not inferred from the browser key',
      'provider write remains false'
    ),
    jsonb_build_object('server_read_authority_inferred',false,'provider_restrictions_required',true)),
  ('meta_facebook_login','AUTH_FLOW','ZERO_TOOL',
    jsonb_build_array(
      'current service identity is Facebook Login/OAuth flow',
      'App ID and server-only App Secret boundaries remain distinct',
      'generic Graph API read/write scope is not inferred from login configuration',
      'provider write remains false in PentaWire'
    ),
    jsonb_build_object('generic_graph_authority_inferred',false,'auth_flow_only',true)),
  ('openai_crownthrive_api','SERVER_EXECUTION_GATED','ZERO_TOOL',
    jsonb_build_array(
      'current service identity is server-only shared API execution',
      'secret remains server/Vault bounded',
      'no model inference or cost-bearing operation is exposed merely to close PentaWire topology',
      'future read or execution tools require a separate exact operation contract and budget gate'
    ),
    jsonb_build_object('model_execution_authority_inferred',false,'cost_bearing_execution_inferred',false)),
  ('unsplash_crownthrive_studios','SECURE_READ','SECURE_READ_REQUIRED',
    jsonb_build_array(
      'server-brokered Access Key remains secret-safe',
      'exact read operations must be enumerated before activation',
      'provider attribution/hotlink/download-tracking obligations remain enforced',
      'fresh provider read canary and independent exact-contract certification are required'
    ),
    jsonb_build_object('secure_read_adapter_required',true,'provider_read_canary_required',true))
)
insert into integration_control.penta_wire_surface_contract_modes_v1(
  service_id,contract_mode,expected_tool_policy,source_semantics_sha256,
  external_evidence_refs,required_checks,classification_state,evidence
)
select c.service_id,c.contract_mode,c.tool_policy,
       integration_control.penta_wire_safe_service_contract_v1(c.service_id)->>'contract_sha256',
       jsonb_build_array(s.docs_url),c.checks,'candidate',
       c.evidence||jsonb_build_object(
         'contract','ct.penta.wire.surface-contract-mode.v1',
         'classification_is_not_certification',true,
         'provider_write',false,'credential_operation',false,'authority_effect','none',
         'source_semantics_authority','integration_control.services.current_runtime',
         'docs_reference_only_not_provider_readback',true
       )
from candidate c
join integration_control.services s using(service_id)
on conflict(service_id) do update set
  contract_mode=excluded.contract_mode,
  expected_tool_policy=excluded.expected_tool_policy,
  source_semantics_sha256=excluded.source_semantics_sha256,
  external_evidence_refs=excluded.external_evidence_refs,
  required_checks=excluded.required_checks,
  classification_state=case
    when integration_control.penta_wire_surface_contract_modes_v1.classification_state='superseded'
      then 'superseded'
    else 'candidate' end,
  evidence=integration_control.penta_wire_surface_contract_modes_v1.evidence||excluded.evidence,
  updated_at=now();

create or replace function integration_control.penta_wire_surface_mode_status_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','integration_control'
as $function$
declare
  v_rows jsonb;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'service_id',m.service_id,
    'contract_mode',m.contract_mode,
    'expected_tool_policy',m.expected_tool_policy,
    'classification_state',m.classification_state,
    'classification_source_sha256',m.source_semantics_sha256,
    'current_source_sha256',cur.contract_sha256,
    'source_current',m.source_semantics_sha256=cur.contract_sha256,
    'latest_certification_id',cert.certification_id,
    'latest_certification_decision',cert.decision,
    'latest_certification_expires_at',cert.expires_at,
    'latest_certification_current',coalesce(cert.decision='pass' and cert.expires_at>clock_timestamp()
      and cert.source_semantics_sha256=cur.contract_sha256,false),
    'external_evidence_refs',m.external_evidence_refs,
    'provider_write',false,'authority_effect','none'
  ) order by m.service_id),'[]'::jsonb)
  into v_rows
  from integration_control.penta_wire_surface_contract_modes_v1 m
  cross join lateral (
    select integration_control.penta_wire_safe_service_contract_v1(m.service_id)->>'contract_sha256' contract_sha256
  ) cur
  left join lateral (
    select c.* from integration_control.penta_wire_surface_mode_certifications_v1 c
    where c.service_id=m.service_id and c.contract_mode=m.contract_mode
    order by c.certified_at desc limit 1
  ) cert on true
  where m.classification_state<>'superseded';

  return jsonb_build_object(
    'contract','ct.penta.wire.surface-contract-mode-status.v1',
    'surfaces',v_rows,
    'classification_is_not_certification',true,
    'provider_write',false,'authority_effect','none','observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_wire_surface_mode_status_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_wire_surface_mode_status_v1() to service_role;

create or replace function integration_control.penta_wire_record_surface_mode_certification_v1(
  p_service_id text,
  p_contract_mode text,
  p_source_semantics_sha256 text,
  p_decision text,
  p_evidence_sha256 text,
  p_evidence_refs jsonb,
  p_checks jsonb,
  p_originator_agent_id text,
  p_certified_by text default 'penta.certify',
  p_expires_at timestamptz default null
)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','chlom_runtime'
as $function$
declare
  m integration_control.penta_wire_surface_contract_modes_v1%rowtype;
  v_current_sha text;
  v_id uuid;
  v_all_pass boolean:=false;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_certified_by<>'penta.certify' then raise exception 'independent_pentacertify_required'; end if;
  if coalesce(p_originator_agent_id,'')='' or p_originator_agent_id=p_certified_by then
    raise exception 'originator_certifier_separation_required';
  end if;
  if p_decision not in ('pass','hold') then raise exception 'invalid_certification_decision'; end if;
  if coalesce(p_evidence_sha256,'') !~ '^[0-9a-f]{64}$' then raise exception 'valid_evidence_sha256_required'; end if;
  if jsonb_typeof(coalesce(p_evidence_refs,'[]'::jsonb))<>'array'
     or jsonb_array_length(coalesce(p_evidence_refs,'[]'::jsonb))=0 then
    raise exception 'nonempty_evidence_refs_required';
  end if;
  if jsonb_typeof(coalesce(p_checks,'[]'::jsonb))<>'array'
     or jsonb_array_length(coalesce(p_checks,'[]'::jsonb))=0 then
    raise exception 'nonempty_checks_required';
  end if;

  select * into m from integration_control.penta_wire_surface_contract_modes_v1
  where service_id=p_service_id and classification_state<>'superseded';
  if not found then raise exception 'surface_contract_mode_not_registered'; end if;
  if m.contract_mode<>p_contract_mode then raise exception 'surface_contract_mode_mismatch'; end if;

  v_current_sha:=integration_control.penta_wire_safe_service_contract_v1(p_service_id)->>'contract_sha256';
  if p_source_semantics_sha256<>v_current_sha or m.source_semantics_sha256<>v_current_sha then
    raise exception 'stale_service_semantics_digest';
  end if;

  v_all_pass:=not exists(
    select 1 from jsonb_array_elements(p_checks) c
    where coalesce((c->>'passed')::boolean,false) is not true
  );
  if p_decision='pass' and not v_all_pass then raise exception 'pass_requires_all_checks'; end if;

  insert into integration_control.penta_wire_surface_mode_certifications_v1(
    service_id,contract_mode,expected_tool_policy,source_semantics_sha256,decision,
    evidence_sha256,evidence_refs,checks,originator_agent_id,certified_by,expires_at,evidence
  ) values(
    p_service_id,p_contract_mode,m.expected_tool_policy,p_source_semantics_sha256,p_decision,
    p_evidence_sha256,p_evidence_refs,p_checks,p_originator_agent_id,p_certified_by,
    coalesce(p_expires_at,clock_timestamp()+interval '72 hours'),
    jsonb_build_object(
      'contract','ct.penta.wire.surface-mode-certification.v1',
      'classification_is_not_provider_capability',true,
      'provider_write',false,'money_movement',false,'credential_operation',false,
      'd3_human_reserved',true,'authority_effect','none'
    )
  ) returning certification_id into v_id;

  perform chlom_runtime.append_dail_event(
    'penta.wire.surface_mode.certified','surface_contract_certification',
    'ct.penta.wire.surface-mode-certification.v1',
    jsonb_build_object(
      'certification_id',v_id,'service_id',p_service_id,'contract_mode',p_contract_mode,
      'source_semantics_sha256',p_source_semantics_sha256,'decision',p_decision,
      'evidence_sha256',p_evidence_sha256,'originator_agent_id',p_originator_agent_id,
      'certified_by',p_certified_by,'provider_write',false,'authority_effect','none',
      'observed_at',clock_timestamp()
    ),
    'PentaCertify/PentaWire',null,'PentaCertify','2.0.0',
    'ctcorr:penta-wire-surface-mode:'||p_service_id,null,'D2',null,'internal'
  );

  return jsonb_build_object(
    'ok',true,'certification_id',v_id,'service_id',p_service_id,
    'decision',p_decision,'source_semantics_sha256',p_source_semantics_sha256,
    'certified_by',p_certified_by,'originator_separated',true,
    'provider_write',false,'authority_effect','none'
  );
end
$function$;

revoke all on function integration_control.penta_wire_record_surface_mode_certification_v1(
  text,text,text,text,text,jsonb,jsonb,text,text,timestamptz
) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_record_surface_mode_certification_v1(
  text,text,text,text,text,jsonb,jsonb,text,text,timestamptz
) to service_role;

create or replace function integration_control.penta_wire_reconcile_surface_modes_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control'
as $function$
declare
  m record;
  v_current_sha text;
  v_mode_cert record;
  v_exact_cert record;
  v_secure jsonb;
  v_resolved integer:=0;
  v_hold integer:=0;
  v_results jsonb:='[]'::jsonb;
  v_reason text;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  for m in
    select * from integration_control.penta_wire_surface_contract_modes_v1
    where classification_state<>'superseded'
    order by service_id
  loop
    v_current_sha:=integration_control.penta_wire_safe_service_contract_v1(m.service_id)->>'contract_sha256';
    select c.* into v_mode_cert
    from integration_control.penta_wire_surface_mode_certifications_v1 c
    where c.service_id=m.service_id
      and c.contract_mode=m.contract_mode
      and c.decision='pass'
      and c.certified_by='penta.certify'
      and c.source_semantics_sha256=v_current_sha
      and c.expires_at>clock_timestamp()
    order by c.certified_at desc limit 1;

    if m.expected_tool_policy='ZERO_TOOL' then
      if m.source_semantics_sha256=v_current_sha and found then
        update integration_control.penta_wire_service_bindings_v1
        set binding_state='registry_bound',gap_state='complete',probe_method='REGISTRY',probe_url=null,
            last_probe_state='not_applicable_zero_tool_contract',
            evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
              'surface_contract_mode',m.contract_mode,
              'expected_tool_policy',m.expected_tool_policy,
              'surface_mode_certification_id',v_mode_cert.certification_id,
              'surface_mode_certification_expires_at',v_mode_cert.expires_at,
              'source_semantics_sha256',v_current_sha,
              'zero_tool_intentional',true,
              'provider_capability_not_inferred',true,
              'provider_write',false,'authority_effect','none'
            ),updated_at=now()
        where service_id=m.service_id;
        update integration_control.services
        set metadata=metadata||jsonb_build_object(
          'penta_wire_surface_contract_mode',m.contract_mode,
          'penta_wire_expected_tool_policy',m.expected_tool_policy,
          'penta_wire_zero_tool_intentional',true,
          'penta_wire_surface_mode_certification_id',v_mode_cert.certification_id,
          'penta_wire_surface_mode_source_sha256',v_current_sha,
          'penta_wire_provider_write',false,'penta_wire_authority_effect','none'
        ),updated_at=now()
        where service_id=m.service_id;
        v_resolved:=v_resolved+1;
        v_reason:='certified_zero_tool_contract';
      else
        update integration_control.penta_wire_service_bindings_v1
        set binding_state='hold_exact_contract',gap_state='exact_provider_contract_required',
            evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
              'surface_contract_mode',m.contract_mode,'expected_tool_policy',m.expected_tool_policy,
              'surface_mode_hold','independent_surface_mode_certification_required',
              'source_semantics_current',m.source_semantics_sha256=v_current_sha,
              'provider_write',false,'authority_effect','none'
            ),updated_at=now()
        where service_id=m.service_id;
        v_hold:=v_hold+1;
        v_reason:='independent_surface_mode_certification_required';
      end if;
    else
      v_secure:=integration_control.penta_wire_secure_adapter_status_v1(m.service_id);
      select c.* into v_exact_cert
      from integration_control.penta_wire_exact_contract_certifications_v2 c
      where c.service_id=m.service_id and c.decision='pass'
        and c.certified_by='penta.certify' and c.expires_at>clock_timestamp()
      order by c.certified_at desc limit 1;

      if m.source_semantics_sha256=v_current_sha
         and v_mode_cert.certification_id is not null
         and coalesce((v_secure->>'ready')::boolean,false)
         and v_exact_cert.service_id is not null then
        update integration_control.penta_wire_service_bindings_v1
        set binding_state='registry_bound',gap_state='complete',probe_method='REGISTRY',probe_url=null,
            evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
              'surface_contract_mode',m.contract_mode,'expected_tool_policy',m.expected_tool_policy,
              'surface_mode_certification_id',v_mode_cert.certification_id,
              'exact_provider_contract',v_exact_cert.exact_contract,
              'exact_provider_evidence_sha256',v_exact_cert.evidence_sha256,
              'secure_adapter_ready',true,'provider_write',false,'authority_effect','none'
            ),updated_at=now()
        where service_id=m.service_id;
        v_resolved:=v_resolved+1;
        v_reason:='certified_secure_read_contract';
      else
        update integration_control.penta_wire_service_bindings_v1
        set binding_state='hold_exact_contract',gap_state='exact_provider_contract_required',
            evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
              'surface_contract_mode',m.contract_mode,'expected_tool_policy',m.expected_tool_policy,
              'surface_mode_hold','secure_read_adapter_and_certification_required',
              'source_semantics_current',m.source_semantics_sha256=v_current_sha,
              'surface_mode_certified',v_mode_cert.certification_id is not null,
              'secure_adapter_ready',coalesce((v_secure->>'ready')::boolean,false),
              'exact_provider_contract_certified',v_exact_cert.service_id is not null,
              'provider_write',false,'authority_effect','none'
            ),updated_at=now()
        where service_id=m.service_id;
        v_hold:=v_hold+1;
        v_reason:='secure_read_adapter_and_certification_required';
      end if;
    end if;

    v_results:=v_results||jsonb_build_array(jsonb_build_object(
      'service_id',m.service_id,'contract_mode',m.contract_mode,
      'expected_tool_policy',m.expected_tool_policy,'result',v_reason,
      'provider_write',false,'authority_effect','none'
    ));
  end loop;

  return jsonb_build_object(
    'contract','ct.penta.wire.surface-mode-reconciliation.v1',
    'resolved',v_resolved,'hold',v_hold,'results',v_results,
    'classification_is_not_certification',true,'provider_write',false,
    'money_movement',false,'checkout_activation',false,'d3_human_reserved',true,
    'authority_effect','none','observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_wire_reconcile_surface_modes_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_wire_reconcile_surface_modes_v1() to service_role;

create or replace function integration_control.penta_wire_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  v_scan jsonb;
  v_modes jsonb;
  v_probe jsonb;
  v_close jsonb;
  v_work jsonb;
begin
  v_scan:=integration_control.penta_wire_scan_v1();
  v_modes:=integration_control.penta_wire_reconcile_surface_modes_v1();
  v_probe:=integration_control.penta_wire_probe_public_v1();
  v_close:=integration_control.penta_wire_close_resolved_gap_work_v1();
  v_work:=integration_control.penta_wire_generate_gap_work_v1(100);
  return jsonb_build_object(
    'state',case
      when coalesce((v_probe->>'fail')::int,0)>0 then 'hold'
      when coalesce((v_modes->>'hold')::int,0)>0 then 'hold'
      else 'pass' end,
    'scan',v_scan,
    'surface_contract_modes',v_modes,
    'public_probe',v_probe,
    'resolved_work_closeout',v_close,
    'gap_work',v_work,
    'agent_id','ct.agent.penta-wire',
    'fabrics',jsonb_build_array('PentaMesh','PentaFabric','PentaFactory','PentaCertify','PentaStatus','PentaPolice'),
    'external_scheduler_slot_delta',0,
    'provider_write',false,'money_movement',false,'checkout_activation',false,
    'd3_human_reserved',true,'at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_wire_tick_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_wire_tick_v1() to service_role;

comment on table integration_control.penta_wire_surface_contract_modes_v1 is
'PentaWire contract-mode registry. Separates intentional zero-tool client/auth/execution surfaces from secure-read adapters; registry classification is not certification.';
comment on table integration_control.penta_wire_surface_mode_certifications_v1 is
'Append-only independent PentaCertify exact-source certifications for PentaWire surface contract modes.';
comment on function integration_control.penta_wire_reconcile_surface_modes_v1() is
'Reconciles PentaWire surface modes after base scan. Intentional zero-tool surfaces close only with current independent PentaCertify certification; secure-read surfaces additionally require adapter and provider-read certification.';
