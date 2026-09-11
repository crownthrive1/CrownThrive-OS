-- Fail-closed operational rollback for source-reconciled migration 20260904033622.
-- Production already applied chlom_dail_v4_identity_sequence_gap_tolerance before this
-- source reconciliation. Rollback therefore MUST NOT delete append-only correction evidence,
-- rewrite immutable DAIL events, or restore the known-buggy dense-sequence verifier.
-- It suspends compact verification until the exact production-approved implementation is
-- re-applied/reconciled through the governed release path.

update chlom_runtime.dail_verification_cursors_v4
set cursor_state='SUSPENDED',
    last_error=jsonb_build_object(
      'rollback','20260904033622_chlom_dail_v4_identity_sequence_gap_tolerance',
      'state','SUSPENDED_FAIL_CLOSED',
      'reason','gap-tolerance verifier withdrawn from active execution; append-only correction evidence retained',
      'immutable_dail_events_mutated',false,
      'correction_evidence_deleted',false,
      'known_buggy_dense_verifier_restored',false,
      'reapply_required',true
    ),
    last_run_at=clock_timestamp(),
    updated_at=clock_timestamp()
where cursor_key='canonical';

comment on function chlom_runtime.dail_verify_next_segment_v4(integer) is
'Rollback posture: verifier implementation is retained but canonical cursor is suspended fail-closed until governed reapply/reconciliation. Immutable DAIL events and algorithm-correction evidence remain untouched.';
