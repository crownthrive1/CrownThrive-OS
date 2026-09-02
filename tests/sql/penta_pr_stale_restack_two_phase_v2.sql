-- ct.penta.pr-terminalization-policy.v2 two-phase stale-restack invariants.
-- Run after migration 20260902192500 in an isolated transaction.
-- Synthetic lifecycle/terminal rows are rolled back; no provider call is made.

begin;

do $test$
declare
  v_repo text := 'ct.test/penta-pr-two-phase';
  v_pr bigint := 999990021;
  v_other_pr bigint := 999990022;
  v_head text := repeat('a',40);
  v_other_head text := repeat('b',40);
  v_result jsonb;
  v_raised boolean := false;
  v_successor bigint := 999990023;
  v_handoff text := 'ct.test.handoff.penta-pr-two-phase';
  v_meta jsonb;
begin
  insert into penta_pr.lifecycle(repo,pr_number,head_sha,base_ref,metadata)
  values(v_repo,v_pr,v_head,'main','{}'::jsonb);

  -- Phase 1: classify the stale predecessor before a successor exists.
  v_result := public.penta_pr_apply_lifecycle_classification_v2(
    v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','test stale predecessor',
    'penta.overlay','create exactly one successor on current main'
  );
  if v_result->>'state' <> 'CLASSIFIED'
     or v_result->>'classification' <> 'STALE_RESTACK_REQUIRED'
     or coalesce((v_result->>'restack_pair_complete')::boolean,true) then
    raise exception 'TEST_FAIL_INITIAL_STALE_CLASSIFICATION:%',v_result;
  end if;

  select metadata into v_meta
  from penta_pr.lifecycle
  where repo=v_repo and pr_number=v_pr and head_sha=v_head;
  if v_meta ? 'successor_pr_number' or v_meta ? 'handoff_receipt_ref' then
    raise exception 'TEST_FAIL_INITIAL_PAIR_MUST_BE_EMPTY:%',v_meta;
  end if;

  -- A partial successor/handoff pair is forbidden in either direction.
  begin
    perform public.penta_pr_apply_lifecycle_classification_v2(
      v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','partial successor',
      'penta.overlay','record pair',v_successor,null,null,null
    );
  exception when others then
    v_raised := position('stale_restack_successor_and_handoff_must_be_supplied_together' in sqlerrm)>0;
  end;
  if not v_raised then raise exception 'TEST_FAIL_SUCCESSOR_ONLY_ACCEPTED'; end if;

  v_raised := false;
  begin
    perform public.penta_pr_apply_lifecycle_classification_v2(
      v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','partial handoff',
      'penta.overlay','record pair',null,v_handoff,null,null
    );
  exception when others then
    v_raised := position('stale_restack_successor_and_handoff_must_be_supplied_together' in sqlerrm)>0;
  end;
  if not v_raised then raise exception 'TEST_FAIL_HANDOFF_ONLY_ACCEPTED'; end if;

  -- No successful terminal decision may be recorded before the restack pair exists.
  v_raised := false;
  begin
    perform public.penta_pr_record_terminal_decision_v3(
      v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','CLOSE','SUCCEEDED',
      'must fail before successor/handoff pair','{}'::jsonb
    );
  exception when others then
    v_raised := position('stale_predecessor_terminalization_requires_successor_and_handoff' in sqlerrm)>0;
  end;
  if not v_raised then raise exception 'TEST_FAIL_DIRECT_TERMINAL_BEFORE_PAIR'; end if;

  v_raised := false;
  begin
    perform public.penta_pr_record_provider_terminal_readback_v2(
      v_repo,v_pr,v_head,'CLOSED','STALE_RESTACK_REQUIRED',
      'must fail before successor/handoff pair',clock_timestamp(),
      jsonb_build_object('test_only',true)
    );
  exception when others then
    v_raised := position('stale_predecessor_terminalization_requires_successor_and_handoff' in sqlerrm)>0;
  end;
  if not v_raised then raise exception 'TEST_FAIL_PROVIDER_TERMINAL_BEFORE_PAIR'; end if;

  -- Phase 2: record successor + handoff atomically.
  v_result := public.penta_pr_apply_lifecycle_classification_v2(
    v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','successor routed',
    'penta.overlay','close predecessor after provider readback',
    v_successor,v_handoff,null,null
  );
  if not coalesce((v_result->>'restack_pair_complete')::boolean,false)
     or (v_result->>'successor_pr_number')::bigint <> v_successor
     or v_result->>'handoff_receipt_ref' <> v_handoff then
    raise exception 'TEST_FAIL_RESTACK_PAIR:%',v_result;
  end if;

  -- Successful decision/readback now passes the pair guard.
  v_result := public.penta_pr_record_terminal_decision_v3(
    v_repo,v_pr,v_head,'STALE_RESTACK_REQUIRED','CLOSE','SUCCEEDED',
    'synthetic terminal decision after complete pair',jsonb_build_object('test_only',true)
  );
  if v_result->>'state' <> 'SUCCEEDED' then
    raise exception 'TEST_FAIL_TERMINAL_AFTER_PAIR:%',v_result;
  end if;

  v_result := public.penta_pr_record_provider_terminal_readback_v2(
    v_repo,v_pr,v_head,'CLOSED','STALE_RESTACK_REQUIRED',
    'synthetic provider readback after complete pair',clock_timestamp(),
    jsonb_build_object('test_only',true)
  );
  if v_result->>'state' <> 'TERMINAL_READBACK_RECORDED' then
    raise exception 'TEST_FAIL_PROVIDER_AFTER_PAIR:%',v_result;
  end if;

  -- Exact-head mismatch remains fail-closed and non-stale classification remains compatible.
  insert into penta_pr.lifecycle(repo,pr_number,head_sha,base_ref,metadata)
  values(v_repo,v_other_pr,v_other_head,'main','{}'::jsonb);

  v_result := public.penta_pr_apply_lifecycle_classification_v2(
    v_repo,v_other_pr,repeat('c',40),'CURRENT_REPAIRABLE','wrong exact head',
    'penta.pm','repair exact predicate'
  );
  if v_result->>'state' <> 'HOLD_PR_NOT_TRACKED_OR_HEAD_MISMATCH' then
    raise exception 'TEST_FAIL_EXACT_HEAD_GUARD:%',v_result;
  end if;

  v_result := public.penta_pr_apply_lifecycle_classification_v2(
    v_repo,v_other_pr,v_other_head,'CURRENT_REPAIRABLE','compatible non-stale lane',
    'penta.pm','repair exact predicate'
  );
  if v_result->>'state' <> 'CLASSIFIED' or v_result->>'disposition' <> 'NURTURE' then
    raise exception 'TEST_FAIL_NON_STALE_COMPATIBILITY:%',v_result;
  end if;

  if public.penta_pr_lifecycle_policy_v2()->>'stale_predecessor_close_guard'
       <> 'successor_pr_number AND handoff_receipt_ref required before predecessor terminalization' then
    raise exception 'TEST_FAIL_POLICY_CLOSE_GUARD';
  end if;

  raise notice 'PENTA_PR_STALE_RESTACK_TWO_PHASE_V2 PASS';
end
$test$;

rollback;