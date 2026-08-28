alter table crm.penta_marketer_campaign_v1
  drop constraint if exists penta_marketer_campaign_v1_monthly_cap_check;

alter table crm.penta_marketer_campaign_v1
  add constraint penta_marketer_campaign_v1_monthly_cap_check
  check (monthly_cap >= 1 and monthly_cap <= 500);

update crm.penta_marketer_campaign_v1
set monthly_cap = 500,
    metadata = jsonb_set(
      coalesce(metadata, '{}'::jsonb),
      '{global_monthly_outreach_ceiling}',
      '500'::jsonb,
      true
    )
where campaign_id = 'ct.pentamarketer.locticians.claim.20260827.v1';

notify pgrst, 'reload schema';
