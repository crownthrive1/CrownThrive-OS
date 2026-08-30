-- CrownThrive Penta Runtime Reference Verifier v2 — bare function-signature repair
-- Builder: PentaBuild/PentaCrawler
-- Independent certification remains PentaCertifier-owned.
-- Scope: database runtime_ref forms such as schema.function(type) and schema.function().
-- Does not weaken provider readback requirements for GitHub, Supabase Edge, or URL references.

create or replace function public.penta_runtime_reference_check_v2(p_system_key text, p_runtime_ref text)
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','public','integration_control','extensions'
as $function$
declare
  v_ref text:=btrim(coalesce(p_runtime_ref,''));
  v_target text;
  v_slug text;
  v_expected_version text;
  v_obs integration_control.penta_census_provider_observations_v1%rowtype;
  v_reg regclass;
  v_proc regprocedure;
  v_count integer:=0;
  v_part text;
  v_check jsonb;
  v_checks jsonb:='[]'::jsonb;
  v_all boolean:=true;
  v_parts integer:=0;
  v_base jsonb;
begin
  if v_ref='' then
    return jsonb_build_object('verified',false,'kind','missing','reason','runtime_ref_missing','system_key',p_system_key,'runtime_ref',p_runtime_ref);
  end if;

  if position(';' in v_ref)>0 then
    for v_part in select btrim(x) from regexp_split_to_table(v_ref,';') x where btrim(x)<>'' loop
      v_check:=public.penta_runtime_reference_check_v2(p_system_key,v_part);
      v_checks:=v_checks||jsonb_build_array(v_check);
      v_parts:=v_parts+1;
      v_all:=v_all and coalesce((v_check->>'verified')::boolean,false);
    end loop;
    return jsonb_build_object('verified',v_all,'kind','composite_runtime_reference','system_key',p_system_key,'runtime_ref',v_ref,'part_count',v_parts,'checks',v_checks);
  end if;

  if v_ref like 'view:%' then
    v_target:=substring(v_ref from 6);
    v_reg:=to_regclass(v_target);
    return jsonb_build_object('verified',v_reg is not null,'kind','database_view','system_key',p_system_key,'runtime_ref',v_ref,'target',v_target,'resolved_regclass',v_reg::text);
  end if;

  if v_ref like 'queue:%' then
    v_target:=substring(v_ref from 7);
    v_reg:=to_regclass(v_target);
    return jsonb_build_object('verified',v_reg is not null,'kind','database_queue_relation','system_key',p_system_key,'runtime_ref',v_ref,'target',v_target,'resolved_regclass',v_reg::text);
  end if;

  if v_ref like 'function:%' or v_ref like 'rpc:%' then
    v_target:=regexp_replace(v_ref,'^(function:|rpc:)','','i');
    begin
      if position('(' in v_target)>0 then
        v_proc:=to_regprocedure(v_target);
        return jsonb_build_object('verified',v_proc is not null,'kind','database_function','system_key',p_system_key,'runtime_ref',v_ref,'target',v_target,'resolved_regprocedure',v_proc::text);
      end if;
    exception when others then
      v_proc:=null;
    end;
    if position('.' in v_target)>0 then
      select count(*) into v_count
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname=split_part(v_target,'.',1) and p.proname=split_part(v_target,'.',2);
      return jsonb_build_object('verified',v_count>0,'kind','database_function_name','system_key',p_system_key,'runtime_ref',v_ref,'target',v_target,'matching_overloads',v_count);
    else
      select count(*) into v_count
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where p.proname=v_target and n.nspname not in ('pg_catalog','information_schema');
      return jsonb_build_object('verified',v_count=1,'kind','database_function_bare_name','system_key',p_system_key,'runtime_ref',v_ref,'target',v_target,'matching_functions',v_count,'reason',case when v_count>1 then 'ambiguous_bare_function_name' when v_count=0 then 'function_missing' else null end);
    end if;
  end if;

  if v_ref ~ '^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\([^;]*\)$' then
    begin
      v_proc:=to_regprocedure(v_ref);
    exception when others then
      v_proc:=null;
    end;
    return jsonb_build_object('verified',v_proc is not null,'kind','database_function_signature','system_key',p_system_key,'runtime_ref',v_ref,'target',v_ref,'resolved_regprocedure',v_proc::text,'verifier_version','v2-bare-signature-v3');
  end if;

  if v_ref like 'github-actions:%' or v_ref like 'scripts/%' or v_ref like '.github/%' or position(' + ' in v_ref)>0 then
    select * into v_obs from integration_control.penta_census_provider_observations_v1
    where lower(provider_system)='github' and resource_type='runtime_reference' and resource_id=p_system_key
      and observed_state in ('ACTIVE','READY','PASS','VERIFIED') and observed_at>=now()-interval '24 hours'
    order by observed_at desc limit 1;
    return jsonb_build_object('verified',found,'kind','github_provider_readback','system_key',p_system_key,'runtime_ref',v_ref,
      'provider_observation_key',case when found then v_obs.observation_key else null end,
      'provider_observed_at',case when found then v_obs.observed_at else null end,
      'provider_evidence_sha256',case when found then v_obs.evidence_sha256 else null end,
      'source_ref_match',case when found then v_obs.source_ref=v_ref else false end);
  end if;

  if v_ref ~* '^https?://' then
    select * into v_obs from integration_control.penta_census_provider_observations_v1
    where resource_type='url_runtime' and resource_id=v_ref and observed_state in ('ACTIVE','READY','PASS','VERIFIED')
      and observed_at>=now()-interval '24 hours'
    order by observed_at desc limit 1;
    return jsonb_build_object('verified',found,'kind','url_provider_readback','system_key',p_system_key,'runtime_ref',v_ref,
      'provider_observation_key',case when found then v_obs.observation_key else null end,
      'provider_observed_at',case when found then v_obs.observed_at else null end,
      'provider_evidence_sha256',case when found then v_obs.evidence_sha256 else null end);
  end if;

  if v_ref like 'edge:%' or v_ref like 'supabase://edge/%' or v_ref like 'supabase-edge:%' or v_ref like 'supabase:%' or exists(
      select 1 from integration_control.penta_census_provider_observations_v1 o
      where lower(o.provider_system) like 'supabase%' and o.resource_type='edge_function' and o.resource_id=v_ref
    ) then
    if v_ref like 'edge:%' then v_slug:=substring(v_ref from 6);
    elsif v_ref like 'supabase://edge/%' then v_slug:=substring(v_ref from 17);
    elsif v_ref like 'supabase-edge:%' then v_slug:=substring(v_ref from 15);
    elsif v_ref like 'supabase:%:%' then v_slug:=split_part(v_ref,':',3);
    else v_slug:=v_ref;
    end if;
    v_slug:=split_part(v_slug,'?',1);
    if position('@' in v_slug)>0 then v_expected_version:=split_part(v_slug,'@',2); v_slug:=split_part(v_slug,'@',1); end if;
    select * into v_obs from integration_control.penta_census_provider_observations_v1
    where lower(provider_system) like 'supabase%' and resource_type='edge_function' and resource_id=v_slug
      and observed_state in ('ACTIVE','READY','PASS','VERIFIED') and observed_at>=now()-interval '24 hours'
      and (v_expected_version is null or coalesce(attributes->>'version','')=v_expected_version)
    order by observed_at desc limit 1;
    return jsonb_build_object('verified',found,'kind','supabase_edge_provider_readback','system_key',p_system_key,'runtime_ref',v_ref,'provider_slug',v_slug,
      'expected_provider_version',v_expected_version,'provider_version',case when found then v_obs.attributes->>'version' else null end,
      'provider_observation_key',case when found then v_obs.observation_key else null end,
      'provider_observed_at',case when found then v_obs.observed_at else null end,
      'provider_evidence_sha256',case when found then v_obs.evidence_sha256 else null end,
      'provider_digest',case when found then v_obs.attributes->>'ezbr_sha256' else null end);
  end if;

  v_base:=public.penta_runtime_reference_check_v1(p_system_key,p_runtime_ref);
  return v_base||jsonb_build_object('verifier_version','v2-fallback-v1');
end;
$function$;

create or replace function public.penta_runtime_reference_regression_v2()
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','public'
as $function$
declare r record; c jsonb; results jsonb:='[]'::jsonb; n int:=0; p int:=0;
begin
  for r in
    select * from (values
      ('ct.dail.human.v1','view:chlom_runtime.dail_human_v1'),
      ('ct.penta.mail.v1','edge:penta-mail'),
      ('ct.penta.pm.v1','github-actions:.github/workflows/penta-pm-governance.yml'),
      ('ct.system.crown-affiliates','https://crownaffiliates.com'),
      ('ct.system.go-flipbooks','go-flipbooks-api-control'),
      ('ct.system.openai-penta-inference','function:integration_control.openai_penta_generate_v1'),
      ('penta.discovery','supabase-edge:penta-discovery'),
      ('penta.context','edge:penta-context@2;rpc:public.penta_context_query_v1;queue:public.penta_context_ingest_queue_v1'),
      ('PentaGovernance','supabase:tzajnzshmtzjenqulehq:penta-governance-control'),
      ('pentaofac','supabase://edge/penta-ofac'),
      ('penta.pr','scripts/penta_pr_lifecycle.py + .github/workflows/penta-pr-lifecycle.yml'),
      ('penta.family.surgical-care','public.penta_self_hard_repair_status_v1()'),
      ('penta.rounds','penta_dnd.hard_repair_contract_test_v1(uuid)'),
      ('penta.surgeon','penta_self.hard_repair_cycle_v1(uuid)')
    ) v(system_key,runtime_ref)
  loop
    c:=public.penta_runtime_reference_check_v2(r.system_key,r.runtime_ref);
    n:=n+1; if coalesce((c->>'verified')::boolean,false) then p:=p+1; end if;
    results:=results||jsonb_build_array(jsonb_build_object('system_key',r.system_key,'runtime_ref',r.runtime_ref,'check',c));
  end loop;
  return jsonb_build_object('contract','ct.penta.runtime-reference-verifier.v2','cases',n,'passed',p,'failed',n-p,'all_passed',p=n,'results',results,'observed_at',now(),'parser_revision','v2-bare-signature-v3');
end;
$function$;
