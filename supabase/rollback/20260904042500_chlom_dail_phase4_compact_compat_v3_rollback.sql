-- Rollback for 20260904042500_chlom_dail_phase4_compact_compat_v3.sql.
-- Restores the prior Phase-4 assurance reader contract. This rollback is fail closed
-- with compact v4 output because missing tail_failure_count evaluates HOT as FAIL.

create or replace function chlom_runtime.read_dail_phase4_assurance_status_v2(
  p_max_checkpoint_age_seconds bigint default 93600
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'chlom_runtime'
set "TimeZone" to 'UTC'
as $function$
declare
  v_verification jsonb;
  v_hot_state text;
  v_checkpoint chlom_runtime.dail_cold_checkpoints_v1%rowtype;
  v_drill chlom_runtime.dail_recovery_drill_receipts_v1%rowtype;
  v_checkpoint_age_seconds bigint;
  v_cold_state text;
  v_assurance_state text;
begin
  if p_max_checkpoint_age_seconds is null
     or p_max_checkpoint_age_seconds<=0
     or p_max_checkpoint_age_seconds>604800 then
    raise exception 'checkpoint age threshold must be between 1 and 604800 seconds' using errcode='22023';
  end if;

  v_verification:=chlom_runtime.verify_dail_chain_checkpoint_v3();
  v_hot_state:=case
    when coalesce((v_verification->>'ok')::boolean,false)
      and coalesce((v_verification->>'tail_failure_count')::bigint,-1)=0 then 'PASS'
    else 'FAIL'
  end;

  select c.* into v_checkpoint
  from chlom_runtime.dail_cold_checkpoints_v1 c
  order by c.snapshot_created_at desc,c.recorded_at desc
  limit 1;

  if not found then
    return jsonb_build_object(
      'hot_route',jsonb_build_object(
        'state',v_hot_state,
        'integrity_state',v_verification->>'integrity_state',
        'verification_mode',v_verification->>'verification_mode',
        'tail_checked_events',(v_verification->>'tail_checked_events')::bigint,
        'head_hash',v_verification->>'current_head_hash',
        'checked_at',v_verification->>'checked_at'
      ),
      'cold_route',jsonb_build_object('state','HOLD_NO_CHECKPOINT'),
      'component_phase4_assurance_state','HOLD',
      'institutional_phase4_activation',false,
      'full_chain_scan_executed',false
    );
  end if;

  v_checkpoint_age_seconds:=greatest(0,ceil(extract(epoch from clock_timestamp()-v_checkpoint.snapshot_created_at))::bigint);

  select x.* into v_drill
  from chlom_runtime.dail_recovery_drill_receipts_v1 x
  where x.checkpoint_id=v_checkpoint.checkpoint_id and x.result='PASS'
  order by x.drill_completed_at desc
  limit 1;

  if v_checkpoint_age_seconds>p_max_checkpoint_age_seconds then
    v_cold_state:='HOLD_STALE_CHECKPOINT';
  elsif not found then
    v_cold_state:='HOLD_LATEST_CHECKPOINT_UNTESTED';
  else
    v_cold_state:=case v_drill.test_scope
      when 'full_data_restore' then 'FULL_DATA_RECOVERY_VERIFIED'
      when 'ledger_lineage' then 'LEDGER_LINEAGE_RECOVERY_VERIFIED'
      else 'METADATA_RECOVERY_VERIFIED'
    end;
  end if;

  v_assurance_state:=case
    when v_hot_state<>'PASS' then 'HOLD_HOT_ROUTE'
    when v_cold_state='FULL_DATA_RECOVERY_VERIFIED' then 'READY_FOR_INDEPENDENT_PHASE4_READBACK'
    when v_cold_state in ('LEDGER_LINEAGE_RECOVERY_VERIFIED','METADATA_RECOVERY_VERIFIED') then 'BOUNDED_COLD_ASSURANCE_ONLY'
    else 'HOLD'
  end;

  return jsonb_build_object(
    'hot_route',jsonb_build_object(
      'state',v_hot_state,
      'integrity_state',v_verification->>'integrity_state',
      'verification_mode',v_verification->>'verification_mode',
      'checkpoint_id',v_verification->>'checkpoint_id',
      'tail_checked_events',(v_verification->>'tail_checked_events')::bigint,
      'tail_failure_count',(v_verification->>'tail_failure_count')::bigint,
      'head_hash',v_verification->>'current_head_hash',
      'checked_at',v_verification->>'checked_at'
    ),
    'cold_route',jsonb_build_object(
      'state',v_cold_state,
      'checkpoint_id',v_checkpoint.checkpoint_id,
      'source_event_count',v_checkpoint.source_event_count,
      'source_max_sequence_id',v_checkpoint.source_max_sequence_id,
      'source_head_event_hash',v_checkpoint.source_head_event_hash,
      'checkpoint_receipt_sha256',v_checkpoint.checkpoint_receipt_sha256,
      'snapshot_created_at',v_checkpoint.snapshot_created_at,
      'checkpoint_age_seconds',v_checkpoint_age_seconds,
      'snapshot_rpo_seconds',v_checkpoint.snapshot_rpo_seconds,
      'last_passing_drill_id',v_drill.drill_id,
      'last_passing_test_scope',v_drill.test_scope,
      'last_passing_drill_completed_at',v_drill.drill_completed_at,
      'last_passing_drill_rpo_seconds',v_drill.observed_rpo_seconds,
      'last_passing_drill_rto_seconds',v_drill.observed_rto_seconds
    ),
    'component_phase4_assurance_state',v_assurance_state,
    'institutional_phase4_activation',false,
    'full_chain_scan_executed',false,
    'exhaustive_verifier_retained','chlom_runtime.verify_dail_chain()'
  );
end;
$function$;

revoke all on function chlom_runtime.read_dail_phase4_assurance_status_v2(bigint) from public,anon,authenticated;
grant execute on function chlom_runtime.read_dail_phase4_assurance_status_v2(bigint) to service_role;
