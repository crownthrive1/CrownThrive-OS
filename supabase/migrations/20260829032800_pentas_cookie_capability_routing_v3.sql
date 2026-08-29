-- PentaCrawler / Pentas capability routing v3
-- Routes information to other Pentas based on the protocol routing descriptor carried in each PentaCookie.
-- This does not grant execution authority to a receiver; it only creates a bounded delivery envelope.

create table if not exists public.pentas_packet_deliveries_v1 (
  delivery_id uuid primary key default gen_random_uuid(),
  packet_id uuid not null references public.pentas_packets_v1(packet_id),
  target_system_key text not null,
  target_cookie_id uuid not null references public.penta_protocol_cookies_v1(cookie_id),
  target_cookie_revision text not null check (target_cookie_revision ~ '^[0-9a-f]{64}$'),
  resolution_basis text not null check (resolution_basis in ('direct_system','cookie_capability','cookie_mesh_lane','bounded_broadcast')),
  delivery_state text not null default 'pending' check (delivery_state in ('pending','leased','delivered','held','dead_letter')),
  lease_id uuid,
  lease_expires_at timestamptz,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 5 check (max_attempts between 1 and 25),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  claimed_at timestamptz,
  delivered_at timestamptz,
  unique(packet_id,target_system_key)
);

create index if not exists pentas_packet_deliveries_target_state_idx
  on public.pentas_packet_deliveries_v1(target_system_key,delivery_state,created_at);
create index if not exists pentas_packet_deliveries_packet_idx
  on public.pentas_packet_deliveries_v1(packet_id,delivery_state,created_at);

alter table public.pentas_packet_deliveries_v1 enable row level security;
revoke all on public.pentas_packet_deliveries_v1 from public, anon, authenticated, service_role;

create or replace function public.pentas_delivery_no_delete_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'pentas_delivery_history_cannot_be_deleted';
end;
$$;

drop trigger if exists pentas_delivery_no_delete_trigger_v1 on public.pentas_packet_deliveries_v1;
create trigger pentas_delivery_no_delete_trigger_v1
before delete on public.pentas_packet_deliveries_v1
for each row execute function public.pentas_delivery_no_delete_v1();

create or replace function public.penta_protocol_risk_rank_v1(p_risk text)
returns integer
language sql
immutable
set search_path = pg_catalog, public
as $$
  select case upper(coalesce(p_risk,''))
    when 'D0' then 0
    when 'D1' then 1
    when 'D2' then 2
    when 'D3' then 3
    else 99
  end;
$$;

create or replace function public.penta_cookie_refresh_routes_v1(
  p_system_key text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, pg_temp
as $$
declare
  v_system public.penta_system_registry%rowtype;
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_capabilities jsonb:='[]'::jsonb;
  v_self_caps jsonb:='[]'::jsonb;
  v_lanes jsonb:='[]'::jsonb;
  v_patch jsonb;
  v_result jsonb;
begin
  select * into v_system
  from public.penta_system_registry
  where system_key=p_system_key;
  if not found then raise exception 'penta_system_not_registered'; end if;

  perform public.penta_cookie_install_v1(p_system_key,'penta.census');
  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_system_key;

  v_capabilities:=v_capabilities || jsonb_build_array('system:'||v_system.system_key);
  if nullif(btrim(coalesce(v_system.category,'')),'') is not null then
    v_capabilities:=v_capabilities || jsonb_build_array('category:'||v_system.category);
  end if;

  v_capabilities:=v_capabilities || case v_system.system_key
    when 'penta.census' then '["census.discovery","census.registry","discovery.canonicalize"]'::jsonb
    when 'penta.helper' then '["help.triage","help.remediate","help.escalate"]'::jsonb
    when 'penta.discovery' then '["discovery.route","discovery.triage"]'::jsonb
    when 'penta.pr' then '["github.pr.lifecycle","remediation.pr"]'::jsonb
    when 'ct.penta.pm.v1' then '["project.manage","remediation.assign"]'::jsonb
    when 'penta.self' then '["self.diagnose","self.heal","self.repair"]'::jsonb
    when 'penta.crawler' then '["crawler.roam","crawler.research","discovery.observe"]'::jsonb
    else '[]'::jsonb
  end;

  if v_system.system_key='penta.self' and to_regclass('penta_self.capability_registry_v1') is not null then
    execute $q$
      select coalesce(jsonb_agg(capability_key order by capability_key),'[]'::jsonb)
      from penta_self.capability_registry_v1
      where enabled
    $q$ into v_self_caps;
    v_capabilities:=v_capabilities || coalesce(v_self_caps,'[]'::jsonb);
  end if;

  if jsonb_typeof(v_system.metadata->'canonical_lanes')='array' then
    select coalesce(jsonb_agg(distinct value order by value),'[]'::jsonb)
    into v_lanes
    from jsonb_array_elements_text(v_system.metadata->'canonical_lanes') as t(value);
  end if;

  select coalesce(jsonb_agg(distinct value order by value),'[]'::jsonb)
  into v_capabilities
  from jsonb_array_elements_text(v_capabilities) as t(value);

  v_patch:=jsonb_build_object(
    'protocol_routing',jsonb_build_object(
      'capabilities',coalesce(v_capabilities,'[]'::jsonb),
      'mesh_lanes',coalesce(v_lanes,'[]'::jsonb),
      'max_packet_risk',v_system.risk_ceiling,
      'source','penta_system_registry+declared_capability_registry',
      'refreshed_at',now()
    )
  );

  v_result:=public.penta_cookie_observe_v1(
    p_system_key,
    v_patch,
    'penta.census',
    jsonb_build_array('penta_system_registry:'||p_system_key)
  );

  return jsonb_build_object(
    'state','refreshed',
    'system_key',p_system_key,
    'capabilities',v_capabilities,
    'mesh_lanes',v_lanes,
    'cookie',v_result
  );
end;
$$;

create or replace function public.penta_cookie_accepts_packet_v1(
  p_system_key text,
  p_packet_type text,
  p_risk_class text,
  p_target_kind text,
  p_target_ref text
)
returns boolean
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_observed_routing jsonb;
  v_oracle_routing jsonb;
  v_max_risk text;
  v_accepts jsonb;
  v_match boolean:=false;
begin
  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_system_key and cookie_state='active';
  if not found then return false; end if;

  v_observed_routing:=case
    when jsonb_typeof(v_cookie.observed_state->'protocol_routing')='object'
      then v_cookie.observed_state->'protocol_routing'
    else '{}'::jsonb end;
  v_oracle_routing:=case
    when jsonb_typeof(v_cookie.oracle_state->'routing')='object'
      then v_cookie.oracle_state->'routing'
    else '{}'::jsonb end;

  v_max_risk:=coalesce(
    nullif(v_oracle_routing->>'max_packet_risk',''),
    nullif(v_observed_routing->>'max_packet_risk',''),
    v_cookie.authority_ceiling
  );
  if public.penta_protocol_risk_rank_v1(v_max_risk) < public.penta_protocol_risk_rank_v1(p_risk_class) then
    return false;
  end if;

  v_accepts:=case
    when jsonb_typeof(v_oracle_routing->'accepts_packet_types')='array'
      then v_oracle_routing->'accepts_packet_types'
    when jsonb_typeof(v_observed_routing->'accepts_packet_types')='array'
      then v_observed_routing->'accepts_packet_types'
    else '[]'::jsonb end;
  if jsonb_array_length(v_accepts)>0 and not (v_accepts ? p_packet_type) then
    return false;
  end if;

  if p_target_kind='system' then
    return p_target_ref=p_system_key;
  elsif p_target_kind='capability' then
    v_match:=
      (jsonb_typeof(v_oracle_routing->'capabilities')='array' and (v_oracle_routing->'capabilities') ? p_target_ref)
      or
      (jsonb_typeof(v_observed_routing->'capabilities')='array' and (v_observed_routing->'capabilities') ? p_target_ref);
  elsif p_target_kind='mesh_lane' then
    v_match:=
      (jsonb_typeof(v_oracle_routing->'mesh_lanes')='array' and (v_oracle_routing->'mesh_lanes') ? p_target_ref)
      or
      (jsonb_typeof(v_observed_routing->'mesh_lanes')='array' and (v_observed_routing->'mesh_lanes') ? p_target_ref);
  elsif p_target_kind='broadcast' then
    v_match:=p_target_ref='all-pentas' and public.penta_protocol_risk_rank_v1(p_risk_class)<=1;
  end if;

  return coalesce(v_match,false);
end;
$$;

create or replace function public.pentas_route_packet_v1(
  p_packet_id uuid,
  p_actor_system_key text default 'penta.mesh'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_packet public.pentas_packets_v1%rowtype;
  v_target record;
  v_basis text;
  v_count integer:=0;
  v_broadcast_count integer:=0;
begin
  select * into v_packet
  from public.pentas_packets_v1
  where packet_id=p_packet_id
  for update;
  if not found then raise exception 'pentas_packet_not_found'; end if;

  if v_packet.packet_state not in ('pending','held') then
    return jsonb_build_object('state','noop','packet_id',p_packet_id,'packet_state',v_packet.packet_state);
  end if;
  if now()>=v_packet.expires_at then
    perform public.pentas_packet_transition_v1(p_packet_id,'expired',p_actor_system_key,jsonb_build_object('reason','ttl_expired_before_route'));
    return jsonb_build_object('state','expired','packet_id',p_packet_id,'deliveries',0);
  end if;

  if v_packet.target_kind='broadcast' then
    if v_packet.target_ref<>'all-pentas' or public.penta_protocol_risk_rank_v1(v_packet.risk_class)>1 then
      perform public.pentas_packet_transition_v1(p_packet_id,'held',p_actor_system_key,jsonb_build_object('reason','broadcast_not_bounded'));
      return jsonb_build_object('state','held','packet_id',p_packet_id,'reason','broadcast_not_bounded','deliveries',0);
    end if;
    select count(*) into v_broadcast_count
    from public.penta_protocol_cookies_v1 c
    where c.cookie_state='active'
      and c.system_key<>v_packet.source_system_key
      and public.penta_cookie_accepts_packet_v1(c.system_key,v_packet.packet_type,v_packet.risk_class,'broadcast','all-pentas');
    if v_broadcast_count>250 then
      perform public.pentas_packet_transition_v1(p_packet_id,'held',p_actor_system_key,jsonb_build_object('reason','broadcast_fanout_limit','candidate_count',v_broadcast_count));
      return jsonb_build_object('state','held','packet_id',p_packet_id,'reason','broadcast_fanout_limit','candidate_count',v_broadcast_count,'deliveries',0);
    end if;
  end if;

  for v_target in
    select c.system_key,c.cookie_id,c.current_revision
    from public.penta_protocol_cookies_v1 c
    where c.cookie_state='active'
      and c.system_key<>case when v_packet.target_kind='broadcast' then v_packet.source_system_key else '' end
      and public.penta_cookie_accepts_packet_v1(
        c.system_key,v_packet.packet_type,v_packet.risk_class,v_packet.target_kind,v_packet.target_ref
      )
    order by c.system_key
    limit 250
  loop
    v_basis:=case v_packet.target_kind
      when 'system' then 'direct_system'
      when 'capability' then 'cookie_capability'
      when 'mesh_lane' then 'cookie_mesh_lane'
      else 'bounded_broadcast'
    end;

    insert into public.pentas_packet_deliveries_v1(
      packet_id,target_system_key,target_cookie_id,target_cookie_revision,resolution_basis,delivery_state
    )
    values(
      v_packet.packet_id,v_target.system_key,v_target.cookie_id,v_target.current_revision,v_basis,'pending'
    )
    on conflict(packet_id,target_system_key) do nothing;

    if found then v_count:=v_count+1; end if;
  end loop;

  if v_count=0 and not exists(select 1 from public.pentas_packet_deliveries_v1 d where d.packet_id=p_packet_id) then
    perform public.pentas_packet_transition_v1(
      p_packet_id,'held',p_actor_system_key,
      jsonb_build_object('reason','no_cookie_route','target_kind',v_packet.target_kind,'target_ref',v_packet.target_ref)
    );
    return jsonb_build_object('state','held','packet_id',p_packet_id,'reason','no_cookie_route','deliveries',0);
  end if;

  perform public.pentas_packet_transition_v1(
    p_packet_id,'routed',p_actor_system_key,
    jsonb_build_object('target_kind',v_packet.target_kind,'target_ref',v_packet.target_ref,'new_deliveries',v_count)
  );

  return jsonb_build_object(
    'state','routed',
    'packet_id',p_packet_id,
    'new_deliveries',v_count,
    'total_deliveries',(select count(*) from public.pentas_packet_deliveries_v1 d where d.packet_id=p_packet_id)
  );
end;
$$;

create or replace function public.pentas_route_pending_v1(
  p_limit integer default 50
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,50),200));
  v_packet record;
  v_routed integer:=0;
  v_held integer:=0;
  v_result jsonb;
begin
  for v_packet in
    select packet_id
    from public.pentas_packets_v1
    where packet_state='pending'
    order by priority desc,created_at
    for update skip locked
    limit v_limit
  loop
    v_result:=public.pentas_route_packet_v1(v_packet.packet_id,'penta.crawler');
    if v_result->>'state'='routed' then v_routed:=v_routed+1;
    elsif v_result->>'state'='held' then v_held:=v_held+1;
    end if;
  end loop;
  return jsonb_build_object('state','complete','routed',v_routed,'held',v_held,'limit',v_limit,'at',now());
end;
$$;

create or replace function public.pentas_claim_v1(
  p_target_system_key text,
  p_limit integer default 10
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_limit integer:=greatest(1,least(coalesce(p_limit,10),50));
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_result jsonb;
begin
  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=p_target_system_key and cookie_state='active';
  if not found then raise exception 'target_penta_cookie_not_active'; end if;

  update public.pentas_packet_deliveries_v1 d
  set delivery_state=case when d.attempt_count+1>=d.max_attempts then 'dead_letter' else 'pending' end,
      attempt_count=d.attempt_count+1,
      lease_id=null,
      lease_expires_at=null,
      last_error=concat_ws(';',nullif(d.last_error,''),'lease_expired'),
      updated_at=now()
  where d.target_system_key=p_target_system_key
    and d.delivery_state='leased'
    and d.lease_expires_at<=now();

  with candidates as (
    select d.delivery_id
    from public.pentas_packet_deliveries_v1 d
    join public.pentas_packets_v1 p on p.packet_id=d.packet_id
    where d.target_system_key=p_target_system_key
      and d.delivery_state='pending'
      and p.packet_state='routed'
      and p.expires_at>now()
      and d.attempt_count<d.max_attempts
    order by p.priority desc,d.created_at
    for update of d skip locked
    limit v_limit
  ), leased as (
    update public.pentas_packet_deliveries_v1 d
    set delivery_state='leased',
        lease_id=gen_random_uuid(),
        lease_expires_at=now()+interval '5 minutes',
        claimed_at=now(),
        updated_at=now()
    from candidates c
    where d.delivery_id=c.delivery_id
    returning d.*
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'delivery_id',l.delivery_id,
    'lease_id',l.lease_id,
    'lease_expires_at',l.lease_expires_at,
    'target_system_key',l.target_system_key,
    'target_cookie_revision',l.target_cookie_revision,
    'resolution_basis',l.resolution_basis,
    'packet',jsonb_build_object(
      'packet_id',p.packet_id,
      'protocol_id',p.protocol_id,
      'protocol_version',p.protocol_version,
      'packet_type',p.packet_type,
      'source_system_key',p.source_system_key,
      'source_cookie_revision',p.source_cookie_revision,
      'target_kind',p.target_kind,
      'target_ref',p.target_ref,
      'route_lane',p.route_lane,
      'correlation_id',p.correlation_id,
      'causation_id',p.causation_id,
      'risk_class',p.risk_class,
      'authority_class',p.authority_class,
      'priority',p.priority,
      'hop_count',p.hop_count,
      'max_hops',p.max_hops,
      'expires_at',p.expires_at,
      'payload',p.payload,
      'payload_sha256',p.payload_sha256,
      'content_address',p.content_address,
      'signature_ref',p.signature_ref,
      'signature_state',p.signature_state,
      'origin_node_ref',p.origin_node_ref,
      'network_epoch',p.network_epoch
    )
  ) order by l.created_at),'[]'::jsonb)
  into v_result
  from leased l
  join public.pentas_packets_v1 p on p.packet_id=l.packet_id;

  return coalesce(v_result,'[]'::jsonb);
end;
$$;

create or replace function public.pentas_ack_v1(
  p_delivery_id uuid,
  p_target_system_key text,
  p_lease_id uuid,
  p_outcome text,
  p_evidence jsonb default '{}'::jsonb,
  p_error text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_delivery public.pentas_packet_deliveries_v1%rowtype;
  v_remaining integer;
  v_delivered integer;
  v_held integer;
  v_dead integer;
  v_packet_state text;
begin
  if p_outcome not in ('delivered','held','dead_letter') then
    raise exception 'invalid_pentas_delivery_outcome';
  end if;

  select * into v_delivery
  from public.pentas_packet_deliveries_v1
  where delivery_id=p_delivery_id
  for update;
  if not found then raise exception 'pentas_delivery_not_found'; end if;
  if v_delivery.target_system_key<>p_target_system_key then raise exception 'pentas_delivery_target_mismatch'; end if;
  if v_delivery.delivery_state<>'leased' or v_delivery.lease_id is distinct from p_lease_id then
    raise exception 'pentas_delivery_lease_mismatch';
  end if;
  if v_delivery.lease_expires_at<=now() then raise exception 'pentas_delivery_lease_expired'; end if;

  update public.pentas_packet_deliveries_v1
  set delivery_state=p_outcome,
      lease_id=null,
      lease_expires_at=null,
      attempt_count=attempt_count+1,
      last_error=case when p_outcome='delivered' then null else left(coalesce(p_error,p_outcome),1000) end,
      delivered_at=case when p_outcome='delivered' then now() else delivered_at end,
      updated_at=now()
  where delivery_id=p_delivery_id;

  perform public.pentas_packet_receipt_v1(
    v_delivery.packet_id,p_target_system_key,'delivery_ack','leased',p_outcome,v_delivery.attempt_count+1,
    coalesce(p_evidence,'{}'::jsonb) || jsonb_build_object('delivery_id',p_delivery_id)
  );

  select
    count(*) filter(where delivery_state in ('pending','leased')),
    count(*) filter(where delivery_state='delivered'),
    count(*) filter(where delivery_state='held'),
    count(*) filter(where delivery_state='dead_letter')
  into v_remaining,v_delivered,v_held,v_dead
  from public.pentas_packet_deliveries_v1
  where packet_id=v_delivery.packet_id;

  if v_remaining=0 then
    v_packet_state:=case
      when v_held>0 then 'held'
      when v_delivered>0 then 'delivered'
      else 'dead_letter'
    end;
    perform public.pentas_packet_transition_v1(
      v_delivery.packet_id,v_packet_state,p_target_system_key,
      jsonb_build_object('deliveries_delivered',v_delivered,'deliveries_held',v_held,'deliveries_dead_letter',v_dead)
    );
  else
    v_packet_state:='routed';
  end if;

  return jsonb_build_object(
    'state',p_outcome,
    'delivery_id',p_delivery_id,
    'packet_id',v_delivery.packet_id,
    'packet_state',v_packet_state,
    'remaining',v_remaining
  );
end;
$$;

-- Extend the crawler cycle so new Pentas receive routing descriptors and pending Pentas packets
-- are fanned out according to cookie-carried capability/lane descriptors.
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
  v_mesh_route jsonb;
  v_row record;
  v_fault jsonb;
  v_faults jsonb;
  v_fault_count integer;
  v_scanned integer:=0;
  v_signals integer:=0;
  v_routes_refreshed integer:=0;
  v_risk text;
  v_priority text;
  v_severity text;
  v_route_refreshed_at timestamptz;
begin
  v_backfill:=public.penta_cookie_backfill_v1(v_limit);

  for v_row in
    select
      s.system_key,s.canonical_name,s.category,s.purpose,s.risk_ceiling,s.maturity,
      s.version,s.runtime_ref,s.last_verified_at,s.metadata,c.last_seen_at,c.observed_state
    from public.penta_system_registry s
    left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
    where s.maturity <> 'retired'
    order by coalesce(c.last_seen_at,'epoch'::timestamptz),s.system_key
    limit v_limit
  loop
    begin
      v_route_refreshed_at:=nullif(v_row.observed_state#>>'{protocol_routing,refreshed_at}','')::timestamptz;
    exception when others then
      v_route_refreshed_at:=null;
    end;
    if v_route_refreshed_at is null or v_route_refreshed_at<now()-interval '6 hours' then
      perform public.penta_cookie_refresh_routes_v1(v_row.system_key);
      v_routes_refreshed:=v_routes_refreshed+1;
    end if;

    v_faults:='[]'::jsonb;
    v_fault_count:=0;

    if v_row.maturity='production' and nullif(btrim(coalesce(v_row.runtime_ref,'')),'') is null then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object('code','runtime_missing','summary','Production Penta has no runtime_ref in the system registry'));
      v_fault_count:=v_fault_count+1;
    end if;
    if v_row.maturity='production' and (v_row.last_verified_at is null or v_row.last_verified_at<now()-interval '24 hours') then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object('code','stale_verification','summary','Production Penta verification evidence is older than 24 hours or missing'));
      v_fault_count:=v_fault_count+1;
    end if;
    if lower(coalesce(v_row.metadata->>'operational_state','')) in ('degraded','failed','error','blocked','hold')
       or lower(coalesce(v_row.metadata->>'continuous_healing_state','')) in ('degraded','failed','error','blocked','hold')
       or lower(coalesce(v_row.metadata->>'last_self_cycle_state','')) in ('degraded','failed','error','blocked','hold') then
      v_faults:=v_faults || jsonb_build_array(jsonb_build_object('code','declared_degraded','summary','Penta registry metadata declares a degraded/failed/blocked operational state'));
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
      for v_fault in select value from jsonb_array_elements(v_faults)
      loop
        v_severity:=case when v_fault->>'code' in ('runtime_missing','declared_degraded') then 'ERROR' else 'WARN' end;
        v_priority:=case when v_severity='ERROR' then 'P1' else 'P2' end;
        v_risk:=case when v_severity='ERROR' then 'D2' else 'D1' end;
        perform public.penta_crawler_flag_broken_v1(
          v_row.system_key,v_fault->>'code',v_severity,v_priority,v_fault->>'summary',v_risk,
          jsonb_build_object(
            'canonical_name',v_row.canonical_name,'category',v_row.category,'maturity',v_row.maturity,
            'version',v_row.version,'runtime_ref',v_row.runtime_ref,'last_verified_at',v_row.last_verified_at,
            'source','penta_system_registry'
          )
        );
        v_signals:=v_signals+1;
      end loop;
    end if;
  end loop;

  v_ingest:=public.penta_discovery_ingest_packets_v1(least(v_limit,100));
  v_route:=public.penta_discovery_route_v1(least(v_limit,50));
  v_mesh_route:=public.pentas_route_pending_v1(least(v_limit,200));

  return jsonb_build_object(
    'service','ct.penta.crawler.systemwide.v3',
    'state','complete',
    'cookie_backfill',v_backfill,
    'routing_descriptors_refreshed',v_routes_refreshed,
    'scanned',v_scanned,
    'signals_raised',v_signals,
    'packet_ingest',v_ingest,
    'discovery_route',v_route,
    'mesh_route',v_mesh_route,
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
    'cookies_with_routing',(select count(*) from public.penta_protocol_cookies_v1 where jsonb_typeof(observed_state->'protocol_routing')='object' or jsonb_typeof(oracle_state->'routing')='object'),
    'packets_pending',(select count(*) from public.pentas_packets_v1 where packet_state='pending' and expires_at>now()),
    'packets_routed',(select count(*) from public.pentas_packets_v1 where packet_state='routed'),
    'packets_held',(select count(*) from public.pentas_packets_v1 where packet_state='held'),
    'deliveries_pending',(select count(*) from public.pentas_packet_deliveries_v1 where delivery_state='pending'),
    'deliveries_leased',(select count(*) from public.pentas_packet_deliveries_v1 where delivery_state='leased'),
    'discovery_open',(select count(*) from public.penta_discovery_cases_v1 where state<>'resolved'),
    'discovery_held',(select count(*) from public.penta_discovery_cases_v1 where state='held'),
    'cookie_mutations',(select count(*) from public.penta_protocol_cookie_mutations_v1),
    'authority_created',false,
    'd3_human_reserved',true,
    'at',now()
  );
$$;

revoke all on function public.pentas_delivery_no_delete_v1() from public, anon, authenticated;
revoke all on function public.penta_protocol_risk_rank_v1(text) from public, anon, authenticated;
revoke all on function public.penta_cookie_refresh_routes_v1(text) from public, anon, authenticated;
revoke all on function public.penta_cookie_accepts_packet_v1(text,text,text,text,text) from public, anon, authenticated;
revoke all on function public.pentas_route_packet_v1(uuid,text) from public, anon, authenticated;
revoke all on function public.pentas_route_pending_v1(integer) from public, anon, authenticated;
revoke all on function public.pentas_claim_v1(text,integer) from public, anon, authenticated;
revoke all on function public.pentas_ack_v1(uuid,text,uuid,text,jsonb,text) from public, anon, authenticated;
revoke all on function public.penta_crawler_roam_v1(integer) from public, anon, authenticated;
revoke all on function public.penta_crawler_status_v3() from public, anon, authenticated;

grant execute on function public.penta_protocol_risk_rank_v1(text) to service_role;
grant execute on function public.penta_cookie_refresh_routes_v1(text) to service_role;
grant execute on function public.penta_cookie_accepts_packet_v1(text,text,text,text,text) to service_role;
grant execute on function public.pentas_route_packet_v1(uuid,text) to service_role;
grant execute on function public.pentas_route_pending_v1(integer) to service_role;
grant execute on function public.pentas_claim_v1(text,integer) to service_role;
grant execute on function public.pentas_ack_v1(uuid,text,uuid,text,jsonb,text) to service_role;
grant execute on function public.penta_crawler_roam_v1(integer) to service_role;
grant execute on function public.penta_crawler_status_v3() to service_role;
