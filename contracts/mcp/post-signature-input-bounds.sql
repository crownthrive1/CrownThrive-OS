-- CT-MCP-EXTCERT-001
-- POST-SIGNATURE ONLY. Do not apply while founder_signature.state != 'signed'.
-- Additive tightening only: no tool, endpoint, service, audit row, history, or prior contract is deleted.

begin;

update integration_control.mcp_tools
set input_schema = jsonb_set(input_schema, '{additionalProperties}', 'false'::jsonb, true),
    updated_at = now()
where enabled = true
  and service_id in ('crownthrive_io','thrivetools_seo')
  and tool_name in (
    'crownthrive_io_list_data',
    'crownthrive_io_list_domains',
    'crownthrive_io_list_my_team_memberships',
    'crownthrive_io_list_notification_handlers',
    'crownthrive_io_list_pixels',
    'crownthrive_io_list_qr_codes',
    'crownthrive_io_list_splash_pages',
    'crownthrive_io_list_teams',
    'crownthrive_io_statistics'
  );

-- Must be exactly 20 enabled central D0 tools and zero permissive central inputs.
do $$
declare
  v_enabled integer;
  v_permissive integer;
begin
  select count(*) into v_enabled
  from integration_control.mcp_tools
  where enabled = true and service_id in ('crownthrive_io','thrivetools_seo');

  select count(*) into v_permissive
  from integration_control.mcp_tools
  where enabled = true
    and service_id in ('crownthrive_io','thrivetools_seo')
    and coalesce((input_schema->>'additionalProperties')::boolean, true) = true;

  if v_enabled <> 20 then
    raise exception 'CT-MCP-EXTCERT-001 expected 20 central enabled tools, found %', v_enabled;
  end if;
  if v_permissive <> 0 then
    raise exception 'CT-MCP-EXTCERT-001 central permissive input schemas remain: %', v_permissive;
  end if;
end $$;

commit;
