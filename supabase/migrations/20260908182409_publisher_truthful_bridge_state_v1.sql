-- 20260908154500_publisher_truthful_bridge_state_v1.sql
--
-- RELEASE CANDIDATE: verified in rollback-only probes; not applied as of
-- 2026-09-08 UTC artifact freeze.
--
-- Narrow scope:
--   * suppress exact tuples with a queued/current job or pending/ready/active/verified
--     dispatch while leaving failed/rolled-back/superseded work retryable;
--   * serialize and recheck the exact tuple before attempting enqueue;
--   * make enqueue telemetry tri-state and explicitly limited to authorization
--     plus exact queued-job readback; and
--   * count normalized six-stage evidence once per governed job with the
--     certified provider and verifier derived from its exact route.
--
-- This does not attest downstream handler execution, provider write, publication,
-- fulfilment, or money movement. It changes no RLS policy, table grant, API route,
-- historical evidence row, policy, candidate, release, job, attempt, or receipt.
--
-- Read-only snapshot (2026-09-08 UTC):
--   target preimage SHA-256:
--     14794619818b28c63c7abf35b3bf4f9c461288be90517ac1d6744c6760d18f55
--   public status preimage SHA-256:
--     f7e43ece128a67372c24469923931adce7a9aa19e7e9d61b00c6be3c834bd56d
--   six-stage finalizer preimage SHA-256:
--     28f62fa393251628859c2a6a0c12951e19934d048b54ca00ab68a50458a9d250
--   gate_snapshot_v6 SHA-256:
--     abdecd59cfffe6008e5e20eaba04f47ab5e76853208e1e61228df9d69e243d36
--   enqueue_governed_site_publish SHA-256:
--     6b25dfe5829e0d5be41dbf45c14ed971d8b7312b29466df2246a9f5579465abe
--   finalizer external-observation dependency SHA-256:
--     c7b03299baa9ca067ea674c7c1090464903cb056161816e4f2a4c8473454f4bc
--   all six functions: owner postgres, SECURITY DEFINER, direct EXECUTE
--     allowlist postgres + service_role; ten active cron jobs connect as postgres.
--   provider proof: 12 dispatch/cycle rows but 11 unique governed jobs.
--   certified eligible adapters include dynamic feed and Brilliant Directories.
--
-- The dependency pins are direct, not transitive. Claims are intentionally
-- limited to the three replaced functions' selection, enqueue-call/readback,
-- finalization, public status, and counting logic.
-- Apply outside cron minutes and their +/- one-minute guard band. A guarded
-- executable reverse artifact is adjacent as:
--   20260908154500_publisher_truthful_bridge_state_v1.rollback.sql
--
begin;

set local lock_timeout = '2s';
set local statement_timeout = '20s';
set local timezone = 'UTC';

do $preflight$
declare
  v_oid oid;
  v_sha text;
  v_function_contract_ok boolean;
  v_companion_contracts_ok boolean;
  v_dependencies_ok boolean;
  v_cron_ok boolean;
  v_rls_ok boolean;
  v_minute integer:=extract(minute from pg_catalog.clock_timestamp())::integer;
begin
  if session_user<>'postgres' or current_user<>'postgres' then
    raise exception 'publisher_truthful_bridge_state_v1_postgres_migration_session_required';
  end if;

  if v_minute in (
    1,2,3,7,8,9,13,14,15,19,20,21,25,26,27,
    31,32,33,37,38,39,43,44,45,49,50,51,55,56,57
  ) then
    raise exception 'publisher_truthful_bridge_state_v1_retry_outside_scheduled_minute';
  end if;

  select p.oid,
         pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
             'sha256'
           ),
           'hex'
         )
    into v_oid,v_sha
  from pg_catalog.pg_proc p
  join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='run_thriveevergreen_autonomous_publisher_v2'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)=
      'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint';

  if v_oid is null then
    raise exception 'publisher_truthful_bridge_state_v1_target_missing';
  end if;
  if v_sha<>'14794619818b28c63c7abf35b3bf4f9c461288be90517ac1d6744c6760d18f55' then
    raise exception 'publisher_truthful_bridge_state_v1_preimage_drift:%',v_sha;
  end if;

  select p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, integration_control, developer_commerce, chlom_runtime, extensions',
           'TimeZone=UTC'
         ]::text[]
         and not pg_catalog.has_function_privilege('anon',p.oid,'EXECUTE')
         and not pg_catalog.has_function_privilege('authenticated',p.oid,'EXECUTE')
         and pg_catalog.has_function_privilege('service_role',p.oid,'EXECUTE')
         and (
           select count(*)=2
           from pg_catalog.aclexplode(
             coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
           ) acl
           where acl.privilege_type='EXECUTE'
             and acl.grantee in (
               p.proowner,
               pg_catalog.to_regrole('service_role')::oid
             )
         )
         and not exists (
           select 1
           from pg_catalog.aclexplode(
             coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
           ) acl
           where acl.privilege_type='EXECUTE'
             and acl.grantee not in (
               p.proowner,
               pg_catalog.to_regrole('service_role')::oid
             )
         )
    into v_function_contract_ok
  from pg_catalog.pg_proc p
  where p.oid=v_oid;
  if v_function_contract_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_function_contract_drift';
  end if;

  with expected(nspname,proname,identity_args,expected_sha,expected_volatility,expected_config) as (
    values
      (
        'public',
        'thriveevergreen_autonomous_publisher_status_v2',
        '',
        'f7e43ece128a67372c24469923931adce7a9aa19e7e9d61b00c6be3c834bd56d',
        's'::"char",
        array['search_path=pg_catalog, integration_control, chlom_runtime']::text[]
      ),
      (
        'integration_control',
        'pentagreen_six_stage_publication_final_v1',
        'p_cycle_id uuid',
        '28f62fa393251628859c2a6a0c12951e19934d048b54ca00ab68a50458a9d250',
        'v'::"char",
        array['search_path=pg_catalog, integration_control, extensions']::text[]
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,p.proacl,
           pg_catalog.encode(
             extensions.digest(
               pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
               'sha256'
             ),
             'hex'
           ) as actual_sha
    from expected e
    join pg_catalog.pg_namespace n on n.nspname=e.nspname
    join pg_catalog.pg_proc p
      on p.pronamespace=n.oid
     and p.proname=e.proname
     and pg_catalog.pg_get_function_identity_arguments(p.oid)=e.identity_args
  )
  select count(*)=2
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and provolatile=expected_volatility
           and proconfig=expected_config
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
           and (
             select count(*)=2
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee in (
                 actual.proowner,
                 pg_catalog.to_regrole('service_role')::oid
               )
           )
           and not exists (
             select 1
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee not in (
                 actual.proowner,
                 pg_catalog.to_regrole('service_role')::oid
               )
           )
         )
    into v_companion_contracts_ok
  from actual;
  if v_companion_contracts_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_companion_preimage_drift';
  end if;

  with expected(proname,identity_args,expected_sha,expected_volatility,expected_config) as (
    values
      (
        'thriveevergreen_publisher_gate_snapshot_v6',
        'p_candidate_id uuid',
        'abdecd59cfffe6008e5e20eaba04f47ab5e76853208e1e61228df9d69e243d36',
        's'::"char",
        array['search_path=pg_catalog, integration_control']::text[]
      ),
      (
        'enqueue_governed_site_publish',
        'p_release_id uuid',
        '6b25dfe5829e0d5be41dbf45c14ed971d8b7312b29466df2246a9f5579465abe',
        'v'::"char",
        array['search_path=pg_catalog, integration_control, chlom_runtime']::text[]
      ),
      (
        'pentagreen_dynamic_feed_external_observation_v1',
        'p_cycle_id uuid, p_stage text, p_route_id text, p_subject_type text, p_subject_ref text, p_exact_version_ref text, p_content_sha256 text, p_expected_present boolean',
        'c7b03299baa9ca067ea674c7c1090464903cb056161816e4f2a4c8473454f4bc',
        'v'::"char",
        array['search_path=pg_catalog, integration_control, extensions, chlom_runtime']::text[]
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,p.proacl,
           pg_catalog.encode(
             extensions.digest(
               pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
               'sha256'
             ),
             'hex'
           ) as actual_sha
    from expected e
    join pg_catalog.pg_proc p
      on p.proname=e.proname
     and pg_catalog.pg_get_function_identity_arguments(p.oid)=e.identity_args
    join pg_catalog.pg_namespace n
      on n.oid=p.pronamespace and n.nspname='integration_control'
  )
  select count(*)=3
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and provolatile=expected_volatility
           and proconfig=expected_config
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
           and (
             select count(*)=2
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee in (
                 actual.proowner,
                 pg_catalog.to_regrole('service_role')::oid
               )
           )
           and not exists (
             select 1
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee not in (
                 actual.proowner,
                 pg_catalog.to_regrole('service_role')::oid
               )
           )
         )
    into v_dependencies_ok
  from actual;
  if v_dependencies_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_privileged_dependency_drift';
  end if;

  with expected(jobname,schedule,command) as (
    values
      ('ct-thriveevergreen-publisher-v2-slot-01','2 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,1::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-02','8 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,2::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-03','14 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,3::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-04','20 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,4::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-05','26 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,5::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-06','32 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,6::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-07','38 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,7::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-08','44 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,8::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-09','50 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,9::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-10','56 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,10::smallint);')
  ), actual as (
    select e.jobname,e.schedule,e.command,
           j.jobid,j.active,j.database,j.username,
           j.schedule as actual_schedule,j.command as actual_command
    from expected e
    left join cron.job j on j.jobname=e.jobname
  )
  select count(*)=10
         and pg_catalog.bool_and(
           jobid is not null
           and active
           and database='postgres'
           and username='postgres'
           and actual_schedule=schedule
           and actual_command=command
         )
         and (
           select count(*)=10
           from cron.job j0
           where j0.jobname~'^ct-thriveevergreen-publisher-v2-slot-(0[1-9]|10)$'
         )
    into v_cron_ok
  from actual;
  if v_cron_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_cron_identity_drift';
  end if;

  select count(*)=11
         and pg_catalog.bool_and(c.relrowsecurity)
         and pg_catalog.bool_and(
           case
             when c.relname in (
               'governed_releases',
               'pentagreen_six_stage_publication_cycles_v1',
               'site_provider_adapters',
               'site_publish_jobs',
               'site_publish_routes'
             ) then not c.relforcerowsecurity
             else c.relforcerowsecurity
           end
         )
    into v_rls_ok
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='integration_control'
    and c.relname in (
      'governed_releases',
      'pentagreen_six_stage_publication_cycles_v1',
      'site_provider_adapters',
      'site_publish_jobs',
      'site_publish_routes',
      'thriveevergreen_publisher_attempts_v2',
      'thriveevergreen_publisher_candidates_v2',
      'thriveevergreen_publisher_dispatch_queue_v2',
      'thriveevergreen_publisher_provider_receipts_v2',
      'thriveevergreen_publisher_slots_v2',
      'thriveevergreen_publisher_windows_v2'
    );
  if v_rls_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_prechange_rls_drift';
  end if;

  if not pg_catalog.pg_try_advisory_xact_lock(
    pg_catalog.hashtext('ct.policy.thriveevergreen-autonomous-publisher.v2'),
    pg_catalog.hashtext(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC')::text
    )
  ) then
    raise exception 'publisher_truthful_bridge_state_v1_active_subslot_retry';
  end if;
end;
$preflight$;

CREATE OR REPLACE FUNCTION integration_control.run_thriveevergreen_autonomous_publisher_v2(p_window_start timestamp with time zone DEFAULT date_trunc('hour'::text, now(), 'UTC'::text), p_invocation_source text DEFAULT 'governed_backend_manual'::text, p_preview boolean DEFAULT true, p_slot_no smallint DEFAULT NULL::smallint)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control', 'developer_commerce', 'chlom_runtime', 'extensions'
 SET "TimeZone" TO 'UTC'
AS $function$
declare
  v_policy integration_control.thriveevergreen_autonomous_publisher_policy_v2%rowtype;
  v_window timestamptz:=date_trunc('hour',p_window_start,'UTC');
  v_candidate record;
  v_snapshot jsonb;
  v_slot_result jsonb;
  v_results jsonb:='[]'::jsonb;
  v_slot_count smallint:=0;
  v_attempt_count smallint:=0;
  v_queued_count smallint:=0;
  v_verified_publication_count smallint:=0;
  v_expected_minute smallint;
  v_attempt_id uuid;
  v_dispatch_id uuid;
  v_payload jsonb;
  v_enqueue_receipt jsonb;
  v_enqueue_state text;
  v_enqueue_job_id uuid;
  v_enqueue_receipt_sha text;
  v_enqueue_readback_sha text;
  v_bridge_attempted boolean:=false;
  v_bridge_ok boolean:=null;
  v_slots_evidence jsonb:='[]'::jsonb;
  v_evidence_sha text;
  v_dail jsonb;
  v_reason_code text;
  v_candidate_selected boolean:=false;
  v_candidate_still_admitted boolean:=false;
  v_exact_publish_exists boolean:=false;
  v_exact_lock_contended boolean:=false;
  v_selected_candidate_id uuid;
  v_selected_release_id uuid;
  v_selected_route_id text;
  v_selected_exact_version_ref text;
  v_selected_content_sha256 text;
begin
  -- NULL never falls through PL/pgSQL three-valued IF semantics. A NULL slot
  -- is accepted only by the explicitly read-only preview contract.
  if p_window_start is null then
    raise exception 'publisher_v2_window_required';
  end if;
  if p_invocation_source is null or pg_catalog.btrim(p_invocation_source)='' then
    raise exception 'publisher_v2_invocation_source_required';
  end if;
  if p_preview is null then
    raise exception 'publisher_v2_preview_mode_required';
  end if;
  if p_preview is not true and p_slot_no is null then
    raise exception 'publisher_v2_slot_number_required';
  end if;
  select * into strict v_policy
  from integration_control.thriveevergreen_autonomous_publisher_policy_v2
  where policy_id='ct.policy.thriveevergreen-autonomous-publisher.v2';

  if v_window<>date_trunc('hour',now(),'UTC') then
    raise exception 'publisher_v2_window_must_be_current_utc_hour';
  end if;

  if p_preview is true then
    for v_candidate in
      select c.candidate_id
      from integration_control.thriveevergreen_publisher_candidates_v2 c
      where c.candidate_state='admitted'
    and not exists (
      select 1
      from integration_control.site_publish_jobs j0
      where j0.release_id=c.release_id
        and j0.route_id=c.route_id
        and j0.exact_version_ref=c.exact_version_ref
        and j0.content_sha256=c.content_sha256
        and j0.state in ('queued','executing','published','rollback_pending')
    )
    and not exists (
      select 1
      from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q0
      join integration_control.thriveevergreen_publisher_attempts_v2 a0
        on a0.attempt_id=q0.attempt_id
      where q0.release_id=c.release_id
        and q0.route_id=c.route_id
        and a0.exact_version_ref=c.exact_version_ref
        and a0.content_sha256=c.content_sha256
        and q0.dispatch_state in (
          'enqueue_pending','ready','leased','provider_written',
          'readback_verified','rollback_verified'
        )
    )
      order by c.priority,c.candidate_id
      limit 10
    loop
      v_results:=v_results||jsonb_build_array(
        integration_control.thriveevergreen_publisher_gate_snapshot_v6(v_candidate.candidate_id)
      );
    end loop;
    return jsonb_build_object(
      'contract','ct.thriveevergreen.autonomous-publisher.v2',
      'run_scope','read_only_preview',
      'canonical_writes_performed',false,'hour_slot_consumed',false,
      'candidate_attempt_count',0,'publication_count',0,
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false,
      'candidate_snapshots',v_results
    );
  end if;

  -- Source text is telemetry, not authority. session_user cannot be forged by
  -- service_role; only the postgres login used by the verified cron jobs may write.
  if session_user<>'postgres' then
    raise exception 'publisher_v2_production_session_identity_invalid';
  end if;

  if p_invocation_source<>'pg_cron_thriveevergreen_publisher_v2' then
    raise exception 'publisher_v2_invocation_identity_invalid';
  end if;

  if p_slot_no is null or p_slot_no not between 1 and 10 then
    raise exception 'publisher_v2_slot_number_invalid';
  end if;

  v_expected_minute:=case p_slot_no
    when 1 then 2 when 2 then 8 when 3 then 14 when 4 then 20 when 5 then 26
    when 6 then 32 when 7 then 38 when 8 then 44 when 9 then 50 when 10 then 56
  end;

  if extract(minute from clock_timestamp())::smallint<>v_expected_minute then
    raise exception 'publisher_v2_no_catch_up_or_off_schedule_execution';
  end if;

  if v_policy.policy_state<>'active'
     or v_policy.runtime_mode not in ('production_observer','production_write')
  then
    return jsonb_build_object(
      'contract','ct.thriveevergreen.autonomous-publisher.v2','run_scope','production',
      'run_state','not_executed','decision','WORKING',
      'canonical_writes_performed',false,'hour_slot_consumed',false,
      'candidate_attempt_count',0,'publication_count',0,
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false,
      'blockers',jsonb_build_array('PUBLISHER_PRODUCTION_ACTIVATION_REQUIRED')
    );
  end if;

  -- Observer mode and a disabled-effects policy are terminal before every lock,
  -- slot, attempt, dispatch, enqueue, or append-only evidence write.
  if v_policy.runtime_mode<>'production_write'
     or v_policy.production_effects_enabled is not true
  then
    return jsonb_build_object(
      'contract','ct.thriveevergreen.autonomous-publisher.v2','run_scope','production',
      'run_state','observer_read_only','decision','WORKING',
      'canonical_writes_performed',false,'hour_slot_consumed',false,
      'candidate_attempt_count',0,'publication_count',0,
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false,
      'blockers',jsonb_build_array('PUBLISHER_PRODUCTION_WRITE_EFFECTS_REQUIRED')
    );
  end if;

  if not pg_try_advisory_xact_lock(hashtext(v_policy.policy_id),hashtext(v_window::text)) then
    return jsonb_build_object(
      'contract','ct.thriveevergreen.autonomous-publisher.v2','run_scope','production',
      'run_state','deferred_contention','decision','WORKING',
      'canonical_writes_performed',false,'hour_slot_consumed',false,
      'candidate_attempt_count',0,'publication_count',0,
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false,
      'blockers',jsonb_build_array('CONCURRENT_SUBSLOT_LOCK_ACTIVE_NO_CATCH_UP')
    );
  end if;

  if v_window<>date_trunc('hour',clock_timestamp(),'UTC')
     or extract(minute from clock_timestamp())::smallint<>v_expected_minute
  then
    raise exception 'publisher_v2_post_lock_no_catch_up_or_stale_window';
  end if;

  insert into integration_control.thriveevergreen_publisher_windows_v2 (
    policy_id,window_start,state,target_attempts
  ) values (v_policy.policy_id,v_window,'running',v_policy.target_candidate_attempts_per_hour)
  on conflict (policy_id,window_start) do nothing;

  if exists (
    select 1 from integration_control.thriveevergreen_publisher_slots_v2
    where policy_id=v_policy.policy_id and window_start=v_window and slot_no=p_slot_no
  ) then
    return jsonb_build_object(
      'contract','ct.thriveevergreen.autonomous-publisher.v2','run_scope','production',
      'duplicate',true,'slot_no',p_slot_no,'hour_slot_consumed',true,
      'candidate_attempt_count',(select attempt_count from integration_control.thriveevergreen_publisher_windows_v2 where policy_id=v_policy.policy_id and window_start=v_window),
      'publication_count',(select verified_publication_count from integration_control.thriveevergreen_publisher_windows_v2 where policy_id=v_policy.policy_id and window_start=v_window),
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false
    );
  end if;

  insert into integration_control.thriveevergreen_publisher_slots_v2 (
    policy_id,window_start,slot_no,scheduled_minute,invocation_source,
    slot_state,economic_decision,reason_code
  ) values (
    v_policy.policy_id,v_window,p_slot_no,v_expected_minute,p_invocation_source,
    'running','WORKING','EVALUATION_RUNNING'
  );

  select c.* into v_candidate
  from integration_control.thriveevergreen_publisher_candidates_v2 c
  left join lateral (
    select max(a.created_at) last_attempt_at
    from integration_control.thriveevergreen_publisher_attempts_v2 a
    where a.candidate_id=c.candidate_id
  ) la on true
  where c.candidate_state='admitted'
    and not exists (
      select 1
      from integration_control.site_publish_jobs j0
      where j0.release_id=c.release_id
        and j0.route_id=c.route_id
        and j0.exact_version_ref=c.exact_version_ref
        and j0.content_sha256=c.content_sha256
        and j0.state in ('queued','executing','published','rollback_pending')
    )
    and not exists (
      select 1
      from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q0
      join integration_control.thriveevergreen_publisher_attempts_v2 a0
        on a0.attempt_id=q0.attempt_id
      where q0.release_id=c.release_id
        and q0.route_id=c.route_id
        and a0.exact_version_ref=c.exact_version_ref
        and a0.content_sha256=c.content_sha256
        and q0.dispatch_state in (
          'enqueue_pending','ready','leased','provider_written',
          'readback_verified','rollback_verified'
        )
    )
    and not exists (
      select 1 from integration_control.thriveevergreen_publisher_attempts_v2 a
      where a.policy_id=v_policy.policy_id
        and a.window_start=v_window
        and a.candidate_id=c.candidate_id
    )
  order by case when la.last_attempt_at is null then 0 else 1 end,
           la.last_attempt_at nulls first,c.priority,c.candidate_id
  limit 1;

  v_candidate_selected:=found;
  if v_candidate_selected then
    -- Snapshot the selected identity for the tuple lock. Then take a row lock and
    -- refresh v_candidate itself, so gate, attempt, and payload all consume the
    -- same locked values. Historical duplicates remain immutable evidence;
    -- failed attempts remain retryable.
    v_selected_candidate_id:=v_candidate.candidate_id;
    v_selected_release_id:=v_candidate.release_id;
    v_selected_route_id:=v_candidate.route_id;
    v_selected_exact_version_ref:=v_candidate.exact_version_ref;
    v_selected_content_sha256:=v_candidate.content_sha256;
    if not pg_catalog.pg_try_advisory_xact_lock(
      pg_catalog.hashtextextended(
        pg_catalog.concat_ws(
          '|',v_selected_release_id::text,v_selected_route_id,
          v_selected_exact_version_ref,v_selected_content_sha256
        ),
        0
      )
    ) then
      v_exact_lock_contended:=true;
      v_candidate_selected:=false;
    else
      begin
        -- publisher_v2_candidate_lock_fence: NOWAIT prevents a privileged
        -- candidate updater from holding this cron backend beyond its slot.
        -- v_candidate is refreshed by the locking read and is the sole record
        -- consumed by the gate, attempt, dispatch payload, and enqueue readback.
        select c1.*
          into v_candidate
        from integration_control.thriveevergreen_publisher_candidates_v2 c1
        where c1.candidate_id=v_selected_candidate_id
        for update nowait;

        v_candidate_still_admitted:=found
          and v_candidate.candidate_state='admitted'
          and v_candidate.release_id=v_selected_release_id
          and v_candidate.route_id=v_selected_route_id
          and v_candidate.exact_version_ref=v_selected_exact_version_ref
          and v_candidate.content_sha256=v_selected_content_sha256;
      exception when lock_not_available then
        v_exact_lock_contended:=true;
        v_candidate_still_admitted:=false;
      end;

      if v_candidate_still_admitted is true then
        select exists (
            select 1
            from integration_control.site_publish_jobs j1
            where j1.release_id=v_candidate.release_id
              and j1.route_id=v_candidate.route_id
              and j1.exact_version_ref=v_candidate.exact_version_ref
              and j1.content_sha256=v_candidate.content_sha256
              and j1.state in ('queued','executing','published','rollback_pending')
          )
          or exists (
            select 1
            from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q1
            join integration_control.thriveevergreen_publisher_attempts_v2 a1
              on a1.attempt_id=q1.attempt_id
            where q1.release_id=v_candidate.release_id
              and q1.route_id=v_candidate.route_id
              and a1.exact_version_ref=v_candidate.exact_version_ref
              and a1.content_sha256=v_candidate.content_sha256
              and q1.dispatch_state in (
                'enqueue_pending','ready','leased','provider_written',
                'readback_verified','rollback_verified'
              )
          )
          into v_exact_publish_exists;
      else
        v_exact_publish_exists:=false;
      end if;
    end if;

    if v_window<>pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC')
       or extract(minute from pg_catalog.clock_timestamp())::smallint<>v_expected_minute
    then
      raise exception 'publisher_v2_post_candidate_lock_no_catch_up_or_stale_window';
    end if;

    if v_candidate_still_admitted is not true
       or v_exact_publish_exists is true then
      v_candidate_selected:=false;
    end if;
  end if;

  if v_candidate_selected is not true then
    v_snapshot:=jsonb_build_object(
      'contract','ct.snapshot.thriveevergreen-publisher.v2',
      'candidate_found',false,'decision','WORKING',
      'publication_decision','WORKING',
      'blockers',jsonb_build_array(
        case when v_exact_lock_contended is true
          then 'EXACT_CANDIDATE_LOCK_CONTENDED'
          when v_exact_publish_exists is true
          then 'EXACT_PUBLICATION_ALREADY_IN_FLIGHT_OR_VERIFIED'
          else 'NO_READY_ADMITTED_CANDIDATE_FOR_SLOT'
        end
      ),
      'no_delete_assertion',true,'money_movement_authorized',false
    );
    v_reason_code:=case when v_exact_lock_contended is true
      then 'EXACT_CANDIDATE_LOCK_CONTENDED'
      when v_exact_publish_exists is true
      then 'EXACT_PUBLICATION_ALREADY_IN_FLIGHT_OR_VERIFIED'
      else 'NO_READY_ADMITTED_CANDIDATE_FOR_SLOT'
    end;
    v_slot_result:=v_snapshot||jsonb_build_object(
      'governed_enqueue_state','not_invoked',
      'governed_enqueue_receipt_sha256',null,
      'governed_enqueue_readback_sha256',null,
      'governed_enqueue_attempted',false,
      'governed_enqueue_bridge_ok',null::boolean,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false
    );
    update integration_control.thriveevergreen_publisher_slots_v2
    set slot_state='completed_idle',economic_decision='WORKING',reason_code=v_reason_code,
        evidence_sha256=encode(extensions.digest(v_slot_result::text,'sha256'),'hex'),
        completed_at=clock_timestamp()
    where policy_id=v_policy.policy_id and window_start=v_window and slot_no=p_slot_no;
  else
    v_snapshot:=integration_control.thriveevergreen_publisher_gate_snapshot_v6(v_candidate.candidate_id);
    v_attempt_id:=gen_random_uuid();
    insert into integration_control.thriveevergreen_publisher_attempts_v2 (
      attempt_id,policy_id,window_start,slot_no,candidate_id,idempotency_key,
      exact_version_ref,content_sha256,economic_decision,attempt_state,
      gate_snapshot,gate_snapshot_sha256
    ) values (
      v_attempt_id,v_policy.policy_id,v_window,p_slot_no,v_candidate.candidate_id,
      'tev2:'||extract(epoch from v_window)::bigint::text||':'||p_slot_no::text||':'||v_candidate.candidate_id::text||':'||v_candidate.content_sha256,
      v_candidate.exact_version_ref,v_candidate.content_sha256,v_snapshot->>'decision',
      case when v_snapshot->>'decision'='ECAC' then 'gate_authorized' when v_snapshot->>'decision'='DENY' then 'denied' else 'working' end,
      v_snapshot,encode(extensions.digest(v_snapshot::text,'sha256'),'hex')
    );

    if v_snapshot->>'decision'='ECAC' then
      v_payload:=jsonb_build_object(
        'contract','ct.dispatch.thriveevergreen-publisher.v2',
        'attempt_id',v_attempt_id,'release_id',v_candidate.release_id,
        'route_id',v_candidate.route_id,'subject_ref',v_candidate.subject_ref,
        'exact_version_ref',v_candidate.exact_version_ref,
        'content_sha256',v_candidate.content_sha256,
        'economic_intent_sha256',v_candidate.economic_intent_sha256,
        'delete_allowed',false,'money_movement_allowed',false,'credential_return_allowed',false
      );
      insert into integration_control.thriveevergreen_publisher_dispatch_queue_v2 (
        attempt_id,release_id,route_id,dispatch_state,public_safe_payload,payload_sha256
      ) values (
        v_attempt_id,v_candidate.release_id,v_candidate.route_id,'enqueue_pending',v_payload,
        encode(extensions.digest(v_payload::text,'sha256'),'hex')
      ) returning dispatch_id into v_dispatch_id;

      v_bridge_attempted:=true;
      begin
        v_enqueue_receipt:=integration_control.enqueue_governed_site_publish(v_candidate.release_id);
        v_enqueue_state:=coalesce(v_enqueue_receipt->>'state','missing_state');
        v_enqueue_job_id:=case
          when coalesce(v_enqueue_receipt->>'job_id','')
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          then (v_enqueue_receipt->>'job_id')::uuid
          else null
        end;

        select encode(extensions.digest(jsonb_build_object(
          'job_id',j.job_id,'release_id',j.release_id,'route_id',j.route_id,
          'surface_id',j.surface_id,'adapter_id',j.adapter_id,'state',j.state,
          'exact_version_ref',j.exact_version_ref,'content_sha256',j.content_sha256
        )::text,'sha256'),'hex')
        into v_enqueue_readback_sha
        from integration_control.site_publish_jobs j
        where j.job_id=v_enqueue_job_id
          and j.release_id=v_candidate.release_id
          and j.route_id=v_candidate.route_id
          and j.exact_version_ref=v_candidate.exact_version_ref
          and j.content_sha256=v_candidate.content_sha256
          and j.state='queued';

        v_bridge_ok:=v_enqueue_state='queued'
          and v_enqueue_job_id is not null
          and v_enqueue_readback_sha is not null;
        if v_bridge_ok is not true then
          raise exception 'publisher_v2_governed_enqueue_exact_readback_failed';
        end if;
      exception when others then
        if v_enqueue_receipt is null then
          v_enqueue_receipt:=jsonb_build_object(
            'state','exception_failed','sqlstate',sqlstate,'provider_write_performed',false
          );
          v_enqueue_state:='exception_failed';
          v_enqueue_job_id:=null;
        end if;
        v_bridge_ok:=false;
        v_enqueue_readback_sha:=null;
      end;

      v_enqueue_state:=coalesce(v_enqueue_state,v_enqueue_receipt->>'state','missing_state');
      v_enqueue_receipt_sha:=encode(
        extensions.digest(coalesce(v_enqueue_receipt,'null'::jsonb)::text,'sha256'),'hex'
      );

      update integration_control.thriveevergreen_publisher_dispatch_queue_v2
      set dispatch_state=case when v_bridge_ok is true then 'ready' else 'failed' end,
          governed_publish_job_id=case when v_bridge_ok is true then v_enqueue_job_id else null end,
          governed_enqueue_state=case when v_bridge_ok is true then 'queued' else 'failed' end,
          governed_enqueue_returned_state=v_enqueue_state,
          governed_enqueue_returned_job_id=v_enqueue_job_id,
          governed_enqueue_receipt_sha256=v_enqueue_receipt_sha,
          governed_enqueue_readback_sha256=case when v_bridge_ok is true then v_enqueue_readback_sha else null end,
          governed_enqueue_observed_at=clock_timestamp(),updated_at=clock_timestamp()
      where dispatch_id=v_dispatch_id;
    end if;

    v_reason_code:=case
      when v_snapshot->>'decision'='ECAC' and v_bridge_ok is true then 'EXACT_GATES_PASS_QUEUED'
      when v_snapshot->>'decision'='ECAC' then 'GOVERNED_SITE_PUBLISH_ENQUEUE_FAILED'
      when v_snapshot->>'decision'='DENY' then 'EXACT_ECONOMIC_DENY'
      else 'EXACT_GATES_WORKING'
    end;
    v_slot_result:=v_snapshot||jsonb_build_object(
      'governed_enqueue_state',case
        when v_bridge_attempted is not true then 'not_invoked'
        when v_bridge_ok is true then 'queued'
        else 'failed'
      end,
      'governed_enqueue_receipt_sha256',v_enqueue_receipt_sha,
      'governed_enqueue_readback_sha256',v_enqueue_readback_sha,
      'governed_enqueue_attempted',v_bridge_attempted,
      'governed_enqueue_bridge_ok',v_bridge_ok,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false
    );
    update integration_control.thriveevergreen_publisher_slots_v2
    set slot_state=case when v_snapshot->>'decision'='ECAC' and v_bridge_ok is true then 'queued'
                        when v_snapshot->>'decision'='DENY' then 'completed_denied'
                        when v_snapshot->>'decision'='ECAC' then 'completed_failed'
                        else 'completed_working' end,
        candidate_id=v_candidate.candidate_id,attempt_id=v_attempt_id,
        economic_decision=v_snapshot->>'decision',reason_code=v_reason_code,
        evidence_sha256=encode(extensions.digest(v_slot_result::text,'sha256'),'hex'),
        completed_at=clock_timestamp()
    where policy_id=v_policy.policy_id and window_start=v_window and slot_no=p_slot_no;
  end if;

  v_results:=jsonb_build_array(v_slot_result);

  select count(*)::smallint into v_slot_count
  from integration_control.thriveevergreen_publisher_slots_v2
  where policy_id=v_policy.policy_id and window_start=v_window;

  select count(*)::smallint into v_attempt_count
  from integration_control.thriveevergreen_publisher_attempts_v2
  where policy_id=v_policy.policy_id and window_start=v_window;

  select count(*)::smallint into v_queued_count
  from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q
  join integration_control.thriveevergreen_publisher_attempts_v2 a on a.attempt_id=q.attempt_id
  where a.policy_id=v_policy.policy_id and a.window_start=v_window
    and q.governed_enqueue_state='queued'
    and q.dispatch_state in ('ready','leased','provider_written','readback_verified','rollback_verified');

  -- Count unique governed jobs, not dispatch/cycle rows. Every normalized
  -- six-stage receipt is bound through its dispatch to the exact release, route,
  -- version, content, certified adapter/provider object, and one verifier.
  -- No adapter ID is hardcoded: certified dynamic-feed and Brilliant Directories
  -- routes satisfy the same evidence contract.
  select count(distinct q.governed_publish_job_id)::smallint
    into v_verified_publication_count
  from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q
  join integration_control.thriveevergreen_publisher_attempts_v2 a
    on a.attempt_id=q.attempt_id
  join integration_control.thriveevergreen_publisher_candidates_v2 cand
    on cand.candidate_id=a.candidate_id
  join integration_control.pentagreen_six_stage_publication_cycles_v1 cy
    on cy.dispatch_id=q.dispatch_id
   and cy.attempt_id=a.attempt_id
   and cy.candidate_id=cand.candidate_id
  join integration_control.site_publish_routes r
    on r.route_id=q.route_id
   and r.route_id=cand.route_id
   and r.route_id=cy.route_id
   and r.surface_id=cy.surface_id
  join integration_control.site_provider_adapters pa
    on pa.adapter_id=r.adapter_id
  where a.policy_id=v_policy.policy_id
    and a.window_start=v_window
    and q.governed_enqueue_state='queued'
    and q.governed_publish_job_id is not null
    and q.release_id=cand.release_id
    and q.release_id=cy.release_id
    and q.governed_publish_job_id=cy.governed_publish_job_id
    and a.policy_id=cy.policy_id
    and a.window_start=cy.window_start
    and a.slot_no=cy.slot_no
    and a.exact_version_ref=cand.exact_version_ref
    and a.exact_version_ref=cy.exact_version_ref
    and a.content_sha256=cand.content_sha256
    and a.content_sha256=cy.content_sha256
    and cy.subject_type=cand.subject_type
    and cy.subject_ref=cand.subject_ref
    and cy.phase='final_verified'
    and cy.cycle_state='pass'
    and cy.completed_at is not null
    and cy.evidence_sha256~'^[0-9a-f]{64}$'
    and cy.provider_object_ref is not null
    and cy.rollback_ref is not null
    and r.route_state='active'
    and r.feed_consumer_state='verified'
    and r.auto_publish_if_release_pass is true
    and r.require_read_after_write is true
    and r.require_rollback_ref is true
    and pa.state='certified'
    and pa.supports_rollback is true
    and pa.supports_read_after_write is true
    and pa.read_capability_state='pass'
    and pa.write_canary_state='pass'
    and pa.rollback_canary_state='pass'
    and pa.read_after_write_state='pass'
    and 1=(
      select count(distinct pr0.provider_system)
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr0
      where pr0.dispatch_id=q.dispatch_id
        and pr0.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr0.result_state='pass'
    )
    and 6=(
      select count(*)
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr_all
      where pr_all.dispatch_id=q.dispatch_id
        and pr_all.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr_all.result_state='pass'
    )
    and (
      select count(*)=6
             and count(distinct pr.receipt_stage)=6
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr
      where pr.dispatch_id=q.dispatch_id
        and pr.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr.result_state='pass'
        and nullif(pg_catalog.btrim(pr.provider_system),'') is not null
        and pr.provider_system=pa.provider_system
        and pr.provider_object_ref=cy.provider_object_ref
        and pr.rollback_ref=cy.rollback_ref
        and pr.exact_content_sha256=cy.content_sha256
        and pr.asserted_by_subject_id=v_policy.service_principal_id
        and pr.secret_material_present is false
        and pg_catalog.right(
          pr.provider_readback_ref,
          pg_catalog.length(':'||cy.cycle_id::text||':'||pr.receipt_stage)
        )=':'||cy.cycle_id::text||':'||pr.receipt_stage
        and (
          (
            pr.receipt_stage in ('prestate','readback','final_readback')
            and pr.metadata->>'cycle_id'=cy.cycle_id::text
            and pr.metadata->>'stage'=pr.receipt_stage
            and pr.metadata->>'state'='pass'
            and pr.metadata->>'surface_id'=cy.surface_id
            and pr.metadata->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->>'content_sha256'=cy.content_sha256
            and pr.metadata->>'provider_system'=pa.provider_system
          )
          or (
            pr.receipt_stage in ('write','reapply')
            and pr.metadata->>'site_job_id'=cy.governed_publish_job_id::text
            and pr.metadata->>'rollback_ref'=cy.rollback_ref
            and pr.metadata->'projection'->>'release_id'=cy.release_id::text
            and pr.metadata->'projection'->>'surface_id'=cy.surface_id
            and pr.metadata->'projection'->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->'projection'->>'content_sha256'=cy.content_sha256
          )
          or (
            pr.receipt_stage='rollback'
            and pr.metadata->'result'->>'job_id'=cy.governed_publish_job_id::text
            and pr.metadata->>'rollback_ref'=cy.rollback_ref
            and pr.metadata->'external_readback'->>'cycle_id'=cy.cycle_id::text
            and pr.metadata->'external_readback'->>'stage'='rollback'
            and pr.metadata->'external_readback'->>'state'='pass'
            and pr.metadata->'external_readback'->>'surface_id'=cy.surface_id
            and pr.metadata->'external_readback'->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->'external_readback'->>'content_sha256'=cy.content_sha256
            and pr.metadata->'external_readback'->>'provider_system'=pa.provider_system
          )
        )
        and case
          when pr.receipt_stage in (
            'prestate','readback','rollback','final_readback'
          ) then
            pr.independent_verifier_subject_id is not null
            and pr.independent_verifier_subject_id<>pr.asserted_by_subject_id
            and pr.independent_verifier_subject_id=(
              select pg_catalog.min(final_pr.independent_verifier_subject_id)
              from integration_control.thriveevergreen_publisher_provider_receipts_v2 final_pr
              where final_pr.dispatch_id=q.dispatch_id
                and final_pr.receipt_stage='final_readback'
                and final_pr.result_state='pass'
              having count(distinct final_pr.independent_verifier_subject_id)=1
            )
          else
            pr.independent_verifier_subject_id is null
        end
    );

  select coalesce(jsonb_agg(jsonb_build_object(
    'slot_no',s.slot_no,'scheduled_minute',s.scheduled_minute,
    'economic_decision',s.economic_decision,'reason_code',s.reason_code,
    'evidence_sha256',s.evidence_sha256
  ) order by s.slot_no),'[]'::jsonb)
  into v_slots_evidence
  from integration_control.thriveevergreen_publisher_slots_v2 s
  where s.policy_id=v_policy.policy_id and s.window_start=v_window;

  v_evidence_sha:=encode(extensions.digest(jsonb_build_object(
    'policy_id',v_policy.policy_id,'window_start',v_window,'slot_no',p_slot_no,
    'slot_count',v_slot_count,'attempt_count',v_attempt_count,
    'queued_count',v_queued_count,'verified_publication_count',v_verified_publication_count,
    'latest_result',v_slot_result,'ordered_slot_evidence',v_slots_evidence
  )::text,'sha256'),'hex');

  update integration_control.thriveevergreen_publisher_windows_v2
  set state=case when v_slot_count=10 then 'completed' else 'running' end,
      slot_count=v_slot_count,attempt_count=v_attempt_count,queued_count=v_queued_count,
      verified_publication_count=v_verified_publication_count,evidence_sha256=v_evidence_sha,
      completed_at=case when v_slot_count=10 then clock_timestamp() else null end
  where policy_id=v_policy.policy_id and window_start=v_window;

  v_dail:=chlom_runtime.append_or_queue_dail_event_v1(
    'ct.dail.thriveevergreen.publisher.v3:'||v_window::text||':'||p_slot_no::text||':'||v_evidence_sha,
    'THRIVEEVERGREEN_AUTONOMOUS_PUBLISHER_SUBSLOT_V2','publisher_subslot',
    v_policy.policy_id,
    jsonb_build_object(
      'window_start',v_window,'slot_no',p_slot_no,'scheduled_minute',v_expected_minute,
      'slot_count',v_slot_count,'candidate_attempt_count',v_attempt_count,
      'queued_count',v_queued_count,'verified_publication_count',v_verified_publication_count,
      'governed_enqueue_state',v_slot_result->>'governed_enqueue_state',
      'governed_enqueue_receipt_sha256',v_enqueue_receipt_sha,
      'governed_enqueue_readback_sha256',v_enqueue_readback_sha,
      'governed_enqueue_attempted',v_bridge_attempted,
      'governed_enqueue_bridge_ok',v_bridge_ok,
      'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
      'downstream_execution_attested',false,
      'maximum_attempts_per_hour',10,'maximum_publications_per_hour',10,
      'hold_consumes_attempt_slot',false,'catch_up_burst_allowed',false,
      'no_delete_assertion',true,'no_secret_assertion',true,
      'money_movement_performed',false,'evidence_sha256',v_evidence_sha
    ),
    v_policy.service_principal_id,null,v_policy.service_principal_id,'2.0.0',
    'ct.publisher-subslot.v2.'||v_window::text||'.'||p_slot_no::text,null,
    v_policy.founder_directive_ref,null,'restricted',90
  );

  return jsonb_build_object(
    'contract','ct.thriveevergreen.autonomous-publisher.v2','run_scope','production',
    'run_state','completed','slot_no',p_slot_no,'scheduled_minute',v_expected_minute,
    'hour_slot_consumed',true,'slot_count',v_slot_count,
    'candidate_attempt_count',v_attempt_count,'queued_count',v_queued_count,
    'publication_count',v_verified_publication_count,'evidence_sha256',v_evidence_sha,
    'governed_enqueue_state',v_slot_result->>'governed_enqueue_state',
    'governed_enqueue_receipt_sha256',v_enqueue_receipt_sha,
    'governed_enqueue_readback_sha256',v_enqueue_readback_sha,
    'governed_enqueue_attempted',v_bridge_attempted,
    'governed_enqueue_bridge_ok',v_bridge_ok,
    'effect_attestation_scope','enqueue_authorization_and_exact_queued_job_readback_only',
    'downstream_execution_attested',false,
    'dail_event_id',v_dail->>'event_id','dail_event_hash',v_dail->>'event_hash',
    'candidate_snapshots',v_results
  );
end
$function$;

CREATE OR REPLACE FUNCTION public.thriveevergreen_autonomous_publisher_status_v2()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control', 'chlom_runtime'
AS $function$
  select jsonb_build_object(
    'contract','ct.status.thriveevergreen-autonomous-publisher.v2',
    'semantic_version',p.semantic_version,
    'component_runtime_state',case
      when p.policy_state='active' and p.runtime_mode='production_observer'
        then 'production_observer_scheduled_publication_hold'
      when p.policy_state='active' and p.runtime_mode='production_write' and p.production_effects_enabled
        then 'production_publisher_active'
      else 'paused_or_staged'
    end,
    'runtime_mode',p.runtime_mode,'production_effects_enabled',p.production_effects_enabled,
    'publication_activation_state',p.publication_activation_state,
    'requested_candidate_attempt_target_per_hour',p.target_candidate_attempts_per_hour,
    'requested_publication_target_per_hour',p.maximum_publications_per_hour,
    'effective_publication_target_per_hour',case
      when p.policy_state='active' and p.runtime_mode='production_write'
        and p.production_effects_enabled and p.publication_activation_state='ECAC'
      then p.maximum_publications_per_hour else 0 end,
    'wrapper_security_state',p.wrapper_security_state,
    'provider_dispatch_certification_state',p.provider_dispatch_certification_state,
    'drive_hierarchy_state',d.hierarchy_readback_state,
    'drive_server_dispatch_state',d.server_dispatch_state,
    'stripe_account_state',s.account_readback_state,
    'stripe_product_state',s.product_readback_state,'stripe_price_state',s.price_readback_state,
    'stripe_tax_state',s.tax_state,'stripe_webhook_state',s.webhook_state,
    'stripe_entitlement_state',s.entitlement_state,'stripe_live_mutation_gate',s.live_mutation_gate,
    'candidate_count',(select count(*) from integration_control.thriveevergreen_publisher_candidates_v2),
    'admitted_candidate_count',(select count(*) from integration_control.thriveevergreen_publisher_candidates_v2 where candidate_state='admitted'),
    'verified_publication_count',(
      select count(distinct q.governed_publish_job_id)
      from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q
      join integration_control.thriveevergreen_publisher_attempts_v2 a
        on a.attempt_id=q.attempt_id
      join integration_control.thriveevergreen_publisher_candidates_v2 cand
        on cand.candidate_id=a.candidate_id
      join integration_control.pentagreen_six_stage_publication_cycles_v1 cy
        on cy.dispatch_id=q.dispatch_id
       and cy.attempt_id=a.attempt_id
       and cy.candidate_id=cand.candidate_id
      join integration_control.site_publish_routes r
        on r.route_id=q.route_id
       and r.route_id=cand.route_id
       and r.route_id=cy.route_id
       and r.surface_id=cy.surface_id
      join integration_control.site_provider_adapters pa
        on pa.adapter_id=r.adapter_id
      where a.policy_id=p.policy_id
        and q.governed_enqueue_state='queued'
        and q.governed_publish_job_id is not null
        and q.release_id=cand.release_id
        and q.release_id=cy.release_id
        and q.governed_publish_job_id=cy.governed_publish_job_id
        and a.policy_id=cy.policy_id
        and a.window_start=cy.window_start
        and a.slot_no=cy.slot_no
        and a.exact_version_ref=cand.exact_version_ref
        and a.exact_version_ref=cy.exact_version_ref
        and a.content_sha256=cand.content_sha256
        and a.content_sha256=cy.content_sha256
        and cy.subject_type=cand.subject_type
        and cy.subject_ref=cand.subject_ref
        and cy.phase='final_verified'
        and cy.cycle_state='pass'
        and cy.completed_at is not null
        and cy.evidence_sha256~'^[0-9a-f]{64}$'
        and cy.provider_object_ref is not null
        and cy.rollback_ref is not null
        and r.route_state='active'
        and r.feed_consumer_state='verified'
        and r.auto_publish_if_release_pass is true
        and r.require_read_after_write is true
        and r.require_rollback_ref is true
        and pa.state='certified'
        and pa.supports_rollback is true
        and pa.supports_read_after_write is true
        and pa.read_capability_state='pass'
        and pa.write_canary_state='pass'
        and pa.rollback_canary_state='pass'
        and pa.read_after_write_state='pass'
        and 1=(
          select count(distinct pr0.provider_system)
          from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr0
          where pr0.dispatch_id=q.dispatch_id
            and pr0.receipt_stage in (
              'prestate','write','readback','rollback','reapply','final_readback'
            )
            and pr0.result_state='pass'
        )
        and 6=(
          select count(*)
          from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr_all
          where pr_all.dispatch_id=q.dispatch_id
            and pr_all.receipt_stage in (
              'prestate','write','readback','rollback','reapply','final_readback'
            )
            and pr_all.result_state='pass'
        )
        and (
          select count(*)=6
                 and count(distinct pr.receipt_stage)=6
          from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr
          where pr.dispatch_id=q.dispatch_id
            and pr.receipt_stage in (
              'prestate','write','readback','rollback','reapply','final_readback'
            )
            and pr.result_state='pass'
            and nullif(pg_catalog.btrim(pr.provider_system),'') is not null
            and pr.provider_system=pa.provider_system
            and pr.provider_object_ref=cy.provider_object_ref
            and pr.rollback_ref=cy.rollback_ref
            and pr.exact_content_sha256=cy.content_sha256
            and pr.asserted_by_subject_id=p.service_principal_id
            and pr.secret_material_present is false
            and pg_catalog.right(
              pr.provider_readback_ref,
              pg_catalog.length(':'||cy.cycle_id::text||':'||pr.receipt_stage)
            )=':'||cy.cycle_id::text||':'||pr.receipt_stage
            and (
              (
                pr.receipt_stage in ('prestate','readback','final_readback')
                and pr.metadata->>'cycle_id'=cy.cycle_id::text
                and pr.metadata->>'stage'=pr.receipt_stage
                and pr.metadata->>'state'='pass'
                and pr.metadata->>'surface_id'=cy.surface_id
                and pr.metadata->>'exact_version_ref'=cy.exact_version_ref
                and pr.metadata->>'content_sha256'=cy.content_sha256
                and pr.metadata->>'provider_system'=pa.provider_system
              )
              or (
                pr.receipt_stage in ('write','reapply')
                and pr.metadata->>'site_job_id'=cy.governed_publish_job_id::text
                and pr.metadata->>'rollback_ref'=cy.rollback_ref
                and pr.metadata->'projection'->>'release_id'=cy.release_id::text
                and pr.metadata->'projection'->>'surface_id'=cy.surface_id
                and pr.metadata->'projection'->>'exact_version_ref'=cy.exact_version_ref
                and pr.metadata->'projection'->>'content_sha256'=cy.content_sha256
              )
              or (
                pr.receipt_stage='rollback'
                and pr.metadata->'result'->>'job_id'=cy.governed_publish_job_id::text
                and pr.metadata->>'rollback_ref'=cy.rollback_ref
                and pr.metadata->'external_readback'->>'cycle_id'=cy.cycle_id::text
                and pr.metadata->'external_readback'->>'stage'='rollback'
                and pr.metadata->'external_readback'->>'state'='pass'
                and pr.metadata->'external_readback'->>'surface_id'=cy.surface_id
                and pr.metadata->'external_readback'->>'exact_version_ref'=cy.exact_version_ref
                and pr.metadata->'external_readback'->>'content_sha256'=cy.content_sha256
                and pr.metadata->'external_readback'->>'provider_system'=pa.provider_system
              )
            )
            and case
              when pr.receipt_stage in (
                'prestate','readback','rollback','final_readback'
              ) then
                pr.independent_verifier_subject_id is not null
                and pr.independent_verifier_subject_id<>pr.asserted_by_subject_id
                and pr.independent_verifier_subject_id=(
                  select pg_catalog.min(final_pr.independent_verifier_subject_id)
                  from integration_control.thriveevergreen_publisher_provider_receipts_v2 final_pr
                  where final_pr.dispatch_id=q.dispatch_id
                    and final_pr.receipt_stage='final_readback'
                    and final_pr.result_state='pass'
                  having count(distinct final_pr.independent_verifier_subject_id)=1
                )
              else
                pr.independent_verifier_subject_id is null
            end
        )
    ),
    'no_delete',true,'no_money_movement',true,'d3_human_reserved',true
  )
  from integration_control.thriveevergreen_autonomous_publisher_policy_v2 p
  join integration_control.thriveevergreen_publisher_drive_custody_v2 d on d.binding_id=p.drive_binding_id
  join integration_control.thriveevergreen_publisher_stripe_binding_v2 s on s.binding_id=p.stripe_binding_id
  where p.policy_id='ct.policy.thriveevergreen-autonomous-publisher.v2';
$function$;

CREATE OR REPLACE FUNCTION integration_control.pentagreen_six_stage_publication_final_v1(p_cycle_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control', 'extensions'
 SET "TimeZone" TO 'UTC'
AS $function$
declare
  x integration_control.pentagreen_six_stage_publication_cycles_v1%rowtype;
  v_obs jsonb;
  v_ref text;
  v_stage_count integer:=0;
  v_pass_count integer:=0;
  v_final_independent boolean:=false;
  v_evidence jsonb;
  v_sha text;
  v_verified_publication_count smallint:=0;
  v_current_cycle_normalized boolean:=false;
  v_service_principal_id text;
  v_now timestamptz;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select * into x from integration_control.pentagreen_six_stage_publication_cycles_v1
  where cycle_id=p_cycle_id for update;
  if not found or x.phase<>'reapply_committed' then raise exception 'six_stage_cycle_not_at_reapply'; end if;
  -- Serialize every finalizer and publisher aggregation for this exact window.
  -- UTC matches run_thriveevergreen_autonomous_publisher_v2's function setting.
  if not pg_try_advisory_xact_lock(hashtext(x.policy_id),hashtext(x.window_start::text)) then
    raise exception 'six_stage_window_lock_contended';
  end if;
  select service_principal_id into strict v_service_principal_id
  from integration_control.thriveevergreen_autonomous_publisher_policy_v2
  where policy_id=x.policy_id;
  v_now:=clock_timestamp();
  v_obs:=integration_control.pentagreen_dynamic_feed_external_observation_v1(
    x.cycle_id,'final_readback',x.route_id,x.subject_type,x.subject_ref,
    x.exact_version_ref,x.content_sha256,true
  );
  if v_obs->>'state'<>'pass' then raise exception 'external_final_readback_failed'; end if;
  v_ref:='ct.provider.dynamic-feed.six-stage:'||x.cycle_id::text||':final_readback';
  insert into integration_control.thriveevergreen_publisher_provider_receipts_v2(
    dispatch_id,receipt_stage,provider_system,provider_object_ref,
    provider_version_before,provider_version_after,rollback_ref,request_sha256,response_sha256,
    exact_content_sha256,result_state,provider_readback_ref,asserted_by_subject_id,
    independent_verifier_subject_id,secret_material_present,observed_at,metadata
  ) values(
    x.dispatch_id,'final_readback','supabase_edge_dynamic_feed',x.provider_object_ref,
    coalesce(x.rollback_observation#>>'{external_readback,generated_at}','withdrawn'),
    x.exact_version_ref,x.rollback_ref,v_obs->>'request_sha256',v_obs->>'response_sha256',
    x.content_sha256,'pass',v_ref,v_service_principal_id,
    'ct.chlom.agent.release-certifier',false,v_now,
    v_obs||jsonb_build_object('independent_verification',true,'final_provider_state','published')
  );

  select count(distinct receipt_stage)::integer,
         count(*) filter(where result_state='pass')::integer,
         bool_or(receipt_stage='final_readback' and result_state='pass'
                 and independent_verifier_subject_id is not null
                 and independent_verifier_subject_id<>asserted_by_subject_id)
    into v_stage_count,v_pass_count,v_final_independent
  from integration_control.thriveevergreen_publisher_provider_receipts_v2
  where dispatch_id=x.dispatch_id
    and receipt_stage in ('prestate','write','readback','rollback','reapply','final_readback');
  if v_stage_count<>6 or v_pass_count<>6 or not v_final_independent then
    raise exception 'six_stage_receipt_acceptance_failed:%:%:%',v_stage_count,v_pass_count,v_final_independent;
  end if;

  v_evidence:=jsonb_build_object(
    'contract','ct.pentagreen.six-stage-publication-proof.v1',
    'cycle_id',x.cycle_id,'candidate_id',x.candidate_id,'release_id',x.release_id,
    'job_id',x.governed_publish_job_id,'attempt_id',x.attempt_id,'dispatch_id',x.dispatch_id,
    'surface_id',x.surface_id,'route_id',x.route_id,
    'subject_type',x.subject_type,'subject_ref',x.subject_ref,
    'exact_version_ref',x.exact_version_ref,'content_sha256',x.content_sha256,
    'receipt_stages',jsonb_build_array('prestate','write','readback','rollback','reapply','final_readback'),
    'stage_count',v_stage_count,'pass_count',v_pass_count,
    'final_independent_readback',v_final_independent,
    'prestate',x.prestate_observation,'write',x.write_observation,
    'readback',x.readback_observation,'rollback',x.rollback_observation,
    'reapply',x.reapply_observation,'final_readback',v_obs,
    'final_state','published','secret_material_present',false,
    'money_movement',false,'completed_at',v_now
  );
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  update integration_control.thriveevergreen_publisher_dispatch_queue_v2
  set dispatch_state='readback_verified',updated_at=v_now where dispatch_id=x.dispatch_id;
  update integration_control.pentagreen_six_stage_publication_cycles_v1
  set phase='final_verified',cycle_state='pass',final_observation=v_obs,
      evidence_sha256=v_sha,updated_at=v_now,completed_at=v_now
  where cycle_id=x.cycle_id;
  select count(distinct q.governed_publish_job_id)::smallint,
         coalesce(pg_catalog.bool_or(cy.cycle_id=x.cycle_id),false)
    into v_verified_publication_count,v_current_cycle_normalized
  from integration_control.thriveevergreen_publisher_dispatch_queue_v2 q
  join integration_control.thriveevergreen_publisher_attempts_v2 a
    on a.attempt_id=q.attempt_id
  join integration_control.thriveevergreen_publisher_candidates_v2 cand
    on cand.candidate_id=a.candidate_id
  join integration_control.pentagreen_six_stage_publication_cycles_v1 cy
    on cy.dispatch_id=q.dispatch_id
   and cy.attempt_id=a.attempt_id
   and cy.candidate_id=cand.candidate_id
  join integration_control.site_publish_routes r
    on r.route_id=q.route_id
   and r.route_id=cand.route_id
   and r.route_id=cy.route_id
   and r.surface_id=cy.surface_id
  join integration_control.site_provider_adapters pa
    on pa.adapter_id=r.adapter_id
  where a.policy_id=x.policy_id
    and a.window_start=x.window_start
    and q.governed_enqueue_state='queued'
    and q.governed_publish_job_id is not null
    and q.release_id=cand.release_id
    and q.release_id=cy.release_id
    and q.governed_publish_job_id=cy.governed_publish_job_id
    and a.policy_id=cy.policy_id
    and a.window_start=cy.window_start
    and a.slot_no=cy.slot_no
    and a.exact_version_ref=cand.exact_version_ref
    and a.exact_version_ref=cy.exact_version_ref
    and a.content_sha256=cand.content_sha256
    and a.content_sha256=cy.content_sha256
    and cy.subject_type=cand.subject_type
    and cy.subject_ref=cand.subject_ref
    and cy.phase='final_verified'
    and cy.cycle_state='pass'
    and cy.completed_at is not null
    and cy.evidence_sha256~'^[0-9a-f]{64}$'
    and cy.provider_object_ref is not null
    and cy.rollback_ref is not null
    and r.route_state='active'
    and r.feed_consumer_state='verified'
    and r.auto_publish_if_release_pass is true
    and r.require_read_after_write is true
    and r.require_rollback_ref is true
    and pa.state='certified'
    and pa.supports_rollback is true
    and pa.supports_read_after_write is true
    and pa.read_capability_state='pass'
    and pa.write_canary_state='pass'
    and pa.rollback_canary_state='pass'
    and pa.read_after_write_state='pass'
    and 1=(
      select count(distinct pr0.provider_system)
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr0
      where pr0.dispatch_id=q.dispatch_id
        and pr0.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr0.result_state='pass'
    )
    and 6=(
      select count(*)
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr_all
      where pr_all.dispatch_id=q.dispatch_id
        and pr_all.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr_all.result_state='pass'
    )
    and (
      select count(*)=6
             and count(distinct pr.receipt_stage)=6
      from integration_control.thriveevergreen_publisher_provider_receipts_v2 pr
      where pr.dispatch_id=q.dispatch_id
        and pr.receipt_stage in (
          'prestate','write','readback','rollback','reapply','final_readback'
        )
        and pr.result_state='pass'
        and nullif(pg_catalog.btrim(pr.provider_system),'') is not null
        and pr.provider_system=pa.provider_system
        and pr.provider_object_ref=cy.provider_object_ref
        and pr.rollback_ref=cy.rollback_ref
        and pr.exact_content_sha256=cy.content_sha256
        and pr.asserted_by_subject_id=v_service_principal_id
        and pr.secret_material_present is false
        and pg_catalog.right(
          pr.provider_readback_ref,
          pg_catalog.length(':'||cy.cycle_id::text||':'||pr.receipt_stage)
        )=':'||cy.cycle_id::text||':'||pr.receipt_stage
        and (
          (
            pr.receipt_stage in ('prestate','readback','final_readback')
            and pr.metadata->>'cycle_id'=cy.cycle_id::text
            and pr.metadata->>'stage'=pr.receipt_stage
            and pr.metadata->>'state'='pass'
            and pr.metadata->>'surface_id'=cy.surface_id
            and pr.metadata->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->>'content_sha256'=cy.content_sha256
            and pr.metadata->>'provider_system'=pa.provider_system
          )
          or (
            pr.receipt_stage in ('write','reapply')
            and pr.metadata->>'site_job_id'=cy.governed_publish_job_id::text
            and pr.metadata->>'rollback_ref'=cy.rollback_ref
            and pr.metadata->'projection'->>'release_id'=cy.release_id::text
            and pr.metadata->'projection'->>'surface_id'=cy.surface_id
            and pr.metadata->'projection'->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->'projection'->>'content_sha256'=cy.content_sha256
          )
          or (
            pr.receipt_stage='rollback'
            and pr.metadata->'result'->>'job_id'=cy.governed_publish_job_id::text
            and pr.metadata->>'rollback_ref'=cy.rollback_ref
            and pr.metadata->'external_readback'->>'cycle_id'=cy.cycle_id::text
            and pr.metadata->'external_readback'->>'stage'='rollback'
            and pr.metadata->'external_readback'->>'state'='pass'
            and pr.metadata->'external_readback'->>'surface_id'=cy.surface_id
            and pr.metadata->'external_readback'->>'exact_version_ref'=cy.exact_version_ref
            and pr.metadata->'external_readback'->>'content_sha256'=cy.content_sha256
            and pr.metadata->'external_readback'->>'provider_system'=pa.provider_system
          )
        )
        and case
          when pr.receipt_stage in (
            'prestate','readback','rollback','final_readback'
          ) then
            pr.independent_verifier_subject_id is not null
            and pr.independent_verifier_subject_id<>pr.asserted_by_subject_id
            and pr.independent_verifier_subject_id=(
              select pg_catalog.min(final_pr.independent_verifier_subject_id)
              from integration_control.thriveevergreen_publisher_provider_receipts_v2 final_pr
              where final_pr.dispatch_id=q.dispatch_id
                and final_pr.receipt_stage='final_readback'
                and final_pr.result_state='pass'
              having count(distinct final_pr.independent_verifier_subject_id)=1
            )
          else
            pr.independent_verifier_subject_id is null
        end
    );

  if v_current_cycle_normalized is not true then
    raise exception 'six_stage_normalized_proof_failed';
  end if;

  update integration_control.thriveevergreen_publisher_windows_v2
  set state='completed',verified_publication_count=v_verified_publication_count,evidence_sha256=v_sha,
      completed_at=v_now where policy_id=x.policy_id and window_start=x.window_start;
  update integration_control.thriveevergreen_publisher_slots_v2
  set slot_state='completed_verified',reason_code='SIX_STAGE_PROVIDER_PROOF_PASS',
      evidence_sha256=v_sha,completed_at=v_now
  where policy_id=x.policy_id and window_start=x.window_start and slot_no=x.slot_no;
  update integration_control.thriveevergreen_publisher_candidates_v2
  set candidate_state='published',updated_at=v_now,
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'six_stage_publication_proof',jsonb_build_object(
          'cycle_id',x.cycle_id,'dispatch_id',x.dispatch_id,'evidence_sha256',v_sha,
          'stage_count',6,'final_independent_readback',true,'verified_at',v_now
        )
      )
  where candidate_id=x.candidate_id;
  return jsonb_build_object(
    'state','PASS','cycle_id',x.cycle_id,'candidate_id',x.candidate_id,
    'release_id',x.release_id,'job_id',x.governed_publish_job_id,
    'dispatch_id',x.dispatch_id,'receipt_stage_count',v_stage_count,
    'receipt_pass_count',v_pass_count,'final_independent_readback',v_final_independent,
    'exact_version_ref',x.exact_version_ref,'content_sha256',x.content_sha256,
    'public_surface',x.surface_id,'evidence_sha256',v_sha,'final_state','published'
  );
end;
$function$;

alter function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) owner to postgres;
alter function public.thriveevergreen_autonomous_publisher_status_v2() owner to postgres;
alter function integration_control.pentagreen_six_stage_publication_final_v1(uuid) owner to postgres;

-- CREATE OR REPLACE retains ACLs. Revoke PUBLIC and every catalog-discovered
-- non-owner/non-service direct grantee, including custom roles.
do $acl$
declare
  v_fn record;
  v_signature text;
  v_role name;
  v_count integer:=0;
begin
  for v_fn in
    select p.oid,p.proowner,n.nspname,p.proname,
           pg_catalog.format(
             '%I.%I(%s)',n.nspname,p.proname,
             pg_catalog.oidvectortypes(p.proargtypes)
           ) as signature
    from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid=p.pronamespace
    where (
      n.nspname='integration_control'
      and p.proname='run_thriveevergreen_autonomous_publisher_v2'
      and pg_catalog.pg_get_function_identity_arguments(p.oid)=
        'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint'
    ) or (
      n.nspname='public'
      and p.proname='thriveevergreen_autonomous_publisher_status_v2'
      and pg_catalog.pg_get_function_identity_arguments(p.oid)=''
    ) or (
      n.nspname='integration_control'
      and p.proname='pentagreen_six_stage_publication_final_v1'
      and pg_catalog.pg_get_function_identity_arguments(p.oid)='p_cycle_id uuid'
    )
  loop
    v_count:=v_count+1;
    v_signature:=v_fn.signature;
    execute 'revoke all privileges on function '||v_signature||' from public';

    for v_role in
      select distinct r.rolname
      from pg_catalog.pg_proc p
      cross join lateral pg_catalog.aclexplode(
        coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
      ) acl
      join pg_catalog.pg_roles r on r.oid=acl.grantee
      where p.oid=v_fn.oid
        and acl.grantee<>v_fn.proowner
        and acl.grantee<>pg_catalog.to_regrole('service_role')::oid
    loop
      execute pg_catalog.format(
        'revoke all privileges on function %s from %I',v_signature,v_role
      );
    end loop;

    execute 'grant execute on function '||v_signature||' to postgres, service_role';
  end loop;

  if v_count<>3 then
    raise exception 'publisher_truthful_bridge_state_v1_acl_target_count:%',v_count;
  end if;
end;
$acl$;

comment on function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) is
'Publisher v2 selection/idempotency and truthful enqueue telemetry patch 2026-09-08. governed_enqueue_bridge_ok attests only enqueue authorization plus exact queued-job readback; it does not attest downstream governed-handler execution, provider write, publication, fulfilment, or money movement.';

comment on function public.thriveevergreen_autonomous_publisher_status_v2() is
'Publisher v2 public status with verified publications counted once per exact governed job under normalized six-stage route/provider/verifier proof.';

comment on function integration_control.pentagreen_six_stage_publication_final_v1(uuid) is
'Finalizes exact six-stage publication evidence under the publisher policy/window lock and recomputes the truthful distinct governed-job window count.';

do $tests$
declare
  v_oid oid;
  v_def text;
  v_acl_ok boolean;
  v_companion_contracts_ok boolean;
  v_dependencies_ok boolean;
  v_cron_ok boolean;
  v_rls_ok boolean;
begin
  select p.oid,pg_catalog.pg_get_functiondef(p.oid)
    into v_oid,v_def
  from pg_catalog.pg_proc p
  join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='run_thriveevergreen_autonomous_publisher_v2'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)=
      'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint'
    and p.prosecdef
    and p.provolatile='v'
    and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
    and p.proconfig=array[
      'search_path=pg_catalog, integration_control, developer_commerce, chlom_runtime, extensions',
      'TimeZone=UTC'
    ]::text[];

  if v_oid is null then
    raise exception 'publisher_truthful_bridge_state_v1_function_contract_failed';
  end if;

  if pg_catalog.encode(
       extensions.digest(pg_catalog.convert_to(v_def,'UTF8'),'sha256'),
       'hex'
     )<>'60649d737d5b1dc1b08b67c3b81a837bad68702b254e1277c3280cbd7a722158' then
    raise exception 'publisher_truthful_bridge_state_v1_unexpected_postimage';
  end if;

  if pg_catalog.strpos(v_def,'publisher_v2_production_session_identity_invalid')=0
     or pg_catalog.strpos(v_def,'PUBLISHER_PRODUCTION_WRITE_EFFECTS_REQUIRED')=0
     or pg_catalog.strpos(v_def,'EXACT_PUBLICATION_ALREADY_IN_FLIGHT_OR_VERIFIED')=0
     or pg_catalog.strpos(v_def,'publisher_v2_candidate_lock_fence')=0
     or pg_catalog.strpos(v_def,'for update nowait')=0
     or pg_catalog.strpos(v_def,'publisher_v2_post_candidate_lock_no_catch_up_or_stale_window')=0
     or pg_catalog.strpos(v_def,'''enqueue_pending'',''ready'',''leased'',''provider_written''')=0
     or pg_catalog.strpos(v_def,'count(distinct q.governed_publish_job_id)')=0
     or pg_catalog.strpos(v_def,'site_provider_adapters pa')=0
     or pg_catalog.strpos(v_def,'pa.adapter_id=r.adapter_id')=0
     or pg_catalog.strpos(v_def,'''ct.adapter.dynamic-feed.v1''')>0
     or pg_catalog.strpos(v_def,'''supabase_edge_dynamic_feed''')>0
     or pg_catalog.strpos(v_def,'governed_enqueue_attempted')=0
     or pg_catalog.strpos(v_def,'downstream_execution_attested')=0
     or pg_catalog.strpos(v_def,'publisher_v2_production_session_identity_invalid')
        > pg_catalog.strpos(v_def,'insert into integration_control.thriveevergreen_publisher_windows_v2')
     or pg_catalog.strpos(v_def,'PUBLISHER_PRODUCTION_WRITE_EFFECTS_REQUIRED')
        > pg_catalog.strpos(v_def,'pg_try_advisory_xact_lock') then
    raise exception 'publisher_truthful_bridge_state_v1_semantic_marker_failed';
  end if;

  with expected(nspname,proname,identity_args,expected_sha,expected_volatility,expected_config) as (
    values
      (
        'public',
        'thriveevergreen_autonomous_publisher_status_v2',
        '',
        'd20a2869087b63a3c2a335c5085adba64f6ed6ccb4548a31a9d7cf0ea7212320',
        's'::"char",
        array['search_path=pg_catalog, integration_control, chlom_runtime']::text[]
      ),
      (
        'integration_control',
        'pentagreen_six_stage_publication_final_v1',
        'p_cycle_id uuid',
        '7bf74ff6de9740c131896214bfeb0414a5389242c3ecbcf6137d1059749a876a',
        'v'::"char",
        array[
          'search_path=pg_catalog, integration_control, extensions',
          'TimeZone=UTC'
        ]::text[]
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,p.proacl,
           pg_catalog.pg_get_functiondef(p.oid) as actual_def,
           pg_catalog.encode(
             extensions.digest(
               pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
               'sha256'
             ),
             'hex'
           ) as actual_sha
    from expected e
    join pg_catalog.pg_namespace n on n.nspname=e.nspname
    join pg_catalog.pg_proc p
      on p.pronamespace=n.oid
     and p.proname=e.proname
     and pg_catalog.pg_get_function_identity_arguments(p.oid)=e.identity_args
  )
  select count(*)=2
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and provolatile=expected_volatility
           and proconfig=expected_config
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
           and (
             select count(*)=2
                    and pg_catalog.bool_and(
                      acl.privilege_type='EXECUTE'
                      and acl.grantee in (
                        actual.proowner,
                        pg_catalog.to_regrole('service_role')::oid
                      )
                    )
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
           )
           and case
             when proname='thriveevergreen_autonomous_publisher_status_v2' then
               pg_catalog.strpos(actual_def,'count(distinct q.governed_publish_job_id)')>0
               and pg_catalog.strpos(actual_def,'site_provider_adapters pa')>0
               and pg_catalog.strpos(actual_def,'count(distinct pr.receipt_stage)=6')>0
               and pg_catalog.strpos(actual_def,'pr.asserted_by_subject_id=p.service_principal_id')>0
               and pg_catalog.strpos(actual_def,'''ct.adapter.dynamic-feed.v1''')=0
             when proname='pentagreen_six_stage_publication_final_v1' then
               pg_catalog.strpos(actual_def,'six_stage_window_lock_contended')>0
               and pg_catalog.strpos(actual_def,'hashtext(x.window_start::text)')>0
               and pg_catalog.strpos(actual_def,'v_ref,v_service_principal_id')>0
               and pg_catalog.strpos(actual_def,'count(distinct q.governed_publish_job_id)')>0
               and pg_catalog.strpos(actual_def,'six_stage_normalized_proof_failed')>0
               and pg_catalog.strpos(actual_def,'verified_publication_count=v_verified_publication_count')>0
             else false
           end
         )
    into v_companion_contracts_ok
  from actual;
  if v_companion_contracts_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_companion_postcondition_failed';
  end if;

  select count(*)=2
         and pg_catalog.bool_and(
           acl.privilege_type='EXECUTE'
           and acl.grantee in (
             p.proowner,pg_catalog.to_regrole('service_role')::oid
           )
         )
    into v_acl_ok
  from pg_catalog.pg_proc p
  cross join lateral pg_catalog.aclexplode(
    coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
  ) acl
  where p.oid=v_oid;

  if v_acl_ok is not true
     or pg_catalog.has_function_privilege('anon',v_oid,'EXECUTE')
     or pg_catalog.has_function_privilege('authenticated',v_oid,'EXECUTE')
     or not pg_catalog.has_function_privilege('service_role',v_oid,'EXECUTE') then
    raise exception 'publisher_truthful_bridge_state_v1_execute_acl_failed';
  end if;

  with expected(proname,identity_args,expected_sha,expected_volatility,expected_config) as (
    values
      (
        'thriveevergreen_publisher_gate_snapshot_v6',
        'p_candidate_id uuid',
        'abdecd59cfffe6008e5e20eaba04f47ab5e76853208e1e61228df9d69e243d36',
        's'::"char",
        array['search_path=pg_catalog, integration_control']::text[]
      ),
      (
        'enqueue_governed_site_publish',
        'p_release_id uuid',
        '6b25dfe5829e0d5be41dbf45c14ed971d8b7312b29466df2246a9f5579465abe',
        'v'::"char",
        array['search_path=pg_catalog, integration_control, chlom_runtime']::text[]
      ),
      (
        'pentagreen_dynamic_feed_external_observation_v1',
        'p_cycle_id uuid, p_stage text, p_route_id text, p_subject_type text, p_subject_ref text, p_exact_version_ref text, p_content_sha256 text, p_expected_present boolean',
        'c7b03299baa9ca067ea674c7c1090464903cb056161816e4f2a4c8473454f4bc',
        'v'::"char",
        array[
          'search_path=pg_catalog, integration_control, extensions, chlom_runtime'
        ]::text[]
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,p.proacl,
           pg_catalog.encode(
             extensions.digest(
               pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
               'sha256'
             ),
             'hex'
           ) actual_sha
    from expected e
    join pg_catalog.pg_proc p
      on p.proname=e.proname
     and pg_catalog.pg_get_function_identity_arguments(p.oid)=e.identity_args
    join pg_catalog.pg_namespace n
      on n.oid=p.pronamespace and n.nspname='integration_control'
  )
  select count(*)=3
         and pg_catalog.bool_and(
           actual.actual_sha=actual.expected_sha
           and pg_catalog.pg_get_userbyid(actual.proowner)='postgres'
           and actual.prosecdef
           and actual.provolatile=actual.expected_volatility
           and actual.proconfig=actual.expected_config
           and (
             select count(*)=2
                    and pg_catalog.bool_and(
                      acl.privilege_type='EXECUTE'
                      and acl.grantee in (
                        actual.proowner,
                        pg_catalog.to_regrole('service_role')::oid
                      )
                    )
             from pg_catalog.aclexplode(
               coalesce(actual.proacl,pg_catalog.acldefault('f',actual.proowner))
             ) acl
           )
         )
    into v_dependencies_ok
  from actual;
  if v_dependencies_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_dependency_postcondition_failed';
  end if;

  with expected(jobname,schedule,command) as (
    values
      ('ct-thriveevergreen-publisher-v2-slot-01','2 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,1::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-02','8 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,2::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-03','14 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,3::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-04','20 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,4::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-05','26 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,5::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-06','32 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,6::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-07','38 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,7::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-08','44 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,8::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-09','50 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,9::smallint);'),
      ('ct-thriveevergreen-publisher-v2-slot-10','56 * * * *','select public.pentagreen_autonomous_publisher_v2(date_trunc(''hour'',now(),''UTC''),''pg_cron_pentagreen_publisher_v2'',false,10::smallint);')
  ), actual as (
    select e.jobname,e.schedule,e.command,
           j.jobid,j.active,j.database,j.username,
           j.schedule as actual_schedule,j.command as actual_command
    from expected e
    left join cron.job j on j.jobname=e.jobname
  )
  select count(*)=10
         and pg_catalog.bool_and(
           jobid is not null
           and active
           and database='postgres'
           and username='postgres'
           and actual_schedule=schedule
           and actual_command=command
         )
         and (
           select count(*)=10
           from cron.job j0
           where j0.jobname~'^ct-thriveevergreen-publisher-v2-slot-(0[1-9]|10)$'
         )
    into v_cron_ok
  from actual;
  if v_cron_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_cron_postcondition_failed';
  end if;

  select count(*)=11
         and pg_catalog.bool_and(c.relrowsecurity)
         and pg_catalog.bool_and(
           case
             when c.relname in (
               'governed_releases',
               'pentagreen_six_stage_publication_cycles_v1',
               'site_provider_adapters',
               'site_publish_jobs',
               'site_publish_routes'
             ) then not c.relforcerowsecurity
             else c.relforcerowsecurity
           end
         )
    into v_rls_ok
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='integration_control'
    and c.relname in (
      'governed_releases',
      'pentagreen_six_stage_publication_cycles_v1',
      'site_provider_adapters',
      'site_publish_jobs',
      'site_publish_routes',
      'thriveevergreen_publisher_attempts_v2',
      'thriveevergreen_publisher_candidates_v2',
      'thriveevergreen_publisher_dispatch_queue_v2',
      'thriveevergreen_publisher_provider_receipts_v2',
      'thriveevergreen_publisher_slots_v2',
      'thriveevergreen_publisher_windows_v2'
    );
  if v_rls_ok is not true then
    raise exception 'publisher_truthful_bridge_state_v1_rls_posture_changed';
  end if;

  -- Compile/run the new entry guards without reaching any canonical write.
  begin
    perform integration_control.run_thriveevergreen_autonomous_publisher_v2(
      null,'migration_null_window_contract_test',true,null
    );
    raise exception 'publisher_truthful_bridge_state_v1_null_window_accepted';
  exception when raise_exception then
    if sqlerrm<>'publisher_v2_window_required' then raise; end if;
  end;

  begin
    perform integration_control.run_thriveevergreen_autonomous_publisher_v2(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC'),null,true,null
    );
    raise exception 'publisher_truthful_bridge_state_v1_null_source_accepted';
  exception when raise_exception then
    if sqlerrm<>'publisher_v2_invocation_source_required' then raise; end if;
  end;

  begin
    perform integration_control.run_thriveevergreen_autonomous_publisher_v2(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC'),
      'migration_null_preview_contract_test',null,null
    );
    raise exception 'publisher_truthful_bridge_state_v1_null_preview_accepted';
  exception when raise_exception then
    if sqlerrm<>'publisher_v2_preview_mode_required' then raise; end if;
  end;

  begin
    perform integration_control.run_thriveevergreen_autonomous_publisher_v2(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC'),
      'pg_cron_thriveevergreen_publisher_v2',false,null
    );
    raise exception 'publisher_truthful_bridge_state_v1_null_production_slot_accepted';
  exception when raise_exception then
    if sqlerrm<>'publisher_v2_slot_number_required' then raise; end if;
  end;

end;
$tests$;

commit;

-- Post-deploy checks remain read-only: call preview, inspect the next scheduled
-- subslot response/DAIL event, then rerun security/performance advisors and API
-- health probes. A TRUE bridge value means only exact queued-job readback.
