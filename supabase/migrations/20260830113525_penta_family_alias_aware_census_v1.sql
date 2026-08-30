create or replace view pentamocracy.citizen_canonical_resolution_v1 as
with resolved_base as (
  select
    c.citizen_id,
    c.penta_identity as raw_penta_identity,
    c.family_id as raw_family_id,
    rf.family_key as raw_family_key,
    rf.name as raw_family_name,
    rf.status as raw_family_status,
    c.citizen_class,
    c.active,
    c.human_person,
    c.legacy_immutable,
    c.registered_at,
    c.retired_at,
    c.metadata as citizen_metadata,
    ia.identity_key as alias_resolved_identity,
    ia.alias_type,
    ia.source_ref as alias_source_ref,
    coalesce(ia.identity_key,c.penta_identity) as resolved_identity,
    ir.canonical_name as resolved_canonical_name,
    ir.family_key as canonical_family_key,
    ir.activation_state as canonical_activation_state,
    ir.runtime_state as canonical_runtime_state,
    ir.current as registry_current,
    ir.active as registry_active,
    cf.family_id as canonical_family_id,
    cf.name as canonical_family_name,
    cf.status as canonical_family_status
  from pentamocracy.citizens_v1 c
  join pentamocracy.families_v1 rf on rf.family_id=c.family_id
  left join integration_control.penta_identity_aliases_v1 ia on ia.alias_key=c.penta_identity
  left join integration_control.penta_identity_registry_v1 ir
    on ir.identity_key=coalesce(ia.identity_key,c.penta_identity) and ir.current
  left join pentamocracy.families_v1 cf on cf.family_key=ir.family_key
), ranked as (
  select b.*,
    count(*) filter(where b.active) over(partition by b.resolved_identity) as active_raw_rows_for_identity,
    row_number() over(
      partition by b.resolved_identity
      order by
        case when b.active then 0 else 1 end,
        case when b.raw_penta_identity=b.resolved_identity then 0 when b.alias_type='SELF' then 1 else 2 end,
        case when b.raw_family_key=b.canonical_family_key then 0 else 1 end,
        b.registered_at,
        b.citizen_id
    ) as canonical_rank
  from resolved_base b
)
select r.*,
  case
    when r.resolved_canonical_name is null then 'UNRESOLVED_IDENTITY'
    when r.canonical_family_key is null or r.canonical_activation_state='HOLD_FAMILY' or r.canonical_family_key='PROVISIONAL_UNASSIGNED' then 'PROVISIONAL_FAMILY'
    when r.raw_family_key is distinct from r.canonical_family_key then 'CANONICAL_FAMILY_DIFFERS_FROM_HISTORY'
    else 'CANONICAL_MATCH'
  end as resolution_state,
  (
    r.active
    and coalesce(r.registry_current,false)
    and coalesce(r.registry_active,false)
    and r.canonical_family_id is not null
    and r.canonical_family_status='ACTIVE'
    and r.canonical_activation_state<>'HOLD_FAMILY'
    and r.canonical_family_key<>'PROVISIONAL_UNASSIGNED'
  ) as canonical_population_eligible,
  (r.active_raw_rows_for_identity>1) as has_active_alias_duplicates,
  (r.canonical_rank>1 and r.active) as excluded_duplicate_alias_row,
  true as historical_assignment_preserved
from ranked r;

create or replace view pentamocracy.family_population_reconciled_v1 as
select
  f.family_id,
  f.family_key,
  f.name as family_name,
  f.status as family_status,
  f.minimum_electors,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.active and r.raw_family_id=f.family_id) as raw_active_citizen_population,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.canonical_rank=1 and r.canonical_population_eligible and r.canonical_family_id=f.family_id) as canonical_unique_member_population,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.active and r.raw_family_id=f.family_id and r.canonical_family_id is distinct from f.family_id and r.canonical_family_id is not null) as historical_rows_reassigned_out_for_representation,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.active and r.canonical_family_id=f.family_id and r.raw_family_id is distinct from f.family_id) as historical_rows_reconciled_in_for_representation,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.active and r.canonical_family_id=f.family_id and r.excluded_duplicate_alias_row) as duplicate_alias_rows_excluded,
  (select count(*)::bigint from pentamocracy.citizen_canonical_resolution_v1 r where r.active and r.raw_family_id=f.family_id and r.resolution_state='PROVISIONAL_FAMILY') as provisional_rows,
  'canonical_identity_fabric_unique'::text as representation_basis,
  true as historical_citizen_rows_preserved
from pentamocracy.families_v1 f;

create table if not exists pentamocracy.family_population_reconciliation_receipts_v1(
  receipt_id uuid primary key default gen_random_uuid(),
  source_ref text not null,
  raw_active_citizens bigint not null,
  unique_resolved_identities bigint not null,
  canonical_assigned_population bigint not null,
  provisional_population bigint not null,
  duplicate_alias_rows bigint not null,
  family_counts jsonb not null,
  evidence_sha256 text not null check(evidence_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now()
);

create or replace function pentamocracy.family_population_reconciliation_receipts_append_only_v1()
returns trigger language plpgsql security definer set search_path='pg_catalog','pentamocracy' as $$
begin
  raise exception 'FAMILY_POPULATION_RECONCILIATION_RECEIPTS_APPEND_ONLY';
end $$;

drop trigger if exists trg_family_population_reconciliation_receipts_append_only_v1 on pentamocracy.family_population_reconciliation_receipts_v1;
create trigger trg_family_population_reconciliation_receipts_append_only_v1
before update or delete on pentamocracy.family_population_reconciliation_receipts_v1
for each row execute function pentamocracy.family_population_reconciliation_receipts_append_only_v1();

create or replace function pentamocracy.family_population_status_v1()
returns jsonb language sql stable security definer
set search_path='pg_catalog','pentamocracy' as $$
with global_state as (
  select
    count(*) filter(where active)::bigint as raw_active_citizens,
    count(distinct resolved_identity) filter(where active)::bigint as unique_resolved_identities,
    count(*) filter(where canonical_rank=1 and canonical_population_eligible)::bigint as canonical_assigned_population,
    count(*) filter(where canonical_rank=1 and resolution_state='PROVISIONAL_FAMILY' and active)::bigint as provisional_population,
    count(*) filter(where excluded_duplicate_alias_row)::bigint as duplicate_alias_rows,
    count(*) filter(where resolution_state='UNRESOLVED_IDENTITY' and active)::bigint as unresolved_identity_rows
  from pentamocracy.citizen_canonical_resolution_v1
)
select jsonb_build_object(
  'contract','ct.pentamocracy.family-population.alias-aware.v1',
  'raw_active_citizens',g.raw_active_citizens,
  'unique_resolved_identities',g.unique_resolved_identities,
  'canonical_assigned_population',g.canonical_assigned_population,
  'provisional_population',g.provisional_population,
  'duplicate_alias_rows',g.duplicate_alias_rows,
  'unresolved_identity_rows',g.unresolved_identity_rows,
  'historical_citizen_rows_preserved',true,
  'representation_basis','canonical_identity_fabric_unique',
  'families',(select coalesce(jsonb_agg(to_jsonb(f) order by f.family_key),'[]'::jsonb) from pentamocracy.family_population_reconciled_v1 f)
)
from global_state g
$$;

create or replace function pentamocracy.record_family_population_reconciliation_v1(p_source_ref text default 'penta-activation-continuity')
returns jsonb language plpgsql security definer
set search_path='pg_catalog','pentamocracy','extensions' as $$
declare
  s jsonb;
  d text;
  rid uuid;
begin
  s:=pentamocracy.family_population_status_v1();
  d:=encode(extensions.digest(convert_to(jsonb_build_object('source_ref',p_source_ref,'status',s)::text,'UTF8'),'sha256'),'hex');
  insert into pentamocracy.family_population_reconciliation_receipts_v1(
    source_ref,raw_active_citizens,unique_resolved_identities,canonical_assigned_population,
    provisional_population,duplicate_alias_rows,family_counts,evidence_sha256
  ) values(
    p_source_ref,
    (s->>'raw_active_citizens')::bigint,
    (s->>'unique_resolved_identities')::bigint,
    (s->>'canonical_assigned_population')::bigint,
    (s->>'provisional_population')::bigint,
    (s->>'duplicate_alias_rows')::bigint,
    s->'families',d
  ) returning receipt_id into rid;
  return jsonb_build_object('receipt_id',rid,'evidence_sha256',d,'status',s,'authority_expansion',false);
end $$;

create or replace function integration_control.penta_family_runtime_canonical_member_count_v1()
returns trigger language plpgsql security definer
set search_path='pg_catalog','integration_control' as $$
begin
  new.member_count := (
    select count(*)::integer
    from integration_control.penta_identity_registry_v1 r
    where r.current and r.active and r.identity_class<>'FAMILY' and r.family_key=new.family_key
  );
  new.metadata := coalesce(new.metadata,'{}'::jsonb) || jsonb_build_object(
    'member_count_basis','canonical_identity_fabric_unique',
    'historical_citizen_rows_preserved',true
  );
  return new;
end $$;

drop trigger if exists trg_penta_family_runtime_canonical_member_count_v1 on integration_control.penta_family_runtime_v1;
create trigger trg_penta_family_runtime_canonical_member_count_v1
before insert or update of family_key,member_count on integration_control.penta_family_runtime_v1
for each row execute function integration_control.penta_family_runtime_canonical_member_count_v1();

create or replace function integration_control.penta_family_census_entity_canonical_member_count_v1()
returns trigger language plpgsql security definer
set search_path='pg_catalog','integration_control' as $$
declare
  v_family_key text;
  v_count integer;
begin
  if new.entity_kind='penta_family' then
    select r.family_key into v_family_key
    from integration_control.penta_identity_registry_v1 r
    where r.current and r.identity_class='FAMILY' and r.identity_key=new.entity_key
    limit 1;
    if v_family_key is not null then
      select count(*)::integer into v_count
      from integration_control.penta_identity_registry_v1 r
      where r.current and r.active and r.identity_class<>'FAMILY' and r.family_key=v_family_key;
      new.attributes := coalesce(new.attributes,'{}'::jsonb) || jsonb_build_object(
        'member_count',v_count,
        'member_count_basis','canonical_identity_fabric_unique',
        'historical_citizen_rows_preserved',true
      );
    end if;
  end if;
  return new;
end $$;

drop trigger if exists trg_penta_family_census_entity_canonical_member_count_v1 on integration_control.penta_census_entities_v1;
create trigger trg_penta_family_census_entity_canonical_member_count_v1
before insert or update of entity_key,entity_kind,attributes on integration_control.penta_census_entities_v1
for each row execute function integration_control.penta_family_census_entity_canonical_member_count_v1();

create or replace function integration_control.penta_family_status_v1(p_family_key text)
returns jsonb language sql stable security definer
set search_path='integration_control','pentamocracy','public','pg_temp' as $$
select jsonb_build_object(
  'family_key',f.family_key,
  'canonical_name',f.canonical_name,
  'job_role',f.job_role,
  'member_count',f.member_count,
  'member_count_basis','canonical_identity_fabric_unique',
  'raw_active_citizen_population',coalesce(p.raw_active_citizen_population,0),
  'canonical_unique_member_population',coalesce(p.canonical_unique_member_population,0),
  'duplicate_alias_rows_excluded',coalesce(p.duplicate_alias_rows_excluded,0),
  'historical_rows_reassigned_out_for_representation',coalesce(p.historical_rows_reassigned_out_for_representation,0),
  'historical_rows_reconciled_in_for_representation',coalesce(p.historical_rows_reconciled_in_for_representation,0),
  'historical_citizen_rows_preserved',true,
  'runtime_state',f.runtime_state,
  'activation_state',f.activation_state,
  'certification_state',f.certification_state,
  'labels',f.labels,
  'members',(select coalesce(jsonb_agg(jsonb_build_object('identity_key',r.identity_key,'name',r.canonical_name,'role',r.role,'maturity',r.maturity,'activation',r.activation_state,'runtime',r.runtime_state) order by r.canonical_name),'[]'::jsonb) from integration_control.penta_identity_registry_v1 r where r.current and r.family_key=f.family_key and r.identity_class<>'FAMILY')
)
from integration_control.penta_family_runtime_v1 f
left join pentamocracy.family_population_reconciled_v1 p on p.family_key=f.family_key
where f.family_key=p_family_key
$$;

create or replace function pentamocracy.run_census_cycle_v1(p_cycle text)
returns jsonb language plpgsql security definer
set search_path='pentamocracy','public','pg_temp' as $$
declare
  r record;
  pop bigint;
  dig text;
  n int:=0;
  canonical_total bigint;
  raw_total bigint;
  provisional_total bigint;
begin
  if coalesce(trim(p_cycle),'')='' then raise exception 'CENSUS_CYCLE_REQUIRED'; end if;
  for r in
    select n.numerator_id,n.family_id,n.penta_identity
    from pentamocracy.numerators_v1 n
    join pentamocracy.families_v1 f using(family_id)
    where n.status='ACTIVE' and f.status='ACTIVE'
  loop
    select canonical_unique_member_population into pop
    from pentamocracy.family_population_reconciled_v1
    where family_id=r.family_id;
    select md5(string_agg(resolved_identity,'|' order by resolved_identity)) into dig
    from pentamocracy.citizen_canonical_resolution_v1
    where canonical_family_id=r.family_id and canonical_rank=1 and canonical_population_eligible;
    insert into pentamocracy.numerator_assignments_v1(numerator_id,family_id,census_cycle,state,observed_population,observed_digest,completed_at)
    values(r.numerator_id,r.family_id,p_cycle,'RECONCILED',coalesce(pop,0),coalesce(dig,md5('empty')),now())
    on conflict(numerator_id,family_id,census_cycle) do update set
      state='RECONCILED',observed_population=excluded.observed_population,observed_digest=excluded.observed_digest,completed_at=now();
    n:=n+1;
  end loop;
  select coalesce(sum(canonical_unique_member_population),0) into canonical_total from pentamocracy.family_population_reconciled_v1 where family_status='ACTIVE';
  select count(*) into raw_total from pentamocracy.citizens_v1 where active;
  select count(*) into provisional_total from pentamocracy.citizen_canonical_resolution_v1 where active and canonical_rank=1 and resolution_state='PROVISIONAL_FAMILY';
  return jsonb_build_object('assignments',n,'population',canonical_total,'raw_active_citizens',raw_total,'provisional_excluded',provisional_total,'representation_basis','canonical_identity_fabric_unique','historical_citizen_rows_preserved',true);
end $$;

create or replace function pentamocracy.certify_population_v1(p_evidence_digest text,p_penta_census_ref text)
returns jsonb language plpgsql security definer
set search_path='pentamocracy','public','pg_temp' as $$
declare
  r record;
  n int:=0;
  canonical_total bigint;
  raw_total bigint;
  provisional_total bigint;
begin
  if coalesce(trim(p_evidence_digest),'')='' then raise exception 'NUMERATOR_EVIDENCE_REQUIRED'; end if;
  for r in
    select family_id,canonical_unique_member_population as population
    from pentamocracy.family_population_reconciled_v1
    where family_status='ACTIVE'
  loop
    insert into pentamocracy.census_snapshots_v1(family_id,population,active_population,numerator_evidence_digest,penta_census_ref,certified,certified_at)
    values(r.family_id,r.population,r.population,p_evidence_digest,p_penta_census_ref,true,now());
    n:=n+1;
  end loop;
  select coalesce(sum(canonical_unique_member_population),0) into canonical_total from pentamocracy.family_population_reconciled_v1 where family_status='ACTIVE';
  select count(*) into raw_total from pentamocracy.citizens_v1 where active;
  select count(*) into provisional_total from pentamocracy.citizen_canonical_resolution_v1 where active and canonical_rank=1 and resolution_state='PROVISIONAL_FAMILY';
  return jsonb_build_object('families_certified',n,'population',canonical_total,'raw_active_citizens',raw_total,'provisional_excluded',provisional_total,'representation_basis','canonical_identity_fabric_unique','historical_citizen_rows_preserved',true);
end $$;

update integration_control.penta_family_runtime_v1 set member_count=member_count;
update integration_control.penta_census_entities_v1 set attributes=attributes where entity_kind='penta_family';