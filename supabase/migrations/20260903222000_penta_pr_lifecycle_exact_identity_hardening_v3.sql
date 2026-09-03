-- ct.penta.pr-terminalization-policy.v2 exact-identity hardening.
--
-- This follow-on hardens the current stale-sequence repair against repository-case aliases and
-- unknown-head lifecycle rows. Classification must mutate only the exact current head, while
-- applying consistently across case-only repository aliases until the dedicated repository
-- identity normalization migration is released.
--
-- No merge, provider, credential, money, rights, D3, vote, quorum, or certification authority
-- is created by this migration.

begin;

create or replace function public.penta_pr_apply_lifecycle_classification_v2(
  p_repo text,
  p_pr_number bigint,
  p_head_sha text,
  p_classification text,
  p_reason text,
  p_owner text,
  p_next_predicate text,
  p_successor_pr_number bigint default null::bigint,
  p_handoff_receipt_ref text default null::text,
  p_provenance_ref text default null::text,
  p_review_at timestamptz default null::timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'penta_pr'
as $function$
declare
  v_repo text := trim(coalesce(p_repo, ''));
  v_class text := upper(trim(coalesce(p_classification, '')));
  v_disposition text;
  v_meta jsonb;
  v_rows integer := 0;
begin
  if v_class not in (
    'CURRENT_MERGE_READY',
    'CURRENT_REPAIRABLE',
    'STALE_RESTACK_REQUIRED',
    'SUPERSEDED',
    'PROVENANCE_ONLY',
    'EXTERNAL_HOLD'
  ) then
    raise exception 'unsupported_pr_classification:%', v_class;
  end if;

  if v_repo = ''
     or p_pr_number is null
     or p_pr_number <= 0
     or coalesce(trim(p_head_sha), '') = '' then
    raise exception 'exact_pr_identity_required';
  end if;

  if coalesce(trim(p_owner), '') = '' then
    raise exception 'pr_owner_required';
  end if;

  if coalesce(trim(p_next_predicate), '') = '' then
    raise exception 'next_predicate_required';
  end if;

  if v_class = 'STALE_RESTACK_REQUIRED'
     and p_successor_pr_number is not null
     and p_successor_pr_number <= 0 then
    raise exception 'invalid_successor_pr_number';
  end if;

  if v_class = 'PROVENANCE_ONLY'
     and coalesce(trim(p_provenance_ref), '') = '' then
    raise exception 'provenance_ref_required';
  end if;

  if v_class = 'EXTERNAL_HOLD' and p_review_at is null then
    raise exception 'external_hold_review_at_required';
  end if;

  v_disposition := case v_class
    when 'CURRENT_MERGE_READY' then 'MERGE'
    when 'STALE_RESTACK_REQUIRED' then 'RESTACK'
    when 'SUPERSEDED' then 'CLOSE'
    when 'PROVENANCE_ONLY' then 'CLOSE'
    else 'NURTURE'
  end;

  v_meta := jsonb_strip_nulls(jsonb_build_object(
    'lifecycle_policy', 'ct.penta.pr-terminalization-policy.v2',
    'classification', v_class,
    'owner', trim(p_owner),
    'next_predicate', trim(p_next_predicate),
    'canonical_repo', v_repo,
    'successor_pr_number', p_successor_pr_number,
    'handoff_receipt_ref', nullif(trim(coalesce(p_handoff_receipt_ref, '')), ''),
    'provenance_ref', nullif(trim(coalesce(p_provenance_ref, '')), ''),
    'review_at', p_review_at,
    'handoff_required_before_terminalization',
      case when v_class = 'STALE_RESTACK_REQUIRED' then true else null end,
    'gold_lane_eligible',
      case when v_class in ('PROVENANCE_ONLY', 'SUPERSEDED', 'STALE_RESTACK_REQUIRED')
        then false else null end,
    'exact_identity_hardening', true,
    'authority_created', false,
    'classified_at', clock_timestamp()
  ));

  -- Repository names are provider case-insensitive. Until the dedicated identity normalization
  -- migration is applied, mutate all case-only aliases for this exact PR/head together.
  -- Unknown-head rows are deliberately excluded: exact-head governance must fail closed.
  update penta_pr.lifecycle
  set disposition = v_disposition,
      reason = p_reason,
      metadata = coalesce(metadata, '{}'::jsonb) || v_meta,
      deadline_at = case
        when v_class in ('SUPERSEDED', 'PROVENANCE_ONLY') then least(deadline_at, now())
        when v_class = 'CURRENT_MERGE_READY' then least(deadline_at, now())
        when v_class = 'STALE_RESTACK_REQUIRED' then least(deadline_at, now() + interval '1 hour')
        when v_class = 'EXTERNAL_HOLD' then greatest(deadline_at, p_review_at)
        else least(deadline_at, now() + interval '2 hours')
      end
  where lower(repo) = lower(v_repo)
    and pr_number = p_pr_number
    and head_sha = p_head_sha
    and terminal_state is null;

  get diagnostics v_rows = row_count;

  if v_rows = 0 then
    return jsonb_build_object(
      'state', 'HOLD_PR_NOT_TRACKED_OR_HEAD_MISMATCH',
      'repo', v_repo,
      'pr_number', p_pr_number,
      'head_sha', p_head_sha,
      'classification', v_class,
      'authority_created', false
    );
  end if;

  return jsonb_build_object(
    'state', 'CLASSIFIED',
    'repo', v_repo,
    'pr_number', p_pr_number,
    'head_sha', p_head_sha,
    'classification', v_class,
    'disposition', v_disposition,
    'lifecycle_rows_updated', v_rows,
    'successor_pr_number', p_successor_pr_number,
    'handoff_required_before_terminalization', v_class = 'STALE_RESTACK_REQUIRED',
    'exact_identity_hardening', true,
    'authority_created', false
  );
end;
$function$;

comment on function public.penta_pr_apply_lifecycle_classification_v2(
  text, bigint, text, text, text, text, text, bigint, text, text, timestamptz
) is 'ct.penta.pr-terminalization-policy.v2 classifier: exact-head only, case-insensitive repository alias convergence, stale classification before successor creation; creates no authority.';

commit;
