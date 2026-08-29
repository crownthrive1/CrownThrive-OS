-- CrownThrive OS — PentaSELF repository_dispatch envelope hotfix
-- GitHub repository_dispatch accepts at most 10 top-level client_payload properties.
-- Preserve the full remediation packet under one top-level `finding` property.

create or replace function public.penta_self_dispatch_pr_handoffs_v1(p_limit integer default 10)
returns jsonb
language plpgsql
security definer
set search_path = penta_self, public, vault, net
as $$
declare
  v_token text;
  v_row penta_self.remediation_handoffs_v1%rowtype;
  v_request_id bigint;
  v_count integer := 0;
  v_limit integer := greatest(1, least(coalesce(p_limit,10),25));
begin
  select decrypted_secret into v_token
  from vault.decrypted_secrets
  where name = 'PENTA_PM_GITHUB_TOKEN'
  limit 1;

  if coalesce(v_token,'') = '' then
    raise exception 'PENTA_PM_GITHUB_TOKEN unavailable: fail closed';
  end if;

  for v_row in
    select *
    from penta_self.remediation_handoffs_v1
    where state in ('queued','deferred')
      and next_attempt_at <= now()
      and attempts < max_attempts
    order by
      case payload->>'priority' when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,
      queued_at,
      created_at
    for update skip locked
    limit v_limit
  loop
    select net.http_post(
      url := 'https://api.github.com/repos/crownthrive1/CrownThrive-OS/dispatches',
      body := jsonb_build_object(
        'event_type','penta-self-remediation',
        'client_payload',jsonb_build_object('finding',v_row.payload)
      ),
      headers := jsonb_build_object(
        'Authorization','Bearer ' || v_token,
        'Accept','application/vnd.github+json',
        'X-GitHub-Api-Version','2022-11-28',
        'Content-Type','application/json',
        'User-Agent','CrownThrive-PentaSELF-PentaPR/1.1'
      ),
      timeout_milliseconds := 15000
    ) into v_request_id;

    update penta_self.remediation_handoffs_v1
      set state='dispatching',
          request_id=v_request_id,
          attempts=attempts+1,
          last_dispatch_at=now(),
          last_http_status=null,
          last_error=null,
          updated_at=now()
      where handoff_id=v_row.handoff_id;
    v_count := v_count + 1;
  end loop;

  return jsonb_build_object(
    'state','DISPATCHING',
    'authority','PentaSELF',
    'dispatched_requests',v_count,
    'receiver','PentaPR',
    'repo','crownthrive1/CrownThrive-OS',
    'wire_schema','ct.penta.self.repository-dispatch-envelope.v1'
  );
end
$$;

-- Re-arm any first-attempt rows created by the pre-hotfix envelope. The payload itself
-- remains unchanged; only transport state is reset. Existing per-problem dedupe keys
-- and material hashes continue to prevent duplicate remediation records.
update penta_self.remediation_handoffs_v1
set state='queued',
    request_id=null,
    attempts=0,
    last_http_status=null,
    last_error='rearmed after GitHub repository_dispatch client_payload envelope correction',
    next_attempt_at=now(),
    last_dispatch_at=null,
    dispatched_at=null,
    updated_at=now()
where state in ('dispatching','failed','deferred')
  and dispatched_at is null;

-- Restore the every-minute production heartbeat only after the corrected dispatch
-- function and workflow receiver are version-controlled together.
do $$
declare v_job_id bigint;
begin
  select jobid into v_job_id from cron.job where jobname='ct-penta-self-pr-pm-handoff-v1' limit 1;
  if v_job_id is not null then perform cron.unschedule(v_job_id); end if;
end $$;
select cron.schedule(
  'ct-penta-self-pr-pm-handoff-v1',
  '* * * * *',
  'select public.penta_self_pr_handoff_tick_v1();'
);

comment on function public.penta_self_dispatch_pr_handoffs_v1(integer) is
  'Dispatches replay-safe PentaSELF remediation packets to PentaPR using a GitHub-compliant nested client_payload envelope.';
