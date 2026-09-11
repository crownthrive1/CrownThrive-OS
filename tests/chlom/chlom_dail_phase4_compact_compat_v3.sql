-- Deterministic regression for compact-v4 Phase-4 assurance compatibility.
do $$
declare
  v_reader_def text;
  v_verification jsonb;
  v_status jsonb;
  v_hot jsonb;
  v_anon boolean;
  v_auth boolean;
begin
  select pg_get_functiondef(p.oid) into v_reader_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime'
    and p.proname='read_dail_phase4_assurance_status_v2'
    and pg_get_function_identity_arguments(p.oid)='p_max_checkpoint_age_seconds bigint';

  if v_reader_def is null then raise exception 'missing_phase4_assurance_reader'; end if;
  if position('derived_compact_v4_failure_counters' in v_reader_def)=0
     or position('v4_unresolved_hold_segment_count' in v_reader_def)=0
     or position('v4_order_overlap_failures' in v_reader_def)=0
     or position('v4_root_link_failures' in v_reader_def)=0
     or position('compact_compatibility_ok' in v_reader_def)=0 then
    raise exception 'compact_v4_compatibility_contract_missing';
  end if;

  v_verification:=chlom_runtime.verify_dail_chain_checkpoint_v3();
  v_status:=chlom_runtime.read_dail_phase4_assurance_status_v2();
  v_hot:=v_status->'hot_route';

  if not (v_hot ? 'tail_failure_count') then
    raise exception 'phase4_hot_tail_failure_count_missing';
  end if;
  if not (v_hot ? 'tail_failure_count_source') then
    raise exception 'phase4_hot_tail_failure_count_source_missing';
  end if;

  if coalesce((v_verification->>'ok')::boolean,false)
     and not (v_verification ? 'tail_failure_count')
     and coalesce((v_verification->>'verified_prefix_ok')::boolean,false)
     and coalesce((v_verification->>'caught_up_to_observed_head')::boolean,false)
     and coalesce((v_verification->>'v4_unresolved_hold_segment_count')::bigint,0)=0
     and coalesce((v_verification->>'v4_order_overlap_failures')::bigint,0)=0
     and coalesce((v_verification->>'v4_root_link_failures')::bigint,0)=0
  then
    if v_hot->>'state'<>'PASS'
       or coalesce((v_hot->>'tail_failure_count')::bigint,-1)<>0
       or v_hot->>'tail_failure_count_source'<>'derived_compact_v4_failure_counters' then
      raise exception 'compact_v4_truth_not_preserved_by_phase4_reader';
    end if;
  end if;

  select has_function_privilege('anon','chlom_runtime.read_dail_phase4_assurance_status_v2(bigint)','EXECUTE'),
         has_function_privilege('authenticated','chlom_runtime.read_dail_phase4_assurance_status_v2(bigint)','EXECUTE')
    into v_anon,v_auth;
  if coalesce(v_anon,false) or coalesce(v_auth,false) then
    raise exception 'phase4_reader_least_privilege_violation';
  end if;

  if coalesce((v_status->>'institutional_phase4_activation')::boolean,true) then
    raise exception 'phase4_reader_must_not_create_activation_authority';
  end if;
  if coalesce((v_status->>'full_chain_scan_executed')::boolean,true) then
    raise exception 'compact_reader_must_not_claim_full_chain_scan';
  end if;
end $$;
