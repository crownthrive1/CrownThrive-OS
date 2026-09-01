-- Bind the accepted Communications Survival Contract to PentaTime and the monotonic scheduler.

create or replace function integration_control.guard_communications_survival_operation_registry_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','pentatime'
as $function$
declare
  v_latest bigint;
  v_new_generation bigint;
  v_old_generation bigint;
begin
  if tg_op='DELETE' then
    if old.operation_key='communications_survival' then
      raise exception using errcode='55000',message='communications_survival_operation_delete_rejected';
    end if;
    return old;
  end if;
  if tg_op='UPDATE' and old.operation_key='communications_survival' and new.operation_key<>'communications_survival' then
    raise exception using errcode='55000',message='communications_survival_operation_rename_rejected';
  end if;
  if new.operation_key<>'communications_survival' then return new; end if;

  select max(generation) into v_latest
  from integration_control.communications_survival_contract_versions_v1
  where contract_key='ct.communications.survival.v1';
  v_new_generation:=nullif(new.metadata->>'contract_generation','')::bigint;

  if new.domain_key<>'ct:communications-survival-lane'
     or new.owner_penta<>'PentaSELF'
     or new.enabled is distinct from true
     or new.base_backoff_seconds<>5
     or new.max_backoff_seconds<>120
     or v_new_generation is distinct from v_latest then
    raise exception using errcode='55000',message='communications_survival_operation_registry_contract_rejected';
  end if;
  if tg_op='UPDATE' then
    v_old_generation:=nullif(old.metadata->>'contract_generation','')::bigint;
    if v_new_generation<=v_old_generation then
      raise exception using errcode='55000',message='communications_survival_operation_requires_better_contract';
    end if;
  end if;
  return new;
end;
$function$;

create or replace function integration_control.guard_communications_survival_executor_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','pentatime'
as $function$
declare
  v_latest bigint;
  v_new_generation bigint;
  v_old_generation bigint;
  v_old_rank integer;
  v_new_rank integer;
  v_executor_schema text;
  v_executor_name text;
begin
  if tg_op='DELETE' then
    if old.operation_key='communications_survival' then
      raise exception using errcode='55000',message='communications_survival_executor_delete_rejected';
    end if;
    return old;
  end if;
  if tg_op='UPDATE' and old.operation_key='communications_survival' and new.operation_key<>'communications_survival' then
    raise exception using errcode='55000',message='communications_survival_executor_rename_rejected';
  end if;
  if new.operation_key<>'communications_survival' then return new; end if;

  select n.nspname,p.proname into v_executor_schema,v_executor_name
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where p.oid=new.executor_regprocedure::oid;

  select max(generation) into v_latest
  from integration_control.communications_survival_contract_versions_v1
  where contract_key='ct.communications.survival.v1';
  v_new_generation:=nullif(new.metadata->>'contract_generation','')::bigint;

  if new.enabled is distinct from true
     or v_executor_schema<>'pentatime'
     or v_executor_name not like 'executor_communications_survival_%'
     or v_new_generation is distinct from v_latest then
    raise exception using errcode='55000',message='communications_survival_executor_contract_rejected';
  end if;

  if tg_op='UPDATE' then
    v_old_generation:=nullif(old.metadata->>'contract_generation','')::bigint;
    if v_new_generation<=v_old_generation then
      raise exception using errcode='55000',message='communications_survival_executor_requires_better_contract';
    end if;
    v_old_rank:=case old.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    v_new_rank:=case new.authority_ceiling when 'D0' then 0 when 'D1' then 1 else 2 end;
    if v_new_rank>v_old_rank then
      raise exception using errcode='55000',message='communications_survival_executor_authority_expansion_rejected';
    end if;
  elsif new.authority_ceiling<>'D2' then
    raise exception using errcode='55000',message='communications_survival_executor_initial_authority_rejected';
  end if;
  return new;
end;
$function$;

create trigger communications_survival_operation_registry_guard_v1
before insert or update or delete on pentatime.operation_registry_v2
for each row execute function integration_control.guard_communications_survival_operation_registry_v1();
create trigger communications_survival_executor_guard_v1
before insert or update or delete on pentatime.operation_executors_v3
for each row execute function integration_control.guard_communications_survival_executor_v1();

insert into pentatime.operation_registry_v2(
  operation_key,domain_key,owner_penta,enabled,base_backoff_seconds,max_backoff_seconds,metadata
) values (
  'communications_survival','ct:communications-survival-lane','PentaSELF',true,5,120,
  jsonb_build_object('class','communications_continuity','contract_key','ct.communications.survival.v1',
    'contract_generation',1,'transport_owner','PentaMail','provider_component','PentaMailer',
    'direct_send_authority',false,'authority_created',false,'rollback_policy','better_contract_generation_only')
);

insert into pentatime.operation_executors_v3(
  operation_key,executor_regprocedure,authority_ceiling,enabled,metadata
) values (
  'communications_survival','pentatime.executor_communications_survival_v1()'::regprocedure,'D2',true,
  jsonb_build_object('family','PentaSELF/PentaMail','contract_key','ct.communications.survival.v1',
    'contract_generation',1,'direct_send_authority',false,'authority_created',false,
    'upgrade_policy','better_contract_generation_only')
);

create or replace function integration_control.guard_communications_survival_scheduler_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $function$
declare
  v_latest bigint;
  v_contract_generation bigint;
  v_old_contract_generation bigint;
  v_expected_sha text;
begin
  if tg_op='DELETE' then
    if old.jobname='ct-communications-survival-v1' then
      raise exception using errcode='55000',message='communications_survival_scheduler_delete_rejected';
    end if;
    return old;
  end if;
  if tg_op='UPDATE' and old.jobname='ct-communications-survival-v1' and new.jobname<>'ct-communications-survival-v1' then
    raise exception using errcode='55000',message='communications_survival_scheduler_rename_rejected';
  end if;
  if new.jobname<>'ct-communications-survival-v1' then return new; end if;

  select max(generation) into v_latest
  from integration_control.communications_survival_contract_versions_v1
  where contract_key='ct.communications.survival.v1';
  v_contract_generation:=nullif(new.metadata->>'contract_generation','')::bigint;

  if new.schedule<>'* * * * *'
     or new.command<>$$select pentatime.execute_guarded_v3('communications_survival');$$
     or new.database_name<>'postgres'
     or new.username<>'postgres'
     or new.active is distinct from true
     or new.allow_auto_restore is distinct from true
     or v_contract_generation is distinct from v_latest
     or new.source_ref not like 'ct.communications.survival.v1@g%' then
    raise exception using errcode='55000',message='communications_survival_scheduler_contract_rejected';
  end if;

  v_expected_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',new.jobname,'schedule',new.schedule,'command',new.command,
    'database_name',new.database_name,'username',new.username,'active',new.active,
    'generation',new.generation,'source_ref',new.source_ref,
    'allow_auto_restore',new.allow_auto_restore,'contract_generation',v_contract_generation
  )::text,'UTF8'),'sha256'),'hex');
  if new.desired_sha256 is distinct from v_expected_sha then
    raise exception using errcode='55000',message='communications_survival_scheduler_sha_mismatch';
  end if;

  if tg_op='UPDATE' then
    v_old_contract_generation:=nullif(old.metadata->>'contract_generation','')::bigint;
    if new.generation<=old.generation or v_contract_generation<=v_old_contract_generation then
      raise exception using errcode='55000',message='communications_survival_scheduler_requires_better_contract';
    end if;
  end if;
  return new;
end;
$function$;

create trigger communications_survival_scheduler_guard_v1
before insert or update or delete on integration_control.scheduler_desired_jobs_v2
for each row execute function integration_control.guard_communications_survival_scheduler_v1();

create or replace function integration_control.reject_scheduler_desired_truncate_with_survival_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
begin
  if exists(select 1 from integration_control.scheduler_desired_jobs_v2 where jobname='ct-communications-survival-v1') then
    raise exception using errcode='55000',message='scheduler_desired_truncate_rejected_communications_survival_protected';
  end if;
  return null;
end;
$function$;
create trigger communications_survival_scheduler_no_truncate_v1
before truncate on integration_control.scheduler_desired_jobs_v2
for each statement execute function integration_control.reject_scheduler_desired_truncate_with_survival_v1();

create or replace function integration_control.reject_pentatime_truncate_with_survival_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','pentatime'
as $function$
begin
  if exists(select 1 from pentatime.operation_registry_v2 where operation_key='communications_survival') then
    raise exception using errcode='55000',message='pentatime_truncate_rejected_communications_survival_protected';
  end if;
  return null;
end;
$function$;
create trigger communications_survival_registry_no_truncate_v1
before truncate on pentatime.operation_registry_v2
for each statement execute function integration_control.reject_pentatime_truncate_with_survival_v1();
create trigger communications_survival_executor_no_truncate_v1
before truncate on pentatime.operation_executors_v3
for each statement execute function integration_control.reject_pentatime_truncate_with_survival_v1();

with desired as (
  select 'ct-communications-survival-v1'::text jobname,'* * * * *'::text schedule,
    $$select pentatime.execute_guarded_v3('communications_survival');$$::text command,
    'postgres'::text database_name,'postgres'::text username,true active,
    202609011701::bigint generation,'ct.communications.survival.v1@g1'::text source_ref,true allow_auto_restore,
    jsonb_build_object('owner','PentaSELF/PentaMail','contract_key','ct.communications.survival.v1',
      'contract_generation',1,'safety_rank',100,'direct_send_authority',false,'authority_created',false,
      'rollback_policy','better_contract_generation_only','removal_requires_better_contract',true,
      'new_external_clock',false,'clock_class','internal_pg_cron_health_and_recovery') metadata
), hashed as (
  select d.*,encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',jobname,'schedule',schedule,'command',command,'database_name',database_name,
    'username',username,'active',active,'generation',generation,'source_ref',source_ref,
    'allow_auto_restore',allow_auto_restore,'contract_generation',1
  )::text,'UTF8'),'sha256'),'hex') desired_sha256 from desired d
)
insert into integration_control.scheduler_desired_jobs_v2(
  jobname,schedule,command,database_name,username,active,generation,source_ref,
  desired_sha256,allow_auto_restore,metadata
)
select jobname,schedule,command,database_name,username,active,generation,source_ref,
  desired_sha256,allow_auto_restore,metadata from hashed;

select integration_control.scheduler_permanence_reconcile_v2();