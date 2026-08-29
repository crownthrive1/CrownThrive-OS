-- Harden PentaDiscovery ingestion against malformed-but-envelope-valid discovery packet payloads.
-- This supersedes only the function body from 20260829032500_penta_crawler_mesh_protocol_v3.sql.

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
  v_signal_kind text;
  v_severity text;
  v_summary text;
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
      nullif(btrim(coalesce(v_packet.payload->>'case_key','')),''),
      'packet-discovery:'||v_packet.packet_id::text
    );

    v_signal_kind:=lower(coalesce(nullif(btrim(v_packet.payload->>'signal_kind'),''),'discovery_requested'));
    if v_signal_kind not in (
      'broken','blocked','stale','degraded','missing_dependency','missing_credential',
      'missing_software','unknown_system','help_requested','discovery_requested'
    ) then
      v_signal_kind:='discovery_requested';
    end if;

    v_severity:=upper(coalesce(nullif(btrim(v_packet.payload->>'severity'),''),'WARN'));
    if v_severity not in ('INFO','WARN','ERROR','CRITICAL') then
      v_severity:='WARN';
    end if;

    v_summary:=left(
      coalesce(nullif(btrim(v_packet.payload->>'summary'),''),'Penta requested discovery assistance'),
      4000
    );

    insert into public.penta_discovery_cases_v1(
      case_key,source_system_key,source_packet_id,signal_kind,severity,risk_class,summary,evidence,state
    )
    values(
      v_case_key,
      v_packet.source_system_key,
      v_packet.packet_id,
      v_signal_kind,
      v_severity,
      v_packet.risk_class,
      v_summary,
      case when jsonb_typeof(v_packet.payload->'evidence')='object'
           then v_packet.payload->'evidence'
           else '{}'::jsonb end,
      'raised'
    )
    on conflict(case_key) do nothing;

    if found then
      v_inserted:=v_inserted+1;
    end if;

    perform public.pentas_packet_transition_v1(
      v_packet.packet_id,'routed','penta.discovery',
      jsonb_build_object(
        'case_key',v_case_key,
        'normalized_signal_kind',v_signal_kind,
        'normalized_severity',v_severity
      )
    );
  end loop;

  return jsonb_build_object(
    'state','complete',
    'ingested',v_inserted,
    'limit',v_limit,
    'malformed_payloads_fail_batch',false,
    'at',now()
  );
end;
$$;

revoke all on function public.penta_discovery_ingest_packets_v1(integer) from public, anon, authenticated;
grant execute on function public.penta_discovery_ingest_packets_v1(integer) to service_role;
