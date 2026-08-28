-- PentaMail hourly system-change digest payload hardening v2
-- Fixes PENTAMAIL_INVALID_BODY under high event volume by emitting one bounded
-- summary digest per window instead of attempting to inline every event.
-- The full append-only event stream remains authoritative in os_v2.system_change_events.
-- No provider authority, recipient scope, money movement, rights, entitlement,
-- credential exposure, vote/quorum effect, or D3 authority is added.

create or replace function public.penta_hourly_system_change_digest_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control','os_v2','extensions'
as $function$
declare
  v_end timestamptz:=clock_timestamp();
  v_start timestamptz;
  v_count integer;
  v_body text;
  v_subject text;
  v_message uuid;
  v_sources jsonb;
  v_pentas jsonb;
  v_sha text;
  v_prev text;
  v_chain text;
  v_recipient text;
  v_group_summary text;
  v_recent text;
  v_truncated boolean:=false;
begin
  select recipient into v_recipient
  from integration_control.penta_hourly_update_policy_v1
  where enabled=true
  order by effective_at desc,created_at desc limit 1;
  if v_recipient is null then raise exception 'PENTA_HOURLY_POLICY_MISSING'; end if;

  select max(window_end) into v_start from integration_control.penta_change_digest_receipts_v1;
  v_start:=coalesce(v_start,v_end-interval '1 hour');
  if v_start>=v_end then
    return jsonb_build_object('ok',true,'state','no_window','window_start',v_start,'window_end',v_end);
  end if;

  select count(*) into v_count
  from os_v2.system_change_events
  where occurred_at>v_start and occurred_at<=v_end;

  v_pentas:=integration_control.penta_change_digest_source_pentas_v1(v_start,v_end);

  select coalesce(jsonb_agg(x.source_system order by x.source_system),'[]'::jsonb)
  into v_sources
  from (
    select distinct source_system
    from os_v2.system_change_events
    where occurred_at>v_start and occurred_at<=v_end
  ) x;

  if v_count=0 then
    select chain_sha256 into v_prev
    from integration_control.penta_change_digest_receipts_v1
    order by created_at desc,digest_id desc limit 1;

    v_chain:=encode(extensions.digest(convert_to(
      coalesce(v_prev,'GENESIS')||'|'||v_start::text||'|'||v_end::text||'|no_changes|'||v_pentas::text,
      'UTF8'),'sha256'),'hex');

    insert into integration_control.penta_change_digest_receipts_v1(
      window_start,window_end,digest_state,event_count,part_no,total_parts,
      source_systems,source_pentas,previous_chain_sha256,chain_sha256,metadata
    ) values(
      v_start,v_end,'no_changes',0,0,0,v_sources,v_pentas,v_prev,v_chain,
      jsonb_build_object(
        'email_enqueued',false,
        'reason','no_recorded_system_changes',
        'authority_expansion',false
      )
    );

    return jsonb_build_object(
      'ok',true,'state','no_changes','window_start',v_start,'window_end',v_end,
      'event_count',0,'source_pentas',v_pentas,'append_only',true
    );
  end if;

  select string_agg(
    format('%s | %s | %s | count=%s',
      g.severity,g.source_system,g.event_type,g.event_count),
    E'\n' order by g.event_count desc,g.source_system,g.event_type,g.severity
  )
  into v_group_summary
  from (
    select
      upper(left(coalesce(severity,'INFO'),16)) as severity,
      left(coalesce(source_system,'unknown'),80) as source_system,
      left(coalesce(event_type,'unknown'),100) as event_type,
      count(*) as event_count
    from os_v2.system_change_events
    where occurred_at>v_start and occurred_at<=v_end
    group by 1,2,3
    order by event_count desc,source_system,event_type,severity
    limit 30
  ) g;

  select string_agg(
    format(E'[%s] %s | %s | %s\n%s\nEntity: %s\n',
      upper(left(coalesce(e.severity,'INFO'),16)),
      to_char(e.occurred_at at time zone 'America/New_York','YYYY-MM-DD HH24:MI:SS'),
      left(coalesce(e.source_system,'unknown'),80),
      left(coalesce(e.event_type,'unknown'),100),
      left(regexp_replace(coalesce(e.summary,''),E'[\\r\\n]+',' ','g'),320),
      left(coalesce(e.entity_ref,'n/a'),140)
    ),
    E'\n' order by e.occurred_at desc,e.event_id desc
  )
  into v_recent
  from (
    select *
    from os_v2.system_change_events
    where occurred_at>v_start and occurred_at<=v_end
    order by occurred_at desc,event_id desc
    limit 10
  ) e;

  v_body:=format(E'CROWNTHRIVE — HOURLY SYSTEM CHANGE DIGEST\n=========================================\nWindow: %s → %s\nTotal recorded changes in window: %s\nSource Pentas: %s\n\nTop change groups (max 30)\n--------------------------\n%s\n\nMost recent events (max 10)\n---------------------------\n%s\n\nContinuity\n• The complete event stream remains preserved append-only in ThriveBase.\n• This email is a bounded operational summary, not a replacement for the event ledger.\n• Raw credentials, OAuth tokens, recovery codes, provider secrets, and private identity mappings are excluded.\n• PentaMail transport and provider lifecycle retain separate append-only receipts.\n',
    to_char(v_start at time zone 'America/New_York','YYYY-MM-DD HH24:MI:SS'),
    to_char(v_end at time zone 'America/New_York','YYYY-MM-DD HH24:MI:SS'),
    v_count,
    v_pentas::text,
    coalesce(v_group_summary,'(none)'),
    coalesce(v_recent,'(none)')
  );

  if length(v_body)>11500 then
    v_body:=left(v_body,11350)||E'\n\n[Digest body bounded to PentaMail transport limit; full event stream remains in ThriveBase.]\n';
    v_truncated:=true;
  end if;

  v_subject:=format('[Penta Change Digest] %s recorded changes',v_count);
  v_sha:=encode(extensions.digest(convert_to(v_body,'UTF8'),'sha256'),'hex');

  v_message:=public.penta_mail_enqueue_v1(
    'penta_hourly_system_change_digest',
    'INFO',
    v_subject,
    v_body,
    'penta-change-digest-'||to_char(v_end at time zone 'UTC','YYYYMMDDHH24MI'),
    jsonb_build_object(
      'source_penta','PentaReports',
      'source_pentas',v_pentas,
      'delivery_penta','PentaMail',
      'window_start',v_start,
      'window_end',v_end,
      'part_no',1,
      'total_parts',1,
      'event_count',v_count,
      'summary_group_limit',30,
      'recent_sample_limit',10,
      'body_bounded',true,
      'body_truncated',v_truncated,
      'full_event_stream_preserved',true,
      'secrets_included',false,
      'authority_expansion',false
    ),
    v_recipient
  );

  select chain_sha256 into v_prev
  from integration_control.penta_change_digest_receipts_v1
  order by created_at desc,digest_id desc limit 1;

  v_chain:=encode(extensions.digest(convert_to(
    coalesce(v_prev,'GENESIS')||'|'||v_start::text||'|'||v_end::text||'|1|'||
    v_message::text||'|'||v_sha||'|'||v_pentas::text,
    'UTF8'),'sha256'),'hex');

  insert into integration_control.penta_change_digest_receipts_v1(
    window_start,window_end,digest_state,event_count,part_no,total_parts,message_id,
    source_systems,source_pentas,body_sha256,previous_chain_sha256,chain_sha256,metadata
  ) values(
    v_start,v_end,'queued',v_count,1,1,v_message,v_sources,v_pentas,v_sha,v_prev,v_chain,
    jsonb_build_object(
      'email_enqueued',true,
      'summary_group_limit',30,
      'recent_sample_limit',10,
      'body_length',length(v_body),
      'body_truncated',v_truncated,
      'full_event_stream_preserved',true,
      'authority_expansion',false
    )
  );

  perform public.penta_mail_outbox_dispatch_v1();

  return jsonb_build_object(
    'ok',true,
    'state','queued',
    'window_start',v_start,
    'window_end',v_end,
    'event_count',v_count,
    'parts',1,
    'body_length',length(v_body),
    'body_truncated',v_truncated,
    'source_systems',v_sources,
    'source_pentas',v_pentas,
    'append_only',true,
    'authority_expansion',false
  );
end
$function$;

revoke all on function public.penta_hourly_system_change_digest_v1() from public, anon, authenticated;
grant execute on function public.penta_hourly_system_change_digest_v1() to service_role;
