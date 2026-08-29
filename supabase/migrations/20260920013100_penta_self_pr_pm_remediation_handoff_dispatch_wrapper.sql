-- CrownThrive OS — bound PentaSELF repository_dispatch payload
-- GitHub permits no more than ten top-level client_payload properties.
-- Wrap the complete finding under one `finding` key, preserve backward-compatible
-- workflow decoding, and requeue only the exact failed 422 payload-shape attempts.
-- No finding is resolved by this migration and no terminal merge authority is added.

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
    order by queued_at, created_at
    for update skip locked
    limit v_limit
  loop
    select net.http_post(
      url := 'https://api.github.com/repos/crownthrive1/CrownThrive-OS/dispatches',
      body := jsonb_build_object(
        'event_type','penta-self-remediation',
        'client_payload',jsonb_build_object(
          'schema','ct.penta.self.dispatch-envelope.v1',
          'finding_id',v_row.problem_id::text,
          'finding',v_row.payload
        )
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
    'dispatch_envelope','ct.penta.self.dispatch-envelope.v1',
    'client_payload_top_level_properties',3
  );
end
$$;

revoke all on function public.penta_self_dispatch_pr_handoffs_v1(integer) from public, anon, authenticated;
grant execute on function public.penta_self_dispatch_pr_handoffs_v1(integer) to service_role;

update penta_self.remediation_handoffs_v1
set state='queued',
    attempts=0,
    last_http_status=null,
    last_error=null,
    request_id=null,
    next_attempt_at=now(),
    updated_at=now()
where state='failed'
  and last_http_status=422
  and coalesce(last_error,'') like '%No more than 10 properties are allowed%';

with desired as (
  select
    'ct.pentaself.job.pr-pm-remediation-handoff'::text as contract_key,
    1::bigint as generation,
    'cron_job'::text as contract_kind,
    'ct-penta-self-pr-pm-handoff-v1'::text as target_key,
    jsonb_build_object(
      'active',true,
      'command','select public.penta_self_pr_handoff_tick_v1();',
      'schedule','* * * * *',
      'risk_class','D2',
      'rollback_rule','higher_generation_supersession_only'
    ) as desired_state,
    'production:2026-08-29:pentaself-remediation-dispatch-envelope-v1'::text as source_ref,
    'ct.penta.self.pr-pm-remediation.v1'::text as authority_ref,
    'PentaSELF/PentaPR/PentaPM'::text as actor_ref
)
insert into penta_self.desired_state_contracts_v1(
  contract_key,generation,contract_kind,target_key,desired_state,
  source_ref,authority_ref,actor_ref,evidence_sha256
)
select contract_key,generation,contract_kind,target_key,desired_state,
       source_ref,authority_ref,actor_ref,
       encode(extensions.digest(jsonb_build_object(
         'contract_key',contract_key,
         'generation',generation,
         'contract_kind',contract_kind,
         'target_key',target_key,
         'desired_state',desired_state,
         'source_ref',source_ref,
         'authority_ref',authority_ref,
         'actor_ref',actor_ref
       )::text,'sha256'),'hex')
from desired
on conflict (contract_key,generation) do nothing;

select penta_self.enforce_desired_state_v1();
