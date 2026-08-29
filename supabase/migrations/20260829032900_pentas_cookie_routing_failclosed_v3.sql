-- Final fail-closed corrections for PentaCookie capability routing.
-- This migration is intentionally applied after 20260829032800 so the deployed final state
-- cannot treat malformed risk metadata as privileged and cannot mask partial fan-out failure.

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
    else -1
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
  v_declared_max_risk text;
  v_declared_rank integer;
  v_cookie_rank integer;
  v_packet_rank integer;
  v_effective_rank integer;
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

  v_declared_max_risk:=coalesce(
    nullif(v_oracle_routing->>'max_packet_risk',''),
    nullif(v_observed_routing->>'max_packet_risk',''),
    v_cookie.authority_ceiling
  );
  v_declared_rank:=public.penta_protocol_risk_rank_v1(v_declared_max_risk);
  v_cookie_rank:=public.penta_protocol_risk_rank_v1(v_cookie.authority_ceiling);
  v_packet_rank:=public.penta_protocol_risk_rank_v1(p_risk_class);

  if v_declared_rank<0 or v_cookie_rank<0 or v_packet_rank<0 then return false; end if;
  v_effective_rank:=least(v_declared_rank,v_cookie_rank);
  if v_effective_rank<v_packet_rank then return false; end if;

  v_accepts:=case
    when jsonb_typeof(v_oracle_routing->'accepts_packet_types')='array'
      then v_oracle_routing->'accepts_packet_types'
    when jsonb_typeof(v_observed_routing->'accepts_packet_types')='array'
      then v_observed_routing->'accepts_packet_types'
    else '[]'::jsonb end;
  if jsonb_array_length(v_accepts)>0 and not (v_accepts ? p_packet_type) then return false; end if;

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
    v_match:=p_target_ref='all-pentas' and v_packet_rank between 0 and 1;
  end if;

  return coalesce(v_match,false);
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
  if p_outcome not in ('delivered','held','dead_letter') then raise exception 'invalid_pentas_delivery_outcome'; end if;

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
      when v_dead>0 and v_delivered>0 then 'held'
      when v_delivered>0 and v_dead=0 then 'delivered'
      when v_dead>0 then 'dead_letter'
      else 'held'
    end;
    perform public.pentas_packet_transition_v1(
      v_delivery.packet_id,v_packet_state,p_target_system_key,
      jsonb_build_object(
        'deliveries_delivered',v_delivered,
        'deliveries_held',v_held,
        'deliveries_dead_letter',v_dead,
        'partial_failure_masked',false
      )
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

revoke all on function public.penta_protocol_risk_rank_v1(text) from public, anon, authenticated;
revoke all on function public.penta_cookie_accepts_packet_v1(text,text,text,text,text) from public, anon, authenticated;
revoke all on function public.pentas_ack_v1(uuid,text,uuid,text,jsonb,text) from public, anon, authenticated;

grant execute on function public.penta_protocol_risk_rank_v1(text) to service_role;
grant execute on function public.penta_cookie_accepts_packet_v1(text,text,text,text,text) to service_role;
grant execute on function public.pentas_ack_v1(uuid,text,uuid,text,jsonb,text) to service_role;
