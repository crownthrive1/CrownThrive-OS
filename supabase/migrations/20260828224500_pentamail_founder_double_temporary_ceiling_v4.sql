-- CrownThrive OS / PentaMail
-- Founder correction: preserve exact provider-email seconds as the timed gateway,
-- double the temporary CrownThrive authorization ceiling to 200/hour, and let the
-- CrownThrive static hourly ceiling disappear when the gateway expires. Provider
-- advertised/enforced limits remain authoritative and may reduce effective rate.

begin;

create or replace function integration_control.penta_mail_enforce_founder_temp_ceiling_v4()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
begin
  if new.policy_key='mailgun-foundation-growth-v1'
     and new.crownthrive_temporary_authorization_ceiling is not null then
    new.crownthrive_temporary_authorization_ceiling:=200;
    new.metadata:=
      (coalesce(new.metadata,'{}'::jsonb)-'founder_temporary_ceiling_v4')
      || jsonb_build_object(
        'founder_temporary_ceiling_v4',jsonb_build_object(
          'configured_hourly_authorization_ceiling',200,
          'temporary_only',true,
          'expires_with_provider_email_gateway',true,
          'provider_ceiling_remains_authoritative',true,
          'static_crownthrive_hourly_cap_removed_after_gateway',true,
          'directive','double the temporary authorization ceiling; do not bypass provider throttles'
        )
      );
  end if;
  return new;
end
$function$;

drop trigger if exists penta_mail_founder_temp_ceiling_v4
  on integration_control.penta_mail_growth_policy_v1;

create trigger penta_mail_founder_temp_ceiling_v4
before insert or update of crownthrive_temporary_authorization_ceiling,metadata
on integration_control.penta_mail_growth_policy_v1
for each row
execute function integration_control.penta_mail_enforce_founder_temp_ceiling_v4();

update integration_control.penta_mail_growth_policy_v1
set crownthrive_temporary_authorization_ceiling=200,
    metadata=(coalesce(metadata,'{}'::jsonb)-'founder_temporary_ceiling_v4')
      || jsonb_build_object(
        'founder_temporary_ceiling_v4',jsonb_build_object(
          'configured_hourly_authorization_ceiling',200,
          'temporary_only',true,
          'expires_with_provider_email_gateway',true,
          'provider_ceiling_remains_authoritative',true,
          'static_crownthrive_hourly_cap_removed_after_gateway',true,
          'directive','double the temporary authorization ceiling; do not bypass provider throttles'
        )
      ),
    updated_at=clock_timestamp()
where policy_key='mailgun-foundation-growth-v1';

update integration_control.penta_mail_provider_limit_notice_v1
set evidence=(coalesce(evidence,'{}'::jsonb)
      -'crownthrive_temporary_hourly_authorization_ceiling'
      -'configured_temporary_authorization_ceiling')
      || jsonb_build_object(
        'crownthrive_temporary_hourly_authorization_ceiling',200,
        'configured_temporary_authorization_ceiling',200,
        'temporary_only',true,
        'provider_ceiling_remains_authoritative',true,
        'crownthrive_static_hourly_limit_removed_after_gateway',true,
        'corrected_by','ct-founder-directive-pentamail-double-temp-ceiling-20260828-v4'
      ),
    updated_at=clock_timestamp()
where provider_route_id='mailgun:relay.crownthrive.com';

-- Preserve the v3 exact-seconds gateway. The effective-rate function already
-- computes least(CrownThrive temporary authorization, provider observed cap),
-- so a Mailgun-advertised 100/hour probation ceiling remains 100/hour until
-- fresh provider evidence changes or removes that provider constraint.

do $evidence$
declare
  v_notice integration_control.penta_mail_provider_limit_notice_v1%rowtype;
  v_incident uuid;
begin
  select * into v_notice
  from integration_control.penta_mail_provider_limit_notice_v1
  where provider_route_id='mailgun:relay.crownthrive.com'
  order by received_at desc,created_at desc,notice_id desc
  limit 1;

  select active_incident_id into v_incident
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id='mailgun:relay.crownthrive.com';

  if found then
    perform integration_control.penta_mail_append_control_event_v1(
      'founder-temp-ceiling-v4:'||coalesce(v_notice.notice_id::text,'none'),
      'mailgun.founder_temporary_authorization_ceiling.doubled',
      v_incident,
      null,
      jsonb_build_object(
        'configured_temporary_authorization_ceiling',200,
        'temporary_only',true,
        'provider_observed_hourly_cap',v_notice.observed_hourly_cap,
        'provider_ceiling_remains_authoritative',true,
        'gateway_seconds',v_notice.gateway_seconds,
        'gateway_until',v_notice.gateway_until,
        'static_crownthrive_hourly_cap_removed_after_gateway',true
      ),
      'ct-founder-directive-pentamail-double-temp-ceiling-20260828-v4'
    );
  end if;
end
$evidence$;

commit;