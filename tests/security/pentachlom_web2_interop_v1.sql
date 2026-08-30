-- Transactional acceptance / negative tests for PentaCHLOM Web2 interoperability v1.
-- The transaction is rolled back so no test bindings, projections or DAIL events persist.

begin;

set local client_min_messages = warning;

-- Contract objects must exist and no raw Web2 subject field may be introduced.
do $$
begin
  if to_regclass('penta_runtime.pentachlom_identity_bindings_v1') is null
     or to_regclass('penta_runtime.pentachlom_projection_requests_v1') is null
     or to_regclass('penta_runtime.pentachlom_projection_events_v1') is null then
    raise exception 'PentaCHLOM runtime tables missing';
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema='penta_runtime'
      and table_name='pentachlom_identity_bindings_v1'
      and column_name in ('provider_subject','raw_subject','subject_value','credential','secret','token')
  ) then
    raise exception 'PentaCHLOM identity binding stores prohibited raw subject/secret material';
  end if;
end
$$;

-- Metadata with credential-like keys must fail closed.
do $$
begin
  begin
    perform penta_runtime.pentachlom_bind_identity_v1(
      'test-web2-provider',
      repeat('a',64),
      'tenant:test',
      'test-purpose',
      'ct.identity.test.subject',
      'evidence:test-secret-negative',
      'ct.test.originator',
      'subject',
      null,
      repeat('b',64),
      null,
      null,
      '{"api_key":"must-not-be-stored"}'::jsonb
    );
    raise exception 'secret-like metadata was accepted';
  exception
    when others then
      if sqlerrm='secret-like metadata was accepted' then raise; end if;
  end;
end
$$;

-- Identity binding must store only a digest, must DAIL-bind, and must be immutable.
do $$
declare
  v jsonb;
  v_binding uuid;
  v_dail uuid;
begin
  v := penta_runtime.pentachlom_bind_identity_v1(
    'test-web2-provider',
    repeat('1',64),
    'tenant:test',
    'identity-resolution',
    'ct.identity.test.subject',
    'evidence:test-identity-binding',
    'ct.test.originator',
    'subject',
    null,
    repeat('2',64),
    null,
    null,
    '{"test":true}'::jsonb
  );

  v_binding := (v->>'binding_id')::uuid;
  v_dail := (v->>'canonical_dail_event_id')::uuid;

  if coalesce((v->>'authority_inherited')::boolean,true)
     or coalesce((v->>'rights_granted')::boolean,true)
     or coalesce((v->>'provider_write_performed')::boolean,true) then
    raise exception 'identity binding manufactured authority/rights/provider write';
  end if;

  if not exists (
    select 1 from penta_runtime.pentachlom_identity_bindings_v1
    where binding_id=v_binding and provider_subject_digest=repeat('1',64)
  ) then
    raise exception 'identity binding not persisted in transaction';
  end if;

  if not exists (
    select 1 from chlom_runtime.dail_events
    where event_id=v_dail and event_hash=v->>'canonical_dail_event_hash'
  ) then
    raise exception 'identity binding canonical DAIL readback failed';
  end if;

  begin
    update penta_runtime.pentachlom_identity_bindings_v1
    set purpose='tamper'
    where binding_id=v_binding;
    raise exception 'identity binding direct mutation was accepted';
  exception
    when others then
      if sqlerrm='identity binding direct mutation was accepted' then raise; end if;
  end;
end
$$;

-- Projection originator cannot self-validate. A separate validator can validate.
do $$
declare
  v jsonb;
  v_request uuid;
  v_render jsonb;
begin
  v := penta_runtime.pentachlom_open_projection_v1(
    'web2_to_chlom',
    'evidence',
    'tenant:test',
    'test-web2-provider',
    'object:test:1',
    repeat('3',64),
    'ct.chlom.protocol.v1',
    'ct.test.originator',
    'evidence:test-projection-open',
    null,
    'ct.chlom.evidence.test',
    null,
    null,
    null,
    '{"test":true}'::jsonb
  );
  v_request := (v->>'request_id')::uuid;

  begin
    perform penta_runtime.pentachlom_record_projection_event_v1(
      v_request,'validated','ct.test.originator','evidence:self-validation','decision'
    );
    raise exception 'originator self-validation was accepted';
  exception
    when others then
      if sqlerrm='originator self-validation was accepted' then raise; end if;
  end;

  perform penta_runtime.pentachlom_record_projection_event_v1(
    v_request,'validated','ct.test.independent-validator','evidence:independent-validation','decision'
  );

  v_render := penta_runtime.pentachlom_render_projection_v1(v_request);
  if (v_render->>'current_state') <> 'validated'
     or coalesce((v_render->>'authority_inherited')::boolean,true)
     or coalesce((v_render->>'rights_granted')::boolean,true)
     or coalesce((v_render->>'provider_write_performed')::boolean,true)
     or coalesce((v_render->>'derived_view')::boolean,false) <> true
     or (v_render->>'canonical_authority') <> 'CHLOM' then
    raise exception 'derived projection envelope violated PentaCHLOM authority boundary';
  end if;

  perform penta_runtime.pentachlom_record_projection_event_v1(
    v_request,'projected','ct.test.projection-executor','evidence:projection-materialized','execution'
  );

  begin
    update penta_runtime.pentachlom_projection_requests_v1
    set target_system='tamper'
    where request_id=v_request;
    raise exception 'projection request direct mutation was accepted';
  exception
    when others then
      if sqlerrm='projection request direct mutation was accepted' then raise; end if;
  end;
end
$$;

-- Governance-bearing projections cannot reach projected state without exact CHLOM authority evidence.
do $$
declare
  v jsonb;
  v_request uuid;
begin
  v := penta_runtime.pentachlom_open_projection_v1(
    'chlom_to_web2',
    'license',
    'tenant:test',
    'ct.chlom.protocol.v1',
    'license:test:1',
    repeat('4',64),
    'test-web2-provider',
    'ct.test.originator.license',
    'evidence:test-license-open',
    null,
    'ct.chlom.license.test',
    null,
    null,
    null,
    '{}'::jsonb
  );
  v_request := (v->>'request_id')::uuid;

  perform penta_runtime.pentachlom_record_projection_event_v1(
    v_request,'validated','ct.test.independent-validator.license','evidence:test-license-validated','decision'
  );

  begin
    perform penta_runtime.pentachlom_record_projection_event_v1(
      v_request,'projected','ct.test.projection-executor','evidence:test-license-projected','execution'
    );
    raise exception 'license projection without CHLOM authority evidence was accepted';
  exception
    when others then
      if sqlerrm='license projection without CHLOM authority evidence was accepted' then raise; end if;
  end;
end
$$;

-- RLS/revokes and registration must preserve service-only/candidate semantics.
do $$
declare
  v_status jsonb;
begin
  if has_table_privilege('anon','penta_runtime.pentachlom_projection_requests_v1','select')
     or has_table_privilege('authenticated','penta_runtime.pentachlom_projection_requests_v1','select') then
    raise exception 'PentaCHLOM internal projection table exposed to anon/authenticated';
  end if;

  if has_function_privilege('anon','penta_runtime.pentachlom_status_v1()','execute')
     or has_function_privilege('authenticated','penta_runtime.pentachlom_status_v1()','execute') then
    raise exception 'PentaCHLOM internal runtime function exposed to anon/authenticated';
  end if;

  if not exists (
    select 1 from public.penta_system_registry
    where system_key='penta.chlom.web2-interop'
      and canonical_name='PentaCHLOM'
      and maturity='implemented'
      and public_exposure=false
      and risk_ceiling='D2'
      and coalesce((metadata->>'production_certified')::boolean,false)=false
  ) then
    raise exception 'PentaCHLOM registry candidate missing or overclaims production';
  end if;

  v_status := penta_runtime.pentachlom_status_v1();
  if coalesce((v_status->>'authority_created')::boolean,true)
     or coalesce((v_status->>'authority_inherited')::boolean,true)
     or coalesce((v_status->>'rights_grant_capability')::boolean,true)
     or coalesce((v_status->>'credential_capability')::boolean,true)
     or coalesce((v_status->>'provider_write_capability')::boolean,true)
     or coalesce((v_status->>'money_movement_capability')::boolean,true)
     or coalesce((v_status->>'token_class_authority')::boolean,true)
     or coalesce((v_status->>'d3_capability')::boolean,true)
     or coalesce((v_status->>'production_certified')::boolean,true) then
    raise exception 'PentaCHLOM runtime status overclaims authority/certification';
  end if;

  if v_status->'canonical_dail_topology' <> '["HUMAN","HYBRID","MACHINE"]'::jsonb
     or v_status->'semantic_stages' <> '["evidence","decision","execution"]'::jsonb then
    raise exception 'PentaCHLOM conflated canonical DAIL systems with semantic stages';
  end if;
end
$$;

rollback;
