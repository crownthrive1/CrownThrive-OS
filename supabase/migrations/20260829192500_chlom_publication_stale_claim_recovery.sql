-- CHLOM publication queue bounded stale-claim recovery.
-- A publisher job has a 20-minute hard timeout. A CLAIMED row older than 22 minutes
-- cannot still belong to a live canonical publisher execution, so recover it through
-- the governed claim contract before selecting the next batch. Attempts at/above the
-- existing retry ceiling remain fail-closed as BLOCKED.

create or replace function public.chlom_claim_publication_commands_v1(
  p_limit integer default 3,
  p_claims jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'pg_catalog'
as $function$
declare
  cmds jsonb;
  recovered int := 0;
begin
  update public.chlom_provider_publication_queue
  set state = case when attempts >= 5 then 'BLOCKED' else 'QUEUED' end,
      available_at = case when attempts >= 5 then available_at else now() end,
      claimed_at = null,
      updated_at = now(),
      last_error = 'stale_claim_timeout_recovered',
      response = coalesce(response, '{}'::jsonb) || jsonb_build_object(
        'stale_claim_recovered_at', now(),
        'stale_claim_timeout_minutes', 22
      )
  where workflow_key = 'chlom-continuous-docs-and-growth'
    and state = 'CLAIMED'
    and claimed_at is not null
    and claimed_at < now() - interval '22 minutes';
  get diagnostics recovered = row_count;

  with candidates as (
    select q.command_id
    from public.chlom_provider_publication_queue q
    join public.chlom_article_drafts d on d.draft_id = q.draft_id
    where q.workflow_key = 'chlom-continuous-docs-and-growth'
      and q.state = 'QUEUED'
      and q.available_at <= now()
      and d.state = 'VERIFIED'
      and q.destination_path ~ '^chlom/[a-z0-9/_-]+$'
    order by q.created_at
    for update of q skip locked
    limit greatest(1, least(coalesce(p_limit, 3), 5))
  ), claimed as (
    update public.chlom_provider_publication_queue q
    set state = 'CLAIMED',
        claimed_at = now(),
        attempts = attempts + 1,
        updated_at = now(),
        request = q.request || jsonb_build_object(
          'github_oidc_claim', p_claims,
          'claimed_at', now()
        )
    from candidates c
    where q.command_id = c.command_id
    returning q.command_id, q.work_item_id, q.draft_id, q.destination_path, q.idempotency_key
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'command_id', c.command_id,
    'work_item_id', c.work_item_id,
    'draft_id', c.draft_id,
    'destination_path', c.destination_path,
    'file_path', c.destination_path || '.mdx',
    'idempotency_key', c.idempotency_key,
    'title', d.title,
    'content_sha256', d.content_sha256,
    'mdx', d.mdx
  ) order by c.command_id), '[]'::jsonb)
  into cmds
  from claimed c
  join public.chlom_article_drafts d on d.draft_id = c.draft_id;

  return jsonb_build_object(
    'ok', true,
    'commands', cmds,
    'count', jsonb_array_length(cmds),
    'claimed_at', now(),
    'stale_recovered', recovered
  );
end;
$function$;

comment on function public.chlom_claim_publication_commands_v1(integer, jsonb)
is 'Claims bounded CHLOM publication commands and fail-closed recovers CLAIMED rows older than the publisher hard-timeout plus two-minute cushion.';
