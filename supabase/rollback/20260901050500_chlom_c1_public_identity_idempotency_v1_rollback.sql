-- Rollback for CHLOM C1 public identity / DID issuance idempotency hardening v1.
-- Restores the pre-v1 function body and caller grants observed before source build.

begin;

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
  if not exists(select 1 from chlom_identity.subjects where subject_id=p_subject_id) then
    raise exception 'unknown_subject';
  end if;
  select * into v_row from chlom_identity.public_identity_records where subject_id=p_subject_id;
  if found then
    return jsonb_build_object('public_id',v_row.public_id,'did_uri',v_row.did_uri,'resolver_state',v_row.resolver_state);
  end if;
  loop
    v_public_id := 'ctid_' || replace(gen_random_uuid()::text,'-','');
    exit when not exists(select 1 from chlom_identity.public_identity_records where public_id=v_public_id);
  end loop;
  v_did := 'did:chlom:' || v_public_id;
  insert into chlom_identity.public_identity_records(public_id,subject_id,did_uri,display_name,public_metadata)
  values(v_public_id,p_subject_id,v_did,p_display_name,coalesce(p_public_metadata,'{}'::jsonb));
  return jsonb_build_object('public_id',v_public_id,'did_uri',v_did,'resolver_state','identifier_active_key_pending');
end
$function$;

revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from public;
revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from anon;
revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from authenticated;
grant execute on function chlom_identity.ensure_public_identity(text,text,jsonb) to service_role;

comment on function chlom_identity.ensure_public_identity(text,text,jsonb) is null;

commit;
