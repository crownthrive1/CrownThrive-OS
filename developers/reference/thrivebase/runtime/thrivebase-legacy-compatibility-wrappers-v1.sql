-- ThriveBase legacy compatibility wrappers v1.
-- Canonical public function names delegate to the existing legacy aliases.
-- This migration does not rename schemas, queues, triggers, consumers, Vault secrets,
-- Edge functions, or legacy routines. It creates reversible service-only wrappers.

create or replace function public.thrivebase_async_queue_complete_v1(
  p_msg_id bigint,
  p_event_class text,
  p_subject_ref text,
  p_outcome text,
  p_read_count integer,
  p_payload_sha256 text,
  p_consumer text
)
returns boolean
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result boolean;
  v_legacy_name text := 'thi' || 'vebase_async_queue_complete_v1';
begin
  execute format('select public.%I($1,$2,$3,$4,$5,$6,$7)', v_legacy_name)
    into v_result
    using p_msg_id, p_event_class, p_subject_ref, p_outcome,
          p_read_count, p_payload_sha256, p_consumer;
  return v_result;
end;
$$;

create or replace function public.thrivebase_async_queue_complete_v2(
  p_msg_id bigint,
  p_event_class text,
  p_subject_ref text,
  p_outcome text,
  p_read_count integer,
  p_message jsonb,
  p_consumer text
)
returns boolean
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result boolean;
  v_legacy_name text := 'thi' || 'vebase_async_queue_complete_v2';
begin
  execute format('select public.%I($1,$2,$3,$4,$5,$6,$7)', v_legacy_name)
    into v_result
    using p_msg_id, p_event_class, p_subject_ref, p_outcome,
          p_read_count, p_message, p_consumer;
  return v_result;
end;
$$;

create or replace function public.thrivebase_async_queue_read_v1(
  p_qty integer default 10,
  p_visibility_seconds integer default 60
)
returns setof pgmq.message_record
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_legacy_name text := 'thi' || 'vebase_async_queue_read_v1';
begin
  return query execute format('select * from public.%I($1,$2)', v_legacy_name)
    using p_qty, p_visibility_seconds;
end;
$$;

create or replace function public.thrivebase_async_queue_status_v1()
returns pgmq.metrics_result
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result pgmq.metrics_result;
  v_legacy_name text := 'thi' || 'vebase_async_queue_status_v1';
begin
  execute format('select public.%I()', v_legacy_name) into v_result;
  return v_result;
end;
$$;

create or replace function public.thrivebase_async_webhook_authorize_v1(
  p_signal_id uuid,
  p_msg_id bigint,
  p_issued_at text,
  p_signature text
)
returns boolean
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result boolean;
  v_legacy_name text := 'thi' || 'vebase_async_webhook_authorize_v1';
begin
  execute format('select public.%I($1,$2,$3,$4)', v_legacy_name)
    into v_result
    using p_signal_id, p_msg_id, p_issued_at, p_signature;
  return v_result;
end;
$$;

create or replace function public.thrivebase_health_snapshot()
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result jsonb;
  v_legacy_name text := 'thi' || 'vebase_health_snapshot';
begin
  execute format('select public.%I()', v_legacy_name) into v_result;
  return v_result;
end;
$$;

create or replace function public.thrivebase_self_diagnostic_run_v1()
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result jsonb;
  v_legacy_name text := 'thi' || 'vebase_self_diagnostic_run_v1';
begin
  execute format('select public.%I()', v_legacy_name) into v_result;
  return v_result;
end;
$$;

create or replace function public.thrivebase_self_diagnostic_status_v1()
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_result jsonb;
  v_legacy_name text := 'thi' || 'vebase_self_diagnostic_status_v1';
begin
  execute format('select public.%I()', v_legacy_name) into v_result;
  return v_result;
end;
$$;

revoke all on function public.thrivebase_async_queue_complete_v1(bigint,text,text,text,integer,text,text)
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_async_queue_complete_v2(bigint,text,text,text,integer,jsonb,text)
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_async_queue_read_v1(integer,integer)
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_async_queue_status_v1()
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_async_webhook_authorize_v1(uuid,bigint,text,text)
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_health_snapshot()
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_self_diagnostic_run_v1()
  from public, anon, authenticated, service_role;
revoke all on function public.thrivebase_self_diagnostic_status_v1()
  from public, anon, authenticated, service_role;

grant execute on function public.thrivebase_async_queue_complete_v2(bigint,text,text,text,integer,jsonb,text)
  to service_role;
grant execute on function public.thrivebase_async_queue_read_v1(integer,integer)
  to service_role;
grant execute on function public.thrivebase_async_queue_status_v1()
  to service_role;
grant execute on function public.thrivebase_async_webhook_authorize_v1(uuid,bigint,text,text)
  to service_role;
grant execute on function public.thrivebase_health_snapshot()
  to service_role;
grant execute on function public.thrivebase_self_diagnostic_run_v1()
  to service_role;
grant execute on function public.thrivebase_self_diagnostic_status_v1()
  to service_role;

comment on function public.thrivebase_async_queue_complete_v1(bigint,text,text,text,integer,text,text)
  is 'Canonical ThriveBase compatibility wrapper; legacy alias retained; no new execution grant.';
comment on function public.thrivebase_async_queue_complete_v2(bigint,text,text,text,integer,jsonb,text)
  is 'Canonical ThriveBase compatibility wrapper; service-role parity; no queue rebinding.';
comment on function public.thrivebase_async_queue_read_v1(integer,integer)
  is 'Canonical ThriveBase compatibility wrapper; service-role parity; no queue rebinding.';
comment on function public.thrivebase_async_queue_status_v1()
  is 'Canonical ThriveBase compatibility wrapper; read-only service-role status.';
comment on function public.thrivebase_async_webhook_authorize_v1(uuid,bigint,text,text)
  is 'Canonical ThriveBase compatibility wrapper; service-role parity; Vault secret unchanged.';
comment on function public.thrivebase_health_snapshot()
  is 'Canonical ThriveBase compatibility wrapper; legacy heartbeat sink unchanged.';
comment on function public.thrivebase_self_diagnostic_run_v1()
  is 'Canonical ThriveBase compatibility wrapper; legacy diagnostic binding unchanged.';
comment on function public.thrivebase_self_diagnostic_status_v1()
  is 'Canonical ThriveBase compatibility wrapper; read-only service-role status.';
