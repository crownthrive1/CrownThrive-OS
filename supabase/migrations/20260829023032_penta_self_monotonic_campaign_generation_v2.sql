do $$
declare
  v_definition text;
begin
  select pg_get_functiondef('penta_self.enforce_desired_state_v1()'::regprocedure) into v_definition;
  v_definition:=replace(v_definition,
    'set state=''active'',daily_cap=200,monthly_cap=5000,expires_at=null,nonrenewing=false',
    'set state=''active'',daily_cap=200,monthly_cap=5000,expires_at=''2099-12-31 23:59:59+00''::timestamptz,nonrenewing=false');
  v_definition:=replace(v_definition,
    'or expires_at is not null or nonrenewing is distinct from false',
    'or expires_at<''2099-12-31 23:59:59+00''::timestamptz or nonrenewing is distinct from false');
  execute v_definition;
end $$;

insert into penta_self.desired_state_contracts_v1(contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,evidence_sha256)
select
  'ct.pentaself.control.locticians-campaign',2,'control','locticians_growth_campaign',
  jsonb_build_object('state','active','daily_cap',200,'monthly_cap',5000,'expires_at','2099-12-31T23:59:59Z','nonrenewing',false,'provider_write_authority',true,'money_movement_authority',false,'credential_authority',false,'rollback_rule','higher_generation_supersession_only'),
  'production:2026-08-29:pentaself-permanence-v2','ct.pentamarketer.locticians.dynamic-outreach.v3','PentaSELF/PentaMarketer',
  encode(extensions.digest(jsonb_build_object('contract_key','ct.pentaself.control.locticians-campaign','generation',2,'target_key','locticians_growth_campaign','state','active','daily_cap',200,'monthly_cap',5000,'expires_at','2099-12-31T23:59:59Z')::text,'sha256'),'hex');

select penta_self.enforce_desired_state_v1();