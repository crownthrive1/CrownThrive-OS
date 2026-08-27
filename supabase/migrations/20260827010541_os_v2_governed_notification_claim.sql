-- OS V2 notification claim boundary for PentaMail controlled release.
-- Claims at most two eligible messages only after the global route gate passes.

create or replace function os_v2.claim_mail_notifications_v1(p_limit integer default 2)
returns setof os_v2.notifications
language plpgsql
security definer
set search_path = pg_catalog, public, os_v2, integration_control
as $$
declare
  v_limit integer := greatest(1, least(coalesce(p_limit, 2), 2));
  v_status jsonb;
  v_now timestamptz := clock_timestamp();
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_status := public.penta_mail_provider_status_v1(null);
  if v_status ->> 'route_state' not in ('closed','controlled_release') then
    return;
  end if;
  update os_v2.notifications
  set state = 'failed',
      last_error = 'stale_sending_reconciliation_required'
  where state = 'sending'
    and last_attempt_at < v_now - interval '5 minutes';
  return query
  with candidates as (
    select n.notification_id
    from os_v2.notifications n
    where n.state = 'queued'
      and n.available_at <= v_now
      and not exists (
        select 1
        from integration_control.penta_mail_trigger_probation_v1 p
        where p.trigger_ref = n.trigger_ref
          and p.probation_until > v_now
      )
    order by case n.severity
      when 'critical' then 1 when 'warning' then 2 else 3 end,
      n.created_at,
      n.notification_id
    for update skip locked
    limit v_limit
  )
  update os_v2.notifications n
  set state = 'sending',
      attempt_count = n.attempt_count + 1,
      last_attempt_at = v_now
  from candidates c
  where n.notification_id = c.notification_id
  returning n.*;
end
$$;

revoke all on function os_v2.claim_mail_notifications_v1(integer)
  from public, anon, authenticated;
grant execute on function os_v2.claim_mail_notifications_v1(integer)
  to service_role;

comment on function os_v2.claim_mail_notifications_v1(integer) is
  'Service-role-only claim of at most two route-eligible OS notifications; active causal probation and provider hold both fail closed.';
