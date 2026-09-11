-- CHLOM C1 public identity / DID issuance idempotency hardening v1
--
-- Purpose:
--   Make ensure_public_identity deterministic under concurrent callers for the
--   same CHLOM subject. The existing UNIQUE(subject_id) constraint prevents
--   duplicate durable identities, but a read-then-insert race can still make
--   one legitimate concurrent caller fail with a uniqueness violation.
--
-- Scope:
--   D1 internal identity control only. No provider write, credential, money,
--   rights, vote/quorum, D3, or authority expansion.

begin;

-- Fail closed on source/runtime drift instead of silently creating a parallel
-- identity path against an unexpected schema.
do $guard$
begin
  if to_regprocedure('chlom_identity.ensure_public_identity(text,text,jsonb)') is null then
    raise exception 'CHLOM_C1_SOURCE_DRIFT: ensure_public_identity missing';
  end if;
  if to_regclass('chlom_identity.public_identity_records') is null then
    raise exception 'CHLOM_C1_SOURCE_DRIFT: public_identity_records missing';
  end if;
  if not exists (
    select 1
    from pg_constraint c
    join pg_class r on r.oid = c.conrelid
    join pg_namespace n on n.oid = r.relnamespace
    where n.nspname = 'chlom_identity'
      and r.relname = 'public_identity_records'
      and c.conname = 'public_identity_records_subject_id_key'
      and c.contype = 'u'
  ) then
    raise exception 'CHLOM_C1_SOURCE_DRIFT: subject identity uniqueness constraint missing';
  end if;
end
$guard$;

create or replace function chlom_identity.ensure_public_identity(
  p_subject_id text,
  p_display_name text default null,
  p_public_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','extensions','chlom_identity'
as $function$
declare
  v_public_id text;
  v_did text;
  v_row chlom_identity.public_identity_records%rowtype;
begin
  if p_subject_id is null or pg_catalog.btrim(p_subject_id) = '' then
    raise exception 'invalid_subject_id';
  end if;

  -- One transaction-scoped lock per canonical subject closes the historical
  -- SELECT -> INSERT race while preserving the existing privacy-preserving
  -- random public identifier. A 64-bit hash collision can only serialize two
  -- unrelated subjects; it cannot merge identities or expand authority.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'chlom_identity.ensure_public_identity|' || p_subject_id,
      0
    )
  );

  if not exists (
    select 1
    from chlom_identity.subjects
    where subject_id = p_subject_id
  ) then
    raise exception 'unknown_subject';
  end if;

  select *
    into v_row
    from chlom_identity.public_identity_records
   where subject_id = p_subject_id;

  if found then
    return jsonb_build_object(
      'public_id', v_row.public_id,
      'did_uri', v_row.did_uri,
      'resolver_state', v_row.resolver_state
    );
  end if;

  loop
    v_public_id := 'ctid_' || replace(extensions.gen_random_uuid()::text, '-', '');
    exit when not exists (
      select 1
      from chlom_identity.public_identity_records
      where public_id = v_public_id
    );
  end loop;

  v_did := 'did:chlom:' || v_public_id;

  insert into chlom_identity.public_identity_records(
    public_id,
    subject_id,
    did_uri,
    display_name,
    public_metadata
  )
  values(
    v_public_id,
    p_subject_id,
    v_did,
    p_display_name,
    coalesce(p_public_metadata, '{}'::jsonb)
  )
  returning * into v_row;

  return jsonb_build_object(
    'public_id', v_row.public_id,
    'did_uri', v_row.did_uri,
    'resolver_state', v_row.resolver_state
  );
end
$function$;

-- Preserve the current least-privilege caller boundary explicitly.
revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from public;
revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from anon;
revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from authenticated;
grant execute on function chlom_identity.ensure_public_identity(text,text,jsonb) to service_role;

comment on function chlom_identity.ensure_public_identity(text,text,jsonb) is
  'CHLOM C1 canonical public identity/DID issuer. Transaction-scoped per-subject serialization guarantees idempotent concurrent issuance; service-role only; no authority expansion.';

commit;
