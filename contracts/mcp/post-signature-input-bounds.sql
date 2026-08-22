-- CT-MCP-EXTCERT-001 SECURITY HOLD
-- This public file intentionally contains no runtime table, provider, operation, schema, or migration detail.
-- No migration is authorized by the invalidated prior payload.
do $$
begin
  raise exception 'CT-MCP-EXTCERT-001 is on security hold; private reviewed replacement required';
end $$;

