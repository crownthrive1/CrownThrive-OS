-- CHLOM C0: deterministic proprietary-protocol registration guard + CAS receipts.
-- Work package: CHLOM-C0-0002
-- Authority: D2 implementation only. This migration does not activate protocols,
-- expand D3 authority, expose proprietary bodies, or self-certify release.

create table if not exists chlom_runtime.protocol_registration_receipts_v1 (
  receipt_id uuid primary key default extensions.gen_random_uuid(),
  protocol_id text not null,
  semantic_version text not null,
  asset_id text not null,
  outcome text not null check (outcome in (
    'registered_hold',
    'already_registered',
    'cas_mismatch',
    'cas_target_missing',
    'digest_conflict',
    'vault_alias_collision'
  )),
  proposed_digest text not null check (proposed_digest ~ '^[0-9a-f]{64}$'),
  existing_digest text null check (existing_digest is null or existing_digest ~ '^[0-9a-f]{64}$'),
  expected_existing_digest text null check (expected_existing_digest is null or expected_existing_digest ~ '^[0-9a-f]{64}$'),
  owner_agent_id text not null,
  verifier_agent_id text not null,
  source_ref text null,
  correlation_id text not null,
  dail_event_id text null,
  body_exposed boolean not null default false check (body_exposed = false),
  activation_allowed boolean not null default false check (activation_allowed = false),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

create index if not exists protocol_registration_receipts_v1_asset_created_idx
  on chlom_runtime.protocol_registration_receipts_v1(asset_id, created_at desc);
create index if not exists protocol_registration_receipts_v1_correlation_idx
  on chlom_runtime.protocol_registration_receipts_v1(correlation_id);

alter table chlom_runtime.protocol_registration_receipts_v1 enable row level security;
revoke all on table chlom_runtime.protocol_registration_receipts_v1 from public, anon, authenticated;
grant select on table chlom_runtime.protocol_registration_receipts_v1 to service_role;

create or replace function chlom_runtime.register_proprietary_protocol_v2(
  p_protocol_id text,
  p_canonical_name text,
  p_semantic_version text,
  p_protocol_body jsonb,
  p_owner_agent_id text,
  p_verifier_agent_id text,
  p_source_ref text,
  p_commercial_candidate boolean default true,
  p_expected_existing_digest text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, chlom_runtime, chlom_secrets, vault, extensions
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_asset_id text;
  v_secret_name text;
  v_secret_id uuid;
  v_digest text;
  v_existing_digest text;
  v_intake_id uuid;
  v_event jsonb;
  v_correlation_id text;
  v_receipt_id uuid;
  v_result jsonb;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_protocol_id is null or p_protocol_id !~ '^ct[.]protocol[.][a-z0-9._-]+$' then
    raise exception 'invalid_protocol_id';
  end if;
  if p_canonical_name is null or length(trim(p_canonical_name)) < 8 then
    raise exception 'invalid_protocol_name';
  end if;
  if p_semantic_version is null or p_semantic_version !~ '^[0-9]+[.][0-9]+[.][0-9]+$' then
    raise exception 'invalid_semantic_version';
  end if;
  if p_protocol_body is null or jsonb_typeof(p_protocol_body) <> 'object' then
    raise exception 'invalid_protocol_body';
  end if;
  if p_expected_existing_digest is not null and p_expected_existing_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid_expected_existing_digest';
  end if;
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id=p_owner_agent_id) then
    raise exception 'unknown_owner_agent';
  end if;
  if not exists(select 1 from chlom_runtime.agent_templates where agent_id=p_verifier_agent_id) then
    raise exception 'unknown_verifier_agent';
  end if;
  if p_owner_agent_id=p_verifier_agent_id then
    raise exception 'owner_verifier_separation_required';
  end if;

  v_digest := encode(extensions.digest(p_protocol_body::text,'sha256'),'hex');
  v_asset_id := p_protocol_id || '.v' || replace(p_semantic_version,'.','_');
  v_secret_name := 'chlom_protocol_' || substr(encode(extensions.digest(v_asset_id,'sha256'),'hex'),1,32);
  v_correlation_id := 'ctcorr:chlom-c0:' || encode(
    extensions.digest(
      concat_ws('|', p_protocol_id, p_semantic_version, v_digest, coalesce(p_expected_existing_digest,''), coalesce(p_source_ref,'')),
      'sha256'
    ),
    'hex'
  );

  -- One writer per protocol/version. This makes the registration decision a
  -- deterministic compare-and-set operation instead of a check-then-write race.
  perform pg_advisory_xact_lock(hashtextextended('chlom.protocol.registration|' || v_asset_id, 0));

  select public_reference_digest
    into v_existing_digest
    from chlom_secrets.trade_secret_assets
   where asset_id=v_asset_id
   for update;

  if v_existing_digest is not null then
    if p_expected_existing_digest is not null and v_existing_digest <> p_expected_existing_digest then
      insert into chlom_runtime.protocol_registration_receipts_v1(
        protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
        expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
        metadata
      ) values (
        p_protocol_id,p_semantic_version,v_asset_id,'cas_mismatch',v_digest,v_existing_digest,
        p_expected_existing_digest,p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
        jsonb_build_object('authority_created',false,'mutation_applied',false,'reason_code','EXPECTED_DIGEST_MISMATCH')
      ) returning receipt_id into v_receipt_id;

      return jsonb_build_object(
        'state','cas_mismatch','protocol_id',p_protocol_id,'version',p_semantic_version,
        'asset_id',v_asset_id,'receipt_id',v_receipt_id,'public_contract_digest',v_digest,
        'existing_public_contract_digest',v_existing_digest,'expected_existing_digest',p_expected_existing_digest,
        'secret_returned',false,'body_exposed',false,'activation_allowed',false,'mutation_applied',false
      );
    end if;

    if v_existing_digest=v_digest then
      insert into chlom_runtime.protocol_registration_receipts_v1(
        protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
        expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
        metadata
      ) values (
        p_protocol_id,p_semantic_version,v_asset_id,'already_registered',v_digest,v_existing_digest,
        p_expected_existing_digest,p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
        jsonb_build_object('authority_created',false,'mutation_applied',false,'reason_code','IDEMPOTENT_EXISTING_REGISTRATION')
      ) returning receipt_id into v_receipt_id;

      return jsonb_build_object(
        'state','already_registered','protocol_id',p_protocol_id,'version',p_semantic_version,
        'asset_id',v_asset_id,'receipt_id',v_receipt_id,'public_contract_digest',v_digest,
        'secret_returned',false,'body_exposed',false,'activation_allowed',false,'mutation_applied',false
      );
    end if;

    insert into chlom_runtime.protocol_registration_receipts_v1(
      protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
      expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
      metadata
    ) values (
      p_protocol_id,p_semantic_version,v_asset_id,'digest_conflict',v_digest,v_existing_digest,
      p_expected_existing_digest,p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
      jsonb_build_object('authority_created',false,'mutation_applied',false,'reason_code','PROTOCOL_VERSION_DIGEST_CONFLICT')
    ) returning receipt_id into v_receipt_id;

    return jsonb_build_object(
      'state','digest_conflict','protocol_id',p_protocol_id,'version',p_semantic_version,
      'asset_id',v_asset_id,'receipt_id',v_receipt_id,'public_contract_digest',v_digest,
      'existing_public_contract_digest',v_existing_digest,
      'secret_returned',false,'body_exposed',false,'activation_allowed',false,'mutation_applied',false
    );
  end if;

  if p_expected_existing_digest is not null then
    insert into chlom_runtime.protocol_registration_receipts_v1(
      protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
      expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
      metadata
    ) values (
      p_protocol_id,p_semantic_version,v_asset_id,'cas_target_missing',v_digest,null,
      p_expected_existing_digest,p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
      jsonb_build_object('authority_created',false,'mutation_applied',false,'reason_code','EXPECTED_EXISTING_REGISTRATION_MISSING')
    ) returning receipt_id into v_receipt_id;

    return jsonb_build_object(
      'state','cas_target_missing','protocol_id',p_protocol_id,'version',p_semantic_version,
      'asset_id',v_asset_id,'receipt_id',v_receipt_id,'public_contract_digest',v_digest,
      'expected_existing_digest',p_expected_existing_digest,
      'secret_returned',false,'body_exposed',false,'activation_allowed',false,'mutation_applied',false
    );
  end if;

  if exists(select 1 from vault.secrets where name=v_secret_name) then
    insert into chlom_runtime.protocol_registration_receipts_v1(
      protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
      expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
      metadata
    ) values (
      p_protocol_id,p_semantic_version,v_asset_id,'vault_alias_collision',v_digest,null,null,
      p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
      jsonb_build_object('authority_created',false,'mutation_applied',false,'reason_code','PROTOCOL_VAULT_ALIAS_COLLISION')
    ) returning receipt_id into v_receipt_id;

    return jsonb_build_object(
      'state','vault_alias_collision','protocol_id',p_protocol_id,'version',p_semantic_version,
      'asset_id',v_asset_id,'receipt_id',v_receipt_id,'public_contract_digest',v_digest,
      'secret_returned',false,'body_exposed',false,'activation_allowed',false,'mutation_applied',false
    );
  end if;

  select vault.create_secret(
    p_protocol_body::text,
    v_secret_name,
    'CHLOM proprietary protocol body; Vault-only; public projection limited to contract digest'
  ) into v_secret_id;

  insert into chlom_secrets.trade_secret_assets(
    asset_id,asset_kind,classification,canonical_name,version,
    vault_secret_id,vault_secret_name,public_reference_digest,public_body_allowed,
    drive_archive_required,lifecycle_state,source_ref,metadata
  ) values (
    v_asset_id,'proprietary_protocol','TRADE_SECRET',p_canonical_name,p_semantic_version,
    v_secret_id,v_secret_name,v_digest,false,true,'controlled_test',p_source_ref,
    jsonb_build_object(
      'protocol_id',p_protocol_id,
      'owner_agent_id',p_owner_agent_id,
      'verifier_agent_id',p_verifier_agent_id,
      'metaprotocol_support',true,
      'activation_allowed',false,
      'public_projection','contract_digest_only',
      'commercial_candidate',p_commercial_candidate,
      'history_policy','append_or_supersede_never_silent_delete',
      'raw_body_return_allowed',false,
      'd3_human_reserved',true,
      'registration_contract','chlom_runtime.register_proprietary_protocol_v2'
    )
  );

  insert into chlom_secrets.novel_asset_intake(
    candidate_key,canonical_name,asset_kind,source_system,source_ref,
    proposed_classification,novelty_basis,body_ingestion_state,vault_asset_id,
    public_projection_state,monetization_state,owner_agent_id,verifier_agent_id,
    reason_codes,metadata
  ) values (
    'protocol:'||p_protocol_id||':'||p_semantic_version,
    p_canonical_name,'proprietary_protocol','chlom_protocol_foundry',p_source_ref,
    'TRADE_SECRET','Supports the CrownThrive CHLOM metaprotocol with a reusable governed protocol body.',
    'vaulted',v_asset_id,'contract_only',
    case when p_commercial_candidate then 'candidate_hold' else 'not_applicable' end,
    p_owner_agent_id,p_verifier_agent_id,
    array['VAULT_FIRST','PUBLIC_DIGEST_ONLY','NO_SELF_APPROVAL','D3_HUMAN_RESERVED','CAS_GUARDED'],
    jsonb_build_object(
      'protocol_id',p_protocol_id,
      'semantic_version',p_semantic_version,
      'public_contract_digest',v_digest,
      'activation_allowed',false,
      'checkout_enabled',false,
      'entitlement_active',false,
      'registration_correlation_id',v_correlation_id
    )
  ) returning intake_id into v_intake_id;

  select chlom_runtime.append_dail_event(
    'protocol.vaulted_candidate_registered',
    'proprietary_protocol',
    p_protocol_id,
    jsonb_build_object(
      'version',p_semantic_version,
      'public_contract_digest',v_digest,
      'asset_id',v_asset_id,
      'owner_agent_id',p_owner_agent_id,
      'verifier_agent_id',p_verifier_agent_id,
      'commercial_candidate',p_commercial_candidate,
      'body_exposed',false,
      'activation_allowed',false,
      'cas_guarded',true,
      'registration_correlation_id',v_correlation_id
    ),
    p_owner_agent_id,null,p_owner_agent_id,p_semantic_version,
    v_digest,null,'founder:Kavonte_Jones_Sr:2026-08-22:protocol_foundry_authorization',
    null,'restricted'
  ) into v_event;

  insert into chlom_runtime.protocol_registration_receipts_v1(
    protocol_id,semantic_version,asset_id,outcome,proposed_digest,existing_digest,
    expected_existing_digest,owner_agent_id,verifier_agent_id,source_ref,correlation_id,
    dail_event_id,metadata
  ) values (
    p_protocol_id,p_semantic_version,v_asset_id,'registered_hold',v_digest,null,null,
    p_owner_agent_id,p_verifier_agent_id,p_source_ref,v_correlation_id,
    v_event->>'event_id',
    jsonb_build_object('authority_created',false,'mutation_applied',true,'reason_code','REGISTERED_HOLD','intake_id',v_intake_id)
  ) returning receipt_id into v_receipt_id;

  v_result := jsonb_build_object(
    'state','registered_hold',
    'protocol_id',p_protocol_id,
    'version',p_semantic_version,
    'asset_id',v_asset_id,
    'intake_id',v_intake_id,
    'dail_event_id',v_event->>'event_id',
    'receipt_id',v_receipt_id,
    'correlation_id',v_correlation_id,
    'public_contract_digest',v_digest,
    'secret_returned',false,
    'body_exposed',false,
    'activation_allowed',false,
    'mutation_applied',true,
    'commercial_candidate',p_commercial_candidate
  );
  return v_result;
end
$function$;

revoke all on function chlom_runtime.register_proprietary_protocol_v2(text,text,text,jsonb,text,text,text,boolean,text) from public, anon, authenticated;
grant execute on function chlom_runtime.register_proprietary_protocol_v2(text,text,text,jsonb,text,text,text,boolean,text) to postgres, service_role;

comment on table chlom_runtime.protocol_registration_receipts_v1 is
  'CHLOM C0 append-only public-digest registration outcomes. No proprietary protocol body may be stored here.';
comment on function chlom_runtime.register_proprietary_protocol_v2(text,text,text,jsonb,text,text,text,boolean,text) is
  'CHLOM C0 compare-and-set protocol registration. Serializes by protocol/version, emits non-secret durable conflict/idempotency receipts, and never activates the protocol.';
