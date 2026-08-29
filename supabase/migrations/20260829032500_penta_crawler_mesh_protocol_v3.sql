-- PentaCrawler Mesh Protocol v3
-- Source candidate only. Deployment/promotion remains gated by current CrownThrive OS + CHLOM evidence.
-- Refs: #695; preserves lineage from closed/unmerged #589.

create extension if not exists pgcrypto;

create table if not exists public.penta_protocol_registry_v1 (
  protocol_id text primary key,
  version text not null,
  lifecycle_state text not null check (lifecycle_state in ('specified','implemented','certified','production','hold','retired')),
  purpose text not null,
  schema_ref text,
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2','D3')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.penta_protocol_cookies_v1 (
  cookie_id uuid primary key default gen_random_uuid(),
  system_key text not null unique,
  protocol_version text not null default '1.0.0',
  cookie_state text not null default 'active' check (cookie_state in ('active','hold','retired')),
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2','D3')),
  identity_claims jsonb not null default '{}'::jsonb,
  observed_state jsonb not null default '{}'::jsonb,
  oracle_state jsonb not null default '{}'::jsonb,
  oracle_policy jsonb not null default jsonb_build_object(
    'minimum_distinct_oracles', 2,
    'confidence_floor', 0.80,
    'maximum_disagreement', 0.20,
    'd3_human_reserved', true,
    'allowed_target', 'oracle_state'
  ),
  identity_public_key_ref text,
  current_revision text not null check (current_revision ~ '^[0-9a-f]{64}$'),
  mutation_seq bigint not null default 0 check (mutation_seq >= 0),
  installed_by text not null default 'penta.crawler',
  installed_at timestamptz not null default now(),
  last_seen_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.penta_protocol_cookie_mutations_v1 (
  mutation_id uuid primary key default gen_random_uuid(),
  cookie_id uuid not null references public.penta_protocol_cookies_v1(cookie_id),
  mutation_kind text not null check (mutation_kind in ('install','observation_refresh','oracle_mutation','hold','restore')),
  patch_target text not null check (patch_target in ('identity_claims','observed_state','oracle_state','cookie_state')),
  prior_revision text,
  expected_revision text,
  new_revision text not null check (new_revision ~ '^[0-9a-f]{64}$'),
  mutation_seq bigint not null check (mutation_seq >= 0),
  patch jsonb not null default '{}'::jsonb,
  patch_sha256 text not null check (patch_sha256 ~ '^[0-9a-f]{64}$'),
  actor_system_key text not null,
  oracle_adjudication_id uuid,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  reason text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  idempotency_key text,
  semantic_fingerprint text not null check (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (cookie_id, mutation_seq),
  unique (idempotency_key)
);

create table if not exists public.pentas_packets_v1 (
  packet_id uuid primary key default gen_random_uuid(),
  protocol_id text not null default 'ct.pentas.packet.v1',
  protocol_version text not null default '1.0.0',
  packet_type text not null check (packet_type in (
    'heartbeat',
    'discovery.raise',
    'discovery.observation',
    'help.raise',
    'help.response',
    'health.signal',
    'fault.detected',
    'tag.proposal',
    'remediation.request',
    'oracle.observation',
    'oracle.mutation.proposal',
    'mesh.ack',
    'governance.escalation'
  )),
  source_system_key text not null,
  source_cookie_id uuid not null references public.penta_protocol_cookies_v1(cookie_id),
  source_cookie_revision text not null check (source_cookie_revision ~ '^[0-9a-f]{64}$'),
  target_kind text not null check (target_kind in ('system','capability','mesh_lane','broadcast')),
  target_ref text not null,
  route_lane text not null default 'default',
  correlation_id uuid,
  causation_id uuid,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  authority_class text not null default 'bounded',
  priority smallint not null default 50 check (priority between 0 and 100),
  hop_count integer not null default 0 check (hop_count >= 0),
  max_hops integer not null default 12 check (max_hops between 1 and 32),
  ttl_seconds integer not null default 900 check (ttl_seconds between 30 and 604800),
  expires_at timestamptz not null,
  payload jsonb not null default '{}'::jsonb,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  content_address text not null check (content_address ~ '^sha256:[0-9a-f]{64}$'),
  signature_ref text,
  signature_state text not null default 'unsigned' check (signature_state in ('unsigned','attested','verified','rejected')),
  origin_node_ref text,
  network_epoch text not null default 'centralized-phase3',
  dedupe_key text not null unique,
  packet_state text not null default 'pending' check (packet_state in ('pending','routed','delivered','held','expired','dead_letter')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  delivered_at timestamptz,
  check (octet_length(payload::text) <= 65536),
  check (hop_count <= max_hops)
);

create table if not exists public.pentas_packet_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  packet_id uuid not null references public.pentas_packets_v1(packet_id),
  actor_system_key text not null,
  action text not null,
  from_state text,
  to_state text,
  hop_count integer not null default 0,
  evidence jsonb not null default '{}'::jsonb,
  previous_receipt_sha256 text,
  receipt_sha256 text not null check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists public.penta_discovery_cases_v1 (
  case_id uuid primary key default gen_random_uuid(),
  case_key text not null unique,
  source_system_key text not null,
  source_packet_id uuid references public.pentas_packets_v1(packet_id),
  signal_kind text not null check (signal_kind in (
    'broken',
    'blocked',
    'stale',
    'degraded',
    'missing_dependency',
    'missing_credential',
    'missing_software',
    'unknown_system',
    'help_requested',
    'discovery_requested'
  )),
  severity text not null check (severity in ('INFO','WARN','ERROR','CRITICAL')),
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  summary text not null,
  evidence jsonb not null default '{}'::jsonb,
  state text not null default 'raised' check (state in ('raised','triaged','routed_help','routed_census','held','resolved')),
  helper_request_id uuid,
  incident_id uuid references public.penta_incidents_v1(incident_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists penta_protocol_cookie_mutations_cookie_created_idx
  on public.penta_protocol_cookie_mutations_v1(cookie_id, created_at desc);
create index if not exists pentas_packets_target_state_idx
  on public.pentas_packets_v1(target_ref, packet_state, priority desc, created_at);
create index if not exists pentas_packets_source_created_idx
  on public.pentas_packets_v1(source_system_key, created_at desc);
create index if not exists pentas_packet_receipts_packet_idx
  on public.pentas_packet_receipts_v1(packet_id, created_at);
create index if not exists penta_discovery_cases_state_idx
  on public.penta_discovery_cases_v1(state, severity, created_at);

alter table public.penta_protocol_registry_v1 enable row level security;
alter table public.penta_protocol_cookies_v1 enable row level security;
alter table public.penta_protocol_cookie_mutations_v1 enable row level security;
alter table public.pentas_packets_v1 enable row level security;
alter table public.pentas_packet_receipts_v1 enable row level security;
alter table public.penta_discovery_cases_v1 enable row level security;

revoke all on public.penta_protocol_registry_v1 from anon, authenticated;
revoke all on public.penta_protocol_cookies_v1 from anon, authenticated;
revoke all on public.penta_protocol_cookie_mutations_v1 from anon, authenticated;
revoke all on public.pentas_packets_v1 from anon, authenticated;
revoke all on public.pentas_packet_receipts_v1 from anon, authenticated;
revoke all on public.penta_discovery_cases_v1 from anon, authenticated;

-- The service role may invoke bounded SECURITY DEFINER RPCs, but it does not receive
-- direct mutation rights on protocol state tables. This keeps authority at the contract boundary.
revoke all on public.penta_protocol_registry_v1 from service_role;
revoke all on public.penta_protocol_cookies_v1 from service_role;
revoke all on public.penta_protocol_cookie_mutations_v1 from service_role;
revoke all on public.pentas_packets_v1 from service_role;
revoke all on public.pentas_packet_receipts_v1 from service_role;
revoke all on public.penta_discovery_cases_v1 from service_role;

create or replace function public.penta_protocol_sha256_v1(p_value jsonb)
returns text
language sql
immutable
set search_path = pg_catalog, public
as $$
  select encode(digest(convert_to(coalesce(p_value, '{}'::jsonb)::text, 'UTF8'), 'sha256'), 'hex');
$$;

create or replace function public.penta_protocol_reject_history_mutation_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'append_only_history';
end;
$$;

drop trigger if exists penta_protocol_cookie_mutations_append_only_v1 on public.penta_protocol_cookie_mutations_v1;
create trigger penta_protocol_cookie_mutations_append_only_v1
before update or delete on public.penta_protocol_cookie_mutations_v1
for each row execute function public.penta_protocol_reject_history_mutation_v1();

drop trigger if exists pentas_packet_receipts_append_only_v1 on public.pentas_packet_receipts_v1;
create trigger pentas_packet_receipts_append_only_v1
before update or delete on public.pentas_packet_receipts_v1
for each row execute function public.penta_protocol_reject_history_mutation_v1();

create or replace function public.penta_cookie_no_delete_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'penta_cookie_tombstone_or_hold_required';
end;
$$;

drop trigger if exists penta_protocol_cookie_no_delete_trigger_v1 on public.penta_protocol_cookies_v1;
create trigger penta_protocol_cookie_no_delete_trigger_v1
before delete on public.penta_protocol_cookies_v1
for each row execute function public.penta_cookie_no_delete_v1();

create or replace function public.pentas_packet_immutable_envelope_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if row(
      new.protocol_id,new.protocol_version,new.packet_type,new.source_system_key,
      new.source_cookie_id,new.source_cookie_revision,new.target_kind,new.target_ref,
      new.route_lane,new.correlation_id,new.causation_id,new.risk_class,new.authority_class,
      new.priority,new.max_hops,new.ttl_seconds,new.expires_at,new.payload,new.payload_sha256,
      new.content_address,new.signature_ref,new.signature_state,new.origin_node_ref,
      new.network_epoch,new.dedupe_key,new.created_at
    ) is distinct from row(
      old.protocol_id,old.protocol_version,old.packet_type,old.source_system_key,
      old.source_cookie_id,old.source_cookie_revision,old.target_kind,old.target_ref,
      old.route_lane,old.correlation_id,old.causation_id,old.risk_class,old.authority_class,
      old.priority,old.max_hops,old.ttl_seconds,old.expires_at,old.payload,old.payload_sha256,
      old.content_address,old.signature_ref,old.signature_state,old.origin_node_ref,
      old.network_epoch,old.dedupe_key,old.created_at
    ) then
    raise exception 'pentas_packet_envelope_is_immutable';
  end if;
  if new.hop_count < old.hop_count then
    raise exception 'pentas_packet_hop_count_must_be_monotonic';
  end if;
  return new;
end;
$$;

drop trigger if exists pentas_packet_immutable_envelope_trigger_v1 on public.pentas_packets_v1;
create trigger pentas_packet_immutable_envelope_trigger_v1
before update on public.pentas_packets_v1
for each row execute function public.pentas_packet_immutable_envelope_v1();

insert into public.penta_protocol_registry_v1
(protocol_id,version,lifecycle_state,purpose,schema_ref,authority_ceiling,metadata)
values
('ct.penta.protocol.v1','1.0.0','implemented',
 'Base protocol contract shared by all Penta systems: stable identity, bounded authority, mesh packet interoperability, evidence and continuity.',
 'penta/crawler/README.md','D2',
 jsonb_build_object('chlom_governed',true,'serialized_mutation',true,'decentralization_ready',true)),
('ct.penta.cookie.v1','1.0.0','implemented',
 'Server-side per-Penta identity/state capsule used for tracking, scoped operational observations and oracle-adjudicated mutation.',
 'schemas/penta/penta-cookie-v1.schema.json','D2',
 jsonb_build_object('browser_cookie',false,'contains_secret',false,'d3_human_reserved',true)),
('ct.pentas.packet.v1','1.0.0','implemented',
 'Content-addressed bounded message envelope carried by Pentas across the Penta mesh.',
 'schemas/penta/pentas-packet-v1.schema.json','D3',
 jsonb_build_object('d3_information_only',true,'payload_limit_bytes',65536,'max_hops_default',12)),
('ct.penta.discovery.v1','1.0.0','implemented',
 'Discovery hand-raise, triage and governed handoff protocol between Penta systems, PentaCensus, PentaCrawler and PentaHelp.',
 'penta/crawler/README.md','D2',
 jsonb_build_object('census_authority','penta.census','helper','penta.helper','crawler','penta.crawler')),
('ct.penta.crawler.systemwide.v3','3.0.0','implemented',
 'PentaCrawler systemwide bounded roaming contract over the registered CrownThrive estate plus bounded public-web evidence collection.',
 'penta/crawler/README.md','D2',
 jsonb_build_object('arbitrary_internal_crawling',false,'provider_write',false,'d3_human_reserved',true))
on conflict (protocol_id) do update
set version=excluded.version,
    purpose=excluded.purpose,
    schema_ref=excluded.schema_ref,
    authority_ceiling=excluded.authority_ceiling,
    metadata=excluded.metadata,
    updated_at=now();

insert into public.penta_system_registry
(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at)
values
('penta.discovery','PentaDiscovery','mesh_discovery_protocol',
 'Receive Penta discovery hand-raises, normalize discovery signals and route them to PentaCensus, PentaCrawler, PentaHelp or human governance without manufacturing canonical state.',
 'May classify and route discovery evidence through D2. PentaCensus owns census/canonical discovery state. D3 execution, authority creation, provider writes, credential changes, money movement and destructive actions remain outside this protocol.',
 'D2','implemented','1.0.0',false,'penta/crawler/README.md',
 'rpc:public.penta_discovery_route_v1(integer)',
 jsonb_build_object(
   'namespace_state','candidate',
   'canonicalization_required',true,
   'protocol_id','ct.penta.discovery.v1',
   'all_pentas_can_raise',true,
   'penta_census_authority',true,
   'd3_human_reserved',true,
   'authority_manufacture',false
 ),null)
on conflict (system_key) do update
set purpose=excluded.purpose,
    authority_boundary=excluded.authority_boundary,
    risk_ceiling=excluded.risk_ceiling,
    version=excluded.version,
    docs_ref=excluded.docs_ref,
    runtime_ref=excluded.runtime_ref,
    metadata=public.penta_system_registry.metadata || excluded.metadata,
    updated_at=now();

insert into public.penta_runtime_routes(route_id,route_class,source,target,trigger,enabled,metadata)
values
('ct.route.penta-census.crawler.v3','cold','penta.census','penta.crawler','census_due_or_registered_estate_drift',true,
 jsonb_build_object('external_scheduler_slot_delta',0,'contract','ct.penta.crawler.systemwide.v3','authority_expansion',false)),
('ct.route.penta-crawler.discovery.v3','hot','penta.crawler','penta.discovery','fault_or_gap_detected',true,
 jsonb_build_object('packet_protocol','ct.pentas.packet.v1','authority_expansion',false)),
('ct.route.penta-discovery.helper.v1','hot','penta.discovery','penta.helper','actionable_discovery_signal',true,
 jsonb_build_object('metaprotocol','ct.penta.help.metaprotocol.v1','d3_human_reserved',true)),
('ct.route.penta-discovery.census.v1','hot','penta.discovery','penta.census','unknown_or_new_system_signal',true,
 jsonb_build_object('census_is_canonical_discovery_authority',true,'authority_expansion',false))
on conflict(route_id) do update
set route_class=excluded.route_class,
    source=excluded.source,
    target=excluded.target,
    trigger=excluded.trigger,
    enabled=excluded.enabled,
    metadata=excluded.metadata,
    updated_at=now();

create or replace function public.penta_cookie_install_v1(
  p_system_key text,
  p_actor_system_key text default 'penta.crawler'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_system public.penta_system_registry%rowtype;
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_identity jsonb;
  v_revision text;
  v_patch_hash text;
  v_fingerprint text;
begin
  perform pg_advisory_xact_lock(hashtext('penta-cookie-install:'||coalesce(p_system_key,'')));
  select * into v_system
  from public.penta_system_registry
  where system_key=p_system_key;

  if not found then
    raise exception 'penta_system_not_registered';
  end if;

  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_system_key;

  if found then
    return jsonb_build_object(
      'state','exists',
      'cookie_id',v_cookie.cookie_id,
      'system_key',v_cookie.system_key,
      'current_revision',v_cookie.current_revision,
      'mutation_seq',v_cookie.mutation_seq
    );
  end if;

  v_identity:=jsonb_build_object(
    'system_key',v_system.system_key,
    'canonical_name',v_system.canonical_name,
    'penta_protocol','ct.penta.protocol.v1',
    'installed_registry_version',v_system.version,
    'installed_maturity',v_system.maturity,
    'installed_category',v_system.category,
    'authority_ceiling',v_system.risk_ceiling
  );

  v_revision:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'identity_claims',v_identity,
    'observed_state','{}'::jsonb,
    'oracle_state','{}'::jsonb,
    'mutation_seq',0
  ));

  insert into public.penta_protocol_cookies_v1(
    system_key,authority_ceiling,identity_claims,observed_state,oracle_state,
    current_revision,mutation_seq,installed_by,last_seen_at
  )
  values(
    v_system.system_key,v_system.risk_ceiling,v_identity,'{}'::jsonb,'{}'::jsonb,
    v_revision,0,coalesce(nullif(p_actor_system_key,''),'penta.crawler'),now()
  )
  returning * into v_cookie;

  v_patch_hash:=public.penta_protocol_sha256_v1(v_identity);
  v_fingerprint:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'cookie_id',v_cookie.cookie_id,
    'kind','install',
    'new_revision',v_revision,
    'patch_sha256',v_patch_hash,
    'actor',p_actor_system_key
  ));

  insert into public.penta_protocol_cookie_mutations_v1(
    cookie_id,mutation_kind,patch_target,prior_revision,expected_revision,new_revision,
    mutation_seq,patch,patch_sha256,actor_system_key,risk_class,reason,evidence_refs,
    idempotency_key,semantic_fingerprint
  )
  values(
    v_cookie.cookie_id,'install','identity_claims',null,null,v_revision,
    0,v_identity,v_patch_hash,coalesce(nullif(p_actor_system_key,''),'penta.crawler'),
    'D0','Install Penta protocol cookie from canonical system registry','[]'::jsonb,
    'cookie-install:'||v_system.system_key,v_fingerprint
  )
  on conflict (idempotency_key) do nothing;

  return jsonb_build_object(
    'state','installed',
    'cookie_id',v_cookie.cookie_id,
    'system_key',v_cookie.system_key,
    'current_revision',v_revision,
    'mutation_seq',0
  );
end;
$$;

create or replace function public.penta_cookie_backfill_v1(
  p_limit integer default 100
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_system_key text;
  v_installed integer:=0;
  v_seen integer:=0;
  v_result jsonb;
begin
  for v_system_key in
    select s.system_key
    from public.penta_system_registry s
    left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
    where c.cookie_id is null
      and s.maturity <> 'retired'
    order by s.system_key
    limit v_limit
  loop
    v_result:=public.penta_cookie_install_v1(v_system_key,'penta.crawler');
    v_seen:=v_seen+1;
    if v_result->>'state'='installed' then
      v_installed:=v_installed+1;
    end if;
  end loop;

  return jsonb_build_object(
    'state','complete',
    'considered',v_seen,
    'installed',v_installed,
    'limit',v_limit,
    'at',now()
  );
end;
$$;

create or replace function public.penta_cookie_observe_v1(
  p_system_key text,
  p_observation jsonb,
  p_actor_system_key text default 'penta.crawler',
  p_evidence_refs jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_new_observed jsonb;
  v_new_seq bigint;
  v_new_revision text;
  v_patch_hash text;
  v_fingerprint text;
begin
  if p_actor_system_key not in ('penta.crawler','penta.census','penta.self','penta.context') then
    raise exception 'cookie_observation_actor_not_allowed';
  end if;
  if jsonb_typeof(coalesce(p_observation,'{}'::jsonb)) <> 'object' then
    raise exception 'cookie_observation_must_be_object';
  end if;
  if octet_length(coalesce(p_observation,'{}'::jsonb)::text) > 32768 then
    raise exception 'cookie_observation_too_large';
  end if;

  perform public.penta_cookie_install_v1(p_system_key,p_actor_system_key);

  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_system_key
  for update;

  if v_cookie.cookie_state <> 'active' then
    raise exception 'cookie_not_active';
  end if;

  v_new_observed:=v_cookie.observed_state || coalesce(p_observation,'{}'::jsonb);
  v_new_seq:=v_cookie.mutation_seq+1;
  v_new_revision:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'identity_claims',v_cookie.identity_claims,
    'observed_state',v_new_observed,
    'oracle_state',v_cookie.oracle_state,
    'mutation_seq',v_new_seq
  ));
  v_patch_hash:=public.penta_protocol_sha256_v1(coalesce(p_observation,'{}'::jsonb));
  v_fingerprint:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'cookie_id',v_cookie.cookie_id,
    'kind','observation_refresh',
    'prior_revision',v_cookie.current_revision,
    'new_revision',v_new_revision,
    'patch_sha256',v_patch_hash,
    'actor',p_actor_system_key
  ));

  insert into public.penta_protocol_cookie_mutations_v1(
    cookie_id,mutation_kind,patch_target,prior_revision,expected_revision,new_revision,
    mutation_seq,patch,patch_sha256,actor_system_key,risk_class,reason,evidence_refs,
    semantic_fingerprint
  )
  values(
    v_cookie.cookie_id,'observation_refresh','observed_state',v_cookie.current_revision,
    v_cookie.current_revision,v_new_revision,v_new_seq,coalesce(p_observation,'{}'::jsonb),
    v_patch_hash,p_actor_system_key,'D0','Bounded operational observation refresh',
    coalesce(p_evidence_refs,'[]'::jsonb),v_fingerprint
  );

  update public.penta_protocol_cookies_v1
  set observed_state=v_new_observed,
      current_revision=v_new_revision,
      mutation_seq=v_new_seq,
      last_seen_at=now(),
      updated_at=now()
  where cookie_id=v_cookie.cookie_id;

  return jsonb_build_object(
    'state','observed',
    'cookie_id',v_cookie.cookie_id,
    'system_key',v_cookie.system_key,
    'prior_revision',v_cookie.current_revision,
    'current_revision',v_new_revision,
    'mutation_seq',v_new_seq
  );
end;
$$;

create or replace function public.penta_cookie_mutate_v1(
  p_system_key text,
  p_expected_revision text,
  p_oracle_patch jsonb,
  p_risk_class text,
  p_actor_system_key text,
  p_oracle_adjudication_id uuid,
  p_reason text,
  p_idempotency_key text,
  p_evidence_refs jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, chlom_runtime
as $$
declare
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_adj chlom_runtime.oracle_adjudications%rowtype;
  v_positions integer;
  v_new_oracle jsonb;
  v_new_seq bigint;
  v_new_revision text;
  v_patch_hash text;
  v_fingerprint text;
  v_existing public.penta_protocol_cookie_mutations_v1%rowtype;
begin
  if p_risk_class not in ('D0','D1','D2','D3') then
    raise exception 'invalid_risk_class';
  end if;
  if p_risk_class='D3' then
    raise exception 'd3_cookie_mutation_human_reserved';
  end if;
  if jsonb_typeof(coalesce(p_oracle_patch,'{}'::jsonb)) <> 'object' then
    raise exception 'oracle_patch_must_be_object';
  end if;
  if exists (
    select 1
    from jsonb_object_keys(coalesce(p_oracle_patch,'{}'::jsonb)) as k(key)
    where k.key not in (
      'capabilities','routing','protocol_preferences','operational_constraints','advisory','feature_flags'
    )
  ) then
    raise exception 'oracle_patch_key_not_allowed';
  end if;
  if octet_length(coalesce(p_oracle_patch,'{}'::jsonb)::text) > 32768 then
    raise exception 'oracle_patch_too_large';
  end if;
  if nullif(btrim(coalesce(p_idempotency_key,'')),'') is null then
    raise exception 'idempotency_key_required';
  end if;

  perform pg_advisory_xact_lock(hashtext('penta-cookie-mutation:'||coalesce(p_idempotency_key,'')));

  v_patch_hash:=public.penta_protocol_sha256_v1(coalesce(p_oracle_patch,'{}'::jsonb));
  v_fingerprint:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'system_key',p_system_key,
    'expected_revision',p_expected_revision,
    'patch_sha256',v_patch_hash,
    'risk_class',p_risk_class,
    'actor',p_actor_system_key,
    'oracle_adjudication_id',p_oracle_adjudication_id,
    'reason',p_reason
  ));

  select * into v_existing
  from public.penta_protocol_cookie_mutations_v1
  where idempotency_key=p_idempotency_key;

  if found then
    if v_existing.semantic_fingerprint <> v_fingerprint then
      raise exception 'idempotency_key_reused_for_different_mutation';
    end if;
    return jsonb_build_object(
      'state','idempotent_replay',
      'mutation_id',v_existing.mutation_id,
      'new_revision',v_existing.new_revision,
      'mutation_seq',v_existing.mutation_seq
    );
  end if;

  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_system_key
  for update;

  if not found then
    raise exception 'penta_cookie_not_installed';
  end if;
  if v_cookie.cookie_state <> 'active' then
    raise exception 'cookie_not_active';
  end if;
  if v_cookie.current_revision <> p_expected_revision then
    raise exception 'stale_cookie_revision';
  end if;

  select * into v_adj
  from chlom_runtime.oracle_adjudications
  where adjudication_id=p_oracle_adjudication_id;

  if not found then
    raise exception 'oracle_adjudication_not_found';
  end if;
  if lower(coalesce(v_adj.state,'')) not in ('resolved','resolved_auto')
     or lower(coalesce(v_adj.final_disposition,'')) !~ '^(allow|approve|pass|accept|apply)' then
    raise exception 'oracle_adjudication_not_approved';
  end if;
  if coalesce(v_adj.founder_required,false) then
    raise exception 'oracle_adjudication_requires_founder';
  end if;
  if coalesce(v_adj.professional_required,false) then
    raise exception 'oracle_adjudication_requires_professional';
  end if;
  if coalesce(v_adj.auto_resolve_eligible,false) is false then
    raise exception 'oracle_adjudication_not_auto_resolve_eligible';
  end if;
  if coalesce(v_adj.confidence,0) < coalesce((v_cookie.oracle_policy->>'confidence_floor')::numeric,0.80) then
    raise exception 'oracle_confidence_below_cookie_policy';
  end if;
  if coalesce(v_adj.disagreement,1) > coalesce((v_cookie.oracle_policy->>'maximum_disagreement')::numeric,0.20) then
    raise exception 'oracle_disagreement_above_cookie_policy';
  end if;
  if coalesce(v_adj.risk_band,'D3')='D3' then
    raise exception 'oracle_adjudication_d3_human_reserved';
  end if;

  select count(distinct actor_id) into v_positions
  from chlom_runtime.oracle_adjudication_positions
  where adjudication_id=p_oracle_adjudication_id
    and position_state in ('accepted','active','verified','final');

  if v_positions < coalesce((v_cookie.oracle_policy->>'minimum_distinct_oracles')::integer,2) then
    raise exception 'oracle_quorum_below_cookie_policy';
  end if;

  v_new_oracle:=v_cookie.oracle_state || coalesce(p_oracle_patch,'{}'::jsonb);
  v_new_seq:=v_cookie.mutation_seq+1;
  v_new_revision:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'identity_claims',v_cookie.identity_claims,
    'observed_state',v_cookie.observed_state,
    'oracle_state',v_new_oracle,
    'mutation_seq',v_new_seq
  ));

  insert into public.penta_protocol_cookie_mutations_v1(
    cookie_id,mutation_kind,patch_target,prior_revision,expected_revision,new_revision,
    mutation_seq,patch,patch_sha256,actor_system_key,oracle_adjudication_id,risk_class,
    reason,evidence_refs,idempotency_key,semantic_fingerprint
  )
  values(
    v_cookie.cookie_id,'oracle_mutation','oracle_state',v_cookie.current_revision,
    p_expected_revision,v_new_revision,v_new_seq,coalesce(p_oracle_patch,'{}'::jsonb),
    v_patch_hash,p_actor_system_key,p_oracle_adjudication_id,p_risk_class,
    coalesce(nullif(p_reason,''),'Oracle-adjudicated Penta cookie mutation'),
    coalesce(p_evidence_refs,'[]'::jsonb),p_idempotency_key,v_fingerprint
  );

  update public.penta_protocol_cookies_v1
  set oracle_state=v_new_oracle,
      current_revision=v_new_revision,
      mutation_seq=v_new_seq,
      last_seen_at=now(),
      updated_at=now()
  where cookie_id=v_cookie.cookie_id;

  return jsonb_build_object(
    'state','mutated',
    'cookie_id',v_cookie.cookie_id,
    'system_key',v_cookie.system_key,
    'prior_revision',v_cookie.current_revision,
    'current_revision',v_new_revision,
    'mutation_seq',v_new_seq,
    'oracle_adjudication_id',p_oracle_adjudication_id
  );
end;
$$;

create or replace function public.pentas_packet_receipt_v1(
  p_packet_id uuid,
  p_actor_system_key text,
  p_action text,
  p_from_state text,
  p_to_state text,
  p_hop_count integer,
  p_evidence jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_previous text;
  v_hash text;
  v_receipt_id uuid;
begin
  select receipt_sha256 into v_previous
  from public.pentas_packet_receipts_v1
  where packet_id=p_packet_id
  order by created_at desc, receipt_id desc
  limit 1;

  v_hash:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'packet_id',p_packet_id,
    'actor_system_key',p_actor_system_key,
    'action',p_action,
    'from_state',p_from_state,
    'to_state',p_to_state,
    'hop_count',coalesce(p_hop_count,0),
    'evidence',coalesce(p_evidence,'{}'::jsonb),
    'previous_receipt_sha256',v_previous
  ));

  insert into public.pentas_packet_receipts_v1(
    packet_id,actor_system_key,action,from_state,to_state,hop_count,evidence,
    previous_receipt_sha256,receipt_sha256
  )
  values(
    p_packet_id,p_actor_system_key,p_action,p_from_state,p_to_state,coalesce(p_hop_count,0),
    coalesce(p_evidence,'{}'::jsonb),v_previous,v_hash
  )
  returning receipt_id into v_receipt_id;

  return v_receipt_id;
end;
$$;

create or replace function public.pentas_emit_v1(
  p_packet_type text,
  p_source_system_key text,
  p_target_kind text,
  p_target_ref text,
  p_payload jsonb default '{}'::jsonb,
  p_risk_class text default 'D1',
  p_authority_class text default 'bounded',
  p_route_lane text default 'default',
  p_priority integer default 50,
  p_ttl_seconds integer default 900,
  p_correlation_id uuid default null,
  p_causation_id uuid default null,
  p_signature_ref text default null,
  p_signature_state text default 'unsigned',
  p_origin_node_ref text default null,
  p_network_epoch text default 'centralized-phase3',
  p_dedupe_key text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_payload_hash text;
  v_content_address text;
  v_packet public.pentas_packets_v1%rowtype;
  v_ttl integer:=greatest(30,least(coalesce(p_ttl_seconds,900),604800));
  v_dedupe text;
  v_initial_state text:='pending';
begin
  if p_packet_type not in (
    'heartbeat','discovery.raise','discovery.observation','help.raise','help.response',
    'health.signal','fault.detected','tag.proposal','remediation.request',
    'oracle.observation','oracle.mutation.proposal','mesh.ack','governance.escalation'
  ) then
    raise exception 'unsupported_pentas_packet_type';
  end if;
  if p_target_kind not in ('system','capability','mesh_lane','broadcast') then
    raise exception 'unsupported_pentas_target_kind';
  end if;
  if p_risk_class not in ('D0','D1','D2','D3') then
    raise exception 'invalid_pentas_risk_class';
  end if;
  if p_risk_class='D3' and coalesce(p_authority_class,'') <> 'human_reserved' then
    raise exception 'd3_packet_requires_human_reserved_authority_class';
  end if;
  if octet_length(coalesce(p_payload,'{}'::jsonb)::text) > 65536 then
    raise exception 'pentas_packet_payload_too_large';
  end if;

  perform public.penta_cookie_install_v1(p_source_system_key,p_source_system_key);

  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_source_system_key
  for update;

  if v_cookie.cookie_state <> 'active' then
    raise exception 'source_penta_cookie_not_active';
  end if;

  v_payload_hash:=public.penta_protocol_sha256_v1(coalesce(p_payload,'{}'::jsonb));
  v_content_address:='sha256:'||public.penta_protocol_sha256_v1(jsonb_build_object(
    'protocol_id','ct.pentas.packet.v1',
    'packet_type',p_packet_type,
    'source_system_key',p_source_system_key,
    'source_cookie_revision',v_cookie.current_revision,
    'target_kind',p_target_kind,
    'target_ref',p_target_ref,
    'route_lane',coalesce(p_route_lane,'default'),
    'risk_class',p_risk_class,
    'authority_class',p_authority_class,
    'payload_sha256',v_payload_hash,
    'correlation_id',p_correlation_id,
    'causation_id',p_causation_id
  ));

  v_dedupe:=coalesce(
    nullif(btrim(coalesce(p_dedupe_key,'')),''),
    v_content_address||':'||coalesce(p_correlation_id::text,'none')
  );

  perform pg_advisory_xact_lock(hashtext('pentas-packet:'||v_dedupe));

  select * into v_packet
  from public.pentas_packets_v1
  where dedupe_key=v_dedupe;

  if found then
    return jsonb_build_object(
      'state','idempotent_replay',
      'packet_id',v_packet.packet_id,
      'packet_state',v_packet.packet_state,
      'content_address',v_packet.content_address
    );
  end if;

  insert into public.pentas_packets_v1(
    packet_type,source_system_key,source_cookie_id,source_cookie_revision,target_kind,
    target_ref,route_lane,correlation_id,causation_id,risk_class,authority_class,
    priority,ttl_seconds,expires_at,payload,payload_sha256,content_address,
    signature_ref,signature_state,origin_node_ref,network_epoch,dedupe_key,packet_state
  )
  values(
    p_packet_type,p_source_system_key,v_cookie.cookie_id,v_cookie.current_revision,p_target_kind,
    p_target_ref,coalesce(p_route_lane,'default'),p_correlation_id,p_causation_id,p_risk_class,
    p_authority_class,greatest(0,least(coalesce(p_priority,50),100)),v_ttl,
    now()+make_interval(secs=>v_ttl),coalesce(p_payload,'{}'::jsonb),v_payload_hash,
    v_content_address,p_signature_ref,coalesce(p_signature_state,'unsigned'),
    p_origin_node_ref,coalesce(p_network_epoch,'centralized-phase3'),v_dedupe,v_initial_state
  )
  returning * into v_packet;

  perform public.pentas_packet_receipt_v1(
    v_packet.packet_id,p_source_system_key,'emit',null,v_initial_state,0,
    jsonb_build_object('content_address',v_content_address,'payload_sha256',v_payload_hash)
  );

  update public.penta_protocol_cookies_v1
  set last_seen_at=now(),updated_at=now()
  where cookie_id=v_cookie.cookie_id;

  return jsonb_build_object(
    'state','emitted',
    'packet_id',v_packet.packet_id,
    'packet_state',v_packet.packet_state,
    'content_address',v_packet.content_address,
    'expires_at',v_packet.expires_at
  );
end;
$$;

create or replace function public.pentas_packet_transition_v1(
  p_packet_id uuid,
  p_to_state text,
  p_actor_system_key text,
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_packet public.pentas_packets_v1%rowtype;
  v_allowed boolean:=false;
  v_new_hop integer;
begin
  select * into v_packet
  from public.pentas_packets_v1
  where packet_id=p_packet_id
  for update;

  if not found then
    raise exception 'pentas_packet_not_found';
  end if;

  if now() >= v_packet.expires_at and v_packet.packet_state not in ('delivered','expired','dead_letter') then
    p_to_state:='expired';
  end if;

  v_allowed:=
    (v_packet.packet_state='pending' and p_to_state in ('routed','held','expired','dead_letter')) or
    (v_packet.packet_state='routed' and p_to_state in ('delivered','held','expired','dead_letter')) or
    (v_packet.packet_state='held' and p_to_state in ('routed','expired','dead_letter')) or
    (v_packet.packet_state=p_to_state);

  if not v_allowed then
    raise exception 'invalid_pentas_packet_transition';
  end if;

  v_new_hop:=case when p_to_state='routed' and v_packet.packet_state<>'routed'
                  then v_packet.hop_count+1 else v_packet.hop_count end;

  if v_new_hop > v_packet.max_hops then
    p_to_state:='dead_letter';
    v_new_hop:=v_packet.hop_count;
  end if;

  update public.pentas_packets_v1
  set packet_state=p_to_state,
      hop_count=v_new_hop,
      updated_at=now(),
      delivered_at=case when p_to_state='delivered' then now() else delivered_at end
  where packet_id=p_packet_id;

  perform public.pentas_packet_receipt_v1(
    p_packet_id,p_actor_system_key,'transition',v_packet.packet_state,p_to_state,v_new_hop,
    coalesce(p_evidence,'{}'::jsonb)
  );

  return jsonb_build_object(
    'state',p_to_state,
    'packet_id',p_packet_id,
    'hop_count',v_new_hop
  );
end;
$$;

create or replace function public.penta_discovery_raise_v1(
  p_source_system_key text,
  p_signal_kind text,
  p_summary text,
  p_severity text default 'WARN',
  p_risk_class text default 'D1',
  p_evidence jsonb default '{}'::jsonb,
  p_case_key text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_case public.penta_discovery_cases_v1%rowtype;
  v_packet jsonb;
  v_case_key text;
  v_packet_id uuid;
begin
  if p_signal_kind not in (
    'broken','blocked','stale','degraded','missing_dependency','missing_credential',
    'missing_software','unknown_system','help_requested','discovery_requested'
  ) then
    raise exception 'unsupported_discovery_signal_kind';
  end if;
  if p_severity not in ('INFO','WARN','ERROR','CRITICAL') then
    raise exception 'unsupported_discovery_severity';
  end if;
  if p_risk_class not in ('D0','D1','D2','D3') then
    raise exception 'unsupported_discovery_risk_class';
  end if;

  v_case_key:=coalesce(
    nullif(btrim(coalesce(p_case_key,'')),''),
    'discovery:'||p_source_system_key||':'||p_signal_kind||':'||
      public.penta_protocol_sha256_v1(jsonb_build_object('summary',p_summary,'evidence',coalesce(p_evidence,'{}'::jsonb)))
  );

  select * into v_case
  from public.penta_discovery_cases_v1
  where case_key=v_case_key;

  if found and v_case.state <> 'resolved' then
    return jsonb_build_object('state','existing','case_id',v_case.case_id,'source_packet_id',v_case.source_packet_id);
  end if;

  v_packet:=public.pentas_emit_v1(
    'discovery.raise',
    p_source_system_key,
    'system',
    'penta.discovery',
    jsonb_build_object(
      'signal_kind',p_signal_kind,
      'summary',p_summary,
      'severity',p_severity,
      'evidence',coalesce(p_evidence,'{}'::jsonb)
    ),
    p_risk_class,
    case when p_risk_class='D3' then 'human_reserved' else 'bounded' end,
    'discovery',
    case p_severity when 'CRITICAL' then 100 when 'ERROR' then 85 when 'WARN' then 60 else 40 end,
    3600,
    null,null,null,'unsigned',null,'centralized-phase3',
    'packet:'||v_case_key
  );

  v_packet_id:=(v_packet->>'packet_id')::uuid;

  insert into public.penta_discovery_cases_v1(
    case_key,source_system_key,source_packet_id,signal_kind,severity,risk_class,summary,evidence,state
  )
  values(
    v_case_key,p_source_system_key,v_packet_id,p_signal_kind,p_severity,p_risk_class,
    p_summary,coalesce(p_evidence,'{}'::jsonb),'raised'
  )
  on conflict(case_key) do update
  set source_packet_id=excluded.source_packet_id,
      severity=excluded.severity,
      risk_class=excluded.risk_class,
      summary=excluded.summary,
      evidence=excluded.evidence,
      state=case when public.penta_discovery_cases_v1.state='resolved' then 'raised' else public.penta_discovery_cases_v1.state end,
      resolved_at=case when public.penta_discovery_cases_v1.state='resolved' then null else public.penta_discovery_cases_v1.resolved_at end,
      updated_at=now()
  returning * into v_case;

  return jsonb_build_object(
    'state','raised',
    'case_id',v_case.case_id,
    'source_packet_id',v_packet_id,
    'case_key',v_case_key
  );
end;
$$;

create or replace function public.penta_discovery_ingest_packets_v1(
  p_limit integer default 25
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,25),100));
  v_packet record;
  v_case_key text;
  v_inserted integer:=0;
begin
  for v_packet in
    select p.*
    from public.pentas_packets_v1 p
    where p.packet_type='discovery.raise'
      and p.target_ref='penta.discovery'
      and p.packet_state='pending'
      and p.expires_at>now()
    order by p.priority desc,p.created_at
    for update skip locked
    limit v_limit
  loop
    v_case_key:=coalesce(
      nullif(v_packet.payload->>'case_key',''),
      'packet-discovery:'||v_packet.packet_id::text
    );

    insert into public.penta_discovery_cases_v1(
      case_key,source_system_key,source_packet_id,signal_kind,severity,risk_class,summary,evidence,state
    )
    values(
      v_case_key,
      v_packet.source_system_key,
      v_packet.packet_id,
      coalesce(nullif(v_packet.payload->>'signal_kind',''),'discovery_requested'),
      coalesce(nullif(v_packet.payload->>'severity',''),'WARN'),
      v_packet.risk_class,
      coalesce(nullif(v_packet.payload->>'summary',''),'Penta requested discovery assistance'),
      coalesce(v_packet.payload->'evidence','{}'::jsonb),
      'raised'
    )
    on conflict(case_key) do nothing;

    if found then
      v_inserted:=v_inserted+1;
    end if;

    perform public.pentas_packet_transition_v1(
      v_packet.packet_id,'routed','penta.discovery',
      jsonb_build_object('case_key',v_case_key)
    );
  end loop;

  return jsonb_build_object('state','complete','ingested',v_inserted,'limit',v_limit,'at',now());
end;
$$;

create or replace function public.penta_discovery_route_v1(
  p_limit integer default 20
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, penta_help
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,20),50));
  v_case public.penta_discovery_cases_v1%rowtype;
  v_request_id uuid;
  v_help_packet jsonb;
  v_routed_help integer:=0;
  v_routed_census integer:=0;
  v_held integer:=0;
  v_resolution_mode text;
begin
  perform public.penta_cookie_install_v1('penta.discovery','penta.discovery');

  for v_case in
    select *
    from public.penta_discovery_cases_v1
    where state in ('raised','triaged')
    order by
      case severity when 'CRITICAL' then 0 when 'ERROR' then 1 when 'WARN' then 2 else 3 end,
      created_at
    for update skip locked
    limit v_limit
  loop
    if v_case.signal_kind in ('unknown_system','discovery_requested') then
      update public.penta_discovery_cases_v1
      set state='routed_census',updated_at=now()
      where case_id=v_case.case_id;

      perform public.pentas_emit_v1(
        'discovery.observation','penta.discovery','system','penta.census',
        jsonb_build_object(
          'case_id',v_case.case_id,
          'source_system_key',v_case.source_system_key,
          'signal_kind',v_case.signal_kind,
          'summary',v_case.summary,
          'evidence',v_case.evidence
        ),
        v_case.risk_class,
        case when v_case.risk_class='D3' then 'human_reserved' else 'bounded' end,
        'census-discovery',70,3600,v_case.case_id,null,null,'unsigned',null,'centralized-phase3',
        'discovery-to-census:'||v_case.case_id::text
      );
      v_routed_census:=v_routed_census+1;
      continue;
    end if;

    v_resolution_mode:=case
      when v_case.signal_kind='missing_software' then 'build_software'
      when v_case.signal_kind='missing_credential' then 'credential_reconcile'
      when v_case.signal_kind in ('stale') then 'restore_evidence'
      when v_case.signal_kind in ('blocked','missing_dependency') then 'provider_route'
      else 'self_repair'
    end;

    v_request_id:=penta_help.raise_v1(
      v_case.source_system_key,
      v_case.case_id::text,
      'penta_discovery',
      coalesce(v_case.source_packet_id::text,v_case.case_id::text),
      v_case.state,
      v_case.signal_kind,
      'discovery',
      v_case.summary,
      v_resolution_mode,
      v_case.risk_class,
      case when v_case.risk_class='D3' then 'D3_HUMAN_RESERVED' else 'D2_MAX' end,
      jsonb_build_object(
        'discovery_case_id',v_case.case_id,
        'source_packet_id',v_case.source_packet_id,
        'source_system_key',v_case.source_system_key,
        'evidence',v_case.evidence,
        'requested_by','penta.discovery'
      ),
      'penta-discovery-help:'||v_case.case_id::text,
      21600,
      case when v_case.risk_class='D3' then 60 else 900 end
    );

    v_help_packet:=public.pentas_emit_v1(
      'help.raise','penta.discovery','system','penta.helper',
      jsonb_build_object(
        'discovery_case_id',v_case.case_id,
        'helper_request_id',v_request_id,
        'source_system_key',v_case.source_system_key,
        'need',v_case.summary,
        'resolution_mode',v_resolution_mode
      ),
      v_case.risk_class,
      case when v_case.risk_class='D3' then 'human_reserved' else 'bounded' end,
      'help',80,3600,v_case.case_id,v_case.source_packet_id,null,'unsigned',null,'centralized-phase3',
      'discovery-to-helper:'||v_case.case_id::text
    );

    update public.penta_discovery_cases_v1
    set helper_request_id=v_request_id,
        state=case when v_case.risk_class='D3' then 'held' else 'routed_help' end,
        updated_at=now()
    where case_id=v_case.case_id;

    if v_case.risk_class='D3' then
      v_held:=v_held+1;
    else
      v_routed_help:=v_routed_help+1;
    end if;

    if v_case.source_packet_id is not null then
      perform public.pentas_packet_transition_v1(
        v_case.source_packet_id,'delivered','penta.discovery',
        jsonb_build_object('helper_request_id',v_request_id,'help_packet_id',v_help_packet->>'packet_id')
      );
    end if;
  end loop;

  return jsonb_build_object(
    'state','complete',
    'routed_help',v_routed_help,
    'routed_census',v_routed_census,
    'held_d3',v_held,
    'at',now()
  );
end;
$$;

create or replace function public.penta_crawler_flag_broken_v1(
  p_system_key text,
  p_fault_code text,
  p_severity text,
  p_priority text,
  p_summary text,
  p_risk_class text default 'D1',
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_fingerprint text;
  v_incident public.penta_incidents_v1%rowtype;
  v_discovery jsonb;
  v_signal_kind text;
begin
  if p_severity not in ('INFO','WARN','ERROR','CRITICAL') then
    raise exception 'invalid_incident_severity';
  end if;
  if p_priority not in ('P0','P1','P2','P3') then
    raise exception 'invalid_incident_priority';
  end if;
  if p_risk_class not in ('D0','D1','D2','D3') then
    raise exception 'invalid_incident_risk';
  end if;

  v_fingerprint:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'system_key',p_system_key,
    'fault_code',p_fault_code,
    'summary',p_summary
  ));

  perform pg_advisory_xact_lock(hashtext('penta-crawler-fault:'||v_fingerprint));

  select * into v_incident
  from public.penta_incidents_v1
  where fingerprint=v_fingerprint
    and state <> 'resolved'
  order by opened_at desc
  limit 1;

  if not found then
    insert into public.penta_incidents_v1(
      system_key,incident_code,severity,priority,state,source_event_ref,fingerprint,
      title,summary,failure_evidence,remediation_state
    )
    values(
      p_system_key,p_fault_code,p_severity,p_priority,'detected','penta-crawler-roam',
      v_fingerprint,'PentaCrawler detected '||p_fault_code,p_summary,
      coalesce(p_evidence,'{}'::jsonb),'pending'
    )
    returning * into v_incident;

    insert into public.penta_flags_v1(incident_id,flag_key,severity,reason,evidence)
    values(
      v_incident.incident_id,'penta-crawler:broken',p_severity,p_summary,
      coalesce(p_evidence,'{}'::jsonb)
    );

    insert into public.penta_tags_v1(incident_id,tag)
    values
      (v_incident.incident_id,'penta:discovered'),
      (v_incident.incident_id,'penta:needs-help'),
      (v_incident.incident_id,'penta:crawler-observed');
  end if;

  v_signal_kind:=case
    when p_fault_code ilike '%credential%' then 'missing_credential'
    when p_fault_code ilike '%dependency%' then 'missing_dependency'
    when p_fault_code ilike '%software%' or p_fault_code ilike '%runtime_missing%' then 'missing_software'
    when p_fault_code ilike '%stale%' then 'stale'
    when p_fault_code ilike '%blocked%' then 'blocked'
    when p_fault_code ilike '%degraded%' then 'degraded'
    else 'broken'
  end;

  v_discovery:=public.penta_discovery_raise_v1(
    p_system_key,v_signal_kind,p_summary,p_severity,p_risk_class,
    coalesce(p_evidence,'{}'::jsonb) || jsonb_build_object(
      'incident_id',v_incident.incident_id,
      'fingerprint',v_fingerprint,
      'fault_code',p_fault_code
    ),
    'crawler-fault:'||v_fingerprint
  );

  update public.penta_discovery_cases_v1
  set incident_id=v_incident.incident_id,updated_at=now()
  where case_id=(v_discovery->>'case_id')::uuid;

  return jsonb_build_object(
    'state','flagged',
    'incident_id',v_incident.incident_id,
    'fingerprint',v_fingerprint,
    'discovery',v_discovery
  );
end;
$$;

create or replace function public.penta_crawler_roam_v1(
  p_limit integer default 100
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_backfill jsonb;
  v_ingest jsonb;
  v_route jsonb;
  v_row record;
  v_faults jsonb;
  v_fault_count integer;
  v_scanned integer:=0;
  v_signals integer:=0;
  v_risk text;
  v_priority text;
  v_severity text;
begin
  v_backfill:=public.penta_cookie_backfill_v1(v_limit);

  for v_row in
    select
      s.system_key,s.canonical_name,s.category,s.purpose,s.risk_ceiling,s.maturity,
      s.version,s.runtime_ref,s.last_verified_at,s.metadata,c.last_seen_at
    from public.penta_system_registry s
    left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
    where s.maturity <> 'retired'
    order by coalesce(c.last_seen_at,'epoch'::timestamptz),s.system_key
    limit v_limit
  loop
    v_faults:='[]'::jsonb;
    v_fault_count:=0;

    if v_row.maturity='production' and nullif(btrim(coalesce(v_row.runtime_ref,'')),'') is null then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object(
        'code','runtime_missing',
        'summary','Production Penta has no runtime_ref in the system registry'
      ));
      v_fault_count:=v_fault_count+1;
    end if;

    if v_row.maturity='production'
       and (v_row.last_verified_at is null or v_row.last_verified_at < now()-interval '24 hours') then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object(
        'code','stale_verification',
        'summary','Production Penta verification evidence is older than 24 hours or missing'
      ));
      v_fault_count:=v_fault_count+1;
    end if;

    if lower(coalesce(v_row.metadata->>'operational_state','')) in ('degraded','failed','error','blocked','hold')
       or lower(coalesce(v_row.metadata->>'continuous_healing_state','')) in ('degraded','failed','error','blocked','hold')
       or lower(coalesce(v_row.metadata->>'last_self_cycle_state','')) in ('degraded','failed','error','blocked','hold') then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object(
        'code','declared_degraded',
        'summary','Penta registry metadata declares a degraded/failed/blocked operational state'
      ));
      v_fault_count:=v_fault_count+1;
    end if;

    perform public.penta_cookie_observe_v1(
      v_row.system_key,
      jsonb_build_object(
        'roam_observed_at',now(),
        'registry_maturity',v_row.maturity,
        'registry_version',v_row.version,
        'runtime_ref_present',nullif(btrim(coalesce(v_row.runtime_ref,'')),'') is not null,
        'last_verified_at',v_row.last_verified_at,
        'fault_count',v_fault_count,
        'faults',v_faults
      ),
      'penta.crawler',
      jsonb_build_array('penta_system_registry:'||v_row.system_key)
    );
    v_scanned:=v_scanned+1;

    if v_fault_count>0 then
      for v_faults in select value from jsonb_array_elements(v_faults)
      loop
        v_severity:=case
          when v_faults->>'code'='runtime_missing' then 'ERROR'
          when v_faults->>'code'='declared_degraded' then 'ERROR'
          else 'WARN'
        end;
        v_priority:=case when v_severity='ERROR' then 'P1' else 'P2' end;
        v_risk:=case when v_severity='ERROR' then 'D2' else 'D1' end;

        perform public.penta_crawler_flag_broken_v1(
          v_row.system_key,
          v_faults->>'code',
          v_severity,
          v_priority,
          v_faults->>'summary',
          v_risk,
          jsonb_build_object(
            'canonical_name',v_row.canonical_name,
            'category',v_row.category,
            'maturity',v_row.maturity,
            'version',v_row.version,
            'runtime_ref',v_row.runtime_ref,
            'last_verified_at',v_row.last_verified_at,
            'source','penta_system_registry'
          )
        );
        v_signals:=v_signals+1;
      end loop;
    end if;
  end loop;

  v_ingest:=public.penta_discovery_ingest_packets_v1(least(v_limit,100));
  v_route:=public.penta_discovery_route_v1(least(v_limit,50));

  return jsonb_build_object(
    'service','ct.penta.crawler.systemwide.v3',
    'state','complete',
    'cookie_backfill',v_backfill,
    'scanned',v_scanned,
    'signals_raised',v_signals,
    'packet_ingest',v_ingest,
    'discovery_route',v_route,
    'authority_created',false,
    'provider_write',false,
    'd3_execution',false,
    'at',now()
  );
end;
$$;

create or replace function public.penta_crawler_status_v3()
returns jsonb
language sql
security definer
set search_path = pg_catalog, public
as $$
  select jsonb_build_object(
    'service','ct.penta.crawler.systemwide.v3',
    'protocols',(select count(*) from public.penta_protocol_registry_v1 where lifecycle_state<>'retired'),
    'registered_pentas',(select count(*) from public.penta_system_registry where maturity<>'retired'),
    'cookies',(select count(*) from public.penta_protocol_cookies_v1 where cookie_state='active'),
    'packets_pending',(select count(*) from public.pentas_packets_v1 where packet_state='pending' and expires_at>now()),
    'packets_held',(select count(*) from public.pentas_packets_v1 where packet_state='held'),
    'discovery_open',(select count(*) from public.penta_discovery_cases_v1 where state not in ('resolved')),
    'discovery_held',(select count(*) from public.penta_discovery_cases_v1 where state='held'),
    'cookie_mutations',(select count(*) from public.penta_protocol_cookie_mutations_v1),
    'authority_created',false,
    'd3_human_reserved',true,
    'at',now()
  );
$$;

create or replace function public.penta_cookie_registry_autoinstall_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if new.maturity <> 'retired' then
    perform public.penta_cookie_install_v1(new.system_key,'penta.census');
  end if;
  return new;
end;
$$;

drop trigger if exists penta_cookie_registry_autoinstall_trigger_v1 on public.penta_system_registry;
create trigger penta_cookie_registry_autoinstall_trigger_v1
after insert or update of maturity on public.penta_system_registry
for each row execute function public.penta_cookie_registry_autoinstall_v1();

revoke all on function public.penta_protocol_sha256_v1(jsonb) from public, anon, authenticated;
revoke all on function public.penta_cookie_install_v1(text,text) from public, anon, authenticated;
revoke all on function public.penta_cookie_backfill_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_cookie_observe_v1(text,jsonb,text,jsonb) from public, anon, authenticated;
revoke all on function public.penta_cookie_mutate_v1(text,text,jsonb,text,text,uuid,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.pentas_packet_receipt_v1(uuid,text,text,text,text,integer,jsonb) from public, anon, authenticated;
revoke all on function public.pentas_emit_v1(text,text,text,text,jsonb,text,text,text,integer,integer,uuid,uuid,text,text,text,text,text) from public, anon, authenticated;
revoke all on function public.pentas_packet_transition_v1(uuid,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.penta_discovery_raise_v1(text,text,text,text,text,jsonb,text) from public, anon, authenticated;
revoke all on function public.penta_discovery_ingest_packets_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_discovery_route_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_crawler_flag_broken_v1(text,text,text,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.penta_crawler_roam_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_crawler_status_v3() from public, anon, authenticated;
revoke all on function public.penta_cookie_registry_autoinstall_v1() from public, anon, authenticated;

grant execute on function public.penta_protocol_sha256_v1(jsonb) to service_role;
grant execute on function public.penta_cookie_install_v1(text,text) to service_role;
grant execute on function public.penta_cookie_backfill_v1(integer) to service_role;
grant execute on function public.penta_cookie_observe_v1(text,jsonb,text,jsonb) to service_role;
grant execute on function public.penta_cookie_mutate_v1(text,text,jsonb,text,text,uuid,text,text,jsonb) to service_role;
grant execute on function public.pentas_packet_receipt_v1(uuid,text,text,text,text,integer,jsonb) to service_role;
grant execute on function public.pentas_emit_v1(text,text,text,text,jsonb,text,text,text,integer,integer,uuid,uuid,text,text,text,text,text) to service_role;
grant execute on function public.pentas_packet_transition_v1(uuid,text,text,jsonb) to service_role;
grant execute on function public.penta_discovery_raise_v1(text,text,text,text,text,jsonb,text) to service_role;
grant execute on function public.penta_discovery_ingest_packets_v1(integer) to service_role;
grant execute on function public.penta_discovery_route_v1(integer) to service_role;
grant execute on function public.penta_crawler_flag_broken_v1(text,text,text,text,text,text,jsonb) to service_role;
grant execute on function public.penta_crawler_roam_v1(integer) to service_role;
grant execute on function public.penta_crawler_status_v3() to service_role;
