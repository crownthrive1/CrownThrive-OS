-- CHLOM Wallet Continuity Factory & Automation v1.0.3
-- Additive performance hardening after targeted FK-index readback.
-- No authority, lifecycle, provider, Rights, money, chain, checkout or phase boundary changes.

create index if not exists continuity_canary_suite_idx
  on chlom_wallet.continuity_canary_runs_v1(suite_ref);

create index if not exists continuity_oracle_observations_connection_idx
  on chlom_wallet.continuity_oracle_observations_v1(connection_ref);

create index if not exists continuity_recovery_plans_suite_idx
  on chlom_wallet.continuity_recovery_plans_v1(suite_ref);
