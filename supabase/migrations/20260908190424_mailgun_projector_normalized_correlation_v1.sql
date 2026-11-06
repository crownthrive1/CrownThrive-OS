-- 20260908160000_mailgun_projector_normalized_correlation_v1.sql
--
-- Guarded function-plus-trigger correction for Mailgun lifecycle correlation.
-- The provider request key is retained as stronger legacy evidence when it is
-- canonical, but it is no longer the only way to bind an accepted Mailgun
-- outcome to its uniquely identified PentaMail outbox row.
--
-- Production snapshot captured 2026-09-08 UTC (read-only):
--   target preimage SHA-256:
--     65fef0db7d7cfb2b1c3b12c3d44508053fa42a02828b89b9232e18590d9a630d
--   target owner / mode / ACL:
--     postgres / SECURITY DEFINER / postgres + service_role EXECUTE only
--   normalized outbox IDs: 2,873 rows / 2,873 distinct
--   normalized unique index: valid, ready, live, unique, immediate
--   pending-or-retry safe matches at audit time: 1,376
--   claimed-ID conflicts at audit time: 0
--
-- This migration does not call the projector, replay completed jobs, update
-- historical receipts or DAIL, alter RLS/table data, or change cron/policy.
-- The trigger only serializes changes to accepted provider-message evidence
-- with the projector's read of that same evidence; it performs no DML.

begin;

set local lock_timeout = '5s';
set local statement_timeout = '60s';

do $preflight$
declare
  v_oid oid;
  v_sha text;
  v_contract_ok boolean;
  v_index_ok boolean;
  v_dependencies_ok boolean;
  v_rls_ok boolean;
  v_runtime_ok boolean;
  v_bad bigint;
  v_safe_backlog bigint;
begin
  -- Exclude the minute worker without pausing or rewriting its cron entry.
  if not pg_catalog.pg_try_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'ct:pentabalancer:managed-job:ct-pentamail-mailgun-projection-v1',
      0
    )
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_worker_active_retry';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_guard_name_collision';
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
  where n.nspname='public'
    and p.proname='penta_mail_project_mailgun_events_v1'
    and pg_catalog.pg_get_function_identity_arguments(p.oid)='p_limit integer';

  if v_oid is null then
    raise exception 'mailgun_projector_normalized_correlation_v1_target_missing';
  end if;
  if v_sha<>'65fef0db7d7cfb2b1c3b12c3d44508053fa42a02828b89b9232e18590d9a630d' then
    raise exception 'mailgun_projector_normalized_correlation_v1_preimage_drift:%',v_sha;
  end if;

  select p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, public, integration_control, crm, chlom_runtime, extensions'
         ]::text[]
         and (
           select count(*)=2
           from pg_catalog.aclexplode(
             coalesce(
               p.proacl,
               pg_catalog.acldefault('f',p.proowner)
             )
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
             coalesce(
               p.proacl,
               pg_catalog.acldefault('f',p.proowner)
             )
           ) acl
           where acl.privilege_type='EXECUTE'
             and acl.grantee not in (
               p.proowner,
               pg_catalog.to_regrole('service_role')::oid
             )
         )
    into v_contract_ok
  from pg_catalog.pg_proc p
  where p.oid=v_oid;
  if v_contract_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_function_contract_drift';
  end if;

  select i.indisvalid
         and i.indisready
         and i.indislive
         and i.indisunique
         and i.indimmediate
         and pg_catalog.pg_get_indexdef(i.indexrelid)=
           'CREATE UNIQUE INDEX penta_mail_outbox_provider_message_id_norm_uidx ON public.penta_mail_outbox_v1 USING btree (NULLIF(lower(btrim(btrim(provider_message_id), ''<>''::text)), ''''::text)) WHERE (NULLIF(lower(btrim(btrim(provider_message_id), ''<>''::text)), ''''::text) IS NOT NULL)'
    into v_index_ok
  from pg_catalog.pg_index i
  where i.indexrelid=
    pg_catalog.to_regclass('public.penta_mail_outbox_provider_message_id_norm_uidx');
  if v_index_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_unique_index_drift';
  end if;

  select count(*) into v_bad
  from (
    select nullif(
             pg_catalog.lower(
               pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
             ),
             ''
           ) normalized_provider_message_id
    from public.penta_mail_outbox_v1 ob
    where nullif(
            pg_catalog.lower(
              pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
            ),
            ''
          ) is not null
    group by 1
    having count(*)<>1
  ) collisions;
  if v_bad<>0 then
    raise exception 'mailgun_projector_normalized_correlation_v1_outbox_id_ambiguous:%',v_bad;
  end if;

  -- Pin the authority check, append-only event writer, cron-facing wrapper,
  -- and the balancer executor whose advisory-lock derivation this migration
  -- uses. The executor hash plus the exact semantic marker closes the
  -- check/apply drift window around the worker fence.
  with expected(
    nspname,proname,identity_args,expected_sha,expected_volatility,
    expected_config_count,expected_config
  ) as (
    values
      (
        'integration_control',
        'penta_mail_assert_service_role_v1',
        '',
        'e8d5ddc47ea758901176f26cfc290d3361f48f59e4f959609b5b32c7d03694a8',
        'v'::"char",
        1,
        array['search_path=pg_catalog']::text[]
      ),
      (
        'chlom_runtime',
        'append_dail_event',
        'p_event_type text, p_entity_type text, p_entity_id text, p_payload jsonb, p_actor_ref text, p_actor_did text, p_agent_id text, p_entity_version text, p_correlation_id text, p_causation_id text, p_authority_basis text, p_approval_id text, p_visibility_class text',
        'a91f502d621b732e768584217e0487f39c12114621b0194a5a3a3ba941841f7c',
        'v'::"char",
        2,
        array[
          'search_path=pg_catalog, extensions, chlom_runtime',
          'TimeZone=UTC'
        ]::text[]
      ),
      (
        'public',
        'penta_mail_project_mailgun_events_shaped_v2',
        'p_limit integer',
        '55080130b40e863983f2114280932ba8ab19d86c793bb3862d68846861a2d63d',
        'v'::"char",
        1,
        array[
          'search_path=pg_catalog, public, integration_control, chlom_runtime'
        ]::text[]
      ),
      (
        'penta_balancer',
        'execute_managed_job_v1',
        'p_jobname text',
        'cffc05ccefe7c98befc04177fab1a971feaf55fc15b60251dfbb75b4ca27e2b1',
        'v'::"char",
        1,
        array[
          'search_path=pg_catalog, penta_balancer, extensions, pg_temp'
        ]::text[]
      )
  ), actual as (
    select e.*,p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,
           pg_catalog.encode(
             extensions.digest(
               pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid),'UTF8'),
               'sha256'
             ),
             'hex'
           ) actual_sha
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
           and provolatile=expected_volatility
           and pg_catalog.cardinality(proconfig)=expected_config_count
           and proconfig @> expected_config
           and (
             select count(*)=2
             from pg_catalog.aclexplode(
               coalesce(
                 (select p2.proacl from pg_catalog.pg_proc p2 where p2.oid=actual.oid),
                 pg_catalog.acldefault('f',actual.proowner)
               )
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
               coalesce(
                 (select p2.proacl from pg_catalog.pg_proc p2 where p2.oid=actual.oid),
                 pg_catalog.acldefault('f',actual.proowner)
               )
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
    raise exception 'mailgun_projector_normalized_correlation_v1_dependency_drift';
  end if;

  if pg_catalog.strpos(
       pg_catalog.pg_get_functiondef(
         'penta_balancer.execute_managed_job_v1(text)'::regprocedure
       ),
       'pg_try_advisory_xact_lock(hashtextextended(''ct:pentabalancer:managed-job:''||p_jobname,0))'
     )=0
  then
    raise exception 'mailgun_projector_normalized_correlation_v1_worker_fence_drift';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_rls_drift';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_client_deny_policy_drift';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_runtime_drift';
  end if;

  -- An accepted provider ID must itself be unambiguous before it can authorize
  -- the normalized outbox fallback.
  select count(*) into v_bad
  from (
    select nullif(
             pg_catalog.lower(
               pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
             ),
             ''
           ) normalized_provider_message_id
    from integration_control.penta_mail_provider_attempt_outcomes_v1 o
    join integration_control.penta_mail_provider_attempts_v1 a
      on a.attempt_id=o.attempt_id
    where o.outcome_state='provider_accepted'
      and nullif(
            pg_catalog.lower(
              pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
            ),
            ''
          ) is not null
    group by 1
    having count(*)<>1 or count(distinct a.provider_route_id)<>1
  ) ambiguous_outcomes;
  if v_bad<>0 then
    raise exception 'mailgun_projector_normalized_correlation_v1_provider_outcome_ambiguous:%',v_bad;
  end if;

  with accepted as (
    select a.request_key,
           nullif(
             pg_catalog.lower(
               pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
             ),
             ''
           ) normalized_provider_message_id
    from integration_control.penta_mail_provider_attempts_v1 a
    join integration_control.penta_mail_provider_attempt_outcomes_v1 o
      on o.attempt_id=a.attempt_id
    where o.outcome_state='provider_accepted'
      and nullif(
            pg_catalog.lower(
              pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
            ),
            ''
          ) is not null
  ), legacy as (
    select a.normalized_provider_message_id,ob.message_id
    from accepted a
    join public.penta_mail_outbox_v1 ob
      on a.request_key='penta-outbox:'||ob.message_id::text
  ), fallback as (
    select nullif(
             pg_catalog.lower(
               pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
             ),
             ''
           ) normalized_provider_message_id,
           ob.message_id
    from public.penta_mail_outbox_v1 ob
    where nullif(
            pg_catalog.lower(
              pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
            ),
            ''
          ) is not null
  )
  select count(*) into v_bad
  from legacy l
  join fallback f using(normalized_provider_message_id)
  where l.message_id<>f.message_id;
  if v_bad<>0 then
    raise exception 'mailgun_projector_normalized_correlation_v1_legacy_fallback_conflict:%',v_bad;
  end if;

  select count(*) into v_bad
  from integration_control.penta_mail_mailgun_event_inbox_v1 e
  join public.penta_mail_outbox_v1 ob
    on nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
         ),
         ''
       )=
       nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(e.provider_message_id),'<>')
         ),
         ''
       )
  where e.claimed_penta_message_id is not null
    and e.claimed_penta_message_id<>ob.message_id;
  if v_bad<>0 then
    raise exception 'mailgun_projector_normalized_correlation_v1_claimed_conflict:%',v_bad;
  end if;

  -- Read-only impact proof. At audit time this returned 1,376 and zero
  -- conflicts. The count is deliberately not pinned because this queue is hot.
  with accepted as (
    select nullif(
             pg_catalog.lower(
               pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
             ),
             ''
           ) normalized_provider_message_id,
           a.provider_route_id
    from integration_control.penta_mail_provider_attempt_outcomes_v1 o
    join integration_control.penta_mail_provider_attempts_v1 a
      on a.attempt_id=o.attempt_id
    where o.outcome_state='provider_accepted'
      and nullif(
            pg_catalog.lower(
              pg_catalog.btrim(pg_catalog.btrim(o.provider_message_id),'<>')
            ),
            ''
          ) is not null
  )
  select count(*) into v_safe_backlog
  from integration_control.penta_mail_mailgun_projection_jobs_v1 j
  join integration_control.penta_mail_mailgun_event_inbox_v1 e
    on e.receipt_id=j.receipt_id
  join public.penta_mail_outbox_v1 ob
    on nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
         ),
         ''
       )=
       nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(e.provider_message_id),'<>')
         ),
         ''
       )
  join accepted a
    on a.normalized_provider_message_id=
       nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(e.provider_message_id),'<>')
         ),
         ''
       )
   and a.provider_route_id=e.provider_route_id
  where j.state in ('pending','retry');

  perform pg_catalog.set_config(
    'ct.mailgun_projector_migration.safe_backlog_before',
    v_safe_backlog::text,
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_migration.completed_before',
    (
      select count(*)::text
      from integration_control.penta_mail_mailgun_projection_jobs_v1
      where state='completed'
    ),
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_migration.receipts_before',
    (
      select count(*)::text
      from integration_control.penta_mail_mailgun_projection_receipts_v1
    ),
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_migration.backlog_before',
    (
      select count(*)::text
      from integration_control.penta_mail_mailgun_projection_jobs_v1
      where state in ('pending','retry')
    ),
    true
  );
  perform pg_catalog.set_config(
    'ct.mailgun_projector_migration.relation_acl_before',
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

create function integration_control.penta_mail_provider_accepted_lock_v1()
returns trigger
language plpgsql
security invoker
volatile
set search_path = pg_catalog
as $provider_lock$
declare
  v_old_norm text;
  v_new_norm text;
begin
  if tg_op in ('UPDATE','DELETE')
     and old.outcome_state='provider_accepted'
  then
    v_old_norm := nullif(
      pg_catalog.lower(
        pg_catalog.btrim(pg_catalog.btrim(old.provider_message_id),'<>')
      ),
      ''
    );
  end if;

  if tg_op in ('INSERT','UPDATE')
     and new.outcome_state='provider_accepted'
  then
    v_new_norm := nullif(
      pg_catalog.lower(
        pg_catalog.btrim(pg_catalog.btrim(new.provider_message_id),'<>')
      ),
      ''
    );
  end if;

  -- Updates that move an accepted provider ID lock both identities in stable
  -- lexical order. That prevents change/change deadlocks and protects the old
  -- identity until the projector transaction releases its matching lock.
  if v_old_norm is not null
     and v_new_norm is not null
     and v_old_norm<>v_new_norm
  then
    perform pg_catalog.pg_advisory_xact_lock(
      pg_catalog.hashtextextended(
        'ct:pentamail:provider-accepted:'||
          least(v_old_norm,v_new_norm),
        0
      )
    );
    perform pg_catalog.pg_advisory_xact_lock(
      pg_catalog.hashtextextended(
        'ct:pentamail:provider-accepted:'||
          greatest(v_old_norm,v_new_norm),
        0
      )
    );
  elsif coalesce(v_old_norm,v_new_norm) is not null then
    perform pg_catalog.pg_advisory_xact_lock(
      pg_catalog.hashtextextended(
        'ct:pentamail:provider-accepted:'||
          coalesce(v_old_norm,v_new_norm),
        0
      )
    );
  end if;

  if tg_op='DELETE' then
    return old;
  end if;
  return new;
end;
$provider_lock$;

alter function integration_control.penta_mail_provider_accepted_lock_v1()
  owner to postgres;
revoke all privileges on function
  integration_control.penta_mail_provider_accepted_lock_v1()
  from public, anon, authenticated, service_role;

comment on function
  integration_control.penta_mail_provider_accepted_lock_v1() is
'Internal trigger only: serializes accepted provider-message identity changes with Mailgun projection. No direct caller receives EXECUTE.';

create trigger penta_mail_provider_accepted_lock_v1
before insert or delete or update of outcome_state, provider_message_id
on integration_control.penta_mail_provider_attempt_outcomes_v1
for each row
execute function integration_control.penta_mail_provider_accepted_lock_v1();

do $patch$
declare
  v_oid oid := 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure;
  v_def text := pg_catalog.pg_get_functiondef(v_oid);
  v_old text;
  v_new text;
begin
  v_old := $old_decl$  v_claimed public.penta_mail_outbox_v1%rowtype;
  v_by_provider public.penta_mail_outbox_v1%rowtype;
  v_outbox public.penta_mail_outbox_v1%rowtype;
$old_decl$;
  v_new := $new_decl$  v_claimed public.penta_mail_outbox_v1%rowtype;
  v_by_provider public.penta_mail_outbox_v1%rowtype;
  v_by_provider_id public.penta_mail_outbox_v1%rowtype;
  v_outbox public.penta_mail_outbox_v1%rowtype;
  v_provider_outcome_count integer := 0;
  v_provider_route_match_count integer := 0;
  v_by_provider_message_id uuid;
  v_by_provider_id_message_id uuid;
$new_decl$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_declaration_marker_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $old_reset$      v_claimed := null;
      v_by_provider := null;
      v_outbox := null;
$old_reset$;
  v_new := $new_reset$      v_claimed := null;
      v_by_provider := null;
      v_by_provider_id := null;
      v_outbox := null;
      v_provider_outcome_count := 0;
      v_provider_route_match_count := 0;
      v_by_provider_message_id := null;
      v_by_provider_id_message_id := null;
$new_reset$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_reset_marker_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $old_correlation$      v_provider_norm := nullif(lower(btrim(btrim(v_event.provider_message_id), '<>')),'');
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
$old_correlation$;
  v_new := $new_correlation$      v_provider_norm := nullif(lower(btrim(btrim(v_event.provider_message_id), '<>')),'');
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
$new_correlation$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_correlation_marker_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $old_resolution$      v_message_id := coalesce(v_by_provider.message_id,v_claimed.message_id);
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
$old_resolution$;
  v_new := $new_resolution$      v_message_id := coalesce(
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
$new_resolution$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_resolution_marker_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  v_old := $old_route$      if v_by_provider.message_id is not null then
        v_route_evidence := 'provider_attempt_route';
      elsif v_claimed.message_id is not null then
        v_route_evidence := 'signed_penta_message_binding';
      end if;

$old_route$;
  v_new := $new_route$      if v_by_provider.message_id is not null then
        v_route_evidence := 'provider_attempt_route_and_request_key';
      elsif v_by_provider_id.message_id is not null then
        v_route_evidence :=
          'accepted_provider_route_and_unique_outbox_provider_message_id';
      elsif v_claimed.message_id is not null then
        v_route_evidence := 'signed_penta_message_binding';
      end if;

$new_route$;
  if (
    pg_catalog.length(v_def)-pg_catalog.length(pg_catalog.replace(v_def,v_old,''))
  )<>pg_catalog.length(v_old) then
    raise exception 'mailgun_projector_normalized_correlation_v1_route_marker_drift';
  end if;
  v_def := pg_catalog.replace(v_def,v_old,v_new);

  execute v_def;

  if 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure::oid<>v_oid then
    raise exception 'mailgun_projector_normalized_correlation_v1_oid_changed';
  end if;
end;
$patch$;

alter function public.penta_mail_project_mailgun_events_v1(integer)
  owner to postgres;
revoke all privileges on function public.penta_mail_project_mailgun_events_v1(integer)
  from public, anon, authenticated;
grant execute on function public.penta_mail_project_mailgun_events_v1(integer)
  to postgres, service_role;

comment on function public.penta_mail_project_mailgun_events_v1(integer) is
'Mailgun lifecycle projector v2 with accepted-same-route, uniquely normalized outbox provider-message correlation; request-key correlation remains independent stronger evidence. Forward-only from 2026-09-08; no historical replay.';

do $postflight$
declare
  v_oid oid := 'public.penta_mail_project_mailgun_events_v1(integer)'::regprocedure;
  v_sha text;
  v_acl_ok boolean;
  v_balancer_ok boolean;
  v_guard_ok boolean;
  v_rls_ok boolean;
  v_runtime_ok boolean;
  v_bad bigint;
  v_completed_after bigint;
  v_receipts_after bigint;
  v_backlog_after bigint;
begin
  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(v_oid),'UTF8'),
             'sha256'
           ),
           'hex'
         )
    into v_sha;
  if v_sha<>'afac97979751fcb39b8aea2c9b8094589d8a50d47791fc0897d8b694146879b8' then
    raise exception 'mailgun_projector_normalized_correlation_v1_postimage_drift:%',v_sha;
  end if;

  if pg_catalog.pg_get_function_identity_arguments(v_oid)<>'p_limit integer' then
    raise exception 'mailgun_projector_normalized_correlation_v1_signature_changed';
  end if;

  select p.prosecdef
         and p.provolatile='v'
         and pg_catalog.pg_get_userbyid(p.proowner)='postgres'
         and p.proconfig=array[
           'search_path=pg_catalog, public, integration_control, crm, chlom_runtime, extensions'
         ]::text[]
         and (
           select count(*)=2
           from pg_catalog.aclexplode(
             coalesce(
               p.proacl,
               pg_catalog.acldefault('f',p.proowner)
             )
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
             coalesce(
               p.proacl,
               pg_catalog.acldefault('f',p.proowner)
             )
           ) acl
           where acl.privilege_type='EXECUTE'
             and acl.grantee not in (
               p.proowner,
               pg_catalog.to_regrole('service_role')::oid
             )
         )
    into v_acl_ok
  from pg_catalog.pg_proc p
  where p.oid=v_oid;
  if v_acl_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_acl_failed';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_worker_fence_changed';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_guard_function_failed';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_guard_trigger_failed';
  end if;

  if pg_catalog.pg_get_functiondef(v_oid) not like
       '%PENTAMAIL_MAILGUN_PROVIDER_OUTCOME_AMBIGUOUS%'
     or pg_catalog.pg_get_functiondef(v_oid) not like
       '%accepted_provider_outbox_provider_message_id%'
     or pg_catalog.pg_get_functiondef(v_oid) not like
       '%ct:pentamail:provider-accepted:%'
     or pg_catalog.pg_get_functiondef(v_oid) like
       '%order by o.recorded_at desc%limit 1%'
  then
    raise exception 'mailgun_projector_normalized_correlation_v1_semantic_markers_failed';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_rls_changed';
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
    'ct.mailgun_projector_migration.relation_acl_before'
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_relation_acl_changed';
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
    raise exception 'mailgun_projector_normalized_correlation_v1_client_deny_policy_changed';
  end if;

  if not exists (
    select 1
    from pg_catalog.pg_index i
    where i.indexrelid=
      pg_catalog.to_regclass('public.penta_mail_outbox_provider_message_id_norm_uidx')
      and i.indisvalid and i.indisready and i.indislive
      and i.indisunique and i.indimmediate
      and pg_catalog.pg_get_indexdef(i.indexrelid)=
        'CREATE UNIQUE INDEX penta_mail_outbox_provider_message_id_norm_uidx ON public.penta_mail_outbox_v1 USING btree (NULLIF(lower(btrim(btrim(provider_message_id), ''<>''::text)), ''''::text)) WHERE (NULLIF(lower(btrim(btrim(provider_message_id), ''<>''::text)), ''''::text) IS NOT NULL)'
  ) then
    raise exception 'mailgun_projector_normalized_correlation_v1_unique_index_changed';
  end if;

  select
    exists (
      select 1 from cron.job j
      where j.jobid=1864
        and j.jobname='ct-pentamail-mailgun-projection-v1'
        and j.schedule='* * * * *'
        and j.active
        and j.username='postgres'
    )
    and exists (
      select 1 from penta_balancer.job_policy_v1 p
      where p.jobname='ct-pentamail-mailgun-projection-v1'
        and p.active and p.instrumented
        and p.original_command=
          'select public.penta_mail_project_mailgun_events_shaped_v2(8);'
        and p.original_command_sha256=
          '366438b4f9c9a637e51bbf846fd6b86ccc41f11d3515e25f54b97f25b59502ab'
    )
    into v_runtime_ok;
  if v_runtime_ok is not true then
    raise exception 'mailgun_projector_normalized_correlation_v1_runtime_changed';
  end if;

  -- The migration itself must be data-silent. The managed worker is fenced by
  -- the transaction advisory lock, so completed jobs and receipts stay exact.
  select count(*) into v_completed_after
  from integration_control.penta_mail_mailgun_projection_jobs_v1
  where state='completed';
  select count(*) into v_receipts_after
  from integration_control.penta_mail_mailgun_projection_receipts_v1;
  select count(*) into v_backlog_after
  from integration_control.penta_mail_mailgun_projection_jobs_v1
  where state in ('pending','retry');

  if v_completed_after<>
       pg_catalog.current_setting(
         'ct.mailgun_projector_migration.completed_before'
       )::bigint
     or v_receipts_after<>
       pg_catalog.current_setting(
         'ct.mailgun_projector_migration.receipts_before'
       )::bigint
     or v_backlog_after<
       pg_catalog.current_setting(
         'ct.mailgun_projector_migration.backlog_before'
       )::bigint
  then
    raise exception 'mailgun_projector_normalized_correlation_v1_unexpected_data_effect';
  end if;

  select count(*) into v_bad
  from integration_control.penta_mail_mailgun_event_inbox_v1 e
  join public.penta_mail_outbox_v1 ob
    on nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(ob.provider_message_id),'<>')
         ),
         ''
       )=
       nullif(
         pg_catalog.lower(
           pg_catalog.btrim(pg_catalog.btrim(e.provider_message_id),'<>')
         ),
         ''
       )
  where e.claimed_penta_message_id is not null
    and e.claimed_penta_message_id<>ob.message_id;
  if v_bad<>0 then
    raise exception 'mailgun_projector_normalized_correlation_v1_postflight_conflict:%',v_bad;
  end if;
end;
$postflight$;

commit;

-- Read-only dry-run / impact query (captured result at review: safe_matches=1376,
-- claimed_conflicts=0). It is intentionally not executed by the migration:
--
-- with accepted as (
--   select nullif(lower(btrim(btrim(o.provider_message_id), '<>')),'') norm,
--          a.provider_route_id
--   from integration_control.penta_mail_provider_attempt_outcomes_v1 o
--   join integration_control.penta_mail_provider_attempts_v1 a using(attempt_id)
--   where o.outcome_state='provider_accepted'
-- ), eligible as (
--   select e.claimed_penta_message_id,ob.message_id
--   from integration_control.penta_mail_mailgun_projection_jobs_v1 j
--   join integration_control.penta_mail_mailgun_event_inbox_v1 e using(receipt_id)
--   join public.penta_mail_outbox_v1 ob
--     on nullif(lower(btrim(btrim(ob.provider_message_id), '<>')),'')=
--        nullif(lower(btrim(btrim(e.provider_message_id), '<>')),'')
--   join accepted a
--     on a.norm=nullif(lower(btrim(btrim(e.provider_message_id), '<>')),'')
--    and a.provider_route_id=e.provider_route_id
--   where j.state in ('pending','retry')
-- )
-- select count(*) safe_matches,
--        count(*) filter (
--          where claimed_penta_message_id is not null
--            and claimed_penta_message_id<>message_id
--        ) claimed_conflicts
-- from eligible;

-- Hot-path canary after commit:
--   1. Do not manually replay or requeue anything. Let the next managed batch of
--      eight run naturally.
--   2. Confirm cron job 1864 succeeds within its 28-second budget.
--   3. Inspect only the eight newest projection receipts. Expected fallback
--      telemetry is correlation_basis=accepted_provider_outbox_provider_message_id
--      (or the corresponding *_and_penta value), with the exact accepted route.
--   4. Confirm no correlation-conflict error, no duplicate
--      (inbox_receipt_id,attempt_no), and no completed historical job changed.
--   5. Run Supabase security/performance advisors and API health probes.
