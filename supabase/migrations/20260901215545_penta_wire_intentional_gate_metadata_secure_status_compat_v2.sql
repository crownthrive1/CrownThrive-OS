-- PentaWire intentional-gate metadata secure-status compatibility v2
-- Provider-applied migration identity: 20260901215545
-- The v1 normalization made the lifecycle classifier recognize these disabled
-- tools but moved the provider-specific INTENTIONAL_*_GATING token away from
-- column start, breaking penta_wire_secure_adapter_status_v1's anchored matcher.
-- This append-only correction restores the original token at column start and
-- retains an explicit classifier-recognized "INTENTIONALLY GATED" phrase.
-- No tool is enabled and no risk/approval/provider/credential authority changes.

do $$
declare
  v_changed integer;
begin
  with expected(tool_name, old_notes) as (
    values
      ('ga4_metadata_read'::text, 'INTENTIONAL_ACCOUNT_GATING: GA4 Data API OAuth/property credentials are required; the current ThriveBase credential is a Measurement ID only.'::text),
      ('ga4_realtime_run'::text, 'INTENTIONAL_ACCOUNT_GATING: GA4 Data API OAuth/property credentials are required; the current ThriveBase credential is a Measurement ID only.'::text),
      ('ga4_report_run'::text, 'INTENTIONAL_ACCOUNT_GATING: GA4 Data API OAuth/property credentials are required; the current ThriveBase credential is a Measurement ID only.'::text),
      ('meta_login_identity_status'::text, 'INTENTIONAL_ACCOUNT_GATING: A user access token is required for /me; ThriveBase currently holds the app ID and app secret only.'::text),
      ('meta_login_permissions_status'::text, 'INTENTIONAL_ACCOUNT_GATING: A user access token is required for /me/permissions; ThriveBase currently holds the app ID and app secret only.'::text),
      ('meta_login_token_debug'::text, 'INTENTIONAL_SECURITY_GATING: Token debugging requires a separately scoped app access token plus an explicit input token; neither may be inferred or exposed.'::text),
      ('openai_billing_status'::text, 'INTENTIONAL_POLICY_GATING: No standard project-key billing-status endpoint is asserted; PentaWire will not invent one.'::text),
      ('unsplash_download_track'::text, 'INTENTIONAL_POLICY_GATING: Download tracking changes the provider counter and requires separate explicit side-effect authority.'::text)
  ), updated as (
    update integration_control.mcp_tools t
       set notes = e.old_notes || ' Lifecycle: INTENTIONALLY GATED.',
           updated_at = clock_timestamp()
      from expected e
     where t.tool_name = e.tool_name
       and t.notes = 'INTENTIONALLY GATED: ' || e.old_notes
       and t.enabled = false
       and coalesce(t.input_schema->>'additionalProperties','') = 'false'
    returning t.tool_name
  )
  select count(*) into v_changed from updated;

  if v_changed <> 8 then
    raise exception 'penta_wire_intentional_gate_secure_status_compat_expected_8_changed_got_%', v_changed;
  end if;
end
$$;
