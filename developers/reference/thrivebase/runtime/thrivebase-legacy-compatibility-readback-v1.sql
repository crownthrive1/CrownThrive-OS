-- ThriveBase legacy compatibility wrapper readback v1.
-- Read-only verification of wrapper identity, privilege parity, and safe status parity.
-- No queue read, completion, authorization, heartbeat write, diagnostic run,
-- trigger rebinding, consumer rebinding, or Edge rebinding is performed.

do $$
declare
  v_wrapper_count integer;
  v_legacy_count integer;
  v_signature_mismatches integer;
  v_public_access integer;
  v_service_role_mismatches integer;
  v_security_definer_count integer;
  v_trigger_bindings integer;
  v_canonical_schema_count integer;
  v_canonical_queue_count integer;
  v_queue_canonical jsonb;
  v_queue_legacy jsonb;
  v_diagnostic_canonical jsonb;
  v_diagnostic_legacy jsonb;
  v_legacy_queue_name text := 'thi' || 'vebase_async_queue_status_v1';
  v_legacy_diagnostic_name text := 'thi' || 'vebase_self_diagnostic_status_v1';
begin
  with expected(canonical_name, legacy_name, arg_types, expected_result, service_role_expected) as (
    values
      ('thrivebase_async_queue_complete_v1', 'thi' || 'vebase_async_queue_complete_v1',
       'bigint,text,text,text,integer,text,text', 'boolean', false),
      ('thrivebase_async_queue_complete_v2', 'thi' || 'vebase_async_queue_complete_v2',
       'bigint,text,text,text,integer,jsonb,text', 'boolean', true),
      ('thrivebase_async_queue_read_v1', 'thi' || 'vebase_async_queue_read_v1',
       'integer,integer', 'setof pgmq.message_record', true),
      ('thrivebase_async_queue_status_v1', 'thi' || 'vebase_async_queue_status_v1',
       '', 'pgmq.metrics_result', true),
      ('thrivebase_async_webhook_authorize_v1', 'thi' || 'vebase_async_webhook_authorize_v1',
       'uuid,bigint,text,text', 'boolean', true),
      ('thrivebase_health_snapshot', 'thi' || 'vebase_health_snapshot',
       '', 'jsonb', true),
      ('thrivebase_self_diagnostic_run_v1', 'thi' || 'vebase_self_diagnostic_run_v1',
       '', 'jsonb', true),
      ('thrivebase_self_diagnostic_status_v1', 'thi' || 'vebase_self_diagnostic_status_v1',
       '', 'jsonb', true)
  )
  select count(*) into v_wrapper_count
  from expected e
  where to_regprocedure(format('public.%I(%s)', e.canonical_name, e.arg_types)) is not null;

  with expected(legacy_name, arg_types) as (
    values
      ('thi' || 'vebase_async_queue_complete_v1', 'bigint,text,text,text,integer,text,text'),
      ('thi' || 'vebase_async_queue_complete_v2', 'bigint,text,text,text,integer,jsonb,text'),
      ('thi' || 'vebase_async_queue_read_v1', 'integer,integer'),
      ('thi' || 'vebase_async_queue_status_v1', ''),
      ('thi' || 'vebase_async_webhook_authorize_v1', 'uuid,bigint,text,text'),
      ('thi' || 'vebase_health_snapshot', ''),
      ('thi' || 'vebase_self_diagnostic_run_v1', ''),
      ('thi' || 'vebase_self_diagnostic_status_v1', '')
  )
  select count(*) into v_legacy_count
  from expected e
  where to_regprocedure(format('public.%I(%s)', e.legacy_name, e.arg_types)) is not null;

  with expected(canonical_name, arg_types, expected_result) as (
    values
      ('thrivebase_async_queue_complete_v1', 'bigint,text,text,text,integer,text,text', 'boolean'),
      ('thrivebase_async_queue_complete_v2', 'bigint,text,text,text,integer,jsonb,text', 'boolean'),
      ('thrivebase_async_queue_read_v1', 'integer,integer', 'setof pgmq.message_record'),
      ('thrivebase_async_queue_status_v1', '', 'pgmq.metrics_result'),
      ('thrivebase_async_webhook_authorize_v1', 'uuid,bigint,text,text', 'boolean'),
      ('thrivebase_health_snapshot', '', 'jsonb'),
      ('thrivebase_self_diagnostic_run_v1', '', 'jsonb'),
      ('thrivebase_self_diagnostic_status_v1', '', 'jsonb')
  )
  select count(*) into v_signature_mismatches
  from expected e
  join pg_proc p on p.oid=to_regprocedure(format('public.%I(%s)', e.canonical_name, e.arg_types))
  where lower(pg_get_function_result(p.oid)) <> e.expected_result;

  with expected(canonical_name, arg_types, service_role_expected) as (
    values
      ('thrivebase_async_queue_complete_v1', 'bigint,text,text,text,integer,text,text', false),
      ('thrivebase_async_queue_complete_v2', 'bigint,text,text,text,integer,jsonb,text', true),
      ('thrivebase_async_queue_read_v1', 'integer,integer', true),
      ('thrivebase_async_queue_status_v1', '', true),
      ('thrivebase_async_webhook_authorize_v1', 'uuid,bigint,text,text', true),
      ('thrivebase_health_snapshot', '', true),
      ('thrivebase_self_diagnostic_run_v1', '', true),
      ('thrivebase_self_diagnostic_status_v1', '', true)
  )
  select
    count(*) filter (
      where has_function_privilege('public', p.oid, 'EXECUTE')
         or has_function_privilege('anon', p.oid, 'EXECUTE')
         or has_function_privilege('authenticated', p.oid, 'EXECUTE')
    ),
    count(*) filter (
      where has_function_privilege('service_role', p.oid, 'EXECUTE')
            is distinct from e.service_role_expected
    ),
    count(*) filter (where p.prosecdef)
  into v_public_access, v_service_role_mismatches, v_security_definer_count
  from expected e
  join pg_proc p on p.oid=to_regprocedure(format('public.%I(%s)', e.canonical_name, e.arg_types));

  with expected(canonical_name, arg_types) as (
    values
      ('thrivebase_async_queue_complete_v1', 'bigint,text,text,text,integer,text,text'),
      ('thrivebase_async_queue_complete_v2', 'bigint,text,text,text,integer,jsonb,text'),
      ('thrivebase_async_queue_read_v1', 'integer,integer'),
      ('thrivebase_async_queue_status_v1', ''),
      ('thrivebase_async_webhook_authorize_v1', 'uuid,bigint,text,text'),
      ('thrivebase_health_snapshot', ''),
      ('thrivebase_self_diagnostic_run_v1', ''),
      ('thrivebase_self_diagnostic_status_v1', '')
  )
  select count(*) into v_trigger_bindings
  from pg_trigger t
  where not t.tgisinternal
    and t.tgfoid in (
      select to_regprocedure(format('public.%I(%s)', e.canonical_name, e.arg_types))
      from expected e
    );

  select count(*) into v_canonical_schema_count
  from pg_namespace
  where nspname='thrivebase_control';

  select count(*) into v_canonical_queue_count
  from pg_class c
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='pgmq'
    and c.relname in ('q_thrivebase_async_work','a_thrivebase_async_work');

  select to_jsonb(public.thrivebase_async_queue_status_v1())
    into v_queue_canonical;
  execute format('select to_jsonb(public.%I())', v_legacy_queue_name)
    into v_queue_legacy;

  select public.thrivebase_self_diagnostic_status_v1()
    into v_diagnostic_canonical;
  execute format('select public.%I()', v_legacy_diagnostic_name)
    into v_diagnostic_legacy;

  if v_wrapper_count <> 8
     or v_legacy_count <> 8
     or v_signature_mismatches <> 0
     or v_public_access <> 0
     or v_service_role_mismatches <> 0
     or v_security_definer_count <> 0
     or v_trigger_bindings <> 0
     or v_canonical_schema_count <> 0
     or v_canonical_queue_count <> 0
     or v_queue_canonical is distinct from v_queue_legacy
     or v_diagnostic_canonical is distinct from v_diagnostic_legacy then
    raise exception
      'thrivebase_compatibility_wrapper_readback_failed wrappers=% legacy=% signatures=% public_access=% service_mismatch=% security_definers=% trigger_bindings=% canonical_schemas=% canonical_queues=% queue_parity=% diagnostic_parity=%',
      v_wrapper_count, v_legacy_count, v_signature_mismatches, v_public_access,
      v_service_role_mismatches, v_security_definer_count, v_trigger_bindings,
      v_canonical_schema_count, v_canonical_queue_count,
      (v_queue_canonical is not distinct from v_queue_legacy),
      (v_diagnostic_canonical is not distinct from v_diagnostic_legacy);
  end if;
end;
$$;

with queue_status as (
  select to_jsonb(public.thrivebase_async_queue_status_v1()) as value
),
diagnostic_status as (
  select public.thrivebase_self_diagnostic_status_v1() as value
)
select jsonb_build_object(
  'result','PASS_THRIVEBASE_LEGACY_COMPATIBILITY_WRAPPER_READBACK',
  'canonical_wrapper_count',8,
  'legacy_alias_count',8,
  'safe_behavior_parity_canaries',2,
  'queue_status_sha256',
    (select encode(extensions.digest(convert_to(value::text,'UTF8'),'sha256'),'hex') from queue_status),
  'diagnostic_status_sha256',
    (select encode(extensions.digest(convert_to(value::text,'UTF8'),'sha256'),'hex') from diagnostic_status),
  'public_execute',false,
  'anon_execute',false,
  'authenticated_execute',false,
  'service_role_wrapper_count',7,
  'security_definer_wrappers',0,
  'trigger_rebinding',false,
  'queue_rebinding',false,
  'consumer_rebinding',false,
  'vault_secret_renamed',false,
  'edge_rebinding',false,
  'legacy_alias_retired',false,
  'destructive_rename',false,
  'production_authority_created',false,
  'provider_write_created',false,
  'credential_access_created',false,
  'money_movement_created',false,
  'rights_grant_created',false,
  'chain_broadcast_created',false,
  'phase_advancement',false,
  'merge_authorized',false
) as thrivebase_compatibility_wrapper_readback;
