-- PentaWire Unsplash secure-read adapter v1
-- Reuses the existing `unsplash-image-control` provider broker rather than creating a second
-- Unsplash integration. This migration adds only a read-only PentaWire adapter and a bounded
-- server-side canary/read helper. Request-budget policy remains authoritative and fail-closed.
-- No provider write, credential export, money movement, rights grant, vote/quorum, or D3 effect.

insert into integration_control.penta_wire_read_adapters_v1(
  service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,
  public_projection,provider_write,credential_forwarding,authority_effect,state,evidence
)
select
  'unsplash_crownthrive_studios',
  'SECURE_HTTP',
  'ct.penta.wire.secure.unsplash-crownthrive-studios.v1',
  'edge:unsplash-image-control',
  '["search.read"]'::jsonb,
  false,false,false,'none','active',
  jsonb_build_object(
    'contract','ct.penta.wire.secure.unsplash-crownthrive-studios.v1',
    'provider_broker','unsplash-image-control',
    'provider_broker_reused',true,
    'provider_write',false,
    'credential_forwarding',false,
    'public_projection',false,
    'budget_guard','integration_control.consume_request_budget_v4',
    'raw_response_stored',false,
    'authority_effect','none',
    'source_semantics_authority','integration_control.services.current_runtime',
    'installed_at',clock_timestamp()
  )
where exists (
  select 1
  from integration_control.services s
  where s.service_id='unsplash_crownthrive_studios'
    and s.base_url='https://api.unsplash.com'
    and s.write_gate is false
    and s.credential_state='configured'
)
on conflict(service_id) do update
set adapter_kind=excluded.adapter_kind,
    exact_contract=excluded.exact_contract,
    transport_ref=excluded.transport_ref,
    allowed_operations=excluded.allowed_operations,
    public_projection=false,
    provider_write=false,
    credential_forwarding=false,
    authority_effect='none',
    state='active',
    evidence=integration_control.penta_wire_read_adapters_v1.evidence || excluded.evidence,
    updated_at=clock_timestamp();

create or replace function integration_control.penta_wire_unsplash_secure_read_v1(
  p_operation_key text default 'search.read',
  p_params jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public','vault','extensions','chlom_runtime'
as $function$
declare
  a integration_control.penta_wire_read_adapters_v1%rowtype;
  s integration_control.services%rowtype;
  v_token text;
  v_budget jsonb;
  v_query text;
  v_per_page integer;
  v_request jsonb;
  v_response extensions.http_response;
  v_body jsonb;
  v_body_text text;
  v_response_sha text;
  v_receipt_id uuid;
  v_evidence jsonb;
  v_evidence_sha text;
  v_item_count integer:=0;
  v_ok boolean:=false;
  v_state text:='hold';
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into a
  from integration_control.penta_wire_read_adapters_v1
  where service_id='unsplash_crownthrive_studios'
    and adapter_kind='SECURE_HTTP'
    and state='active';
  if not found then
    return jsonb_build_object('ok',false,'state','hold','reason','unsplash_secure_adapter_not_active');
  end if;
  if not (a.allowed_operations ? p_operation_key) then
    return jsonb_build_object('ok',false,'state','hold','reason','operation_not_allowed','operation',p_operation_key);
  end if;
  if p_operation_key <> 'search.read' then
    return jsonb_build_object('ok',false,'state','hold','reason','unsupported_operation','operation',p_operation_key);
  end if;

  select * into s from integration_control.services where service_id=a.service_id;
  if not found
     or s.base_url <> 'https://api.unsplash.com'
     or s.write_gate is not false
     or s.credential_state <> 'configured' then
    return jsonb_build_object('ok',false,'state','hold','reason','authoritative_service_semantics_not_ready');
  end if;

  -- Consume the canonical CrownThrive-local request budget BEFORE any provider request.
  -- Null/zero/exhausted budgets fail closed inside consume_request_budget_v4.
  begin
    v_budget:=integration_control.consume_request_budget_v4(a.service_id,p_operation_key);
  exception when others then
    return jsonb_build_object(
      'ok',false,'state','hold','reason','request_budget_denied',
      'error_class',sqlstate,
      'provider_called',false,
      'provider_write',false,
      'credential_exposed',false,
      'authority_effect','none'
    );
  end;

  -- Resolve the existing Supabase service-role JWT only inside the database boundary.
  -- The token is used solely to authenticate to the already-deployed internal broker and is
  -- never returned, persisted in receipts, or forwarded to the external provider.
  select ds.decrypted_secret into v_token
  from vault.decrypted_secrets ds
  where ds.decrypted_secret is not null
    and (
      lower(ds.name) in ('supabase_service_role_key','service_role_key','thrivebase_service_role_key','thivebase_service_role_key','supabase-service-role-key')
      or lower(ds.name) like '%service%role%'
    )
    and ds.decrypted_secret like 'eyJ%'
  order by case when lower(ds.name)='supabase_service_role_key' then 0
                when lower(ds.name) like '%thrivebase%service%role%' then 1 else 2 end,
           ds.created_at desc
  limit 1;
  if coalesce(v_token,'')='' then
    return jsonb_build_object(
      'ok',false,'state','hold','reason','internal_service_auth_unavailable',
      'provider_called',false,'provider_write',false,'credential_exposed',false,'authority_effect','none'
    );
  end if;

  v_query:=left(coalesce(nullif(btrim(p_params->>'query'),''),'architecture'),120);
  if length(v_query)<2 then v_query:='architecture'; end if;
  v_per_page:=least(2,greatest(1,coalesce((p_params->>'per_page')::integer,1)));
  v_request:=jsonb_build_object('action','search','query',v_query,'page',1,'per_page',v_per_page);

  v_response:=chlom_runtime.dail_http_v1((row(
    'POST',
    'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/unsplash-image-control',
    array[
      extensions.http_header('authorization','Bearer '||v_token),
      extensions.http_header('apikey',v_token),
      extensions.http_header('content-type','application/json'),
      extensions.http_header('x-crownthrive-source','PentaWire secure-read adapter v1')
    ],
    'application/json',
    v_request::text
  ))::extensions.http_request);

  v_body_text:=coalesce(v_response.content,'');
  v_response_sha:=encode(extensions.digest(convert_to(v_body_text,'UTF8'),'sha256'),'hex');
  begin
    v_body:=case when v_body_text='' then '{}'::jsonb else v_body_text::jsonb end;
  exception when others then
    v_body:='{}'::jsonb;
  end;

  if jsonb_typeof(v_body->'items')='array' then
    v_item_count:=jsonb_array_length(v_body->'items');
  end if;
  v_ok:=v_response.status between 200 and 299
        and coalesce((v_body->>'ok')::boolean,false)
        and coalesce(v_body#>>'{usage_contract,hotlink}','false')='true'
        and coalesce(v_body#>>'{usage_contract,attribution}','false')='true'
        and coalesce(v_body#>>'{usage_contract,no_ai_training}','false')='true';
  v_state:=case when v_ok then 'pass' else 'fail' end;

  v_evidence:=jsonb_build_object(
    'contract',a.exact_contract,
    'provider','Unsplash',
    'provider_broker','unsplash-image-control',
    'provider_broker_reused',true,
    'operation',p_operation_key,
    'query_sha256',encode(extensions.digest(convert_to(v_query,'UTF8'),'sha256'),'hex'),
    'item_count',v_item_count,
    'downstream_http_status',v_response.status,
    'budget_decision',v_budget->>'decision',
    'budget_count_after',v_budget->'month_request_count',
    'provider_rate_limit_remaining',v_body#>'{rate_limit,remaining}',
    'hotlink_required',coalesce(v_body#>>'{usage_contract,hotlink}','false')='true',
    'attribution_required',coalesce(v_body#>>'{usage_contract,attribution}','false')='true',
    'ai_training_allowed',false,
    'raw_response_stored',false,
    'credential_exposed',false,
    'credential_forwarded_to_caller',false,
    'provider_write',false,
    'authority_effect','none',
    'observed_at',clock_timestamp()
  );
  v_evidence_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.penta_wire_secure_read_receipts_v1(
    service_id,operation_key,state,downstream_service,downstream_http_status,
    response_sha256,raw_response_stored,credential_exposed,credential_forwarded_to_caller,
    provider_write,authority_effect,evidence,evidence_sha256,observed_at
  ) values (
    a.service_id,p_operation_key,v_state,'unsplash-image-control',v_response.status,
    v_response_sha,false,false,false,false,'none',v_evidence,v_evidence_sha,clock_timestamp()
  ) returning receipt_id into v_receipt_id;

  perform chlom_runtime.append_dail_event(
    'penta.wire.secure_read.observed',
    'provider_read_evidence',
    v_receipt_id::text,
    jsonb_build_object(
      'service_id',a.service_id,
      'operation',p_operation_key,
      'state',v_state,
      'contract',a.exact_contract,
      'downstream_http_status',v_response.status,
      'response_sha256',v_response_sha,
      'evidence_sha256',v_evidence_sha,
      'item_count',v_item_count,
      'raw_response_stored',false,
      'credential_exposed',false,
      'credential_forwarded_to_caller',false,
      'provider_write',false,
      'authority_effect','none'
    ),
    'PentaWire/PentaSecurity',null,'PentaWire','1.0.0',
    'ctcorr:penta-wire-unsplash-secure-read-v1:'||v_receipt_id::text,
    null,'D1_AUTONOMOUS',null,'internal'
  );

  return jsonb_build_object(
    'ok',v_ok,
    'state',v_state,
    'service_id',a.service_id,
    'contract',a.exact_contract,
    'operation',p_operation_key,
    'receipt_id',v_receipt_id,
    'downstream_http_status',v_response.status,
    'response_sha256',v_response_sha,
    'evidence_sha256',v_evidence_sha,
    'item_count',v_item_count,
    'raw_response_stored',false,
    'credential_exposed',false,
    'credential_forwarded_to_caller',false,
    'provider_write',false,
    'authority_effect','none'
  );
end
$function$;

revoke all on function integration_control.penta_wire_unsplash_secure_read_v1(text,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_unsplash_secure_read_v1(text,jsonb) to service_role;

-- Deterministic install-time assertions. These perform no provider request.
do $assertions$
declare a integration_control.penta_wire_read_adapters_v1%rowtype;
begin
  select * into a from integration_control.penta_wire_read_adapters_v1 where service_id='unsplash_crownthrive_studios';
  if not found then raise exception 'unsplash_pentawire_adapter_missing'; end if;
  if a.adapter_kind<>'SECURE_HTTP' then raise exception 'unsplash_adapter_kind_invalid'; end if;
  if a.allowed_operations<>'["search.read"]'::jsonb then raise exception 'unsplash_allowed_operations_invalid'; end if;
  if a.provider_write or a.credential_forwarding or a.public_projection or a.authority_effect<>'none' then
    raise exception 'unsplash_adapter_authority_boundary_invalid';
  end if;
end
$assertions$;

comment on function integration_control.penta_wire_unsplash_secure_read_v1(text,jsonb) is
'Read-only PentaWire adapter that reuses the existing unsplash-image-control broker. Canonical request-budget semantics are consumed before any provider read; null/zero/exhausted budgets fail closed. Raw provider responses and credentials are never returned or persisted.';
