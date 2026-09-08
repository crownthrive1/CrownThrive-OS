-- Guarded rollback for 20260908160000_mailgun_projector_normalized_correlation_v1.sql
-- Restores the exact projector preimage and removes only the exact correlation
-- lock trigger/function installed by the forward migration. It does not replay
-- or mutate any Mailgun event, job, projection receipt, DAIL event, preference,
-- or contact.

begin;

set local lock_timeout = '5s';
set local statement_timeout = '60s';

do $preflight$
declare
  v_oid oid := 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure;
  v_sha text;
  v_contract_ok boolean;
  v_balancer_ok boolean;
  v_guard_ok boolean;
  v_rls_ok boolean;
  v_runtime_ok boolean;
begin
  if not pg_catalog.pg_try_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'ct:pentabalancer:managed-job:ct-pentamail-mailgun-projection-v1',
      0
    )
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_worker_active_retry';
  end if;

  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(v_oid),'UTF8'),
             'sha256'
           ),
           'hex'
         ),
         p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, public, integration_control, crm, chlom_runtime, extensions'
         ]::text[]
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
    into v_sha,v_contract_ok
  from pg_catalog.pg_proc p
  where p.oid=v_oid;

  if v_sha<>'afac97979751fcb39b8aea2c9b8094589d8a50d47791fc0897d8b694146879b8' then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_postimage_drift:%',v_sha;
  end if;
  if v_contract_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_contract_drift';
  end if;

  select count(*)=1
         and pg_catalog.bool_and(
           not p.prosecdef
           and p.provolatile='v'
           and p.prokind='f'
           and not p.proisstrict
           and not p.proleakproof
           and p.proparallel='u'
           and p.pronargs=0
           and p.prorettype='pg_catalog.trigger'::regtype
           and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
           and p.proconfig=array['search_path=pg_catalog']::text[]
           and pg_catalog.encode(
                 extensions.digest(
                   pg_catalog.convert_to(p.prosrc,'UTF8'),
                   'sha256'
                 ),
                 'hex'
               )='4946770d7916efed3c3621c488812b8d3627cd84c6be0073fdac08a2ae7fe30e'
           and (
             select count(*)=1
             from pg_catalog.aclexplode(
               coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee=p.proowner
           )
           and not exists (
             select 1
             from pg_catalog.aclexplode(
               coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))
             ) acl
             where acl.privilege_type='EXECUTE'
               and acl.grantee<>p.proowner
           )
         )
    into v_guard_ok
  from pg_catalog.pg_proc p
  join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_mail_provider_accepted_lock_v1'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)='';
  if v_guard_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_guard_function_drift';
  end if;

  select count(*)=1
         and pg_catalog.bool_and(
           t.tgfoid=
             'integration_control.penta_mail_provider_accepted_lock_v1()'::regprocedure
           and t.tgtype=31
           and t.tgenabled='O'
           and not t.tgisinternal
           and (
             select pg_catalog.array_agg(a.attname order by a.attname)
             from pg_catalog.pg_attribute a
             where a.attrelid=t.tgrelid
               and a.attnum=any(t.tgattr::smallint[])
           )=array['outcome_state','provider_message_id']::name[]
         )
    into v_guard_ok
  from pg_catalog.pg_trigger t
  where t.tgrelid=
          'integration_control.penta_mail_provider_attempt_outcomes_v1'::regclass
    and t.tgname='penta_mail_provider_accepted_lock_v1';
  if v_guard_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_guard_trigger_drift';
  end if;

  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
             'sha256'
           ),
           'hex'
         )='cffc05ccefe7c98befc04177fab1a971feaf55fc15b60251dfbb75b4ca27e2b1'
         and p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, penta_balancer, extensions, pg_temp'
         ]::text[]
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
         and pg_catalog.strpos(
               pg_catalog.pg_get_functiondef(p.oid),
               'pg_try_advisory_xact_lock(hashtextextended(''ct:pentabalancer:managed-job:''||p_jobname,0))'
             )>0
    into v_balancer_ok
  from pg_catalog.pg_proc p
  join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='penta_balancer'
    and p.proname='execute_managed_job_v1'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)='p_jobname text';
  if v_balancer_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_worker_fence_drift';
  end if;

  select exists (
    select 1 from cron.job j
    where j.jobid=1864
      and j.jobname='ct-pentamail-mailgun-projection-v1'
      and j.schedule='* * * * *'
      and j.active
      and j.username='postgres'
      and j.command=
        'select penta_balancer.execute_managed_job_v1(''ct-pentamail-mailgun-projection-v1'');'
  ) and exists (
    select 1 from penta_balancer.job_policy_v1 p
    where p.jobname='ct-pentamail-mailgun-projection-v1'
      and p.active and p.instrumented
      and p.original_command=
        'select public.penta_mail_project_mailgun_events_shaped_v2(8);'
      and p.original_command_sha256=
        '366438b4f9c9a637e51bbf846fd6b86ccc41f11d3515e25f54b97f25b59502ab'
      and p.admission_class='critical'
      and p.priority=95
      and p.max_runtime_seconds=28
      and p.cooldown_seconds=0
  ) into v_runtime_ok;
  if v_runtime_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_runtime_drift';
  end if;

  with expected(nspname,relname,force_rls) as (
    values
      ('public','penta_mail_outbox_v1',false),
      ('integration_control','penta_mail_mailgun_event_inbox_v1',true),
      ('integration_control','penta_mail_mailgun_projection_jobs_v1',true),
      ('integration_control','penta_mail_mailgun_projection_receipts_v1',true),
      ('integration_control','penta_mail_provider_attempts_v1',false),
      ('integration_control','penta_mail_provider_attempt_outcomes_v1',false)
  ), actual as (
    select e.*,c.relrowsecurity,c.relforcerowsecurity,
           pg_catalog.pg_get_userbyid(c.relowner) owner
    from expected e
    join pg_catalog.pg_namespace n on n.nspname=e.nspname
    join pg_catalog.pg_class c
      on c.relnamespace=n.oid and c.relname=e.relname and c.relkind='r'
  )
  select count(*)=6
         and pg_catalog.bool_and(relrowsecurity)
         and pg_catalog.bool_and(relforcerowsecurity=force_rls)
         and pg_catalog.bool_and(owner='postgres')
    into v_rls_ok
  from actual;
  if v_rls_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_rls_drift';
  end if;

  if not exists (
    select 1
    from pg_catalog.pg_policies p
    where p.schemaname='public'
      and p.tablename='penta_mail_outbox_v1'
      and p.policyname='ct_explicit_client_deny_v1'
      and p.cmd='ALL'
      and p.roles @> array['anon','authenticated']::name[]
      and p.qual='false'
      and p.with_check='false'
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_client_deny_policy_drift';
  end if;

  perform pg_catalog.set_config(
    'ct.mailgun_projector_rollback.completed_before',
    (
      select count(*)::text
      from integration_control.penta_mail_mailgun_projection_jobs_v1
      where state='completed'
    ),
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_rollback.receipts_before',
    (
      select count(*)::text
      from integration_control.penta_mail_mailgun_projection_receipts_v1
    ),
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_rollback.relation_acl_before',
    (
      select pg_catalog.jsonb_object_agg(
               n.nspname||'.'||c.relname,
               coalesce(c.relacl::text,'<default>')
             )::text
      from pg_catalog.pg_class c
      join pg_catalog.pg_namespace n on n.oid=c.relnamespace
      where (n.nspname,c.relname) in (
        ('public','penta_mail_outbox_v1'),
        ('integration_control','penta_mail_mailgun_event_inbox_v1'),
        ('integration_control','penta_mail_mailgun_projection_jobs_v1'),
        ('integration_control','penta_mail_mailgun_projection_receipts_v1'),
        ('integration_control','penta_mail_provider_attempts_v1'),
        ('integration_control','penta_mail_provider_attempt_outcomes_v1')
      )
    ),
    true
  );
end;
$preflight$;

do $rollback$
declare
  v_oid oid := 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure;
  v_def text := pg_catalog.pg_get_functiondef(v_oid);
  v_old text;
  v_new text;
begin
  v_old := $patched_decl$  v_claimed public.penta_mail_outbox_v1%rowtype;
  v_by_provider public.penta_mail_outbox_v1%rowtype;
  v_by_provider_id public.penta_mail_outbox_v1%rowtype;
  v_outbox public.penta_mail_outbox_v1%rowtype;
  v_provider_outcome_count integer := 0;
  v_provider_route_match_count integer := 0;
  v_by_provider_message_id uuid;
  v_by_provider_id_message_id uuid;
$patched_decl$;
  v_new := $original_decl$  v_claimed public.penta_mail_outbox_v1%rowtype;
  v_by_provider public.penta_mail_outbox_v1%rowtype;
  v_outbox public.penta_mail_outbox_v1%rowtype;
$original_decl$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_declaration_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $patched_reset$      v_claimed := null;
      v_by_provider := null;
      v_by_provider_id := null;
      v_outbox := null;
      v_provider_outcome_count := 0;
      v_provider_route_match_count := 0;
      v_by_provider_message_id := null;
      v_by_provider_id_message_id := null;
$patched_reset$;
  v_new := $original_reset$      v_claimed := null;
      v_by_provider := null;
      v_outbox := null;
$original_reset$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_reset_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $patched_correlation$      v_provider_norm := nullif(lower(btrim(btrim(v_event.provider_message_id), '<>')),'');
      if v_provider_norm is not null then
        -- The outcomes-table trigger takes this exact transaction lock before
        -- any accepted provider ID can enter, leave, or change. Waiting here
        -- completes before the SELECT below takes its READ COMMITTED snapshot.
        perform pg_catalog.pg_advisory_xact_lock(
          pg_catalog.hashtextextended(
            'ct:pentamail:provider-accepted:'||v_provider_norm,
            0
          )
        );

        -- All evidence comes from one READ COMMITTED statement snapshot.
        -- The shared trigger/projector transaction lock prevents a later
        -- accepted-evidence change until this projection transaction ends.
        with accepted as materialized (
          select a.provider_route_id,a.request_key
          from integration_control.penta_mail_provider_attempts_v1 a
          join integration_control.penta_mail_provider_attempt_outcomes_v1 o
            on o.attempt_id=a.attempt_id
          where o.outcome_state='provider_accepted'
            and nullif(lower(btrim(btrim(o.provider_message_id), '<>')),'')
              =v_provider_norm
        ), evidence as (
          select count(*)::integer outcome_count,
                 count(*) filter (
                   where provider_route_id=v_event.provider_route_id
                 )::integer route_match_count,
                 min(request_key) filter (
                   where provider_route_id=v_event.provider_route_id
                 ) request_key
          from accepted
        )
        select e.outcome_count,e.route_match_count,
               (
                 select ob.message_id
                 from public.penta_mail_outbox_v1 ob
                 where e.outcome_count=1
                   and e.route_match_count=1
                   and e.request_key='penta-outbox:'||ob.message_id::text
               ),
               (
                 select ob.message_id
                 from public.penta_mail_outbox_v1 ob
                 where e.outcome_count=1
                   and e.route_match_count=1
                   and nullif(lower(btrim(btrim(ob.provider_message_id), '<>')),'')
                     =v_provider_norm
               )
          into v_provider_outcome_count,v_provider_route_match_count,
               v_by_provider_message_id,v_by_provider_id_message_id
        from evidence e;

        if v_provider_outcome_count>1 then
          raise exception 'PENTAMAIL_MAILGUN_PROVIDER_OUTCOME_AMBIGUOUS';
        elsif v_provider_outcome_count=1
              and v_provider_route_match_count<>1 then
          raise exception 'PENTAMAIL_MAILGUN_PROVIDER_ROUTE_CORRELATION_CONFLICT';
        elsif v_provider_route_match_count=1 then
          if v_by_provider_message_id is not null then
            select * into strict v_by_provider
            from public.penta_mail_outbox_v1
            where message_id=v_by_provider_message_id;
          end if;
          if v_by_provider_id_message_id is not null then
            select * into strict v_by_provider_id
            from public.penta_mail_outbox_v1
            where message_id=v_by_provider_id_message_id;
          end if;
        end if;
      end if;

      if v_by_provider.message_id is not null
         and v_by_provider.provider_message_id is not null
         and nullif(lower(btrim(btrim(v_by_provider.provider_message_id), '<>')),'')
           is distinct from v_provider_norm then
        raise exception 'PENTAMAIL_MAILGUN_LEGACY_PROVIDER_ID_CORRELATION_CONFLICT';
      end if;
      if v_by_provider_id.message_id is not null
         and nullif(
               lower(
                 btrim(btrim(v_by_provider_id.provider_message_id), '<>')
               ),
               ''
             ) is distinct from v_provider_norm then
        raise exception 'PENTAMAIL_MAILGUN_OUTBOX_PROVIDER_ID_CHANGED';
      end if;
      if v_by_provider.message_id is not null
         and v_by_provider_id.message_id is not null
         and v_by_provider.message_id is distinct from v_by_provider_id.message_id then
        raise exception 'PENTAMAIL_MAILGUN_LEGACY_FALLBACK_CORRELATION_CONFLICT';
      end if;
      if coalesce(v_by_provider.message_id,v_by_provider_id.message_id) is not null
         and v_claimed.message_id is not null
         and coalesce(v_by_provider.message_id,v_by_provider_id.message_id)
           is distinct from v_claimed.message_id then
        raise exception 'PENTAMAIL_MAILGUN_MESSAGE_CORRELATION_CONFLICT';
      end if;
$patched_correlation$;
  v_new := $original_correlation$      v_provider_norm := nullif(lower(btrim(btrim(v_event.provider_message_id), '<>')),'');
      if v_provider_norm is not null then
        select ob.* into v_by_provider
        from integration_control.penta_mail_provider_attempts_v1 a
        join integration_control.penta_mail_provider_attempt_outcomes_v1 o
          on o.attempt_id=a.attempt_id
        join public.penta_mail_outbox_v1 ob
          on a.request_key='penta-outbox:'||ob.message_id::text
        where a.provider_route_id='mailgun:relay.crownthrive.com'
          and o.outcome_state='provider_accepted'
          and nullif(lower(btrim(btrim(o.provider_message_id), '<>')),'')
            =v_provider_norm
        order by o.recorded_at desc
        limit 1;
      end if;
      if v_by_provider.message_id is not null
         and v_claimed.message_id is not null
         and v_by_provider.message_id is distinct from v_claimed.message_id then
        raise exception 'PENTAMAIL_MAILGUN_MESSAGE_CORRELATION_CONFLICT';
      end if;
$original_correlation$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_correlation_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $patched_resolution$      v_message_id := coalesce(
        v_by_provider.message_id,
        v_by_provider_id.message_id,
        v_claimed.message_id
      );
      if v_message_id is not null then
        select * into strict v_outbox
        from public.penta_mail_outbox_v1
        where message_id=v_message_id;
      elsif v_provider_norm is not null
            and v_event.received_at > v_now-interval '24 hours' then
        -- Completion may not have persisted both the accepted outcome and the
        -- uniquely normalized outbox ID yet. Retry before finalizing unmatched.
        raise exception 'PENTAMAIL_MAILGUN_CORRELATION_PENDING';
      end if;

      if v_event.claimed_penta_message_id is not null
         and v_claimed.message_id is null then
        raise exception 'PENTAMAIL_MAILGUN_EXPLICIT_PENTA_MESSAGE_NOT_FOUND';
      end if;

      v_correlation_basis := case
        when v_by_provider.message_id is not null
             and v_by_provider_id.message_id is not null
             and v_claimed.message_id is not null
          then 'provider_request_outbox_and_penta'
        when v_by_provider.message_id is not null
             and v_by_provider_id.message_id is not null
          then 'provider_request_and_outbox_provider_id'
        when v_by_provider_id.message_id is not null
             and v_claimed.message_id is not null
          then 'accepted_provider_outbox_and_penta'
        when v_by_provider_id.message_id is not null
          then 'accepted_provider_outbox_provider_message_id'
        when v_by_provider.message_id is not null
             and v_claimed.message_id is not null
          then 'provider_and_penta'
        when v_by_provider.message_id is not null then 'provider_message_id'
        when v_claimed.message_id is not null then 'penta_message_id'
        else 'unmatched'
      end;
$patched_resolution$;
  v_new := $original_resolution$      v_message_id := coalesce(v_by_provider.message_id,v_claimed.message_id);
      if v_message_id is not null then
        select * into strict v_outbox
        from public.penta_mail_outbox_v1
        where message_id=v_message_id;
      elsif v_provider_norm is not null
            and v_event.received_at > v_now-interval '24 hours' then
        -- Completion may not have persisted the provider ID yet. Retry before
        -- finalizing an unmatched event.
        raise exception 'PENTAMAIL_MAILGUN_CORRELATION_PENDING';
      end if;

      if v_event.claimed_penta_message_id is not null
         and v_claimed.message_id is null then
        raise exception 'PENTAMAIL_MAILGUN_EXPLICIT_PENTA_MESSAGE_NOT_FOUND';
      end if;

      v_correlation_basis := case
        when v_by_provider.message_id is not null and v_claimed.message_id is not null
          then 'provider_and_penta'
        when v_by_provider.message_id is not null then 'provider_message_id'
        when v_claimed.message_id is not null then 'penta_message_id'
        else 'unmatched'
      end;
$original_resolution$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_resolution_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $patched_route$      if v_by_provider.message_id is not null then
        v_route_evidence := 'provider_attempt_route_and_request_key';
      elsif v_by_provider_id.message_id is not null then
        v_route_evidence :=
          'accepted_provider_route_and_unique_outbox_provider_message_id';
      elsif v_claimed.message_id is not null then
        v_route_evidence := 'signed_penta_message_binding';
      end if;

$patched_route$;
  v_new := $original_route$      if v_by_provider.message_id is not null then
        v_route_evidence := 'provider_attempt_route';
      elsif v_claimed.message_id is not null then
        v_route_evidence := 'signed_penta_message_binding';
      end if;

$original_route$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_route_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  execute v_def;
  if 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure::oid<>v_oid then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_oid_changed';
  end if;
end;
$rollback$;

alter function public.penta_mail_project_mailgun_events_v1(integer)
  owner to postgres;
revoke all privileges on function public.penta_mail_project_mailgun_events_v1(integer)
  from public, anon, authenticated;
grant execute on function public.penta_mail_project_mailgun_events_v1(integer)
  to postgres, service_role;
comment on function public.penta_mail_project_mailgun_events_v1(integer) is null;

drop trigger penta_mail_provider_accepted_lock_v1
  on integration_control.penta_mail_provider_attempt_outcomes_v1;
drop function integration_control.penta_mail_provider_accepted_lock_v1();

do $postflight$
declare
  v_oid oid := 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure;
  v_sha text;
  v_acl_ok boolean;
  v_balancer_ok boolean;
  v_rls_ok boolean;
  v_runtime_ok boolean;
  v_completed_after bigint;
  v_receipts_after bigint;
begin
  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(v_oid),'UTF8'),
             'sha256'
           ),
           'hex'
         ),
         p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, public, integration_control, crm, chlom_runtime, extensions'
         ]::text[]
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
    into v_sha,v_acl_ok
  from pg_catalog.pg_proc p
  where p.oid=v_oid;

  if v_sha<>'65fef0db7d7cfb2b1c3b12c3d44508053fa42a02828b89b9232e18590d9a630d' then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_restore_failed:%',v_sha;
  end if;
  if v_acl_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_acl_failed';
  end if;

  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
             'sha256'
           ),
           'hex'
         )='cffc05ccefe7c98befc04177fab1a971feaf55fc15b60251dfbb75b4ca27e2b1'
         and p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, penta_balancer, extensions, pg_temp'
         ]::text[]
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
         and pg_catalog.strpos(
               pg_catalog.pg_get_functiondef(p.oid),
               'pg_try_advisory_xact_lock(hashtextextended(''ct:pentabalancer:managed-job:''||p_jobname,0))'
             )>0
    into v_balancer_ok
  from pg_catalog.pg_proc p
  join pg_catalog.pg_namespace n on n.oid=p.pronamespace
  where n.nspname='penta_balancer'
    and p.proname='execute_managed_job_v1'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)='p_jobname text';
  if v_balancer_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_worker_fence_changed';
  end if;

  if pg_catalog.to_regprocedure(
       'integration_control.penta_mail_provider_accepted_lock_v1()'
     ) is not null
     or exists (
       select 1
       from pg_catalog.pg_trigger t
       where t.tgrelid=
         'integration_control.penta_mail_provider_attempt_outcomes_v1'::regclass
         and t.tgname='penta_mail_provider_accepted_lock_v1'
         and not t.tgisinternal
     )
  then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_guard_remains';
  end if;

  with expected(nspname,relname,force_rls) as (
    values
      ('public','penta_mail_outbox_v1',false),
      ('integration_control','penta_mail_mailgun_event_inbox_v1',true),
      ('integration_control','penta_mail_mailgun_projection_jobs_v1',true),
      ('integration_control','penta_mail_mailgun_projection_receipts_v1',true),
      ('integration_control','penta_mail_provider_attempts_v1',false),
      ('integration_control','penta_mail_provider_attempt_outcomes_v1',false)
  ), actual as (
    select e.*,c.relrowsecurity,c.relforcerowsecurity,
           pg_catalog.pg_get_userbyid(c.relowner) owner
    from expected e
    join pg_catalog.pg_namespace n on n.nspname=e.nspname
    join pg_catalog.pg_class c
      on c.relnamespace=n.oid and c.relname=e.relname and c.relkind='r'
  )
  select count(*)=6
         and pg_catalog.bool_and(relrowsecurity)
         and pg_catalog.bool_and(relforcerowsecurity=force_rls)
         and pg_catalog.bool_and(owner='postgres')
    into v_rls_ok
  from actual;
  if v_rls_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_rls_changed';
  end if;

  if (
    select pg_catalog.jsonb_object_agg(
             n.nspname||'.'||c.relname,
             coalesce(c.relacl::text,'<default>')
           )::text
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid=c.relnamespace
    where (n.nspname,c.relname) in (
      ('public','penta_mail_outbox_v1'),
      ('integration_control','penta_mail_mailgun_event_inbox_v1'),
      ('integration_control','penta_mail_mailgun_projection_jobs_v1'),
      ('integration_control','penta_mail_mailgun_projection_receipts_v1'),
      ('integration_control','penta_mail_provider_attempts_v1'),
      ('integration_control','penta_mail_provider_attempt_outcomes_v1')
    )
  ) is distinct from pg_catalog.current_setting(
    'ct.mailgun_projector_rollback.relation_acl_before'
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_relation_acl_changed';
  end if;

  if not exists (
    select 1
    from pg_catalog.pg_policies p
    where p.schemaname='public'
      and p.tablename='penta_mail_outbox_v1'
      and p.policyname='ct_explicit_client_deny_v1'
      and p.cmd='ALL'
      and p.roles @> array['anon','authenticated']::name[]
      and p.qual='false'
      and p.with_check='false'
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_client_deny_policy_changed';
  end if;

  select
    exists (
      select 1 from cron.job j
      where j.jobid=1864
        and j.jobname='ct-pentamail-mailgun-projection-v1'
        and j.schedule='* * * * *'
        and j.active
        and j.username='postgres'
        and j.command=
          'select penta_balancer.execute_managed_job_v1(''ct-pentamail-mailgun-projection-v1'');'
    )
    and exists (
      select 1 from penta_balancer.job_policy_v1 p
      where p.jobname='ct-pentamail-mailgun-projection-v1'
        and p.active
        and p.instrumented
        and p.original_command=
          'select public.penta_mail_project_mailgun_events_shaped_v2(8);'
        and p.original_command_sha256=
          '366438b4f9c9a637e51bbf846fd6b86ccc41f11d3515e25f54b97f25b59502ab'
        and p.admission_class='critical'
        and p.priority=95
        and p.max_runtime_seconds=28
        and p.cooldown_seconds=0
    )
    into v_runtime_ok;
  if v_runtime_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_runtime_changed';
  end if;

  select count(*) into v_completed_after
  from integration_control.penta_mail_mailgun_projection_jobs_v1
  where state='completed';
  select count(*) into v_receipts_after
  from integration_control.penta_mail_mailgun_projection_receipts_v1;
  if v_completed_after<>
       pg_catalog.current_setting(
         'ct.mailgun_projector_rollback.completed_before'
       )::bigint
     or v_receipts_after<>
       pg_catalog.current_setting(
         'ct.mailgun_projector_rollback.receipts_before'
       )::bigint
  then
    raise exception 'mailgun_projector_normalized_correlation_v1_rollback_data_effect';
  end if;
end;
$postflight$;

commit;
