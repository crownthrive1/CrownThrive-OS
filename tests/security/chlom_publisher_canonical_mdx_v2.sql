-- Transactional acceptance/negative tests for CHLOM publisher canonical MDX v2.
-- No provider operation is visible outside this transaction; all fixtures roll back.

begin;

do $test$
declare
  work_id uuid := gen_random_uuid();
  old_draft_id uuid := gen_random_uuid();
  blocked_command_id uuid := gen_random_uuid();
  verified_command_id uuid := gen_random_uuid();
  old_mdx text;
  old_sha text;
  result jsonb;
  new_draft_id uuid;
  new_sha text;
  new_mdx text;
  wrapper_definition text;
begin
  old_mdx := '---\\n'
    || 'title: "Canonical MDX v2 transactional test"\\n'
    || 'description: "fixture"\\n'
    || '---\\n\\n'
    || '# Canonical MDX v2 transactional test\\n';
  old_sha := encode(extensions.digest(convert_to(old_mdx, 'UTF8'), 'sha256'), 'hex');

  insert into public.chlom_publication_work_items(
    id,
    workflow_key,
    title,
    slug,
    audience,
    content_mode,
    state,
    repository_target,
    metadata
  ) values (
    work_id,
    'chlom-continuous-docs-and-growth',
    'Canonical MDX v2 transactional test',
    'chlom/insights/canonical-mdx-v2-test-' || replace(work_id::text, '-', ''),
    'security test',
    'GOVERNANCE',
    'NEEDS_REVIEW',
    'parent+commercial-child',
    jsonb_build_object('topic_family', 'governance', 'vertical', 'security-test')
  );

  insert into public.chlom_article_drafts(
    draft_id,
    workflow_key,
    work_item_id,
    title,
    slug,
    mdx,
    content_sha256,
    source_basis,
    state
  ) values (
    old_draft_id,
    'chlom-continuous-docs-and-growth',
    work_id,
    'Canonical MDX v2 transactional test',
    'chlom/insights/canonical-mdx-v2-test-' || replace(work_id::text, '-', ''),
    old_mdx,
    old_sha,
    jsonb_build_object('fixture', true),
    'VERIFIED'
  );

  update public.chlom_publication_work_items
  set metadata = metadata || jsonb_build_object('draft_id', old_draft_id, 'draft_sha256', old_sha)
  where id = work_id;

  insert into public.chlom_provider_publication_queue(
    command_id,
    workflow_key,
    work_item_id,
    draft_id,
    provider,
    destination_path,
    state,
    attempts,
    idempotency_key,
    request,
    last_error
  ) values (
    blocked_command_id,
    'chlom-continuous-docs-and-growth',
    work_id,
    old_draft_id,
    'Mintlify/GitHub',
    'chlom/insights/canonical-mdx-v2-test-' || replace(work_id::text, '-', ''),
    'BLOCKED',
    5,
    'test-blocked:' || blocked_command_id,
    jsonb_build_object('content_sha256', old_sha),
    'github_provider_job_failed'
  );

  -- Historical provider truth must remain immutable when a corrected edition is queued.
  insert into public.chlom_provider_publication_queue(
    command_id,
    workflow_key,
    work_item_id,
    draft_id,
    provider,
    destination_path,
    state,
    attempts,
    idempotency_key,
    request,
    response,
    readback,
    completed_at
  ) values (
    verified_command_id,
    'chlom-continuous-docs-and-growth',
    work_id,
    old_draft_id,
    'Mintlify/GitHub',
    'chlom/insights/canonical-mdx-v2-test-' || replace(work_id::text, '-', ''),
    'VERIFIED',
    1,
    'test-verified:' || verified_command_id,
    jsonb_build_object('content_sha256', old_sha),
    jsonb_build_object('provider_fixture', true),
    jsonb_build_object('verified_fixture', true),
    now()
  );

  result := public.chlom_canonicalize_growth_draft_v2(old_draft_id);

  if coalesce((result ->> 'ok')::boolean, false) is not true
     or coalesce((result ->> 'changed')::boolean, false) is not true then
    raise exception 'canonicalizer did not report a material correction: %', result;
  end if;

  new_draft_id := (result ->> 'draft_id')::uuid;
  new_sha := result ->> 'content_sha256';

  if new_draft_id = old_draft_id or new_sha = old_sha then
    raise exception 'canonicalization failed to create a distinct append-only edition';
  end if;

  select mdx into new_mdx
  from public.chlom_article_drafts
  where draft_id = new_draft_id;

  if substring(new_mdx from 1 for 4) <> E'---\n' then
    raise exception 'corrected draft still has malformed frontmatter';
  end if;

  if new_mdx like E'%\\\\n%' then
    raise exception 'corrected draft still contains literal backslash-n sequences';
  end if;

  if new_sha <> encode(extensions.digest(convert_to(new_mdx, 'UTF8'), 'sha256'), 'hex') then
    raise exception 'corrected digest does not match exact corrected bytes';
  end if;

  if not exists (
    select 1
    from public.chlom_article_drafts
    where draft_id = old_draft_id
      and mdx = old_mdx
      and content_sha256 = old_sha
  ) then
    raise exception 'predecessor draft bytes were rewritten or deleted';
  end if;

  if (select state from public.chlom_provider_publication_queue where command_id = blocked_command_id) <> 'SUPERSEDED' then
    raise exception 'blocked malformed queue predecessor was not superseded';
  end if;

  if (select state from public.chlom_provider_publication_queue where command_id = verified_command_id) <> 'VERIFIED' then
    raise exception 'historical VERIFIED provider evidence was mutated';
  end if;

  if not exists (
    select 1
    from public.chlom_provider_publication_queue
    where draft_id = new_draft_id
      and state = 'QUEUED'
      and idempotency_key = 'chlom-publish:' || new_sha
      and request ->> 'content_sha256' = new_sha
  ) then
    raise exception 'corrected idempotent provider command was not queued';
  end if;

  if (select metadata ->> 'draft_id' from public.chlom_publication_work_items where id = work_id) <> new_draft_id::text then
    raise exception 'current work-item projection does not point to corrected draft';
  end if;

  -- The canonical v1 entrypoint must route through v2 and the raw historical
  -- implementation must not remain directly callable by service_role.
  select pg_get_functiondef('public.chlom_build_growth_mdx_v1(uuid)'::regprocedure)
  into wrapper_definition;

  if wrapper_definition not like '%chlom_canonicalize_growth_draft_v2%' then
    raise exception 'canonical v1 generator does not invoke canonicalization v2';
  end if;

  if has_function_privilege('anon', 'public.chlom_build_growth_mdx_v1(uuid)', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.chlom_build_growth_mdx_v1(uuid)', 'EXECUTE') then
    raise exception 'canonical generator is exposed to untrusted application roles';
  end if;

  if has_function_privilege('service_role', 'public.chlom_build_growth_mdx_raw_v1(uuid)', 'EXECUTE') then
    raise exception 'service_role can bypass canonical wrapper through raw generator';
  end if;

  if not has_function_privilege('service_role', 'public.chlom_build_growth_mdx_v1(uuid)', 'EXECUTE')
     or not has_function_privilege('service_role', 'public.chlom_canonicalize_growth_draft_v2(uuid)', 'EXECUTE') then
    raise exception 'governed service execution path is not available';
  end if;
end;
$test$;

rollback;
