-- Deterministic contract regression for production-applied DAIL v4 identity-gap tolerance.
-- This test validates the executable contract without mutating DAIL events.

do $$
declare
  v_next text;
  v_proof text;
  v_verify text;
  v_anon_exec boolean;
  v_auth_exec boolean;
  v_anon_table boolean;
  v_auth_table boolean;
begin
  if to_regclass('chlom_runtime.dail_verification_algorithm_corrections_v4') is null then
    raise exception 'missing_algorithm_corrections_table';
  end if;

  select pg_get_functiondef(p.oid) into v_next
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='dail_verify_next_segment_v4'
    and pg_get_function_identity_arguments(p.oid)='p_max_events integer';
  if v_next is null then raise exception 'missing_dail_verify_next_segment_v4'; end if;
  if position('where sequence_id>v_cursor.verified_through_sequence_id' in v_next)=0 then
    raise exception 'verifier_not_selecting_committed_events_after_cursor';
  end if;
  if position('identity_sequence_gaps_permitted' in v_next)=0 then
    raise exception 'identity_gap_semantics_missing';
  end if;
  if position('bounded_ordered_event_batch_no_membership_rewrite' in v_next)=0 then
    raise exception 'ordered_event_verification_mode_missing';
  end if;
  if position('previous_event_hash is distinct from prior_stored_hash' in v_next)=0
     or position('event_hash is distinct from expected_event_hash' in v_next)=0
     or position('payload_sha256 is distinct from expected_payload_sha256' in v_next)=0 then
    raise exception 'cryptographic_fail_closed_checks_missing';
  end if;
  if position('pg_try_advisory_xact_lock' in v_next)=0 then
    raise exception 'concurrency_lease_missing';
  end if;

  select pg_get_functiondef(p.oid) into v_proof
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='dail_merkle_proof_v4'
    and pg_get_function_identity_arguments(p.oid)='p_sequence_id bigint';
  if v_proof is null or position('dail_verification_algorithm_corrections_v4' in v_proof)=0 then
    raise exception 'proof_algorithm_correction_exclusion_missing';
  end if;
  if position('segment_root_mismatch' in v_proof)=0 then
    raise exception 'proof_root_recompute_guard_missing';
  end if;

  select pg_get_functiondef(p.oid) into v_verify
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='verify_dail_chain_v4'
    and pg_get_function_identity_arguments(p.oid)='';
  if v_verify is null then raise exception 'missing_verify_dail_chain_v4'; end if;
  if position('v4_invalidated_algorithm_segment_count' in v_verify)=0
     or position('identity_sequence_gaps_permitted' in v_verify)=0
     or position('v4_root_link_failures' in v_verify)=0 then
    raise exception 'compact_chain_assurance_contract_missing';
  end if;

  select has_function_privilege('anon','chlom_runtime.dail_verify_next_segment_v4(integer)','EXECUTE'),
         has_function_privilege('authenticated','chlom_runtime.dail_verify_next_segment_v4(integer)','EXECUTE')
    into v_anon_exec,v_auth_exec;
  if coalesce(v_anon_exec,false) or coalesce(v_auth_exec,false) then
    raise exception 'least_privilege_execute_violation';
  end if;

  select has_table_privilege('anon','chlom_runtime.dail_verification_algorithm_corrections_v4','SELECT,INSERT,UPDATE,DELETE'),
         has_table_privilege('authenticated','chlom_runtime.dail_verification_algorithm_corrections_v4','SELECT,INSERT,UPDATE,DELETE')
    into v_anon_table,v_auth_table;
  if coalesce(v_anon_table,false) or coalesce(v_auth_table,false) then
    raise exception 'least_privilege_table_violation';
  end if;

  if exists (
    select 1 from chlom_runtime.dail_verification_algorithm_corrections_v4
    where correction_state='ACCEPTED' and chain_integrity_failures<>0
  ) then
    raise exception 'unsafe_algorithm_correction_with_chain_failures';
  end if;
end $$;
