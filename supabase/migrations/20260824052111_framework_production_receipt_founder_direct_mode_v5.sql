-- Live migration: 20260824052111 / framework_production_receipt_founder_direct_mode_v5
-- Extends the immutable production-receipt authority vocabulary so explicit human founder_direct
-- activations can be recorded without weakening existing independent, deadlock, or rollback modes.

alter table chlom_runtime.framework_production_receipts_v1
  drop constraint if exists framework_production_receipts_v1_authority_mode_check;

alter table chlom_runtime.framework_production_receipts_v1
  add constraint framework_production_receipts_v1_authority_mode_check
  check (authority_mode = any (array[
    'agent_d_certification'::text,
    'founder_override'::text,
    'founder_direct'::text,
    'rollback_only'::text
  ]));

comment on constraint framework_production_receipts_v1_authority_mode_check
  on chlom_runtime.framework_production_receipts_v1
  is 'Production receipt authority vocabulary: independent Agent D, ask-first Founder deadlock override, explicit human founder_direct, or rollback-only authority reduction.';
