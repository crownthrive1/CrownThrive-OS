create table if not exists integration_control.penta_identity_source_snapshot_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references integration_control.penta_identity_source_snapshots_v1(snapshot_id),
  source_type text not null,
  source_ref text not null,
  predecessor_snapshot_id uuid references integration_control.penta_identity_source_snapshots_v1(snapshot_id),
  predecessor_source_ref text,
  provider_blob_sha text not null check (provider_blob_sha ~ '^[0-9a-f]{40}$'),
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null default '{}'::jsonb,
  authority_expansion boolean not null default false check (authority_expansion = false),
  created_at timestamptz not null default clock_timestamp(),
  unique(snapshot_id)
);

create or replace function integration_control.penta_identity_source_snapshot_receipts_append_only_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  raise exception 'PENTA_IDENTITY_SOURCE_SNAPSHOT_RECEIPTS_APPEND_ONLY';
end
$$;

drop trigger if exists trg_penta_identity_source_snapshot_receipts_append_only_v1 on integration_control.penta_identity_source_snapshot_receipts_v1;
create trigger trg_penta_identity_source_snapshot_receipts_append_only_v1
before update or delete on integration_control.penta_identity_source_snapshot_receipts_v1
for each row execute function integration_control.penta_identity_source_snapshot_receipts_append_only_v1();

create or replace function integration_control.penta_identity_source_snapshot_rebind_unchanged_v1(
  p_source_ref text,
  p_provider_blob_sha text,
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_prev integration_control.penta_identity_source_snapshots_v1%rowtype;
  v_new integration_control.penta_identity_source_snapshots_v1%rowtype;
  v_receipt uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_source_ref !~ '^crownthrive1/CrownThrive-OS@[0-9a-f]{40}:data/penta/os-v1\.registry\.json$' then
    raise exception 'PENTA_IDENTITY_SOURCE_REF_INVALID';
  end if;
  if coalesce(p_provider_blob_sha,'') !~ '^[0-9a-f]{40}$' then
    raise exception 'PENTA_IDENTITY_PROVIDER_BLOB_SHA_INVALID';
  end if;
  if coalesce(p_evidence->>'provider_readback','') <> 'verified' then
    raise exception 'PENTA_IDENTITY_PROVIDER_READBACK_REQUIRED';
  end if;
  if coalesce(p_evidence->>'predecessor_blob_sha','') <> p_provider_blob_sha then
    raise exception 'PENTA_IDENTITY_BLOB_IDENTITY_NOT_PROVEN';
  end if;

  perform pg_advisory_xact_lock(hashtext('ct:penta:identity-source-snapshot-rebind-v1'));

  select * into v_prev
  from integration_control.penta_identity_source_snapshots_v1
  where source_type='github_penta_os_registry'
  order by observed_at desc, snapshot_id desc
  limit 1;
  if not found then raise exception 'PENTA_IDENTITY_SOURCE_SNAPSHOT_PREDECESSOR_MISSING'; end if;

  select * into v_new
  from integration_control.penta_identity_source_snapshots_v1
  where source_type='github_penta_os_registry'
    and source_ref=p_source_ref
    and source_sha256=v_prev.source_sha256
  limit 1;

  if not found then
    insert into integration_control.penta_identity_source_snapshots_v1(
      source_type,source_ref,source_version,source_sha256,source_count,payload,observed_at
    ) values (
      'github_penta_os_registry',p_source_ref,v_prev.source_version,v_prev.source_sha256,v_prev.source_count,v_prev.payload,clock_timestamp()
    ) returning * into v_new;
  end if;

  insert into integration_control.penta_identity_source_snapshot_receipts_v1(
    snapshot_id,source_type,source_ref,predecessor_snapshot_id,predecessor_source_ref,
    provider_blob_sha,source_sha256,evidence,authority_expansion
  ) values (
    v_new.snapshot_id,v_new.source_type,v_new.source_ref,
    case when v_new.snapshot_id=v_prev.snapshot_id then null else v_prev.snapshot_id end,
    case when v_new.snapshot_id=v_prev.snapshot_id then null else v_prev.source_ref end,
    p_provider_blob_sha,v_new.source_sha256,
    coalesce(p_evidence,'{}'::jsonb) || jsonb_build_object(
      'contract','ct.penta.identity-source-snapshot.rebind-unchanged.v1',
      'source_payload_copied_from_verified_predecessor',true,
      'historical_snapshot_mutated',false,
      'authority_expansion',false
    ),false
  ) on conflict(snapshot_id) do nothing
  returning receipt_id into v_receipt;

  if v_receipt is null then
    select receipt_id into v_receipt
    from integration_control.penta_identity_source_snapshot_receipts_v1
    where snapshot_id=v_new.snapshot_id;
  end if;

  return jsonb_build_object(
    'ok',true,
    'state',case when v_new.snapshot_id=v_prev.snapshot_id then 'IDEMPOTENT' else 'APPENDED_UNCHANGED' end,
    'snapshot_id',v_new.snapshot_id,
    'source_ref',v_new.source_ref,
    'source_version',v_new.source_version,
    'source_sha256',v_new.source_sha256,
    'source_count',v_new.source_count,
    'provider_blob_sha',p_provider_blob_sha,
    'predecessor_snapshot_id',case when v_new.snapshot_id=v_prev.snapshot_id then null else v_prev.snapshot_id end,
    'predecessor_source_ref',case when v_new.snapshot_id=v_prev.snapshot_id then null else v_prev.source_ref end,
    'receipt_id',v_receipt,
    'authority_expansion',false,
    'historical_snapshot_mutated',false,
    'at',clock_timestamp()
  );
end
$$;

revoke all on function integration_control.penta_identity_source_snapshot_rebind_unchanged_v1(text,text,jsonb) from public, anon, authenticated;
grant execute on function integration_control.penta_identity_source_snapshot_rebind_unchanged_v1(text,text,jsonb) to service_role;
