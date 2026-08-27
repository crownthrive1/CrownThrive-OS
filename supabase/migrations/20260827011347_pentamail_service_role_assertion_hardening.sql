-- Authenticate the invoker rather than the SECURITY DEFINER owner.

create or replace function integration_control.penta_mail_assert_service_role_v1()
returns void
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
begin
  if session_user not in ('postgres','service_role') and v_role <> 'service_role' then
    raise exception 'PENTAMAIL_SERVICE_ROLE_REQUIRED';
  end if;
end
$$;

revoke all on function integration_control.penta_mail_assert_service_role_v1()
  from public, anon, authenticated;

comment on function integration_control.penta_mail_assert_service_role_v1() is
  'Internal invoker assertion using session_user or the PostgREST service_role JWT claim; current_user is intentionally excluded because SECURITY DEFINER changes it to the owner.';
