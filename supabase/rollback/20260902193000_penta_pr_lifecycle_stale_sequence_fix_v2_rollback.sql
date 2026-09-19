-- Fail-closed rollback for 20260902193000_penta_pr_lifecycle_stale_sequence_fix_v2.sql.
-- Restores the exact pre-change classifier and provider terminal-readback semantics.

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
  v_class text:=upper(trim(coalesce(p_classification,'')));
  v_disposition text;
  v_meta jsonb;
begin
  if v_class not in ('CURRENT_MERGE_READY','CURRENT_REPAIRABLE','STALE_RESTACK_REQUIRED','SUPERSEDED','PROVENANCE_ONLY','EXTERNAL_HOLD') then
    raise exception 'unsupported_pr_classification:%',v_class;
  end if;
  if coalesce(trim(p_repo),'')='' or p_pr_number is null or p_pr_number<=0 or coalesce(trim(p_head_sha),'')='' then
    raise exception 'exact_pr_identity_required';
  end if;
  if coalesce(trim(p_owner),'')='' then raise exception 'pr_owner_required'; end if;
  if coalesce(trim(p_next_predicate),'')='' then raise exception 'next_predicate_required'; end if;
  if v_class='STALE_RESTACK_REQUIRED' and p_successor_pr_number is null and coalesce(trim(p_handoff_receipt_ref),'')='' then
    raise exception 'stale_predecessor_requires_successor_or_handoff_before_close';
  end if;
  if v_class='PROVENANCE_ONLY' and coalesce(trim(p_provenance_ref),'')='' then
    raise exception 'provenance_ref_required';
  end if;
  if v_class='EXTERNAL_HOLD' and p_review_at is null then
    raise exception 'external_hold_review_at_required';
  end if;
  v_disposition:=case v_class
    when 'CURRENT_MERGE_READY' then 'MERGE'
    when 'STALE_RESTACK_REQUIRED' then 'RESTACK'
    when 'SUPERSEDED' then 'CLOSE'
    when 'PROVENANCE_ONLY' then 'CLOSE'
    else 'NURTURE' end;
  v_meta:=jsonb_strip_nulls(jsonb_build_object(
    'lifecycle_policy','ct.penta.pr-terminalization-policy.v2',
    'classification',v_class,
    'owner',p_owner,
    'next_predicate',p_next_predicate,
    'successor_pr_number',p_successor_pr_number,
    'handoff_receipt_ref',p_handoff_receipt_ref,
    'provenance_ref',p_provenance_ref,
    'review_at',p_review_at,
    'gold_lane_eligible',case when v_class in ('PROVENANCE_ONLY','SUPERSEDED','STALE_RESTACK_REQUIRED') then false else null end,
    'authority_created',false,
    'classified_at',clock_timestamp()
  ));
  update penta_pr.lifecycle
  set disposition=v_disposition,
      reason=p_reason,
      metadata=coalesce(metadata,'{}'::jsonb)||v_meta,
      deadline_at=case
        when v_class in ('SUPERSEDED','PROVENANCE_ONLY') then least(deadline_at,now())
        when v_class='CURRENT_MERGE_READY' then least(deadline_at,now())
        when v_class='STALE_RESTACK_REQUIRED' then least(deadline_at,now()+interval '1 hour')
        when v_class='EXTERNAL_HOLD' then greatest(deadline_at,p_review_at)
        else least(deadline_at,now()+interval '2 hours') end
  where repo=p_repo and pr_number=p_pr_number and (head_sha=p_head_sha or head_sha is null) and terminal_state is null;
  if not found then
    return jsonb_build_object('state','HOLD_PR_NOT_TRACKED_OR_HEAD_MISMATCH','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'classification',v_class,'authority_created',false);
  end if;
  return jsonb_build_object('state','CLASSIFIED','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'classification',v_class,'disposition',v_disposition,'successor_pr_number',p_successor_pr_number,'authority_created',false);
end;
$function$;

create or replace function public.penta_pr_record_provider_terminal_readback_v2(
  p_repo text,
  p_pr_number bigint,
  p_head_sha text,
  p_terminal_state text,
  p_classification text,
  p_reason text,
  p_provider_updated_at timestamptz,
  p_provider_readback jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'penta_pr', 'public'
as $function$
declare
  v_terminal text:=upper(trim(coalesce(p_terminal_state,'')));
  v_class text:=upper(trim(coalesce(p_classification,'')));
  v_action text;
  v_repo text:=trim(coalesce(p_repo,''));
  v_result jsonb;
  v_rows integer:=0;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_repo='' or p_pr_number is null or p_pr_number<=0 or coalesce(trim(p_head_sha),'')='' then raise exception 'exact_pr_identity_required'; end if;
  if v_terminal not in ('CLOSED','MERGED') then raise exception 'unsupported_terminal_state:%',v_terminal; end if;
  if v_class not in ('CURRENT_MERGE_READY','SUPERSEDED','PROVENANCE_ONLY','STALE_RESTACK_REQUIRED','EXTERNAL_HOLD','CURRENT_REPAIRABLE') then raise exception 'unsupported_pr_classification:%',v_class; end if;
  if coalesce(trim(p_reason),'')='' then raise exception 'terminal_reason_required'; end if;
  if v_terminal='MERGED' and coalesce(trim(p_provider_readback->>'merge_commit_sha'),'')='' then raise exception 'merge_commit_sha_required_for_merged_readback'; end if;
  v_action:=case when v_terminal='MERGED' then 'MERGE' else 'CLOSE' end;

  update penta_pr.lifecycle
  set terminal_state=v_terminal,
      terminal_at=coalesce(p_provider_updated_at,clock_timestamp()),
      disposition=v_action,
      reason=p_reason,
      last_observed_at=greatest(coalesce(last_observed_at,'epoch'::timestamptz),coalesce(p_provider_updated_at,clock_timestamp())),
      provider_updated_at=coalesce(p_provider_updated_at,provider_updated_at),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'lifecycle_policy','ct.penta.pr-terminalization-policy.v2',
        'classification',v_class,
        'provider_terminal_state',v_terminal,
        'provider_terminal_readback_v2',coalesce(p_provider_readback,'{}'::jsonb),
        'provider_terminal_readback_at',clock_timestamp(),
        'authority_created',false
      )
  where lower(repo)=lower(v_repo) and pr_number=p_pr_number and head_sha=p_head_sha and terminal_state is null;
  get diagnostics v_rows=row_count;

  if v_rows=0 then
    return jsonb_build_object('state','NO_OPEN_EXACT_LIFECYCLE_ROW','repo',v_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'terminal_state',v_terminal,'classification',v_class,'authority_created',false);
  end if;

  v_result:=public.penta_pr_record_terminal_decision_v3(
    v_repo,p_pr_number,p_head_sha,v_class,v_action,'SUCCEEDED',p_reason,
    jsonb_build_object('policy','ct.penta.pr-terminalization-policy.v2','provider_terminal_readback_v2',true,'authority_created',false),
    200,lower(v_terminal),v_terminal='MERGED',nullif(p_provider_readback->>'merge_commit_sha',''),coalesce(p_provider_readback,'{}'::jsonb)
  );

  return jsonb_build_object('state','TERMINAL_READBACK_RECORDED','repo',v_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'terminal_state',v_terminal,'classification',v_class,'lifecycle_rows_updated',v_rows,'terminal_decision',v_result,'authority_created',false);
end;
$function$;

commit;
