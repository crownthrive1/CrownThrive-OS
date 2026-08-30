-- CrownThrive Penta Family Topology Overlay v1
-- Preserves the 15-family constitutional crosswalk while allowing bounded
-- operational subfamilies to exist without manufacturing representation.

create table if not exists integration_control.penta_family_topology_v1 (
  family_key text primary key,
  topology_class text not null check (topology_class in (
    'CANONICAL_FAMILY','OPERATIONAL_SUBFAMILY','PROVISIONAL_FAMILY','RETIRED_FAMILY'
  )),
  constitutional_family_key text,
  constitutional_state text not null check (constitutional_state in (
    'CANONICAL','PROVISIONAL_PARENT','SUPERSEDED','RETIRED'
  )),
  representation_eligible boolean not null default false,
  source_ref text not null,
  evidence jsonb not null default '{}'::jsonb,
  current boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint penta_family_topology_canonical_self_v1 check (
    topology_class <> 'CANONICAL_FAMILY'
    or (constitutional_state='CANONICAL'
        and constitutional_family_key=family_key
        and representation_eligible)
  ),
  constraint penta_family_topology_provisional_parent_v1 check (
    constitutional_state <> 'PROVISIONAL_PARENT'
    or constitutional_family_key is null
  )
);

create table if not exists integration_control.penta_family_topology_history_v1 (
  event_id uuid primary key default gen_random_uuid(),
  family_key text not null,
  event_type text not null,
  before_state jsonb,
  after_state jsonb not null,
  source_ref text not null,
  event_sha256 text not null,
  observed_at timestamptz not null default now()
);

create or replace function integration_control.penta_family_topology_reject_delete_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
begin
  raise exception 'PENTA_FAMILY_TOPOLOGY_HISTORY_DELETE_PROHIBITED';
end
$$;

drop trigger if exists penta_family_topology_history_no_delete_v1
  on integration_control.penta_family_topology_history_v1;
create trigger penta_family_topology_history_no_delete_v1
before delete or truncate on integration_control.penta_family_topology_history_v1
for each statement execute function integration_control.penta_family_topology_reject_delete_v1();

create or replace function integration_control.penta_family_topology_capture_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control, extensions
as $$
declare
  v_before jsonb := case when tg_op='INSERT' then null else to_jsonb(old) end;
  v_after jsonb := to_jsonb(new);
  v_payload text;
begin
  v_payload := coalesce(v_before,'null'::jsonb)::text || '|' || v_after::text || '|' || tg_op;
  insert into integration_control.penta_family_topology_history_v1(
    family_key,event_type,before_state,after_state,source_ref,event_sha256
  ) values (
    new.family_key,
    case when tg_op='INSERT' then 'TOPOLOGY_CREATED' else 'TOPOLOGY_UPDATED' end,
    v_before,
    v_after,
    new.source_ref,
    encode(extensions.digest(convert_to(v_payload,'UTF8'),'sha256'),'hex')
  );
  return new;
end
$$;

drop trigger if exists penta_family_topology_capture_v1
  on integration_control.penta_family_topology_v1;
create trigger penta_family_topology_capture_v1
after insert or update on integration_control.penta_family_topology_v1
for each row execute function integration_control.penta_family_topology_capture_v1();

-- Route material topology mutations into the existing DAIL evidence spine.
drop trigger if exists ct_dail_route_v1
  on integration_control.penta_family_topology_v1;
create trigger ct_dail_route_v1
after insert or update or delete or truncate on integration_control.penta_family_topology_v1
for each statement execute function chlom_runtime.dail_route_capture_v1();

drop trigger if exists ct_dail_route_v1
  on integration_control.penta_family_topology_history_v1;
create trigger ct_dail_route_v1
after insert or update or delete or truncate on integration_control.penta_family_topology_history_v1
for each statement execute function chlom_runtime.dail_route_capture_v1();

-- Seed only the existing constitutional 15-family set. This source remains
-- pentamocracy.families_v1 + the production label crosswalk; no new state is inferred.
insert into integration_control.penta_family_topology_v1(
  family_key,topology_class,constitutional_family_key,constitutional_state,
  representation_eligible,source_ref,evidence,current
)
select
  f.family_key,
  'CANONICAL_FAMILY',
  f.family_key,
  'CANONICAL',
  true,
  'pentamocracy.families_v1/15-family-crosswalk',
  jsonb_build_object(
    'family_id',f.family_id,
    'canonical_name',f.name,
    'pentadocs_family',true,
    'history_preserved',true,
    'authority_expansion',false
  ),
  true
from pentamocracy.families_v1 f
where f.status='ACTIVE'
  and f.metadata->>'pentadocs_family'='true'
on conflict(family_key) do update set
  topology_class=excluded.topology_class,
  constitutional_family_key=excluded.constitutional_family_key,
  constitutional_state=excluded.constitutional_state,
  representation_eligible=excluded.representation_eligible,
  source_ref=excluded.source_ref,
  evidence=integration_control.penta_family_topology_v1.evidence || excluded.evidence,
  current=true,
  updated_at=now();

-- Surgical Care is production software with immutable lineage but is not in
-- the 15-family constitutional crosswalk. Preserve it as an operational
-- subfamily while leaving its constitutional parent unresolved.
insert into integration_control.penta_family_topology_v1(
  family_key,topology_class,constitutional_family_key,constitutional_state,
  representation_eligible,source_ref,evidence,current
)
select
  f.family_key,
  'OPERATIONAL_SUBFAMILY',
  null,
  'PROVISIONAL_PARENT',
  false,
  coalesce(f.metadata->>'source_ref','ct.pentaself.surgical-care-family.production.v1'),
  jsonb_build_object(
    'runtime_state',f.runtime_state,
    'activation_state',f.activation_state,
    'certification_state',f.certification_state,
    'member_count',f.member_count,
    'certification_preserved',true,
    'runtime_preserved',true,
    'top_level_constitutional_authority',false,
    'representation_eligible',false,
    'canonical_parent_inferred',false,
    'history_preserved',true,
    'authority_expansion',false
  ),
  true
from integration_control.penta_family_runtime_v1 f
where f.family_key='SURGICAL_CARE'
on conflict(family_key) do update set
  topology_class='OPERATIONAL_SUBFAMILY',
  constitutional_family_key=null,
  constitutional_state='PROVISIONAL_PARENT',
  representation_eligible=false,
  source_ref=excluded.source_ref,
  evidence=integration_control.penta_family_topology_v1.evidence || excluded.evidence,
  current=true,
  updated_at=now();

update integration_control.penta_family_runtime_v1
set metadata = metadata || jsonb_build_object(
      'topology_class','OPERATIONAL_SUBFAMILY',
      'constitutional_state','PROVISIONAL_PARENT',
      'constitutional_family_key',null,
      'representation_eligible',false,
      'top_level_constitutional_authority',false,
      'canonical_parent_inferred',false,
      'history_preserved',true,
      'pm_execution_eligible',false,
      'authority_expansion',false
    ),
    labels = array(
      select distinct x
      from unnest(coalesce(labels,'{}'::text[]) || array[
        'topology:operational-subfamily',
        'constitutional-parent:provisional',
        'representation:ineligible-until-parent-resolved',
        'penta:pm-nonexecutable'
      ]) x
      order by x
    ),
    updated_at=now()
where family_key='SURGICAL_CARE';

update integration_control.penta_identity_registry_v1
set metadata = metadata || jsonb_build_object(
      'topology_class','OPERATIONAL_SUBFAMILY',
      'constitutional_state','PROVISIONAL_PARENT',
      'constitutional_family_key',null,
      'representation_eligible',false,
      'top_level_constitutional_authority',false,
      'canonical_parent_inferred',false,
      'history_preserved',true,
      'pm_execution_eligible',false,
      'authority_expansion',false
    ),
    labels = array(
      select distinct x
      from unnest(coalesce(labels,'{}'::text[]) || array[
        'topology:operational-subfamily',
        'constitutional-parent:provisional',
        'representation:ineligible-until-parent-resolved',
        'penta:pm-nonexecutable'
      ]) x
      order by x
    ),
    updated_at=now()
where current and identity_key='penta.family.surgical-care';

update integration_control.penta_identity_registry_v1
set metadata = metadata || jsonb_build_object(
      'runtime_subfamily_key','SURGICAL_CARE',
      'constitutional_family_state','PROVISIONAL_PARENT',
      'constitutional_family_key',null,
      'representation_eligible',false,
      'canonical_parent_inferred',false,
      'runtime_authority_preserved',true,
      'pm_execution_eligible',false,
      'authority_expansion',false
    ),
    labels = array(
      select distinct x
      from unnest(coalesce(labels,'{}'::text[]) || array[
        'topology:operational-subfamily-member',
        'constitutional-parent:provisional',
        'representation:ineligible-until-parent-resolved',
        'penta:pm-nonexecutable'
      ]) x
      order by x
    ),
    updated_at=now()
where current and identity_key in ('penta.surgeon','penta.chart','penta.rounds');

-- Synchronize the machine label registry from the identity rows, including
-- the explicit topology and PentaPM eligibility labels above. No existing
-- label history is deleted or rewritten.
insert into integration_control.penta_identity_labels_v1(
  identity_key,label,label_class,source_ref,active
)
select i.identity_key,l,split_part(l,':',1),
       'ct.penta.family-topology-overlay.v1',true
from integration_control.penta_identity_registry_v1 i
cross join lateral unnest(coalesce(i.labels,'{}'::text[])) l
where i.current
  and i.identity_key in ('penta.family.surgical-care','penta.surgeon','penta.chart','penta.rounds')
on conflict(identity_key,label) do update set
  active=true,
  source_ref=excluded.source_ref,
  last_seen_at=now();

create or replace function integration_control.penta_family_topology_status_v1()
returns jsonb
language sql
stable security definer
set search_path = pg_catalog, integration_control, pentamocracy
as $$
with expected as (
  select count(*)::int n
  from pentamocracy.families_v1
  where status='ACTIVE' and metadata->>'pentadocs_family'='true'
), observed as (
  select
    count(*) filter(where current and topology_class='CANONICAL_FAMILY')::int canonical_families,
    count(*) filter(where current and topology_class='OPERATIONAL_SUBFAMILY')::int operational_subfamilies,
    count(*) filter(where current and constitutional_state='PROVISIONAL_PARENT')::int provisional_parent,
    count(*) filter(where current and representation_eligible)::int representation_eligible,
    count(*) filter(where current and topology_class='CANONICAL_FAMILY'
      and (constitutional_family_key is distinct from family_key
           or constitutional_state<>'CANONICAL'
           or not representation_eligible))::int canonical_contract_violations
  from integration_control.penta_family_topology_v1
), surgical as (
  select jsonb_build_object(
    'family_key',family_key,
    'topology_class',topology_class,
    'constitutional_family_key',constitutional_family_key,
    'constitutional_state',constitutional_state,
    'representation_eligible',representation_eligible,
    'source_ref',source_ref,
    'evidence',evidence
  ) v
  from integration_control.penta_family_topology_v1
  where family_key='SURGICAL_CARE' and current
)
select jsonb_build_object(
  'contract','ct.penta.family-topology.v1',
  'expected_constitutional_families',(select n from expected),
  'canonical_families',observed.canonical_families,
  'operational_subfamilies',observed.operational_subfamilies,
  'provisional_parent',observed.provisional_parent,
  'representation_eligible_families',observed.representation_eligible,
  'canonical_contract_violations',observed.canonical_contract_violations,
  'surgical_care',(select v from surgical),
  'history_preservation',true,
  'authority_expansion',false,
  'state',case
    when observed.canonical_families=(select n from expected)
     and observed.canonical_contract_violations=0
    then 'PASS_WITH_PROVISIONAL_SUBFAMILIES'
    else 'HOLD_CANONICAL_FAMILY_TOPOLOGY_DRIFT'
  end
)
from observed
$$;

comment on table integration_control.penta_family_topology_v1 is
'Canonical Family versus operational-subfamily topology overlay. Does not grant representation, provider, credential, financial, D3, deployment, certification or dispatch authority.';

comment on function integration_control.penta_family_topology_status_v1() is
'Read-only topology status: preserves the 15 constitutional Family crosswalk while allowing explicit non-representational operational subfamilies.';
