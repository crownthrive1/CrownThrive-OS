-- 20260908183000_publisher_verified_count_correction_v1.rollback.sql
--
-- Guarded rollback to the exact publisher definitions installed by
-- 20260908154500_publisher_truthful_bridge_state_v1.sql. No evidence row,
-- queue row, candidate, policy, cron, API grant, or RLS policy is changed.

begin;

set local lock_timeout = '2s';
set local statement_timeout = '20s';
set local timezone = 'UTC';

do $preflight$
declare
  v_ok boolean;
  v_minute integer:=extract(minute from pg_catalog.clock_timestamp())::integer;
begin
  if session_user<>'postgres' or current_user<>'postgres' then
    raise exception 'publisher_verified_count_correction_v1_rollback_postgres_session_required';
  end if;

  if v_minute in (
    1,2,3,7,8,9,13,14,15,19,20,21,25,26,27,
    31,32,33,37,38,39,43,44,45,49,50,51,55,56,57
  ) then
    raise exception 'publisher_verified_count_correction_v1_rollback_retry_outside_publisher_minute';
  end if;

  with expected(nspname,proname,identity_args,expected_sha) as (
    values
      (
        'integration_control',
        'run_thriveevergreen_autonomous_publisher_v2',
        'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint',
        '3264c47b312ae2ed8c07aa65990b6e14ed6f0d947445f785d132b3e7b2db6808'
      ),
      (
        'public',
        'thriveevergreen_autonomous_publisher_status_v2',
        '',
        'dfef261a5628afc79d94371e410368d03835b573cb4dc78df4a41d0eee19885f'
      ),
      (
        'integration_control',
        'pentagreen_six_stage_publication_final_v1',
        'p_cycle_id uuid',
        '04f6d5acdbb1b3a2a470d9eba903675a43631219096cf660be4661f8f2d2901c'
      ),
      (
        'integration_control',
        'thriveevergreen_verified_publication_count_v3',
        'p_policy_id text, p_window_start timestamp with time zone, p_required_cycle_id uuid',
        'c72f82fbe4a8e651f3c0c09bdd14130b745cc86d93b3f3c61cbf5d58d06c3b30'
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.proacl,
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
  select count(*)=4
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
         )
    into v_ok
  from actual;
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_rollback_postimage_drift';
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
    into v_ok
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
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_rollback_rls_drift';
  end if;

  if not pg_catalog.pg_try_advisory_xact_lock(
    pg_catalog.hashtext('ct.policy.thriveevergreen-autonomous-publisher.v2'),
    pg_catalog.hashtext(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC')::text
    )
  ) then
    raise exception 'publisher_verified_count_correction_v1_rollback_active_window';
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

revoke all privileges on function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) from public, anon, authenticated;
grant execute on function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) to postgres, service_role;
revoke all privileges on function public.thriveevergreen_autonomous_publisher_status_v2() from public, anon, authenticated;
grant execute on function public.thriveevergreen_autonomous_publisher_status_v2() to postgres, service_role;
revoke all privileges on function integration_control.pentagreen_six_stage_publication_final_v1(uuid) from public, anon, authenticated;
grant execute on function integration_control.pentagreen_six_stage_publication_final_v1(uuid) to postgres, service_role;

drop function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid);

do $postassert$
declare
  v_ok boolean;
begin
  if pg_catalog.to_regprocedure(
    'integration_control.thriveevergreen_verified_publication_count_v3(text,timestamptz,uuid)'
  ) is not null then
    raise exception 'publisher_verified_count_correction_v1_rollback_helper_remains';
  end if;

  with expected(nspname,proname,identity_args,expected_sha) as (
    values
      (
        'integration_control',
        'run_thriveevergreen_autonomous_publisher_v2',
        'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint',
        '60649d737d5b1dc1b08b67c3b81a837bad68702b254e1277c3280cbd7a722158'
      ),
      (
        'public',
        'thriveevergreen_autonomous_publisher_status_v2',
        '',
        'd20a2869087b63a3c2a335c5085adba64f6ed6ccb4548a31a9d7cf0ea7212320'
      ),
      (
        'integration_control',
        'pentagreen_six_stage_publication_final_v1',
        'p_cycle_id uuid',
        '7bf74ff6de9740c131896214bfeb0414a5389242c3ecbcf6137d1059749a876a'
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.proacl,
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
  select count(*)=3
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
         )
    into v_ok
  from actual;
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_rollback_restore_failed';
  end if;

  select count(*)=11 and pg_catalog.bool_and(c.relrowsecurity)
    into v_ok
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
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_rollback_rls_changed';
  end if;
end;
$postassert$;

commit;
