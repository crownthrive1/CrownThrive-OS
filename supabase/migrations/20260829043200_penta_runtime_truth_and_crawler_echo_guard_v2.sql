-- Current-truth verification for production Pentas.
-- Locally verifiable DB references are checked directly; provider references require
-- fresh provider observations. Aggregate fail-closed projections do not recursively
-- manufacture new root incidents.

insert into integration_control.penta_census_provider_observations_v1(
  observation_key,provider_system,resource_type,resource_id,resource_name,
  source_ref,observed_state,attributes,observed_at,evidence_sha256
)
select
  'supabase-edge:'||v.slug,'Supabase','edge_function',v.slug,v.slug,
  'supabase-edge-function-readback','ACTIVE',
  jsonb_build_object(
    'version',v.version,'function_id',v.function_id,'verify_jwt',v.verify_jwt,
    'provider_readback',true,'authority_created',false
  ),
  now(),
  encode(extensions.digest(convert_to(jsonb_build_object(
    'slug',v.slug,'version',v.version,'function_id',v.function_id,
    'verify_jwt',v.verify_jwt,'state','ACTIVE'
  )::text,'UTF8'),'sha256'),'hex')
from (values
  ('penta-mail',5,'292a31b6-4a8e-4ca5-8bcf-02c502482fcf',false),
  ('penta-heartbeat',1,'4109934d-0d15-4e9b-bc3b-8ded9352717c',true),
  ('pentaod-control',1,'8c4b30be-3d4f-41b0-b541-75a7c7f7f9fe',true),
  ('penta-federation-control',2,'ec7e2e28-203a-40db-a76a-61b9b3ee1aa2',true),
  ('penta-helper',3,'8be2c4db-97a3-4d09-b0bc-acdf06a3a8b5',false),
  ('penta-liaison',1,'4decefbe-41e8-4281-9bb2-e4e1ebffdd6d',true),
  ('penta-governance-control',1,'8222a50b-9359-4116-b22c-18993423aa12',true),
  ('penta-ofac',2,'ebe3d2b9-3d19-4bc8-b84b-3af705371ebe',false),
  ('penta-police-control',1,'5acfe0a7-5d9b-47f1-bd8c-59cdf1e01000',true),
  ('penta-policy-control',1,'05ba0803-3215-4244-8389-805d82b694e1',true),
  ('penta-context',2,'e111f3eb-a3c7-488e-92b9-f55d3e63bbce',false),
  ('penta-flow',1,'e3ca7b47-9fdb-408a-92f1-936585998256',false),
  ('penta-crawler',1,'ee7883ef-f4da-4184-8bc1-d1f76d7b7108',false),
  ('go-flipbooks-api-control',2,'cded6f48-59ab-4025-893c-6e841587cefd',true)
) v(slug,version,function_id,verify_jwt)
on conflict(observation_key) do update set
  provider_system=excluded.provider_system,
  resource_type=excluded.resource_type,
  resource_id=excluded.resource_id,
  resource_name=excluded.resource_name,
  source_ref=excluded.source_ref,
  observed_state=excluded.observed_state,
  attributes=excluded.attributes,
  observed_at=excluded.observed_at,
  evidence_sha256=excluded.evidence_sha256;

insert into integration_control.penta_census_provider_observations_v1(
  observation_key,provider_system,resource_type,resource_id,resource_name,
  source_ref,observed_state,attributes,observed_at,evidence_sha256
)
values
  (
    'github-runtime:penta.pr','GitHub','runtime_reference','penta.pr','PentaPR',
    'scripts/penta_pr_lifecycle.py + .github/workflows/penta-pr-lifecycle.yml','ACTIVE',
    jsonb_build_object(
      'repository','crownthrive1/CrownThrive-OS','branch','main',
      'script_blob_sha','bbdd08b170aa4da0b82a7c9e0b7c040ef77efb16',
      'workflow_blob_sha','081ac06e1402708cdec59d19119fa35eb8e5382c',
      'provider_readback',true,'authority_created',false
    ),now(),
    encode(extensions.digest(convert_to(
      'penta.pr|bbdd08b170aa4da0b82a7c9e0b7c040ef77efb16|081ac06e1402708cdec59d19119fa35eb8e5382c','UTF8'
    ),'sha256'),'hex')
  ),
  (
    'github-runtime:penta.tagger','GitHub','runtime_reference','penta.tagger','PentaTagger',
    'scripts/penta_github_tagger.py + .github/workflows/penta-github-tagger.yml','ACTIVE',
    jsonb_build_object(
      'repository','crownthrive1/CrownThrive-OS','branch','main',
      'script_blob_sha','f1998ba986d3f349c99e9557ef5613d1aaf042ce',
      'workflow_blob_sha','502e6e7f2d756949463f79907cca4b3ac460c820',
      'provider_readback',true,'authority_created',false
    ),now(),
    encode(extensions.digest(convert_to(
      'penta.tagger|f1998ba986d3f349c99e9557ef5613d1aaf042ce|502e6e7f2d756949463f79907cca4b3ac460c820','UTF8'
    ),'sha256'),'hex')
  )
on conflict(observation_key) do update set
  provider_system=excluded.provider_system,
  resource_type=excluded.resource_type,
  resource_id=excluded.resource_id,
  resource_name=excluded.resource_name,
  source_ref=excluded.source_ref,
  observed_state=excluded.observed_state,
  attributes=excluded.attributes,
  observed_at=excluded.observed_at,
  evidence_sha256=excluded.evidence_sha256;

update public.penta_system_registry
set runtime_ref='function:penta_runtime.penta_governance_status_v1()',
    metadata=metadata||jsonb_build_object(
      'runtime_reference_reconciled',jsonb_build_object(
        'previous','schema:penta_three_branch_governance',
        'current','function:penta_runtime.penta_governance_status_v1()',
        'basis','live_status_function_and_public_governance_tables',
        'reconciled_at',now(),'authority_created',false
      )
    ),updated_at=now()
where system_key='penta.democracy'
  and runtime_ref='schema:penta_three_branch_governance';

update public.penta_system_registry
set runtime_ref='function:penta_runtime.penta_workforce_status_v1()',
    metadata=metadata||jsonb_build_object(
      'runtime_reference_reconciled',jsonb_build_object(
        'previous','schema:penta_workforce',
        'current','function:penta_runtime.penta_workforce_status_v1()',
        'basis','live_status_function_and_public_workforce_tables',
        'reconciled_at',now(),'authority_created',false
      )
    ),updated_at=now()
where system_key='penta.workforce'
  and runtime_ref='schema:penta_workforce';

create table if not exists public.penta_runtime_reference_receipts_v1(
  receipt_id uuid primary key default gen_random_uuid(),
  system_key text not null,
  runtime_ref text,
  verification_kind text not null,
  verified boolean not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);

alter table public.penta_runtime_reference_receipts_v1 enable row level security;
revoke all on public.penta_runtime_reference_receipts_v1 from public,anon,authenticated;
grant select,insert on public.penta_runtime_reference_receipts_v1 to service_role;
drop policy if exists penta_runtime_reference_receipts_select_v1 on public.penta_runtime_reference_receipts_v1;
create policy penta_runtime_reference_receipts_select_v1
  on public.penta_runtime_reference_receipts_v1 for select to service_role using(true);
drop policy if exists penta_runtime_reference_receipts_insert_v1 on public.penta_runtime_reference_receipts_v1;
create policy penta_runtime_reference_receipts_insert_v1
  on public.penta_runtime_reference_receipts_v1 for insert to service_role with check(true);

create or replace function public.penta_runtime_reference_receipts_immutable_v1()
returns trigger language plpgsql security definer set search_path=pg_catalog,public as $$
begin
  raise exception 'penta_runtime_reference_receipts_v1 is append-only';
end $$;
revoke all on function public.penta_runtime_reference_receipts_immutable_v1() from public,anon,authenticated;
grant execute on function public.penta_runtime_reference_receipts_immutable_v1() to service_role;
drop trigger if exists penta_runtime_reference_receipts_immutable_v1 on public.penta_runtime_reference_receipts_v1;
create trigger penta_runtime_reference_receipts_immutable_v1
before update or delete on public.penta_runtime_reference_receipts_v1
for each row execute function public.penta_runtime_reference_receipts_immutable_v1();

create or replace function public.penta_runtime_reference_check_v1(
  p_system_key text,p_runtime_ref text
) returns jsonb
language plpgsql stable security definer
set search_path=pg_catalog,public,integration_control,extensions
as $$
declare
  v_ref text:=btrim(coalesce(p_runtime_ref,''));
  v_target text;
  v_schema text;
  v_name text;
  v_extension text;
  v_expected_version text;
  v_actual_version text;
  v_slug text;
  v_exists boolean:=false;
  v_kind text:='unresolved';
  v_matches integer:=0;
  v_observation_key text;
  v_observed_at timestamptz;
  v_primitive text;
begin
  if v_ref='' then
    return jsonb_build_object('verified',false,'kind','missing','runtime_ref',p_runtime_ref,'reason','runtime_ref_missing');
  end if;

  if v_ref like 'table:%' then
    v_kind:='database_relation';
    v_target:=substring(v_ref from 7);
    if position('.' in v_target)>0 then
      begin v_exists:=to_regclass(v_target) is not null;
      exception when others then v_exists:=false; end;
    else
      select count(*) into v_matches
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where c.relname=v_target
        and n.nspname not in ('pg_catalog','information_schema')
        and n.nspname not like 'pg_toast%';
      v_exists:=v_matches>0;
    end if;
  elsif v_ref like 'schema:%' then
    v_kind:='database_schema';
    v_target:=substring(v_ref from 8);
    select exists(select 1 from pg_namespace where nspname=v_target) into v_exists;
  elsif v_ref like 'function:%' or v_ref like 'rpc:%' then
    v_kind:=case when v_ref like 'rpc:%' then 'database_rpc' else 'database_function' end;
    v_target:=substring(v_ref from case when v_ref like 'rpc:%' then 5 else 10 end);
    begin v_exists:=to_regprocedure(v_target) is not null;
    exception when others then v_exists:=false; end;
  elsif v_ref like 'postgres:%' then
    v_kind:='postgres_function';
    v_target:=substring(v_ref from 10);
    if position('(' in v_target)>0 then
      begin v_exists:=to_regprocedure(v_target) is not null;
      exception when others then v_exists:=false; end;
    elsif v_target ~ '^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$' then
      v_schema:=split_part(v_target,'.',1);
      v_name:=split_part(v_target,'.',2);
      select exists(
        select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname=v_schema and p.proname=v_name
      ) into v_exists;
    end if;
  elsif v_ref like 'extension:%' then
    v_kind:='database_extension';
    v_target:=substring(v_ref from 11);
    v_extension:=split_part(v_target,'@',1);
    v_expected_version:=nullif(split_part(v_target,'@',2),'');
    select extversion into v_actual_version from pg_extension where extname=v_extension;
    v_exists:=v_actual_version is not null
      and (v_expected_version is null or v_actual_version=v_expected_version);
  elsif v_ref like 'edge:%' or v_ref like 'supabase://edge/%' or v_ref like 'supabase:%' then
    v_kind:='supabase_edge_provider_readback';
    if v_ref like 'edge:%' then
      v_slug:=substring(v_ref from 6);
    elsif v_ref like 'supabase://edge/%' then
      v_slug:=substring(v_ref from 17);
    else
      v_slug:=split_part(v_ref,':',3);
    end if;
    v_slug:=split_part(split_part(split_part(v_slug,';',1),'@',1),'?',1);
    select observation_key,observed_at
    into v_observation_key,v_observed_at
    from integration_control.penta_census_provider_observations_v1
    where provider_system='Supabase'
      and resource_type='edge_function'
      and resource_id=v_slug
      and upper(observed_state)='ACTIVE'
      and observed_at>=now()-interval '24 hours'
    order by observed_at desc limit 1;
    v_exists:=v_observation_key is not null;
  elsif v_ref like 'scripts/%' or v_ref like '.github/%' then
    v_kind:='github_provider_readback';
    select observation_key,observed_at
    into v_observation_key,v_observed_at
    from integration_control.penta_census_provider_observations_v1
    where provider_system='GitHub'
      and resource_type='runtime_reference'
      and resource_id=p_system_key
      and upper(observed_state)='ACTIVE'
      and observed_at>=now()-interval '24 hours'
    order by observed_at desc limit 1;
    v_exists:=v_observation_key is not null;
  elsif v_ref ~ '^ct\.penta\.discovery\.(fetch|get|parse|query|resolve|search)\.v1$' then
    v_kind:='penta_discovery_protocol_capability';
    v_primitive:=split_part(v_ref,'.',4);
    select exists(
      select 1 from public.penta_protocol_registry_v1
      where protocol_id='ct.penta.discovery.v1'
        and lifecycle_state in ('implemented','active','production')
    ) into v_exists;
  elsif v_ref ~ '^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$' then
    v_kind:='database_relation_or_function';
    v_schema:=split_part(v_ref,'.',1);
    v_name:=split_part(v_ref,'.',2);
    begin v_exists:=to_regclass(v_ref) is not null;
    exception when others then v_exists:=false; end;
    if not v_exists then
      select exists(
        select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname=v_schema and p.proname=v_name
      ) into v_exists;
    end if;
  else
    v_kind:='provider_runtime_reference';
    v_slug:=v_ref;
    select observation_key,observed_at
    into v_observation_key,v_observed_at
    from integration_control.penta_census_provider_observations_v1
    where (
      provider_system='Supabase' and resource_type='edge_function' and resource_id=v_slug
    ) or (
      resource_type='runtime_reference' and resource_id=p_system_key
    )
    and upper(observed_state)='ACTIVE'
    and observed_at>=now()-interval '24 hours'
    order by observed_at desc limit 1;
    v_exists:=v_observation_key is not null;
  end if;

  return jsonb_strip_nulls(jsonb_build_object(
    'verified',v_exists,'kind',v_kind,'system_key',p_system_key,
    'runtime_ref',v_ref,'target',v_target,
    'matches',case when v_matches>0 then v_matches else null end,
    'expected_version',v_expected_version,'actual_version',v_actual_version,
    'provider_slug',v_slug,'primitive',v_primitive,
    'provider_observation_key',v_observation_key,
    'provider_observed_at',v_observed_at
  ));
end $$;

revoke all on function public.penta_runtime_reference_check_v1(text,text) from public,anon,authenticated;
grant execute on function public.penta_runtime_reference_check_v1(text,text) to service_role;

create or replace function public.penta_registry_runtime_reference_sweep_v1(
  p_limit integer default 500
) returns jsonb
language plpgsql security definer
set search_path=pg_catalog,public,integration_control,penta_self,extensions,chlom_runtime
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_limit integer:=greatest(1,least(coalesce(p_limit,500),1000));
  v_row record;
  v_incident record;
  v_check jsonb;
  v_verified boolean;
  v_evidence jsonb;
  v_digest text;
  v_checked integer:=0;
  v_verified_count integer:=0;
  v_unverified_count integer:=0;
  v_incidents_resolved integer:=0;
  v_echoes_suppressed integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  for v_row in
    select * from public.penta_system_registry
    where maturity='production'
    order by case when last_verified_at<now()-interval '24 hours' then 0 else 1 end,
             last_verified_at,system_key
    limit v_limit
  loop
    if coalesce((v_row.metadata->>'aggregate_fail_closed')::boolean,false) then
      for v_incident in
        select incident_id from public.penta_incidents_v1
        where system_key=v_row.system_key
          and incident_code='declared_degraded'
          and state<>'resolved'
        for update
      loop
        update public.penta_incidents_v1
        set state='resolved',
            remediation_state='aggregate_echo_suppressed',
            resolved_at=now(),
            remediation_evidence=coalesce(remediation_evidence,'{}'::jsonb)||jsonb_build_object(
              'suppressed_at',now(),
              'reason','aggregate_fail_closed_projection_not_root_incident',
              'root_failures_remain_independently_owned',true,
              'authority_created',false
            ),
            verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
              'verified_at',now(),'aggregate_fail_closed',true,'echo_loop_removed',true
            ),updated_at=now()
        where incident_id=v_incident.incident_id;

        update penta_self.problem_ledger_v1
        set state='resolved',
            resolved_at=coalesce(resolved_at,now()),
            blocked_reason=null,last_error=null,
            verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
              'verified_at',now(),'incident_id',v_incident.incident_id,
              'aggregate_echo_suppressed',true,
              'root_failures_remain_independently_owned',true
            ),updated_at=now()
        where state<>'resolved'
          and evidence->>'incident_id'=v_incident.incident_id::text;
        v_echoes_suppressed:=v_echoes_suppressed+1;
      end loop;
    end if;

    v_check:=public.penta_runtime_reference_check_v1(v_row.system_key,v_row.runtime_ref);
    v_verified:=coalesce((v_check->>'verified')::boolean,false);
    v_evidence:=jsonb_build_object(
      'system_key',v_row.system_key,'runtime_ref',v_row.runtime_ref,
      'check',v_check,'checked_at',now(),
      'authority_created',false,'provider_write',false,'d3_execution',false
    );
    v_digest:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

    insert into public.penta_runtime_reference_receipts_v1(
      system_key,runtime_ref,verification_kind,verified,evidence,evidence_sha256
    ) values(
      v_row.system_key,v_row.runtime_ref,coalesce(v_check->>'kind','unknown'),
      v_verified,v_evidence,v_digest
    );
    v_checked:=v_checked+1;

    if v_verified then
      update public.penta_system_registry
      set last_verified_at=now(),
          metadata=metadata||jsonb_build_object(
            'runtime_reference_verification',jsonb_build_object(
              'state','verified','kind',v_check->>'kind',
              'verified_at',now(),'evidence_sha256',v_digest,
              'authority_created',false
            )
          ),updated_at=now()
      where system_key=v_row.system_key;
      v_verified_count:=v_verified_count+1;

      for v_incident in
        select incident_id from public.penta_incidents_v1
        where system_key=v_row.system_key
          and incident_code='stale_verification'
          and state<>'resolved'
        for update
      loop
        update public.penta_incidents_v1
        set state='resolved',
            remediation_state='runtime_reference_verified',
            resolved_at=now(),
            remediation_evidence=coalesce(remediation_evidence,'{}'::jsonb)||jsonb_build_object(
              'verified_at',now(),'runtime_ref',v_row.runtime_ref,
              'verification_kind',v_check->>'kind','evidence_sha256',v_digest
            ),
            verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||v_check,
            updated_at=now()
        where incident_id=v_incident.incident_id;

        update penta_self.problem_ledger_v1
        set state='resolved',
            resolved_at=coalesce(resolved_at,now()),
            blocked_reason=null,last_error=null,
            verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object(
              'verified_at',now(),'incident_id',v_incident.incident_id,
              'runtime_ref',v_row.runtime_ref,
              'verification_kind',v_check->>'kind','evidence_sha256',v_digest
            ),updated_at=now()
        where state<>'resolved'
          and evidence->>'incident_id'=v_incident.incident_id::text;
        v_incidents_resolved:=v_incidents_resolved+1;
      end loop;
    else
      v_unverified_count:=v_unverified_count+1;
    end if;
  end loop;

  perform chlom_runtime.append_dail_event(
    'penta.runtime-reference.sweep','runtime_verification',
    'ct.penta.crawler.systemwide.v3',
    jsonb_build_object(
      'checked',v_checked,'verified',v_verified_count,
      'unverified',v_unverified_count,
      'incidents_resolved',v_incidents_resolved,
      'aggregate_echoes_suppressed',v_echoes_suppressed,
      'authority_created',false,'provider_write',false,
      'd3_execution',false,'observed_at',now()
    ),
    'PentaCrawler/PentaAssure/PentaSELF',null,
    'PentaCrawler','1.0.0',null,null,
    'ct.penta.crawler.systemwide.v3',null,'internal'
  );

  return jsonb_build_object(
    'state','complete','checked',v_checked,
    'verified',v_verified_count,'unverified',v_unverified_count,
    'incidents_resolved',v_incidents_resolved,
    'aggregate_echoes_suppressed',v_echoes_suppressed,
    'authority_created',false,'provider_write',false,
    'd3_execution',false,'at',now()
  );
end $$;

revoke all on function public.penta_registry_runtime_reference_sweep_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_registry_runtime_reference_sweep_v1(integer) to service_role;

-- Patch the systemwide crawler so verification precedes stale detection and aggregate
-- fail-closed projections do not recursively manufacture root incidents.
do $patch$
declare
  v_def text;
  v_old text;
  v_new text;
begin
  select pg_get_functiondef('public.penta_crawler_roam_v1(integer)'::regprocedure)
  into v_def;

  if position('v_verification jsonb;' in v_def)=0 then
    v_def:=replace(
      v_def,
      'v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));',
      'v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_verification jsonb;'
    );
  end if;

  if position('v_verification:=public.penta_registry_runtime_reference_sweep_v1(v_limit);' in v_def)=0 then
    v_def:=replace(
      v_def,
      'begin
  v_backfill:=public.penta_cookie_backfill_v1(v_limit);',
      'begin
  v_verification:=public.penta_registry_runtime_reference_sweep_v1(v_limit);
  v_backfill:=public.penta_cookie_backfill_v1(v_limit);'
    );
  end if;

  v_old:='if lower(coalesce(v_row.metadata->>''operational_state'','''')) in (''degraded'',''failed'',''error'',''blocked'',''hold'')';
  v_new:='if not coalesce((v_row.metadata->>''aggregate_fail_closed'')::boolean,false) and (lower(coalesce(v_row.metadata->>''operational_state'','''')) in (''degraded'',''failed'',''error'',''blocked'',''hold'')';
  if position(v_old in v_def)>0 then
    v_def:=replace(v_def,v_old,v_new);
    v_def:=replace(
      v_def,
      'or lower(coalesce(v_row.metadata->>''last_self_cycle_state'','''')) in (''degraded'',''failed'',''error'',''blocked'',''hold'') then',
      'or lower(coalesce(v_row.metadata->>''last_self_cycle_state'','''')) in (''degraded'',''failed'',''error'',''blocked'',''hold'')) then'
    );
  end if;

  if position('''runtime_verification'',v_verification' in v_def)=0 then
    v_def:=replace(
      v_def,
      '''state'',''complete'',',
      '''state'',''complete'',''runtime_verification'',v_verification,'
    );
  end if;

  execute v_def;
end
$patch$;

revoke all on function public.penta_crawler_roam_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_crawler_roam_v1(integer) to service_role;

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-penta-runtime-reference-sweep-v1',
  '2 0,6,12,18 * * *',
  'select public.penta_registry_runtime_reference_sweep_v1(500);',
  2026082903,
  'ct.penta.crawler.runtime-reference-verification.v1',
  jsonb_build_object(
    'owner','PentaCrawler/PentaAssure/PentaSELF',
    'rollback_policy','monotonic',
    'provider_write',false,'d3_execution',false,'authority_created',false
  )
);
select cron.unschedule(jobid) from cron.job where jobname='ct-penta-runtime-reference-sweep-v1';
select cron.schedule(
  'ct-penta-runtime-reference-sweep-v1',
  '2 0,6,12,18 * * *',
  'select public.penta_registry_runtime_reference_sweep_v1(500);'
);

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-penta-crawler-roam-v3',
  '8,18,28,38,48,58 * * * *',
  'select public.penta_crawler_roam_v1(100);',
  2026082902,
  'ct.penta.crawler.systemwide.v3',
  jsonb_build_object(
    'owner','PentaCrawler/PentaDiscovery/PentaCensus',
    'rollback_policy','monotonic',
    'd3_execution',false,'provider_write',false,'authority_created',false
  )
);
select cron.unschedule(jobid) from cron.job where jobname='ct-penta-crawler-roam-v3';
select cron.schedule(
  'ct-penta-crawler-roam-v3',
  '8,18,28,38,48,58 * * * *',
  'select public.penta_crawler_roam_v1(100);'
);

select integration_control.scheduler_desired_job_upsert_v2(
  'ct-pentas-mesh-router-v3',
  '* * * * *',
  'select public.pentas_route_pending_v1(100); select public.penta_discovery_ingest_packets_v1(50); select public.penta_discovery_route_v1(50);',
  2026082902,
  'ct.pentas.packet.v1',
  jsonb_build_object(
    'owner','PentaRoute/PentaDiscovery',
    'rollback_policy','monotonic',
    'd3_execution',false,'provider_write',false,'authority_created',false
  )
);
select cron.unschedule(jobid) from cron.job where jobname='ct-pentas-mesh-router-v3';
select cron.schedule(
  'ct-pentas-mesh-router-v3',
  '* * * * *',
  'select public.pentas_route_pending_v1(100); select public.penta_discovery_ingest_packets_v1(50); select public.penta_discovery_route_v1(50);'
);

select integration_control.scheduler_permanence_reconcile_v2();
select public.penta_registry_runtime_reference_sweep_v1(500);
