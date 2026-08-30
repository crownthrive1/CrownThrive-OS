-- CHLOM Continuous Publisher canonical MDX repair v2
--
-- Root cause addressed: the historical growth generator materialized literal "\\n"
-- byte sequences into otherwise-valid MDX. Provider digest verification correctly
-- accepted those bytes, but PentaDocs rejected the resulting page as malformed
-- frontmatter. This migration repairs the defect before provider publication while
-- preserving predecessor drafts, provider receipts, and queue history.
--
-- Authority boundary: database-local draft/queue normalization only. No provider
-- write, D3 action, rights grant, credential mutation, certification, or money move.

-- Preserve the historical generator as an internal implementation primitive. The
-- public canonical v1 name is recreated below as a guarded wrapper so existing
-- callers keep the same API contract while receiving canonical bytes.
do $migration$
begin
  if to_regprocedure('public.chlom_build_growth_mdx_raw_v1(uuid)') is null then
    if to_regprocedure('public.chlom_build_growth_mdx_v1(uuid)') is null then
      raise exception 'required function public.chlom_build_growth_mdx_v1(uuid) is absent';
    end if;
    execute 'alter function public.chlom_build_growth_mdx_v1(uuid) rename to chlom_build_growth_mdx_raw_v1';
  end if;
end
$migration$;

revoke all on function public.chlom_build_growth_mdx_raw_v1(uuid) from public, anon, authenticated, service_role;
grant execute on function public.chlom_build_growth_mdx_raw_v1(uuid) to postgres;

create or replace function public.chlom_canonicalize_growth_draft_v2(p_draft_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'extensions', 'pg_catalog'
as $function$
declare
  d public.chlom_article_drafts%rowtype;
  w public.chlom_publication_work_items%rowtype;
  fixed text;
  new_sha text;
  new_draft_id uuid;
  new_command_id uuid;
  superseded_count integer := 0;
begin
  select * into d
  from public.chlom_article_drafts
  where draft_id = p_draft_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'draft_not_found', 'draft_id', p_draft_id);
  end if;

  select * into w
  from public.chlom_publication_work_items
  where id = d.work_item_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'work_item_not_found', 'draft_id', p_draft_id);
  end if;

  if d.workflow_key <> 'chlom-continuous-docs-and-growth'
     or d.state <> 'VERIFIED'
     or w.content_mode = 'RECOVERY' then
    return jsonb_build_object(
      'ok', false,
      'reason', 'draft_outside_growth_repair_scope',
      'draft_id', p_draft_id,
      'workflow_key', d.workflow_key,
      'draft_state', d.state,
      'content_mode', w.content_mode
    );
  end if;

  -- Lock all mutable provider-queue predecessors for this exact draft before the
  -- claim/readback worker can race the correction.
  perform 1
  from public.chlom_provider_publication_queue q
  where q.draft_id = d.draft_id
    and q.state in ('QUEUED', 'CLAIMED', 'BLOCKED')
  for update;

  if exists (
    select 1
    from public.chlom_provider_publication_queue q
    where q.draft_id = d.draft_id
      and q.state = 'CLAIMED'
      and q.claimed_at is not null
      and q.claimed_at > now() - interval '25 minutes'
  ) then
    return jsonb_build_object(
      'ok', false,
      'reason', 'active_provider_claim',
      'draft_id', p_draft_id
    );
  end if;

  fixed := public.chlom_finalize_mdx_newlines_v1(d.mdx);

  if substring(fixed from 1 for 4) <> E'---\n' then
    return jsonb_build_object(
      'ok', false,
      'reason', 'frontmatter_invalid_after_canonicalization',
      'draft_id', p_draft_id
    );
  end if;

  new_sha := encode(extensions.digest(convert_to(fixed, 'UTF8'), 'sha256'), 'hex');

  if fixed = d.mdx and new_sha = d.content_sha256 then
    return jsonb_build_object(
      'ok', true,
      'changed', false,
      'reason', 'already_canonical',
      'draft_id', d.draft_id,
      'content_sha256', d.content_sha256
    );
  end if;

  -- Append a corrected draft rather than rewriting the predecessor body. This
  -- preserves exact historical bytes and provider evidence for audit/readback.
  insert into public.chlom_article_drafts(
    workflow_key,
    work_item_id,
    title,
    slug,
    mdx,
    content_sha256,
    editorial_profile,
    source_basis,
    state
  ) values (
    d.workflow_key,
    d.work_item_id,
    d.title,
    d.slug,
    fixed,
    new_sha,
    d.editorial_profile,
    coalesce(d.source_basis, '{}'::jsonb) || jsonb_build_object(
      'canonicalization', 'chlom_canonicalize_growth_draft_v2',
      'canonicalized_from_draft_id', d.draft_id,
      'canonicalized_from_sha256', d.content_sha256,
      'canonicalized_at', now(),
      'immutable_predecessor_preserved', true
    ),
    'VERIFIED'
  )
  on conflict (work_item_id, content_sha256) do nothing
  returning draft_id into new_draft_id;

  if new_draft_id is null then
    select draft_id into new_draft_id
    from public.chlom_article_drafts
    where work_item_id = d.work_item_id
      and content_sha256 = new_sha
    order by created_at desc
    limit 1;
  end if;

  if new_draft_id is null then
    raise exception 'canonical draft could not be resolved for work item %', d.work_item_id;
  end if;

  update public.chlom_publication_work_items
  set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'draft_id', new_draft_id,
        'draft_sha256', new_sha,
        'canonical_mdx_v2', true,
        'canonicalized_from_draft_id', d.draft_id,
        'canonicalized_from_sha256', d.content_sha256,
        'canonicalized_at', now()
      ),
      updated_at = now()
  where id = d.work_item_id;

  update public.chlom_provider_publication_queue q
  set state = 'SUPERSEDED',
      last_error = concat_ws(
        ' | ',
        nullif(q.last_error, ''),
        'superseded_pre_canonical_mdx_v2'
      ),
      updated_at = now()
  where q.draft_id = d.draft_id
    and (
      q.state in ('QUEUED', 'BLOCKED')
      or (
        q.state = 'CLAIMED'
        and (q.claimed_at is null or q.claimed_at <= now() - interval '25 minutes')
      )
    );

  get diagnostics superseded_count = row_count;

  insert into public.chlom_provider_publication_queue(
    workflow_key,
    work_item_id,
    draft_id,
    provider,
    repository_target,
    branch_target,
    destination_path,
    idempotency_key,
    request
  ) values (
    d.workflow_key,
    d.work_item_id,
    new_draft_id,
    'Mintlify/GitHub',
    coalesce(w.repository_target, 'parent+commercial-child'),
    'admin-mcp/chlom-docs-recovery-publication-8d3723a',
    d.slug,
    'chlom-publish:' || new_sha,
    jsonb_build_object(
      'title', d.title,
      'slug', d.slug,
      'content_sha256', new_sha,
      'operation', 'UPSERT_PAGE',
      'requires_destination_readback', true,
      'proprietary_guard', true,
      'founder_override_program', true,
      'canonical_mdx_v2', true,
      'predecessor_draft_id', d.draft_id,
      'predecessor_sha256', d.content_sha256
    )
  )
  on conflict (idempotency_key) do nothing
  returning command_id into new_command_id;

  if new_command_id is null then
    select command_id into new_command_id
    from public.chlom_provider_publication_queue
    where idempotency_key = 'chlom-publish:' || new_sha
    order by created_at desc
    limit 1;
  end if;

  insert into public.chlom_content_history(
    workflow_key,
    work_item_id,
    title,
    audience,
    topic_family,
    vertical,
    keywords,
    content_sha256,
    publication_state
  ) values (
    d.workflow_key,
    d.work_item_id,
    d.title,
    w.audience,
    w.metadata ->> 'topic_family',
    w.metadata ->> 'vertical',
    array['CHLOM', 'canonical-mdx-v2'],
    new_sha,
    'VERIFIED_DRAFT'
  );

  return jsonb_build_object(
    'ok', true,
    'changed', true,
    'predecessor_draft_id', d.draft_id,
    'predecessor_sha256', d.content_sha256,
    'draft_id', new_draft_id,
    'content_sha256', new_sha,
    'command_id', new_command_id,
    'superseded_queue_rows', superseded_count,
    'frontmatter_canonical', true,
    'predecessor_preserved', true
  );
end;
$function$;

revoke all on function public.chlom_canonicalize_growth_draft_v2(uuid) from public, anon, authenticated;
grant execute on function public.chlom_canonicalize_growth_draft_v2(uuid) to postgres, service_role;

create or replace function public.chlom_build_growth_mdx_v1(p_item_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'extensions', 'pg_catalog'
as $function$
declare
  raw_result jsonb;
  canonical_result jsonb;
  raw_draft_id uuid;
begin
  raw_result := public.chlom_build_growth_mdx_raw_v1(p_item_id);

  if coalesce((raw_result ->> 'ok')::boolean, false) is not true then
    return raw_result;
  end if;

  raw_draft_id := nullif(raw_result ->> 'draft_id', '')::uuid;
  if raw_draft_id is null then
    return raw_result || jsonb_build_object(
      'ok', false,
      'reason', 'raw_generator_missing_draft_id',
      'canonical_mdx_v2', false
    );
  end if;

  canonical_result := public.chlom_canonicalize_growth_draft_v2(raw_draft_id);
  if coalesce((canonical_result ->> 'ok')::boolean, false) is not true then
    return raw_result || jsonb_build_object(
      'ok', false,
      'reason', coalesce(canonical_result ->> 'reason', 'canonicalization_failed'),
      'canonical_mdx_v2', false,
      'canonicalization', canonical_result
    );
  end if;

  return raw_result || jsonb_build_object(
    'ok', true,
    'raw_draft_id', raw_draft_id,
    'draft_id', canonical_result ->> 'draft_id',
    'sha256', canonical_result ->> 'content_sha256',
    'canonical_mdx_v2', true,
    'canonicalization', canonical_result
  );
end;
$function$;

revoke all on function public.chlom_build_growth_mdx_v1(uuid) from public, anon, authenticated;
grant execute on function public.chlom_build_growth_mdx_v1(uuid) to postgres, service_role;

-- Recreate the only database-resident caller discovered during the fresh census so
-- it resolves the canonical wrapper by name after the historical function rename.
create or replace function public.chlom_draft_pending_growth_v1(p_limit integer default 3)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'pg_catalog'
as $function$
declare
  r record;
  n integer := 0;
  results jsonb := '[]'::jsonb;
  x jsonb;
begin
  for r in
    select id
    from public.chlom_publication_work_items
    where workflow_key = 'chlom-continuous-docs-and-growth'
      and content_mode <> 'RECOVERY'
      and state = 'NEXT'
    order by created_at
    limit greatest(1, least(coalesce(p_limit, 3), 10))
    for update skip locked
  loop
    x := public.chlom_build_growth_mdx_v1(r.id);
    results := results || jsonb_build_array(x);
    n := n + 1;
  end loop;

  return jsonb_build_object('ok', true, 'drafted', n, 'results', results, 'at', now());
end;
$function$;

revoke all on function public.chlom_draft_pending_growth_v1(integer) from public, anon, authenticated;
grant execute on function public.chlom_draft_pending_growth_v1(integer) to postgres, service_role;

create or replace function public.chlom_repair_growth_drafts_v2()
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'extensions', 'pg_catalog'
as $function$
declare
  r record;
  x jsonb;
  repaired integer := 0;
  unchanged integer := 0;
  held integer := 0;
  results jsonb := '[]'::jsonb;
begin
  for r in
    select d.draft_id
    from public.chlom_article_drafts d
    join public.chlom_publication_work_items w on w.id = d.work_item_id
    where d.workflow_key = 'chlom-continuous-docs-and-growth'
      and d.state = 'VERIFIED'
      and w.content_mode <> 'RECOVERY'
      and w.metadata ->> 'draft_id' = d.draft_id::text
      and d.mdx like E'%\\\\n%'
    order by d.created_at
  loop
    x := public.chlom_canonicalize_growth_draft_v2(r.draft_id);
    results := results || jsonb_build_array(x);

    if coalesce((x ->> 'ok')::boolean, false) is not true then
      held := held + 1;
    elsif coalesce((x ->> 'changed')::boolean, false) then
      repaired := repaired + 1;
    else
      unchanged := unchanged + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'ok', held = 0,
    'repaired', repaired,
    'unchanged', unchanged,
    'held', held,
    'results', results,
    'at', now()
  );
end;
$function$;

revoke all on function public.chlom_repair_growth_drafts_v2() from public, anon, authenticated;
grant execute on function public.chlom_repair_growth_drafts_v2() to postgres, service_role;

comment on function public.chlom_canonicalize_growth_draft_v2(uuid) is
'Append-only CHLOM growth-draft canonicalizer. Preserves predecessor bytes and provider evidence; creates a corrected verified draft and new idempotent provider command. No provider-write or certification authority.';

comment on function public.chlom_build_growth_mdx_v1(uuid) is
'Canonical CHLOM growth-draft entrypoint. Executes the historical generator internally, then canonicalizes MDX bytes and digest before provider publication.';

comment on function public.chlom_repair_growth_drafts_v2() is
'Bounded repair for current malformed CHLOM growth drafts. Holds on active provider claims and never rewrites VERIFIED provider receipts.';
