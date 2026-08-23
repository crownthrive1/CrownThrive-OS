-- CHLOM Wallet Continuity Factory & Automation v1.0.1
-- Additive correction: pgcrypto is installed in the `extensions` schema on ThriveBase.
-- The v1 registration/tick functions intentionally use fixed SECURITY DEFINER search paths,
-- so `extensions` must be present for digest(...). No authority or capability boundary changes.

alter function chlom_wallet.register_continuity_suite_v1(text)
  set search_path = pg_catalog, chlom_wallet, chlom_runtime, integration_control, extensions;

alter function chlom_wallet.continuity_tick_v1()
  set search_path = pg_catalog, chlom_wallet, chlom_runtime, extensions;

-- Preserve private execution boundary explicitly after the correction.
revoke all on function chlom_wallet.register_continuity_suite_v1(text) from public, anon, authenticated;
revoke all on function chlom_wallet.continuity_tick_v1() from public, anon, authenticated;
grant execute on function chlom_wallet.register_continuity_suite_v1(text) to service_role;
grant execute on function chlom_wallet.continuity_tick_v1() to service_role;
