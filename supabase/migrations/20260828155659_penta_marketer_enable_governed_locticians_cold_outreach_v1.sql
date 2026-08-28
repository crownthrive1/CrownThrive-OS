update crm.outbound_config
set cold_outreach_enabled=true,
    updated_at=now()
where singleton=true;
