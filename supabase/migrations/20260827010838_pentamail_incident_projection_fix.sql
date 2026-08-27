-- Return incident acceptance from the post-mutation control projection.
-- This prevents a cleared prior readback from appearing in the RPC response.

create or replace function public.penta_mail_accept_mailgun_probation_v3(
  p_provider_event_id text,
  p_provider_event_sha256 text,
  p_trigger_ref text,
  p_retry_after_seconds integer default null,
  p_evidence_kind text default 'authenticated_provider_response',
  p_authority_ref text default 'ct-founder-directive-pentamail-provider-probation-20260826-v1'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_result jsonb;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_result := public.penta_mail_accept_mailgun_probation_v2(
    p_provider_event_id, p_provider_event_sha256, p_trigger_ref,
    p_retry_after_seconds, p_evidence_kind, p_authority_ref
  );
  return public.penta_mail_provider_status_v1(p_trigger_ref) || jsonb_build_object(
    'incident_id', v_result ->> 'incident_id',
    'idempotent_replay', coalesce((v_result ->> 'idempotent_replay')::boolean, false),
    'provider_enable_estimate', v_result -> 'provider_enable_estimate'
  );
end
$$;

revoke execute on function public.penta_mail_accept_mailgun_probation_v2(text,text,text,integer,text,text)
  from service_role;
revoke all on function public.penta_mail_accept_mailgun_probation_v3(text,text,text,integer,text,text)
  from public, anon, authenticated;
grant execute on function public.penta_mail_accept_mailgun_probation_v3(text,text,text,integer,text,text)
  to service_role;

comment on function public.penta_mail_accept_mailgun_probation_v3(text,text,text,integer,text,text) is
  'Serialized incident acceptance returning only the post-mutation provider-control projection; prior readback evidence cannot leak into a new incident response.';
