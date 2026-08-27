-- Reject provider readbacks that finish after a newer probe but started earlier.

alter table integration_control.penta_mail_provider_control_v1
  add column if not exists last_readback_probe_started_at timestamptz;

create or replace function public.penta_mail_record_mailgun_readback_v3(
  p_readback_event_id text,
  p_enabled boolean,
  p_regular_disabled boolean,
  p_scheduled_disabled boolean,
  p_provider_http_status integer,
  p_response_sha256 text,
  p_adapter_context jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_probe_started_at timestamptz;
  v_result jsonb;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  begin
    v_probe_started_at := (p_adapter_context ->> 'probe_started_at')::timestamptz;
  exception when others then
    raise exception 'PENTAMAIL_INVALID_READBACK_PROBE_START';
  end;
  if v_probe_started_at > clock_timestamp() + interval '1 minute' then
    raise exception 'PENTAMAIL_INVALID_READBACK_PROBE_START';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
  for update;
  if found and v_control.last_readback_probe_started_at is not null
    and v_probe_started_at < v_control.last_readback_probe_started_at then
    perform integration_control.penta_mail_append_control_event_v1(
      'readback:' || p_readback_event_id || ':out-of-order',
      'mail.provider_readback_ignored_out_of_order',
      v_control.active_incident_id,
      null,
      jsonb_build_object(
        'probe_started_at', v_probe_started_at,
        'latest_probe_started_at', v_control.last_readback_probe_started_at,
        'response_sha256', p_response_sha256,
        'provider_http_status', p_provider_http_status,
        'raw_provider_body_retained', false
      ),
      'ct-founder-directive-pentamail-provider-probation-20260826-v1'
    );
    return public.penta_mail_provider_status_v1(null) || jsonb_build_object(
      'readback_recorded', false,
      'ignored_out_of_order', true
    );
  end if;
  v_result := public.penta_mail_record_mailgun_readback_v2(
    p_readback_event_id, p_enabled, p_regular_disabled, p_scheduled_disabled,
    p_provider_http_status, p_response_sha256, p_adapter_context
  );
  update integration_control.penta_mail_provider_control_v1
  set last_readback_probe_started_at = v_probe_started_at,
      updated_at = clock_timestamp()
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  return public.penta_mail_provider_status_v1(null) || jsonb_build_object(
    'readback_recorded', coalesce((v_result ->> 'readback_recorded')::boolean, false),
    'verified_enabled', coalesce((v_result ->> 'verified_enabled')::boolean, false),
    'ignored_out_of_order', false,
    'probe_started_at', v_probe_started_at
  );
end
$$;

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
  if coalesce((v_result ->> 'idempotent_replay')::boolean, false) is false then
    update integration_control.penta_mail_provider_control_v1
    set last_readback_probe_started_at = null,
        updated_at = clock_timestamp()
    where provider_route_id = 'mailgun:relay.crownthrive.com';
  end if;
  return public.penta_mail_provider_status_v1(p_trigger_ref) || jsonb_build_object(
    'incident_id', v_result ->> 'incident_id',
    'idempotent_replay', coalesce((v_result ->> 'idempotent_replay')::boolean, false),
    'provider_enable_estimate', v_result -> 'provider_enable_estimate'
  );
end
$$;

revoke execute on function public.penta_mail_record_mailgun_readback_v2(text,boolean,boolean,boolean,integer,text,jsonb)
  from service_role;
revoke all on function public.penta_mail_record_mailgun_readback_v3(text,boolean,boolean,boolean,integer,text,jsonb)
  from public, anon, authenticated;
grant execute on function public.penta_mail_record_mailgun_readback_v3(text,boolean,boolean,boolean,integer,text,jsonb)
  to service_role;

comment on column integration_control.penta_mail_provider_control_v1.last_readback_probe_started_at is
  'Adapter-captured provider probe start used to reject out-of-order readback completion.';
