-- CHLOM Wallet Continuity Factory & Automation v1.0.2
-- Additive correction: integration_control.services requires non-null base_url, docs_url,
-- and credential_ref even when a service is intentionally unbound. Use explicit sentinel
-- references rather than NULL so the registry remains fail-closed without claiming a live endpoint.

DO $$
DECLARE
  ddl text;
  before_fragment text := '''CHLOM Wallet Continuity Control Plane'',null,null,''private_internal'',null,''unverified'',''configured''';
  after_fragment text := '''CHLOM Wallet Continuity Control Plane'',''internal://unbound/chlom-wallet-continuity'',''repo://CrownThrive-Support/developers/chlom-wallet-continuity-factory-v1.mdx'',''private_internal'',''NONE_CONTROLLED_TEST'',''unverified'',''configured''';
BEGIN
  select pg_get_functiondef('chlom_wallet.register_continuity_suite_v1(text)'::regprocedure) into ddl;
  if position(before_fragment in ddl) = 0 then
    raise exception 'continuity_v1_0_2_expected_service_fragment_not_found';
  end if;
  ddl := replace(ddl, before_fragment, after_fragment);
  execute ddl;
END $$;

-- pg_get_functiondef restores the function definition as stored; reassert the fixed pgcrypto path
-- and the private execution boundary after replacement.
alter function chlom_wallet.register_continuity_suite_v1(text)
  set search_path = pg_catalog, chlom_wallet, chlom_runtime, integration_control, extensions;

revoke all on function chlom_wallet.register_continuity_suite_v1(text) from public, anon, authenticated;
grant execute on function chlom_wallet.register_continuity_suite_v1(text) to service_role;
