create table if not exists integration_control.penta_identity_source_snapshots_v1 (
  snapshot_id uuid primary key default gen_random_uuid(),
  source_type text not null,
  source_ref text not null,
  source_version text,
  source_sha256 text not null,
  source_count integer,
  payload jsonb not null,
  observed_at timestamptz not null default now(),
  unique(source_type, source_sha256)
);

create table if not exists integration_control.penta_family_label_map_v1 (
  raw_label text primary key,
  family_key text not null,
  canonical_family_name text not null,
  mapping_state text not null default 'ACTIVE',
  source_ref text not null,
  created_at timestamptz not null default now()
);

insert into integration_control.penta_family_label_map_v1(raw_label,family_key,canonical_family_name,source_ref) values
('Automation Agentic','AUTOMATION_AGENTIC','Penta Automation & Agentic Family','PentaDocs 15-family crosswalk'),
('Penta Automation & Agentic Family','AUTOMATION_AGENTIC','Penta Automation & Agentic Family','PentaDocs canonical family'),
('Build Release','BUILD_RELEASE','Penta Build, Certification & Release Family','PentaDocs 15-family crosswalk'),
('Penta Build, Certification & Release Family','BUILD_RELEASE','Penta Build, Certification & Release Family','PentaDocs canonical family'),
('Commerce Economy','COMMERCE_ECONOMY','Penta Commerce & Economy Family','PentaDocs 15-family crosswalk'),
('Penta Commerce & Economy Family','COMMERCE_ECONOMY','Penta Commerce & Economy Family','PentaDocs canonical family'),
('Communications Service','COMMUNICATIONS_SERVICE','Penta Communications & Service Family','PentaDocs 15-family crosswalk'),
('Penta Communications & Service Family','COMMUNICATIONS_SERVICE','Penta Communications & Service Family','PentaDocs canonical family'),
('Governance Legal','GOVERNANCE_LEGAL','Penta Governance, Legal & Institutional Controls Family','PentaDocs 15-family crosswalk'),
('Penta Governance, Legal & Institutional Controls Family','GOVERNANCE_LEGAL','Penta Governance, Legal & Institutional Controls Family','PentaDocs canonical family'),
('Intelligence Research','INTELLIGENCE_RESEARCH','Penta Intelligence, Research & Impact Family','PentaDocs 15-family crosswalk'),
('Penta Intelligence, Research & Impact Family','INTELLIGENCE_RESEARCH','Penta Intelligence, Research & Impact Family','PentaDocs canonical family'),
('Knowledge Semantics Data','KNOWLEDGE_DATA','Penta Knowledge, Semantics & Data Family','PentaDocs 15-family crosswalk'),
('Penta Knowledge, Semantics & Data Family','KNOWLEDGE_DATA','Penta Knowledge, Semantics & Data Family','PentaDocs canonical family'),
('Media Creative','MEDIA_CREATIVE','Penta Media, Studio & Publishing Family','PentaDocs 15-family crosswalk'),
('Penta Media, Studio & Publishing Family','MEDIA_CREATIVE','Penta Media, Studio & Publishing Family','PentaDocs canonical family'),
('Observability Organic','OBSERVABILITY_ORGANIC','Penta Observability & Organic Systems Family','PentaDocs 15-family crosswalk'),
('Penta Observability & Organic Systems Family','OBSERVABILITY_ORGANIC','Penta Observability & Organic Systems Family','PentaDocs canonical family'),
('Resilience Continuity','RESILIENCE_CONTINUITY','Penta Resilience & Continuity Family','PentaDocs 15-family crosswalk'),
('Penta Resilience & Continuity Family','RESILIENCE_CONTINUITY','Penta Resilience & Continuity Family','PentaDocs canonical family'),
('Routing Interoperability','ROUTING_INTEROP','Penta Routing & Interoperability Family','PentaDocs 15-family crosswalk'),
('Penta Routing & Interoperability Family','ROUTING_INTEROP','Penta Routing & Interoperability Family','PentaDocs canonical family'),
('Security Trust','SECURITY_TRUST','Penta Security, Identity & Trust Family','PentaDocs 15-family crosswalk'),
('Penta Security, Identity & Trust Family','SECURITY_TRUST','Penta Security, Identity & Trust Family','PentaDocs canonical family'),
('System Architecture','SYSTEM_ARCHITECTURE','Penta System Architecture Family','PentaDocs 15-family crosswalk'),
('Penta System Architecture Family','SYSTEM_ARCHITECTURE','Penta System Architecture Family','PentaDocs canonical family'),
('Transport Primitives','TRANSPORT_PRIMITIVES','Penta Transport & Capability Primitives Family','PentaDocs 15-family crosswalk'),
('Penta Transport & Capability Primitives Family','TRANSPORT_PRIMITIVES','Penta Transport & Capability Primitives Family','PentaDocs canonical family'),
('Workforce People','WORKFORCE_PEOPLE','Penta Workforce & People Family','PentaDocs 15-family crosswalk'),
('Penta Workforce & People Family','WORKFORCE_PEOPLE','Penta Workforce & People Family','PentaDocs canonical family'),
('Pending canonical family','PROVISIONAL_UNASSIGNED','Provisional / Family Assignment Pending','PentaDocs pending family'),
('Infrastructure & Continuity','SYSTEM_ARCHITECTURE','Penta System Architecture Family','PentaMocracy bootstrap supersession crosswalk'),
('Evidence & Knowledge','INTELLIGENCE_RESEARCH','Penta Intelligence, Research & Impact Family','PentaMocracy bootstrap supersession crosswalk'),
('Governance & Justice','GOVERNANCE_LEGAL','Penta Governance, Legal & Institutional Controls Family','PentaMocracy bootstrap supersession crosswalk'),
('Production & Engineering','BUILD_RELEASE','Penta Build, Certification & Release Family','PentaMocracy bootstrap supersession crosswalk'),
('Commerce & Economy','COMMERCE_ECONOMY','Penta Commerce & Economy Family','PentaMocracy bootstrap supersession crosswalk'),
('Communications & Coordination','COMMUNICATIONS_SERVICE','Penta Communications & Service Family','PentaMocracy bootstrap supersession crosswalk'),
('Workforce & Institutional Services','WORKFORCE_PEOPLE','Penta Workforce & People Family','PentaMocracy bootstrap supersession crosswalk')
on conflict(raw_label) do update set family_key=excluded.family_key,canonical_family_name=excluded.canonical_family_name,mapping_state=excluded.mapping_state,source_ref=excluded.source_ref;

create table if not exists integration_control.penta_identity_registry_v1 (
  identity_key text primary key,
  canonical_name text not null,
  identity_class text not null check(identity_class in ('CANONICAL','CANDIDATE','LIVE_ONLY','FAMILY')),
  docs_path text,
  docs_namespace text,
  family_key text,
  family_name text,
  role text,
  axis text,
  kind text,
  maturity text,
  registration_state text,
  activation_state text not null,
  runtime_state text not null,
  labels text[] not null default '{}',
  source_refs jsonb not null default '{}',
  source_sha256 text,
  current boolean not null default true,
  active boolean not null default true,
  metadata jsonb not null default '{}',
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_identity_aliases_v1 (
  alias_key text primary key,
  identity_key text not null references integration_control.penta_identity_registry_v1(identity_key),
  alias_type text not null,
  source_ref text not null,
  metadata jsonb not null default '{}',
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists integration_control.penta_identity_labels_v1 (
  identity_key text not null references integration_control.penta_identity_registry_v1(identity_key),
  label text not null,
  label_class text not null,
  source_ref text not null,
  active boolean not null default true,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  primary key(identity_key,label)
);

create table if not exists integration_control.penta_identity_history_v1 (
  event_id uuid primary key default gen_random_uuid(),
  identity_key text not null,
  event_type text not null,
  before_state jsonb,
  after_state jsonb,
  source_ref text not null,
  source_sha256 text,
  event_sha256 text not null,
  observed_at timestamptz not null default now()
);

create or replace function integration_control.penta_identity_history_trigger_v1() returns trigger
language plpgsql security definer set search_path=integration_control,public,extensions,pg_temp as $$
declare b jsonb; a jsonb; et text; src text; sha text;
begin
  if tg_op='INSERT' then b:=null; a:=to_jsonb(new); et:='IDENTITY_CREATED'; src:=coalesce(new.source_refs->>'primary','identity-fabric'); sha:=new.source_sha256;
  elsif tg_op='UPDATE' then b:=to_jsonb(old); a:=to_jsonb(new); et:='IDENTITY_RECONCILED'; src:=coalesce(new.source_refs->>'primary','identity-fabric'); sha:=new.source_sha256;
  else raise exception 'Penta identity records are immutable-by-history; retire/supersede instead of delete'; end if;
  if tg_op='INSERT' or b is distinct from a then
    insert into integration_control.penta_identity_history_v1(identity_key,event_type,before_state,after_state,source_ref,source_sha256,event_sha256)
    values(new.identity_key,et,b,a,src,sha,encode(extensions.digest(coalesce(new.identity_key,'')||'|'||et||'|'||coalesce(b::text,'')||'|'||coalesce(a::text,''),'sha256'),'hex'));
  end if;
  return new;
end $$;

drop trigger if exists trg_penta_identity_history_v1 on integration_control.penta_identity_registry_v1;
create trigger trg_penta_identity_history_v1 after insert or update on integration_control.penta_identity_registry_v1 for each row execute function integration_control.penta_identity_history_trigger_v1();

drop trigger if exists trg_penta_identity_no_delete_v1 on integration_control.penta_identity_registry_v1;
create trigger trg_penta_identity_no_delete_v1 before delete on integration_control.penta_identity_registry_v1 for each row execute function integration_control.penta_identity_history_trigger_v1();

create table if not exists integration_control.penta_family_runtime_v1 (
  family_key text primary key,
  canonical_name text not null,
  job_role text not null,
  member_count integer not null default 0,
  runtime_state text not null,
  activation_state text not null,
  certification_state text not null,
  labels text[] not null default '{}',
  metadata jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_identity_projection_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  target text not null,
  projected_count integer not null,
  state text not null,
  source_sha256 text,
  observed_at timestamptz not null default now()
);

create or replace function integration_control.penta_family_lookup_v1(p_raw text)
returns table(family_key text, family_name text)
language sql stable security definer set search_path=integration_control,public,pg_temp as $$
  select m.family_key,m.canonical_family_name from integration_control.penta_family_label_map_v1 m where lower(m.raw_label)=lower(p_raw) limit 1
$$;

create or replace function integration_control.penta_identity_lookup_v1(p_query text)
returns jsonb language sql stable security definer set search_path=integration_control,public,pg_temp as $$
select coalesce(jsonb_agg(jsonb_build_object('identity_key',r.identity_key,'canonical_name',r.canonical_name,'class',r.identity_class,'family_key',r.family_key,'family_name',r.family_name,'role',r.role,'axis',r.axis,'kind',r.kind,'maturity',r.maturity,'activation_state',r.activation_state,'runtime_state',r.runtime_state,'labels',r.labels,'aliases',(select coalesce(jsonb_agg(a.alias_key),'[]'::jsonb) from integration_control.penta_identity_aliases_v1 a where a.identity_key=r.identity_key)) order by r.canonical_name),'[]'::jsonb)
from integration_control.penta_identity_registry_v1 r
where r.current and (lower(r.identity_key)=lower(p_query) or lower(r.canonical_name)=lower(p_query) or exists(select 1 from integration_control.penta_identity_aliases_v1 a where a.identity_key=r.identity_key and lower(a.alias_key)=lower(p_query)))
$$;

create or replace function integration_control.penta_family_status_v1(p_family_key text)
returns jsonb language sql stable security definer set search_path=integration_control,public,pg_temp as $$
select jsonb_build_object('family_key',f.family_key,'canonical_name',f.canonical_name,'job_role',f.job_role,'member_count',f.member_count,'runtime_state',f.runtime_state,'activation_state',f.activation_state,'certification_state',f.certification_state,'labels',f.labels,'members',(select coalesce(jsonb_agg(jsonb_build_object('identity_key',r.identity_key,'name',r.canonical_name,'role',r.role,'maturity',r.maturity,'activation',r.activation_state,'runtime',r.runtime_state) order by r.canonical_name),'[]'::jsonb) from integration_control.penta_identity_registry_v1 r where r.current and r.family_key=f.family_key and r.identity_class<>'FAMILY')) from integration_control.penta_family_runtime_v1 f where f.family_key=p_family_key
$$;

create or replace function integration_control.penta_family_route_v1(p_family_key text,p_capability text default null)
returns jsonb language sql stable security definer set search_path=integration_control,public,pg_temp as $$
select jsonb_build_object('family_key',p_family_key,'requested_capability',p_capability,'dispatch_authority','NONE_FROM_ROUTER','candidates',coalesce(jsonb_agg(jsonb_build_object('identity_key',r.identity_key,'canonical_name',r.canonical_name,'role',r.role,'axis',r.axis,'maturity',r.maturity,'activation_state',r.activation_state,'runtime_state',r.runtime_state,'eligible_for_consideration',(r.active and r.activation_state<>'HOLD_FAMILY')) order by case when r.runtime_state='RUNTIME_PRESENT' then 0 else 1 end,r.canonical_name),'[]'::jsonb)) from integration_control.penta_identity_registry_v1 r where r.current and r.family_key=p_family_key and r.identity_class<>'FAMILY' and (p_capability is null or lower(coalesce(r.role,'')||' '||array_to_string(r.labels,' ')) like '%'||lower(p_capability)||'%')
$$;

alter table integration_control.penta_identity_source_snapshots_v1 enable row level security;
alter table integration_control.penta_family_label_map_v1 enable row level security;
alter table integration_control.penta_identity_registry_v1 enable row level security;
alter table integration_control.penta_identity_aliases_v1 enable row level security;
alter table integration_control.penta_identity_labels_v1 enable row level security;
alter table integration_control.penta_identity_history_v1 enable row level security;
alter table integration_control.penta_family_runtime_v1 enable row level security;
alter table integration_control.penta_identity_projection_receipts_v1 enable row level security;
revoke all on integration_control.penta_identity_source_snapshots_v1,integration_control.penta_family_label_map_v1,integration_control.penta_identity_registry_v1,integration_control.penta_identity_aliases_v1,integration_control.penta_identity_labels_v1,integration_control.penta_identity_history_v1,integration_control.penta_family_runtime_v1,integration_control.penta_identity_projection_receipts_v1 from anon,authenticated;
revoke all on function integration_control.penta_identity_lookup_v1(text),integration_control.penta_family_status_v1(text),integration_control.penta_family_route_v1(text,text),integration_control.penta_family_lookup_v1(text) from anon,authenticated;