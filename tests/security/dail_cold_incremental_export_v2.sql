-- Deterministic/security acceptance checks for CHLOM C13 incremental cold DAIL v2.
-- Provider writes are not exercised here. Drive byte/readback + isolated restore are
-- separately required by the connector completion contract and production readback.

begin;

do $test$
declare
  v_src text;
  v_args text;
  v_rls_count integer;
  v_force_count integer;
  v_bad_acl integer;
  v_trigger_count integer;
begin
  select count(*) filter (where c.relrowsecurity),
         count(*) filter (where c.relforcerowsecurity)
    into v_rls_count,v_force_count
  from pg_class c
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='chlom_runtime'
    and c.relname in (
      'dail_cold_incremental_exports_v2',
      'dail_cold_incremental_checkpoints_v2',
      'dail_incremental_recovery_drills_v2'
    );
  if v_rls_count<>3 or v_force_count<>3 then
    raise exception 'incremental_dail_tables_must_force_rls';
  end if;

  select count(*) into v_bad_acl
  from information_schema.role_table_grants g
  where g.table_schema='chlom_runtime'
    and g.table_name in (
      'dail_cold_incremental_exports_v2',
      'dail_cold_incremental_checkpoints_v2',
      'dail_incremental_recovery_drills_v2'
    )
    and g.grantee in ('anon','authenticated');
  if v_bad_acl<>0 then raise exception 'incremental_dail_table_acl_exposed'; end if;

  select count(*) into v_trigger_count
  from pg_trigger t
  join pg_class c on c.oid=t.tgrelid
  join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='chlom_runtime'
    and c.relname in (
      'dail_cold_incremental_exports_v2',
      'dail_cold_incremental_checkpoints_v2',
      'dail_incremental_recovery_drills_v2'
    )
    and not t.tgisinternal
    and t.tgname in (
      'dail_cold_incremental_exports_append_only_v2',
      'dail_cold_incremental_checkpoints_append_only_v2',
      'dail_incremental_recovery_drills_append_only_v2'
    );
  if v_trigger_count<>3 then raise exception 'incremental_dail_append_only_triggers_missing'; end if;

  select p.prosrc into v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='enqueue_dail_cold_incremental_backup_v2';
  if v_src is null then raise exception 'incremental_enqueue_missing'; end if;
  if v_src not ilike '%verify_dail_chain_v3()%' then raise exception 'fast_checkpoint_tail_verifier_required'; end if;
  if v_src ilike '%verify_dail_chain()%' then raise exception 'exhaustive_full_chain_scan_forbidden_on_incremental_hot_path'; end if;
  if v_src not ilike '%v_delta_first_previous_hash is distinct from v_previous_head%' then raise exception 'prior_head_linkage_guard_missing'; end if;
  if v_src not ilike '%HOLD_PREVIOUS_CHECKPOINT_UNTESTED%' then raise exception 'prior_recovery_gate_missing'; end if;
  if v_src not ilike '%payload_bodies_included%' or v_src not ilike '%false%' then raise exception 'payload_exclusion_contract_missing'; end if;
  if v_src not ilike '%actor_identifiers_included%' or v_src not ilike '%entity_identifiers_included%' then raise exception 'identity_exclusion_contract_missing'; end if;

  select p.prosrc into v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname='dail_cold_incremental_export_chunk_v2';
  if v_src is null then raise exception 'incremental_chunk_export_missing'; end if;
  if v_src ilike '%''payload'',e.payload%'
     or v_src ilike '%''actor_ref''%'
     or v_src ilike '%''actor_did''%'
     or v_src ilike '%''entity_id''%'
     or v_src ilike '%''entity_type''%' then
    raise exception 'incremental_chunk_export_leaks_payload_or_identity';
  end if;
  if v_src not ilike '%''payload_sha256'',e.payload_sha256%' then raise exception 'payload_digest_lineage_missing'; end if;
  if v_src not ilike '%''previous_event_hash'',e.previous_event_hash%' then raise exception 'event_chain_link_missing'; end if;
  if v_src not ilike '%chunk_sha256%' then raise exception 'chunk_integrity_digest_missing'; end if;

  select pg_get_function_identity_arguments(p.oid),p.prosrc
    into v_args,v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='record_dail_incremental_recovery_drill_v2';
  if v_src is null then raise exception 'incremental_recovery_drill_missing'; end if;
  if v_args not ilike '%p_delta_internal_chain_verified boolean%' then raise exception 'explicit_recovered_internal_chain_proof_missing'; end if;
  if v_src not ilike '%p_delta_internal_chain_verified is true%' then raise exception 'internal_chain_proof_not_required_for_pass'; end if;
  if v_src not ilike '%v_first_links%' or v_src not ilike '%v_prior_ok%' then raise exception 'incremental_recovery_linkage_or_prior_recovery_gate_missing'; end if;
  if v_src not ilike '%isolated_non_production%' then raise exception 'isolated_restore_target_contract_missing'; end if;

  select p.prosrc into v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='complete_dail_cold_incremental_backup_v2';
  if v_src is null then raise exception 'incremental_completion_missing'; end if;
  if v_src not ilike '%HOLD_DAIL_COLD_READBACK_OR_RECOVERY_EVIDENCE_UNVERIFIED%' then raise exception 'missing_recovery_evidence_must_hold'; end if;
  if v_src not ilike '%HOLD_INCREMENTAL_RECOVERY_DRILL_FAILED%' then raise exception 'failed_recovery_drill_must_hold'; end if;
  if v_src not ilike '%delta_internal_chain_verified%' then raise exception 'completion_does_not_require_internal_chain_evidence'; end if;
  if v_src not ilike '%provider_write_authority_created%' or v_src not ilike '%false%' then raise exception 'authority_nonexpansion_receipt_missing'; end if;

  select p.prosrc into v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='read_dail_phase4_assurance_status_v3';
  if v_src is null then raise exception 'phase4_assurance_v3_missing'; end if;
  if v_src not ilike '%LEDGER_LINEAGE_RECOVERY_VERIFIED_INCREMENTAL%' then raise exception 'incremental_recovery_status_missing'; end if;
  if v_src not ilike '%BOUNDED_COLD_ASSURANCE_ONLY%' then raise exception 'incremental_lineage_must_remain_bounded_assurance'; end if;
  if v_src not ilike '%institutional_phase4_activation%' or v_src not ilike '%false%' then raise exception 'phase4_activation_must_remain_false'; end if;

  select p.prosrc into v_src
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_runtime' and p.proname='read_dail_phase4_assurance_status_v2';
  if v_src is null or v_src not ilike '%read_dail_phase4_assurance_status_v3%' then
    raise exception 'legacy_v2_status_contract_not_forwarded_to_v3';
  end if;

  select count(*) into v_bad_acl
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  cross join lateral unnest(coalesce(p.proacl,acldefault('f',p.proowner))) a
  where ((n.nspname='chlom_runtime' and p.proname in (
           'enqueue_dail_cold_incremental_backup_v2',
           'record_dail_cold_incremental_checkpoint_v2',
           'record_dail_incremental_recovery_drill_v2',
           'complete_dail_cold_incremental_backup_v2',
           'read_dail_phase4_assurance_status_v3',
           'read_dail_phase4_assurance_status_v2'
         ))
         or (n.nspname='public' and p.proname in (
           'dail_cold_incremental_export_job_v2',
           'dail_cold_incremental_export_chunk_v2'
         )))
    and (a::text like 'anon=%' or a::text like 'authenticated=%');
  if v_bad_acl<>0 then raise exception 'incremental_dail_function_acl_exposed'; end if;
end
$test$;

-- Pure arithmetic adversarial checks for chunk boundaries: no overlaps, no gaps
-- for representative first catch-up and later hourly deltas.
with cases(delta_first,delta_last,span) as (
  values
    (3043::bigint,1322993::bigint,10000::bigint),
    (1322994::bigint,1324137::bigint,10000::bigint),
    (10000::bigint,10001::bigint,1000::bigint),
    (10001::bigint,20000::bigint,10000::bigint)
), bounds as (
  select *,floor((delta_first-1)::numeric/span)::int first_chunk,
           floor((delta_last-1)::numeric/span)::int last_chunk
  from cases
), expanded as (
  select b.*,g chunk_no,
         greatest(delta_first,g::bigint*span+1) chunk_start,
         least(delta_last,(g::bigint+1)*span) chunk_end
  from bounds b cross join lateral generate_series(first_chunk,last_chunk) g
), assessed as (
  select delta_first,delta_last,span,
         min(chunk_start) min_start,max(chunk_end) max_end,
         sum(chunk_end-chunk_start+1) covered,
         delta_last-delta_first+1 expected
  from expanded group by delta_first,delta_last,span
)
select case when bool_and(min_start=delta_first and max_end=delta_last and covered=expected)
  then 1 else 1/0 end as chunk_partition_pass
from assessed;

rollback;
