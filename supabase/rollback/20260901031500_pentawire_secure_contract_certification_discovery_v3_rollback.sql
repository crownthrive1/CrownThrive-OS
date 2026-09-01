-- Rollback for PentaWire secure-read exact-contract certification discovery v3.
-- Restores the historical four-service v2 certification implementation and removes v3.

create or replace function integration_control.penta_wire_certify_exact_contracts_v2()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public','chlom_runtime','extensions'
as $function$
declare
  a integration_control.penta_wire_read_adapters_v1%rowtype;
  v_required integer;
  v_pass integer;
  v_latest timestamptz;
  v_ops jsonb;
  v_evidence jsonb;
  v_sha text;
  v_decision text;
  v_expires timestamptz;
  v_results jsonb:='[]'::jsonb;
  v_system_key text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  for a in
    select * from integration_control.penta_wire_read_adapters_v1
    where service_id in ('cpanel_crownthrive_io','cpanel_whm','ct.service.commerce.go-flipbooks','mailgun_account')
      and adapter_kind='SECURE_HTTP' and state='active'
    order by service_id
  loop
    with required as (
      select jsonb_array_elements_text(a.allowed_operations) required_operation_key
    ), latest as (
      select r.required_operation_key,
             q.state,q.observed_at,q.receipt_id,q.downstream_http_status,
             q.credential_exposed,q.provider_write,q.evidence_sha256
      from required r
      left join lateral (
        select x.* from integration_control.penta_wire_secure_read_receipts_v1 x
        where x.service_id=a.service_id and x.operation_key=r.required_operation_key
        order by x.observed_at desc limit 1
      ) q on true
    )
    select count(*),count(*) filter(where state='pass' and downstream_http_status between 200 and 299
      and not credential_exposed and not provider_write and observed_at>=a.updated_at
      and observed_at>clock_timestamp()-interval '72 hours'),max(observed_at),
      coalesce(jsonb_agg(jsonb_build_object('operation_key',required_operation_key,'state',coalesce(state,'missing'),
        'receipt_id',receipt_id,'observed_at',observed_at,'http_status',downstream_http_status,
        'evidence_sha256',evidence_sha256) order by required_operation_key),'[]'::jsonb)
    into v_required,v_pass,v_latest,v_ops
    from latest;

    v_decision:=case when v_required>0 and v_required=v_pass then 'pass' else 'hold' end;
    v_expires:=coalesce(v_latest,clock_timestamp())+interval '72 hours';
    v_evidence:=jsonb_build_object('service_id',a.service_id,'exact_contract',a.exact_contract,
      'adapter_updated_at',a.updated_at,'required_operations',a.allowed_operations,
      'pass_operations',v_pass,'required_operation_count',v_required,'operations',v_ops,
      'last_provider_evidence_at',v_latest,'evidence_ttl_hours',72,'decision',v_decision,
      'credential_exposed',false,'provider_write',false,'authority_effect','none');
    v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

    insert into integration_control.penta_wire_exact_contract_certifications_v2(
      service_id,exact_contract,adapter_updated_at,required_operations,pass_operations,
      required_operation_count,decision,evidence_sha256,evidence,last_provider_evidence_at,
      expires_at,certified_by,certified_at,updated_at
    ) values(a.service_id,a.exact_contract,a.updated_at,a.allowed_operations,v_pass,v_required,
      v_decision,v_sha,v_evidence,coalesce(v_latest,clock_timestamp()),v_expires,'penta.certify',clock_timestamp(),clock_timestamp())
    on conflict(service_id) do update set exact_contract=excluded.exact_contract,
      adapter_updated_at=excluded.adapter_updated_at,required_operations=excluded.required_operations,
      pass_operations=excluded.pass_operations,required_operation_count=excluded.required_operation_count,
      decision=excluded.decision,evidence_sha256=excluded.evidence_sha256,evidence=excluded.evidence,
      last_provider_evidence_at=excluded.last_provider_evidence_at,expires_at=excluded.expires_at,
      certified_by='penta.certify',certified_at=clock_timestamp(),updated_at=clock_timestamp();

    v_system_key:=case a.service_id
      when 'cpanel_crownthrive_io' then 'ct.system.cpanel-crownthrive-io'
      when 'cpanel_whm' then 'ct.system.cpanel-whm'
      when 'ct.service.commerce.go-flipbooks' then 'ct.system.go-flipbooks'
      when 'mailgun_account' then 'ct.system.mailgun-account' end;

    perform integration_control.penta_census_record_provider_observation_v1(
      a.service_id,'exact_provider_contract',a.exact_contract,v_system_key,
      'penta-wire-secure-read-receipts',v_decision,
      jsonb_build_object('evidence_sha256',v_sha,'pass_operations',v_pass,
        'required_operations',v_required,'last_provider_evidence_at',v_latest,
        'expires_at',v_expires,'authority_created',false)
    );

    insert into chlom_runtime.oracle_observations(
      oracle_id,observation_type,subject_id,value,confidence,observed_at,expires_at,
      source_digest_sha256,observation_state,metadata
    )
    select o,'provider_contract_certification',a.service_id,
      jsonb_build_object('decision',v_decision,'exact_contract',a.exact_contract,
        'evidence_sha256',v_sha,'pass_operations',v_pass,'required_operations',v_required),
      case o when 'ct.oracle.penta-certify' then 0.99 when 'ct.oracle.penta-census' then 0.98 else 0.95 end,
      clock_timestamp(),v_expires,v_sha,'accepted',jsonb_build_object('authority_created',false)
    from unnest(array['ct.oracle.penta-certify','ct.oracle.penta-census','ct.oracle.penta-discovery','ct.oracle.penta-wire']) o;

    perform public.penta_cookie_observe_v1(v_system_key,
      jsonb_build_object('provider_contract',jsonb_build_object('service_id',a.service_id,
        'exact_contract',a.exact_contract,'decision',v_decision,'evidence_sha256',v_sha,
        'last_provider_evidence_at',v_latest,'expires_at',v_expires),
        'last_verified_at',clock_timestamp()),'penta.census',jsonb_build_array(v_sha));

    v_results:=v_results||jsonb_build_array(jsonb_build_object('service_id',a.service_id,
      'decision',v_decision,'pass_operations',v_pass,'required_operations',v_required,
      'evidence_sha256',v_sha,'last_provider_evidence_at',v_latest,'expires_at',v_expires));
  end loop;
  return jsonb_build_object('ok',not exists(select 1 from integration_control.penta_wire_exact_contract_certifications_v2
      where service_id in ('cpanel_crownthrive_io','cpanel_whm','ct.service.commerce.go-flipbooks','mailgun_account')
        and decision<>'pass'),
    'results',v_results,'observed_at',clock_timestamp());
end
$function$;

revoke all on function integration_control.penta_wire_certify_exact_contracts_v2() from public,anon,authenticated;
grant execute on function integration_control.penta_wire_certify_exact_contracts_v2() to service_role;

drop function if exists integration_control.penta_wire_certify_exact_contracts_v3();
