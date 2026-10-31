-- 20260908183000_publisher_verified_count_correction_v1.sql
--
-- Additive correction for the already-live publisher truthful-bridge patch.
-- It preserves tuple selection, NOWAIT locking, enqueue fencing, and telemetry.
-- It replaces only the repeated verified-publication aggregate with one exact
-- evidence helper. Historical rows and RLS policies are not changed.

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
    raise exception 'publisher_verified_count_correction_v1_postgres_session_required';
  end if;

  if v_minute in (
    1,2,3,7,8,9,13,14,15,19,20,21,25,26,27,
    31,32,33,37,38,39,43,44,45,49,50,51,55,56,57
  ) then
    raise exception 'publisher_verified_count_correction_v1_retry_outside_publisher_minute';
  end if;

  if pg_catalog.to_regprocedure(
    'integration_control.thriveevergreen_verified_publication_count_v3(text,timestamptz,uuid)'
  ) is not null then
    raise exception 'publisher_verified_count_correction_v1_helper_already_exists';
  end if;

  with expected(nspname,proname,identity_args,expected_sha,expected_volatility,expected_config) as (
    values
      (
        'integration_control',
        'run_thriveevergreen_autonomous_publisher_v2',
        'p_window_start timestamp with time zone, p_invocation_source text, p_preview boolean, p_slot_no smallint',
        '60649d737d5b1dc1b08b67c3b81a837bad68702b254e1277c3280cbd7a722158',
        'v'::"char",
        array[
          'search_path=pg_catalog, integration_control, developer_commerce, chlom_runtime, extensions',
          'TimeZone=UTC'
        ]::text[]
      ),
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
         )
    into v_ok
  from actual;
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_live_postimage_drift';
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
    raise exception 'publisher_verified_count_correction_v1_rls_drift';
  end if;

  if not pg_catalog.pg_try_advisory_xact_lock(
    pg_catalog.hashtext('ct.policy.thriveevergreen-autonomous-publisher.v2'),
    pg_catalog.hashtext(
      pg_catalog.date_trunc('hour',pg_catalog.clock_timestamp(),'UTC')::text
    )
  ) then
    raise exception 'publisher_verified_count_correction_v1_active_window';
  end if;
end;
$preflight$;

CREATE OR REPLACE FUNCTION integration_control.thriveevergreen_verified_publication_count_v3(p_policy_id text, p_window_start timestamp with time zone, p_required_cycle_id uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'integration_control'
 SET "TimeZone" TO 'UTC'
AS $function$
  select jsonb_build_object(
    'verified_publication_count',count(distinct j.job_id),
    'current_cycle_normalized',case
      when p_required_cycle_id is null then null::boolean
      else coalesce(bool_or(cy.cycle_id=p_required_cycle_id),false)
    end,
    'evidence_scope','immutable_six_stage_receipts_and_exact_route_adapter_job_identity'
  )
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
  join integration_control.site_publish_jobs j
    on j.job_id=q.governed_publish_job_id
   and j.job_id=cy.governed_publish_job_id
   and j.release_id=q.release_id
   and j.release_id=cand.release_id
   and j.release_id=cy.release_id
   and j.route_id=q.route_id
   and j.route_id=cand.route_id
   and j.route_id=cy.route_id
   and j.surface_id=cy.surface_id
   and j.adapter_id=r.adapter_id
   and j.adapter_id=pa.adapter_id
   and j.exact_version_ref=a.exact_version_ref
   and j.exact_version_ref=cand.exact_version_ref
   and j.exact_version_ref=cy.exact_version_ref
   and j.content_sha256=a.content_sha256
   and j.content_sha256=cand.content_sha256
   and j.content_sha256=cy.content_sha256
  join integration_control.thriveevergreen_autonomous_publisher_policy_v2 p
    on p.policy_id=a.policy_id
   and p.policy_id=cy.policy_id
  where p.policy_id=p_policy_id
    and (p_window_start is null or a.window_start=p_window_start)
    and q.governed_enqueue_state='queued'
    and q.governed_publish_job_id is not null
    and q.release_id=cand.release_id
    and q.release_id=cy.release_id
    and q.governed_publish_job_id=cy.governed_publish_job_id
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
        and pr.provider_object_ref=cy.provider_object_ref
        and pr.rollback_ref=cy.rollback_ref
        and pr.exact_content_sha256=cy.content_sha256
        and pr.asserted_by_subject_id=p.service_principal_id
        and pr.secret_material_present is false
        and pg_catalog.right(
          pr.provider_readback_ref,
          pg_catalog.length(':'||cy.cycle_id::text||':'||pr.receipt_stage)
        )=':'||cy.cycle_id::text||':'||pr.receipt_stage
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
$function$;

alter function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) owner to postgres;
revoke all privileges on function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) from public;
revoke all privileges on function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) from anon;
revoke all privileges on function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) from authenticated;
grant execute on function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) to postgres, service_role;

do $patch_functions$
declare
  v_def text;
  v_start integer;
  v_relative_end integer;
  v_end integer;
  v_replacement text;
begin
  select pg_catalog.pg_get_functiondef(
    'integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamptz,text,boolean,smallint)'::regprocedure
  ) into v_def;
  v_start:=pg_catalog.strpos(
    v_def,
    '  -- Count unique governed jobs, not dispatch/cycle rows. Every normalized'
  );
  v_relative_end:=pg_catalog.strpos(
    pg_catalog.substr(v_def,v_start),
    E'\n\n  select coalesce(jsonb_agg(jsonb_build_object('
  );
  if v_start=0 or v_relative_end=0 then
    raise exception 'publisher_verified_count_correction_v1_runner_marker_drift';
  end if;
  v_end:=v_start+v_relative_end-1;
  v_replacement:=$runner$  -- Count truthful unique governed jobs through immutable six-stage receipts
  -- and exact candidate/release/route/adapter/job identities. Current mutable
  -- certification states and display-oriented provider labels are not evidence.
  select (
    integration_control.thriveevergreen_verified_publication_count_v3(
      v_policy.policy_id,v_window,null
    )->>'verified_publication_count'
  )::smallint
    into v_verified_publication_count;
$runner$;
  execute pg_catalog.substr(v_def,1,v_start-1)
          ||v_replacement||pg_catalog.substr(v_def,v_end);

  select pg_catalog.pg_get_functiondef(
    'public.thriveevergreen_autonomous_publisher_status_v2()'::regprocedure
  ) into v_def;
  v_start:=pg_catalog.strpos(v_def,E'    ''verified_publication_count'',(');
  v_relative_end:=pg_catalog.strpos(
    pg_catalog.substr(v_def,v_start),
    E'\n    ''no_delete'','
  );
  if v_start=0 or v_relative_end=0 then
    raise exception 'publisher_verified_count_correction_v1_status_marker_drift';
  end if;
  v_end:=v_start+v_relative_end-1;
  v_replacement:=$status$    'verified_publication_count',(
      integration_control.thriveevergreen_verified_publication_count_v3(
        p.policy_id,null,null
      )->>'verified_publication_count'
    )::bigint,
$status$;
  execute pg_catalog.substr(v_def,1,v_start-1)
          ||v_replacement||pg_catalog.substr(v_def,v_end);

  select pg_catalog.pg_get_functiondef(
    'integration_control.pentagreen_six_stage_publication_final_v1(uuid)'::regprocedure
  ) into v_def;
  v_start:=pg_catalog.strpos(
    v_def,
    '  select count(distinct q.governed_publish_job_id)::smallint,'
  );
  v_relative_end:=pg_catalog.strpos(
    pg_catalog.substr(v_def,v_start),
    E'\n\n  if v_current_cycle_normalized is not true then'
  );
  if v_start=0 or v_relative_end=0 then
    raise exception 'publisher_verified_count_correction_v1_finalizer_marker_drift';
  end if;
  v_end:=v_start+v_relative_end-1;
  v_replacement:=$finalizer$  select (normalized.result->>'verified_publication_count')::smallint,
         coalesce((normalized.result->>'current_cycle_normalized')::boolean,false)
    into v_verified_publication_count,v_current_cycle_normalized
  from (
    select integration_control.thriveevergreen_verified_publication_count_v3(
      cy0.policy_id,cy0.window_start,cy0.cycle_id
    ) as result
    from integration_control.pentagreen_six_stage_publication_cycles_v1 cy0
    where cy0.cycle_id=p_cycle_id
  ) normalized;
$finalizer$;
  execute pg_catalog.substr(v_def,1,v_start-1)
          ||v_replacement||pg_catalog.substr(v_def,v_end);
end;
$patch_functions$;

-- CREATE OR REPLACE retains the exact live allowlists. Reassert them and the
-- helper's closed client posture explicitly.
revoke all privileges on function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) from public, anon, authenticated;
grant execute on function integration_control.run_thriveevergreen_autonomous_publisher_v2(timestamp with time zone,text,boolean,smallint) to postgres, service_role;
revoke all privileges on function public.thriveevergreen_autonomous_publisher_status_v2() from public, anon, authenticated;
grant execute on function public.thriveevergreen_autonomous_publisher_status_v2() to postgres, service_role;
revoke all privileges on function integration_control.pentagreen_six_stage_publication_final_v1(uuid) from public, anon, authenticated;
grant execute on function integration_control.pentagreen_six_stage_publication_final_v1(uuid) to postgres, service_role;

comment on function integration_control.thriveevergreen_verified_publication_count_v3(text,timestamp with time zone,uuid) is
'Counts each governed publish job once using immutable final six-stage receipt evidence plus exact candidate, release, route, adapter, attempt, dispatch, and cycle identities. Mutable current certification state and adapter display labels are intentionally excluded.';

do $postassert$
declare
  v_ok boolean;
begin
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
  select count(*)=4
         and pg_catalog.bool_and(
           actual_sha=expected_sha
           and pg_catalog.pg_get_userbyid(proowner)='postgres'
           and prosecdef
           and not pg_catalog.has_function_privilege('anon',oid,'EXECUTE')
           and not pg_catalog.has_function_privilege('authenticated',oid,'EXECUTE')
           and pg_catalog.has_function_privilege('service_role',oid,'EXECUTE')
           and pg_catalog.strpos(
             actual_def,
             'thriveevergreen_verified_publication_count_v3'
           )>0
         )
    into v_ok
  from actual;
  if v_ok is not true then
    raise exception 'publisher_verified_count_correction_v1_postimage_failed';
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
    raise exception 'publisher_verified_count_correction_v1_rls_changed';
  end if;
end;
$postassert$;

commit;
