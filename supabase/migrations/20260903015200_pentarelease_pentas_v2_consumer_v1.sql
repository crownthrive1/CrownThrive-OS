-- PentaRelease Pentas-v2 target consumer v1
-- Bounded target-authored reconciliation only. No release approval, certification,
-- provider write, money movement, rights grant, credential mutation, quorum/vote,
-- or D3 authority is created by this consumer.

begin;

create or replace function public.penta_release_packet_consumer_v1(
  p_limit integer default 10,
  p_packet_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','pentas','integration_control'
as $function$
declare
  d record;
  v_verify jsonb;
  v_delivered jsonb;
  v_ack jsonb;
  v_results jsonb := '[]'::jsonb;
  v_processed integer := 0;
  v_completed integer := 0;
  v_held integer := 0;
  v_reason text;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;

  for d in
    select del.delivery_id, del.packet_id, del.target_node_id,
           p.packet_type, p.protocol_version, p.authority_class,
           p.payload, p.metadata, p.expires_at, p.delivery_state
    from pentas.deliveries_v2 del
    join pentas.packets_v2 p on p.packet_id = del.packet_id
    where del.state = 'routed'
      and p.delivery_state = 'routed'
      and del.target_node_id = 'ct.penta.release'
      and p.target_ref = 'ct.penta.release'
      and p.packet_type = 'institutional.production-reconciliation.request'
      and (p_packet_id is null or p.packet_id = p_packet_id)
    order by p.priority, p.issued_at
    limit greatest(1, least(coalesce(p_limit,10),50))
    for update of del skip locked
  loop
    v_processed := v_processed + 1;
    v_reason := null;
    v_verify := pentas.verify_packet_v2(d.packet_id);

    if not coalesce((v_verify->>'ok')::boolean,false) then
      v_reason := 'packet_verification_failed';
    elsif coalesce((v_verify->>'expired')::boolean,true) then
      v_reason := 'packet_expired';
    elsif d.authority_class not in ('D0','D1','D2') then
      v_reason := 'authority_ceiling_exceeded';
    elsif coalesce(d.payload->>'requested_outcome','') <> 'reconciliation' then
      v_reason := 'unsupported_requested_outcome';
    elsif coalesce((d.payload->'guardrails'->>'money_movement')::boolean,true) then
      v_reason := 'money_movement_not_allowed';
    elsif coalesce((d.payload->'guardrails'->>'authority_manufacture')::boolean,true) then
      v_reason := 'authority_manufacture_not_allowed';
    elsif coalesce((d.payload->'guardrails'->>'D3_human_reserved')::boolean,false) is not true then
      v_reason := 'd3_reservation_not_proven';
    end if;

    if v_reason is not null then
      v_ack := pentas.ack_v2(
        d.packet_id,
        'ct.penta.release',
        'hold',
        jsonb_build_object(
          'consumer_key','ct.penta.release.pentas-v2-consumer.v1',
          'reason',v_reason,
          'packet_verify',v_verify,
          'release_approval',false,
          'certification',false,
          'provider_write',false,
          'authority_created',false,
          'observed_at',clock_timestamp()
        ),
        true
      );
      v_held := v_held + 1;
      v_results := v_results || jsonb_build_array(jsonb_build_object(
        'packet_id',d.packet_id,'state','held','reason',v_reason,'ack',v_ack));
      continue;
    end if;

    update pentas.deliveries_v2
    set state='delivered',
        delivered_at=coalesce(delivered_at,clock_timestamp()),
        attempt_count=attempt_count+1,
        evidence=evidence || jsonb_build_object(
          'consumer_key','ct.penta.release.pentas-v2-consumer.v1',
          'target_authored',true,
          'reconciliation_only',true,
          'release_approval',false,
          'authority_created',false,
          'delivered_at',clock_timestamp()
        )
    where delivery_id=d.delivery_id;

    v_delivered := pentas.append_receipt_v2(
      d.packet_id,
      d.delivery_id,
      'ct.penta.release',
      'delivered',
      'accept',
      jsonb_build_object(
        'consumer_key','ct.penta.release.pentas-v2-consumer.v1',
        'requested_outcome','reconciliation',
        'target_authored',true,
        'release_approval',false,
        'certification',false,
        'provider_write',false,
        'authority_created',false,
        'packet_verify',v_verify
      )
    );

    v_ack := pentas.ack_v2(
      d.packet_id,
      'ct.penta.release',
      'complete',
      jsonb_build_object(
        'consumer_key','ct.penta.release.pentas-v2-consumer.v1',
        'outcome','reconciliation_accepted',
        'target_authored',true,
        'release_approval',false,
        'certification',false,
        'provider_write',false,
        'authority_created',false,
        'delivered_receipt',v_delivered,
        'completed_at',clock_timestamp()
      ),
      true
    );

    update pentas.nodes_v2
    set last_heartbeat_at=clock_timestamp(), updated_at=clock_timestamp()
    where node_id='ct.penta.release';

    v_completed := v_completed + 1;
    v_results := v_results || jsonb_build_array(jsonb_build_object(
      'packet_id',d.packet_id,
      'delivery_id',d.delivery_id,
      'state','completed',
      'verify',v_verify,
      'delivered_receipt',v_delivered,
      'ack',v_ack
    ));
  end loop;

  return jsonb_build_object(
    'ok',v_held=0,
    'consumer_key','ct.penta.release.pentas-v2-consumer.v1',
    'processed',v_processed,
    'completed',v_completed,
    'held',v_held,
    'release_approval',false,
    'certification',false,
    'provider_write',false,
    'authority_created',false,
    'results',v_results,
    'observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function public.penta_release_packet_consumer_v1(integer,uuid) from public;
grant execute on function public.penta_release_packet_consumer_v1(integer,uuid) to service_role;

-- Reuse the canonical Pentas-v2 route scheduler rather than creating a duplicate
-- scheduler/runtime. The route pass remains first; PentaRelease then consumes only
-- its own already-routed bounded reconciliation packets.
do $scheduler$
declare
  v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-pentas-route-v2' and active limit 1;
  if v_jobid is null then
    raise exception 'canonical ct-pentas-route-v2 scheduler missing or inactive';
  end if;
  perform cron.alter_job(
    v_jobid,
    command := 'select pentas.route_tick_v2(100); select public.penta_release_packet_consumer_v1(25,null);'
  );
end
$scheduler$;

commit;

-- Recovery posture: preserve this migration and receipts. If a material regression
-- is proven, use a forward migration to remove the consumer invocation from the
-- canonical scheduler and leave the function/evidence available for provenance.
