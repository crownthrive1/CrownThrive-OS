-- CrownThrive OS — PentaSELF repository_dispatch envelope hotfix
-- GitHub repository_dispatch accepts at most 10 top-level client_payload properties.
-- Preserve the full remediation packet under one top-level `finding` property.
-- A problem that resolves before dispatch is retained as skipped evidence and is not
-- converted into a stale corrective PR. If it later reopens, PentaSELF requeues it.

alter table penta_self.remediation_handoffs_v1
  drop constraint if exists remediation_handoffs_v1_state_check;
alter table penta_self.remediation_handoffs_v1
  add constraint remediation_handoffs_v1_state_check
  check (state in ('queued','dispatching','dispatched','deferred','failed','skipped'));

create or replace function public.penta_self_queue_pr_handoffs_v1()
returns jsonb
language plpgsql
security definer
set search_path = penta_self, public, extensions
as $$
declare
  v_problem penta_self.problem_ledger_v1%rowtype;
  v_payload jsonb;
  v_material_state jsonb;
  v_sha text;
  v_queued integer := 0;
  v_changed integer := 0;
  v_owner_array jsonb;
begin
  for v_problem in
    select *
    from penta_self.problem_ledger_v1
    where persistent is true
      and state not in ('resolved','closed')
    order by
      case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,
      last_seen_at desc
  loop
    select coalesce(jsonb_agg(trim(x)) filter (where trim(x) <> ''), '[]'::jsonb)
      into v_owner_array
    from unnest(regexp_split_to_array(coalesce(v_problem.owner_penta,''), '\s*/\s*')) as x;

    v_payload := jsonb_build_object(
      'schema', 'ct.penta.self.problem-remediation.v1',
      'finding_id', v_problem.problem_id::text,
      'problem_id', v_problem.problem_id::text,
      'fingerprint', v_problem.fingerprint,
      'source_kind', v_problem.source_kind,
      'source_system', v_problem.source_system,
      'source_ref', v_problem.source_ref,
      'category', v_problem.category,
      'severity', v_problem.severity,
      'priority', v_problem.priority,
      'risk', coalesce(nullif(v_problem.authority_class,''), 'D1'),
      'lane', penta_self.remediation_lane_v1(v_problem.category, v_problem.source_system),
      'state', v_problem.state,
      'target_ref', coalesce(v_problem.source_ref, v_problem.source_system, ''),
      'symptom', coalesce(v_problem.title, v_problem.summary, 'PentaSELF persistent problem'),
      'summary', v_problem.summary,
      'required_pentas', v_owner_array,
      'handler_key', v_problem.handler_key,
      'attempt_count', v_problem.attempt_count,
      'blocked_reason', v_problem.blocked_reason,
      'auto_heal_allowed', v_problem.auto_heal_allowed,
      'acceptance_criteria', jsonb_build_array(
        'Resolve the observed PentaSELF problem without weakening existing governance or evidence gates.',
        'Add or update the repair implementation, automated tests, and provider/runtime readback evidence required for the affected lane.',
        'PentaSELF must independently verify the repaired condition before the problem can be closed.'
      ),
      'evidence', jsonb_build_object(
        'problem_evidence', coalesce(v_problem.evidence,'{}'::jsonb),
        'verification_evidence', coalesce(v_problem.verification_evidence,'{}'::jsonb),
        'first_seen_at', v_problem.first_seen_at,
        'last_seen_at', v_problem.last_seen_at,
        'last_attempt_at', v_problem.last_attempt_at,
        'last_error', v_problem.last_error
      )
    );

    v_material_state := jsonb_build_object(
      'problem_id', v_problem.problem_id::text,
      'fingerprint', v_problem.fingerprint,
      'category', v_problem.category,
      'severity', v_problem.severity,
      'priority', v_problem.priority,
      'risk', coalesce(nullif(v_problem.authority_class,''), 'D1'),
      'lane', penta_self.remediation_lane_v1(v_problem.category, v_problem.source_system),
      'state', v_problem.state,
      'target_ref', coalesce(v_problem.source_ref, v_problem.source_system, ''),
      'symptom', coalesce(v_problem.title, v_problem.summary, 'PentaSELF persistent problem'),
      'required_pentas', v_owner_array,
      'handler_key', v_problem.handler_key,
      'blocked_reason', v_problem.blocked_reason,
      'auto_heal_allowed', v_problem.auto_heal_allowed
    );
    v_sha := encode(extensions.digest(v_material_state::text, 'sha256'), 'hex');

    insert into penta_self.remediation_handoffs_v1(
      problem_id, dedupe_key, state, payload, payload_sha256, next_attempt_at, queued_at, updated_at
    ) values (
      v_problem.problem_id,
      'pentaself:problem:' || v_problem.problem_id::text,
      'queued',
      v_payload,
      v_sha,
      now(),
      now(),
      now()
    )
    on conflict (problem_id) do update
      set payload = excluded.payload,
          payload_sha256 = excluded.payload_sha256,
          state = case
            when penta_self.remediation_handoffs_v1.state = 'skipped'
              then 'queued'
            when penta_self.remediation_handoffs_v1.payload_sha256 is distinct from excluded.payload_sha256
              and penta_self.remediation_handoffs_v1.state <> 'dispatching'
              then 'queued'
            else penta_self.remediation_handoffs_v1.state
          end,
          attempts = case
            when penta_self.remediation_handoffs_v1.state = 'skipped'
              then 0
            when penta_self.remediation_handoffs_v1.payload_sha256 is distinct from excluded.payload_sha256
              and penta_self.remediation_handoffs_v1.state <> 'dispatching'
              then 0
            else penta_self.remediation_handoffs_v1.attempts
          end,
          next_attempt_at = case
            when penta_self.remediation_handoffs_v1.state = 'skipped'
              then now()
            when penta_self.remediation_handoffs_v1.payload_sha256 is distinct from excluded.payload_sha256
              and penta_self.remediation_handoffs_v1.state <> 'dispatching'
              then now()
            else penta_self.remediation_handoffs_v1.next_attempt_at
          end,
          last_error = case
            when penta_self.remediation_handoffs_v1.state = 'skipped'
              then 'requeued because PentaSELF reports the problem persistent and unresolved again'
            when penta_self.remediation_handoffs_v1.payload_sha256 is distinct from excluded.payload_sha256
              and penta_self.remediation_handoffs_v1.state <> 'dispatching'
              then null
            else penta_self.remediation_handoffs_v1.last_error
          end,
          updated_at = now();

    v_queued := v_queued + 1;
  end loop;

  -- Suppress any unsent handoff whose source problem resolved after it was queued.
  update penta_self.remediation_handoffs_v1 h
  set state='skipped',
      request_id=null,
      last_error='not dispatched: PentaSELF problem resolved/closed or is no longer persistent before corrective PR creation',
      next_attempt_at=now() + interval '100 years',
      updated_at=now()
  where h.dispatched_at is null
    and h.state in ('queued','deferred','failed')
    and not exists (
      select 1
      from penta_self.problem_ledger_v1 p
      where p.problem_id=h.problem_id
        and p.persistent is true
        and p.state not in ('resolved','closed')
    );

  select count(*) into v_changed
  from penta_self.remediation_handoffs_v1 h
  where h.state in ('queued','deferred')
    and h.next_attempt_at <= now()
    and exists (
      select 1
      from penta_self.problem_ledger_v1 p
      where p.problem_id=h.problem_id
        and p.persistent is true
        and p.state not in ('resolved','closed')
    );

  return jsonb_build_object(
    'state','QUEUED',
    'authority','PentaSELF',
    'persistent_problems_seen',v_queued,
    'ready_handoffs',v_changed,
    'next_authority','PentaPR'
  );
end
$$;

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

  -- Skip anything whose PentaSELF source ledger no longer says persistent+unresolved.
  update penta_self.remediation_handoffs_v1 h
  set state='skipped',
      request_id=null,
      last_error='not dispatched: PentaSELF problem resolved/closed or is no longer persistent before corrective PR creation',
      next_attempt_at=now() + interval '100 years',
      updated_at=now()
  where h.dispatched_at is null
    and h.state in ('queued','deferred')
    and not exists (
      select 1
      from penta_self.problem_ledger_v1 p
      where p.problem_id=h.problem_id
        and p.persistent is true
        and p.state not in ('resolved','closed')
    );

  for v_row in
    select h.*
    from penta_self.remediation_handoffs_v1 h
    where h.state in ('queued','deferred')
      and h.next_attempt_at <= now()
      and h.attempts < h.max_attempts
      and exists (
        select 1
        from penta_self.problem_ledger_v1 p
        where p.problem_id=h.problem_id
          and p.persistent is true
          and p.state not in ('resolved','closed')
      )
    order by
      case h.payload->>'priority' when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,
      h.queued_at,
      h.created_at
    for update of h skip locked
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

-- Preserve stale pre-hotfix rows as skipped evidence rather than creating PRs for
-- problems that PentaSELF has already resolved or closed.
update penta_self.remediation_handoffs_v1 h
set state='skipped',
    request_id=null,
    attempts=0,
    last_http_status=null,
    last_error='not replayed: PentaSELF problem resolved/closed or is no longer persistent before corrected dispatch',
    next_attempt_at=now() + interval '100 years',
    last_dispatch_at=null,
    dispatched_at=null,
    updated_at=now()
where h.state in ('dispatching','failed','deferred')
  and h.dispatched_at is null
  and not exists (
    select 1
    from penta_self.problem_ledger_v1 p
    where p.problem_id=h.problem_id
      and p.persistent is true
      and p.state not in ('resolved','closed')
  );

-- Re-arm only problems PentaSELF still declares persistent and unresolved.
update penta_self.remediation_handoffs_v1 h
set state='queued',
    request_id=null,
    attempts=0,
    last_http_status=null,
    last_error='rearmed after GitHub repository_dispatch client_payload envelope correction',
    next_attempt_at=now(),
    last_dispatch_at=null,
    dispatched_at=null,
    updated_at=now()
where h.state in ('dispatching','failed','deferred')
  and h.dispatched_at is null
  and exists (
    select 1
    from penta_self.problem_ledger_v1 p
    where p.problem_id=h.problem_id
      and p.persistent is true
      and p.state not in ('resolved','closed')
  );

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
  'Dispatches replay-safe PentaSELF remediation packets to PentaPR using a GitHub-compliant nested client_payload envelope and suppresses stale resolved work.';
