-- CHLOM C2: deterministic exact-lease revocation with non-secret receipts.
-- Work package: CHLOM-C2-0001
-- Authority: implementation only. This migration creates no lease, revokes no
-- production lease, grants no D3 authority, and does not self-certify release.

create table if not exists chlom_runtime.authority_lease_revocation_receipts_v1 (
  receipt_id uuid primary key default extensions.gen_random_uuid(),
  lease_id uuid not null,
  outcome text not null check (outcome in (
    'revoked',
    'already_terminal',
    'expired_before_revoke',
    'lease_not_found'
  )),
  expected_state text not null default 'active' check (expected_state = 'active'),
  observed_state text null check (
    observed_state is null or observed_state in ('active','revoked','expired','killed','superseded')
  ),
  principal_kind text null,
  principal_id text null,
  capability text null,
  resource_type text null,
  resource_id text null,
  revoker_kind text not null check (revoker_kind = 'founder'),
  revoker_id text not null,
  authority_ref uuid not null,
  reason_code text not null,
  mutation_applied boolean not null default false,
  authority_created boolean not null default false check (authority_created = false),
  dail_event_id text null,
  correlation_id text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

create index if not exists authority_lease_revocation_receipts_v1_lease_created_idx
  on chlom_runtime.authority_lease_revocation_receipts_v1(lease_id, created_at desc);
create index if not exists authority_lease_revocation_receipts_v1_correlation_idx
  on chlom_runtime.authority_lease_revocation_receipts_v1(correlation_id);

alter table chlom_runtime.authority_lease_revocation_receipts_v1 enable row level security;
revoke all on table chlom_runtime.authority_lease_revocation_receipts_v1 from public, anon, authenticated;
grant select on table chlom_runtime.authority_lease_revocation_receipts_v1 to service_role;

create or replace function chlom_runtime.revoke_agent_authority_lease_v1(
  p_lease_id uuid,
  p_revoker_kind text,
  p_revoker_id text,
  p_authorization_id uuid,
  p_reason_code text,
  p_expected_state text default 'active'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, chlom_runtime, extensions
as $function$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_founder_ok boolean := false;
  v_state text;
  v_principal_kind text;
  v_principal_id text;
  v_capability text;
  v_resource_type text;
  v_resource_id text;
  v_expires_at timestamptz;
  v_receipt_id uuid;
  v_event jsonb;
  v_correlation_id text;
  v_outcome text;
  v_mutation boolean := false;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_lease_id is null then
    raise exception 'lease_id_required';
  end if;
  if p_revoker_kind <> 'founder' then
    raise exception 'founder_revoker_required';
  end if;
  if p_revoker_id is null or length(trim(p_revoker_id)) < 2 then
    raise exception 'revoker_id_required';
  end if;
  if p_authorization_id is null then
    raise exception 'authorization_id_required';
  end if;
  if p_reason_code is null or p_reason_code !~ '^[A-Z0-9_:-]{4,96}$' then
    raise exception 'invalid_reason_code';
  end if;
  if p_expected_state <> 'active' then
    raise exception 'expected_state_must_be_active';
  end if;

  select exists(
    select 1
      from chlom_runtime.archive_reverse_authorizations
     where authorization_id=p_authorization_id
       and principal_kind='founder'
       and principal_id=p_revoker_id
       and founder_granted=true
       and state='active'
       and (expires_at is null or expires_at>clock_timestamp())
  ) into v_founder_ok;
  if not v_founder_ok then
    raise exception 'exact_active_founder_authority_required';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('chlom.authority.lease|' || p_lease_id::text, 0));

  select state, principal_kind, principal_id, capability, resource_type, resource_id, expires_at
    into v_state, v_principal_kind, v_principal_id, v_capability, v_resource_type, v_resource_id, v_expires_at
    from chlom_runtime.agent_authority_leases_v1
   where lease_id=p_lease_id
   for update;

  v_correlation_id := 'ctcorr:chlom-c2:lease-revoke:' || encode(
    extensions.digest(
      concat_ws('|', p_lease_id::text, p_revoker_id, p_authorization_id::text, p_reason_code, coalesce(v_state,'missing')),
      'sha256'
    ),
    'hex'
  );

  if not found then
    v_outcome := 'lease_not_found';
  elsif v_state <> 'active' then
    v_outcome := 'already_terminal';
  elsif v_expires_at <= clock_timestamp() then
    update chlom_runtime.agent_authority_leases_v1
       set state='expired', updated_at=clock_timestamp()
     where lease_id=p_lease_id and state='active';
    v_state := 'expired';
    v_outcome := 'expired_before_revoke';
    v_mutation := true;
  else
    update chlom_runtime.agent_authority_leases_v1
       set state='revoked',
           revoked_at=clock_timestamp(),
           revoked_by=p_revoker_id,
           updated_at=clock_timestamp()
     where lease_id=p_lease_id and state='active';
    v_state := 'revoked';
    v_outcome := 'revoked';
    v_mutation := true;

    select chlom_runtime.append_dail_event(
      'authority.lease.revoked',
      'agent_authority_lease',
      p_lease_id::text,
      jsonb_build_object(
        'lease_id',p_lease_id,
        'principal_kind',v_principal_kind,
        'principal_id',v_principal_id,
        'capability',v_capability,
        'resource_type',v_resource_type,
        'resource_id',v_resource_id,
        'reason_code',p_reason_code,
        'authority_ref',p_authorization_id,
        'authority_created',false
      ),
      p_revoker_id,
      null,
      case when v_principal_kind='agent' then v_principal_id else null end,
      '1.0.0',
      v_correlation_id,
      null,
      'archive_reverse_authorizations:' || p_authorization_id::text,
      null,
      'restricted'
    ) into v_event;
  end if;

  insert into chlom_runtime.authority_lease_revocation_receipts_v1(
    lease_id,outcome,expected_state,observed_state,principal_kind,principal_id,
    capability,resource_type,resource_id,revoker_kind,revoker_id,authority_ref,reason_code,
    mutation_applied,dail_event_id,correlation_id,metadata
  ) values (
    p_lease_id,v_outcome,p_expected_state,v_state,v_principal_kind,v_principal_id,
    v_capability,v_resource_type,v_resource_id,p_revoker_kind,p_revoker_id,p_authorization_id,p_reason_code,
    v_mutation,case when v_event is null then null else v_event->>'event_id' end,v_correlation_id,
    jsonb_build_object(
      'authority_created',false,
      'lease_authority_expanded',false,
      'key_material_returned',false,
      'plaintext_returned',false
    )
  ) returning receipt_id into v_receipt_id;

  return jsonb_build_object(
    'state',v_outcome,
    'lease_id',p_lease_id,
    'receipt_id',v_receipt_id,
    'observed_state',v_state,
    'authority_ref',p_authorization_id,
    'mutation_applied',v_mutation,
    'authority_created',false,
    'dail_event_id',case when v_event is null then null else v_event->>'event_id' end,
    'correlation_id',v_correlation_id
  );
end
$function$;

revoke all on function chlom_runtime.revoke_agent_authority_lease_v1(uuid,text,text,uuid,text,text) from public, anon, authenticated;
grant execute on function chlom_runtime.revoke_agent_authority_lease_v1(uuid,text,text,uuid,text,text) to postgres, service_role;

comment on table chlom_runtime.authority_lease_revocation_receipts_v1 is
  'CHLOM C2 non-secret receipts for exact authority-lease revocation outcomes; exact founder authority is bound and no authority is created by this surface.';
comment on function chlom_runtime.revoke_agent_authority_lease_v1(uuid,text,text,uuid,text,text) is
  'CHLOM C2 exact-authority-bound lease revocation with advisory serialization, fail-closed role checks, DAIL lineage on successful revocation, and non-secret receipts.';
