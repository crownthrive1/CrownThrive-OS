update crm.penta_marketer_campaign_v1
set state='active',
    metadata=metadata||jsonb_build_object(
      'cold_outreach_enabled_at',now(),
      'cold_outreach_enabled_by','founder_directive_2026-08-28',
      'safe_conflict_mode',true,
      'research_required',true,
      'claimable_profile_required_for_locticians_cold',true
    )
where campaign_id='ct.pentamarketer.locticians.claim.20260827.v1';
