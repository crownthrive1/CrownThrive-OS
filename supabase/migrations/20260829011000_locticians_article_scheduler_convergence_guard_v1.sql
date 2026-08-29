-- CrownThrive OS / PentaMarketer / Locticians
-- Production convergence guard for the provider-scheduled next-five batch.
-- This guard is intentionally non-destructive: it certifies the production
-- migration series and prevents release if the runtime contract drifts.

begin;

do $guard$
declare
  v_count integer;
  v_bad integer;
  v_route record;
  v_persona record;
begin
  if to_regclass('integration_control.locticians_article_schedule_v1') is null then
    raise exception 'LOCTICIANS_ARTICLE_SCHEDULE_TABLE_MISSING';
  end if;
  if to_regclass('integration_control.locticians_article_schedule_events_v1') is null then
    raise exception 'LOCTICIANS_ARTICLE_SCHEDULE_EVENTS_MISSING';
  end if;

  if to_regprocedure('public.locticians_article_schedule_simulate_v1(text,integer)') is null
     or to_regprocedure('integration_control.locticians_article_schedule_provider_duplicate_check_v1(uuid)') is null
     or to_regprocedure('integration_control.locticians_article_schedule_provider_create_guarded_v2(uuid)') is null
     or to_regprocedure('integration_control.locticians_article_schedule_reverify_one_v1(uuid)') is null
     or to_regprocedure('public.locticians_article_schedule_dispatch_v1(integer)') is null
     or to_regprocedure('public.locticians_article_schedule_due_verifier_v1(integer)') is null
     or to_regprocedure('public.locticians_article_schedule_status_v1(text)') is null then
    raise exception 'LOCTICIANS_ARTICLE_SCHEDULER_FUNCTION_SET_INCOMPLETE';
  end if;

  select * into v_route
  from integration_control.site_publish_routes
  where route_id='ct.route.locticians.bd-articles.production.v1';

  if not found
     or v_route.route_state<>'active'
     or not v_route.auto_publish_if_release_pass
     or v_route.feed_consumer_state<>'verified'
     or v_route.metadata #>> '{provider_identifiers,user_id}'<>'5'
     or v_route.metadata #>> '{provider_identifiers,data_id}'<>'14'
     or v_route.metadata #>> '{provider_identifiers,data_type}'<>'20' then
    raise exception 'LOCTICIANS_PROVIDER_ROUTE_BINDING_DRIFT';
  end if;

  select * into v_persona
  from crm.penta_persona_publish_test_runs_v1
  order by completed_at desc
  limit 1;

  if not found
     or v_persona.overall_state<>'pass'
     or v_persona.expected_personas<>39
     or v_persona.observed_personas<>39
     or v_persona.total_tests<>235
     or v_persona.passed_tests<>235
     or v_persona.hold_tests<>0
     or v_persona.failed_tests<>0 then
    raise exception 'LOCTICIANS_PERSONA_CERTIFICATION_DRIFT';
  end if;

  select count(*) into v_count
  from integration_control.locticians_article_schedule_v1
  where batch_ref='locticians.next5.2026-08-29.v1';

  if v_count<>5 then
    raise exception 'LOCTICIANS_NEXT_FIVE_COUNT_DRIFT: %',v_count;
  end if;

  select count(*) into v_bad
  from integration_control.locticians_article_schedule_v1
  where batch_ref='locticians.next5.2026-08-29.v1'
    and (
      state<>'scheduled'
      or provider_user_id<>5
      or provider_data_id<>14
      or provider_data_type<>20
      or provider_post_id not between 4177 and 4181
      or provider_create_http_status<>200
      or audit_decision<>'approve'
      or image_present
      or image_rights_state<>'not_applicable_image_absent'
      or content_sha256<>provider_content_sha256
      or coalesce((provider_readback #>> '{reverification,exact_readback_pass}')::boolean,false) is not true
      or scheduled_for<>provider_post_live_date
    );

  if v_bad<>0 then
    raise exception 'LOCTICIANS_NEXT_FIVE_PROVIDER_READBACK_DRIFT: %',v_bad;
  end if;

  if not exists(
    select 1 from cron.job
    where jobname='ct-locticians-article-schedule-dispatch-v1'
      and active
      and schedule='5,15,25,35,45,55 * * * *'
  ) then
    raise exception 'LOCTICIANS_ARTICLE_DISPATCH_CRON_MISSING';
  end if;

  if not exists(
    select 1 from cron.job
    where jobname='ct-locticians-article-live-verifier-v1'
      and active
      and schedule='*/10 * * * *'
  ) then
    raise exception 'LOCTICIANS_ARTICLE_LIVE_VERIFIER_CRON_MISSING';
  end if;
end
$guard$;

comment on table integration_control.locticians_article_schedule_v1 is
'Forced-RLS, service-role-only Locticians provider scheduling ledger. Exact provider binding: user_id=5, data_id=14, data_type=20. Create attempts are bounded; ambiguous outcomes quarantine; images require verified rights.';

comment on function public.locticians_article_schedule_dispatch_v1(integer) is
'Autonomous bounded dispatcher for independently audited, simulated Locticians article schedules. Executes provider duplicate search, one-attempt create, and exact post-ID/content/date readback.';

comment on function public.locticians_article_schedule_due_verifier_v1(integer) is
'Every-ten-minute verifier that promotes due provider-scheduled Locticians articles to live_verified only after exact provider readback.';

select chlom_runtime.append_dail_event(
  'locticians.article_scheduler.github_convergence_guard',
  'source_control_convergence',
  'ct.pentamarketer.locticians.next-five-schedule.v1',
  jsonb_build_object(
    'batch_ref','locticians.next5.2026-08-29.v1',
    'scheduled_posts',jsonb_build_array(4177,4178,4179,4180,4181),
    'provider_binding',jsonb_build_object('user_id',5,'data_id',14,'data_type',20),
    'dispatch_cron','ct-locticians-article-schedule-dispatch-v1',
    'live_verifier_cron','ct-locticians-article-live-verifier-v1',
    'manifest','data/penta/locticians-next-five-schedule.20260829.v1.json',
    'secret_material_committed',false,
    'verified_at',clock_timestamp()
  ),
  'PentaMarketer/PentaPublish/PentaCertify',
  null,
  'PentaCertify',
  '1.0.0',
  'ctcorr:locticians-next5-20260829',
  null,
  'D2_FOUNDER_DIRECTIVE',
  null,
  'internal'
);

commit;
