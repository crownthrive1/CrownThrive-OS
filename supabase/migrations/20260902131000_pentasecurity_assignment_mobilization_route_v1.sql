-- PentaSecurity assignment mobilization route repair v1
-- Scope: register the already-production PentaSecurity runtime as a Pentas v2 node
-- and teach the existing census mobilizer to resolve the canonical penta.security route.
-- This does not create new D3, money, credential, rights, vote/quorum, or provider-write authority.

insert into pentas.nodes_v2 (
  node_id,
  display_name,
  node_class,
  authority_ceiling,
  capabilities,
  topics,
  endpoint_kind,
  endpoint_ref,
  health_state,
  lifecycle_state,
  metadata,
  last_heartbeat_at,
  updated_at
)
select
  'ct.penta.security',
  i.canonical_name,
  'penta',
  'D2',
  array['security.review','security.provider-source-review','security.runtime-review','evidence.attest']::text[],
  array['security','identity','trust','evidence']::text[],
  'internal_sql',
  'penta_security.review_system_v1',
  case when i.activation_state='ACTIVE' and i.runtime_state='RUNTIME_PRESENT' then 'healthy' else 'degraded' end,
  'active',
  jsonb_build_object(
    'role','bounded security review and evidence coordination',
    'identity_key',i.identity_key,
    'source_maturity',i.maturity,
    'production_receipt_id',i.metadata->>'production_receipt_id',
    'independent_certification_id',i.metadata->>'independent_certification_id',
    'source_ref','ct.penta.security.assignment-mobilization-route.v1',
    'authority_created',false,
    'd3_human_reserved',true
  ),
  clock_timestamp(),
  clock_timestamp()
from integration_control.penta_identity_registry_v1 i
where i.identity_key='penta.security'
  and i.current=true
  and i.active=true
  and i.maturity='production'
  and i.activation_state='ACTIVE'
  and i.runtime_state='RUNTIME_PRESENT'
order by i.updated_at desc
limit 1
on conflict (node_id) do update set
  display_name=excluded.display_name,
  node_class=excluded.node_class,
  authority_ceiling=excluded.authority_ceiling,
  capabilities=excluded.capabilities,
  topics=excluded.topics,
  endpoint_kind=excluded.endpoint_kind,
  endpoint_ref=excluded.endpoint_ref,
  health_state=excluded.health_state,
  lifecycle_state=excluded.lifecycle_state,
  metadata=pentas.nodes_v2.metadata || excluded.metadata,
  last_heartbeat_at=excluded.last_heartbeat_at,
  updated_at=excluded.updated_at;

create or replace function integration_control.penta_census_mobilize_safe_handoffs_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'integration_control', 'pentas', 'extensions', 'chlom_runtime'
as $function$
declare
  h record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_target text;
  v_packet jsonb;
  v_packet_id uuid;
  v_emitted integer:=0;
  v_failed integer:=0;
  v_route jsonb;
  v_sha text;
  v_evidence jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:census-mobilization',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','emitted',0);
  end if;

  for h in
    select x.*,d.entity_kind,d.entity_key,d.canonical_name,d.rationale
    from integration_control.penta_census_handoffs_v1 x
    join integration_control.penta_census_discoveries_v1 d on d.discovery_key=x.discovery_key
    where x.state='queued'
      and x.risk_class in ('D0','D1','D2')
      and not exists(
        select 1
        from integration_control.penta_production_mobilization_v1 m
        where m.handoff_key=x.handoff_key
          and m.state not in ('failed','superseded')
      )
    order by case x.risk_class when 'D0' then 0 when 'D1' then 1 else 2 end,x.created_at
    limit v_limit
    for update of x skip locked
  loop
    v_target:=case h.target_ref
      when 'penta.build' then 'ct.penta.factory.software'
      when 'penta.certify' then 'ct.penta.certify'
      when 'ct.agent.penta-wire' then 'ct.penta.wire'
      when 'penta.release' then 'ct.penta.release'
      when 'penta.security' then 'ct.penta.security'
      else null
    end;

    if v_target is null
       or not exists(
         select 1
         from pentas.nodes_v2 n
         where n.node_id=v_target
           and n.lifecycle_state='active'
           and n.health_state in ('healthy','degraded')
       ) then
      v_failed:=v_failed+1;
      v_evidence:=jsonb_build_object(
        'reason','target_node_unavailable',
        'target_ref',h.target_ref,
        'mapped_target_node_id',v_target,
        'authority_created',false
      );
      v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
      insert into integration_control.penta_production_mobilization_v1(
        handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,
        state,evidence_sha256,evidence,updated_at
      ) values(
        h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,
        coalesce(v_target,'unresolved://target'),'failed',v_sha,v_evidence,now()
      )
      on conflict(handoff_key) do update set
        state='failed',
        evidence_sha256=excluded.evidence_sha256,
        evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,
        updated_at=now();
      update integration_control.penta_census_handoffs_v1
      set state='failed',payload=payload||v_evidence,updated_at=now()
      where handoff_key=h.handoff_key;
      continue;
    end if;

    v_packet:=pentas.emit_v2(
      'institutional.production-reconciliation.request',
      'ct.penta.census',
      'direct',
      v_target,
      'penta.production.reconciliation',
      'penta-census-handoff:'||h.handoff_key,
      jsonb_build_object(
        'handoff_key',h.handoff_key,
        'discovery_key',h.discovery_key,
        'entity_kind',h.entity_kind,
        'entity_key',h.entity_key,
        'canonical_name',h.canonical_name,
        'tag',h.tag,
        'risk_class',h.risk_class,
        'target_ref',h.target_ref,
        'production_presence',exists(
          select 1 from integration_control.penta_production_presence_v1 p where p.subject_key=h.entity_key
        ),
        'government_assignment',exists(
          select 1 from integration_control.penta_government_assignments_v1 g
          where g.entity_kind=h.entity_kind and g.entity_key=h.entity_key and g.state='active'
        ),
        'requested_outcome',case h.tag
          when 'needs-build' then 'exact_build_candidate_and_tests'
          when 'needs-contract' then 'complete_contract_and_assurance'
          when 'needs-production' then 'exact_release_and_provider_readback'
          when 'needs-registration' then 'canonical_registry_binding'
          when 'needs-upgrade' then 'newer_generation_candidate'
          when 'needs-wiring' then 'exact_adapter_and_route_binding'
          else 'reconciliation'
        end,
        'guardrails',jsonb_build_object(
          'source_maturity_preserved',true,
          'D3_human_reserved',true,
          'money_movement',false,
          'authority_manufacture',false,
          'provider_write_requires_exact_existing_authority',true
        )
      ),
      h.risk_class,
      h.risk_class,
      case h.risk_class when 'D0' then 10 when 'D1' then 20 else 30 end,
      86400,
      null,
      'penta-census-handoff:'||h.handoff_key,
      jsonb_build_object(
        'campaign_key','ct.campaign.all-pentas-production-government.v1',
        'source','PentaCensus',
        'classification_only',false,
        'authority_created',false
      )
    );
    v_packet_id:=nullif(v_packet->>'packet_id','')::uuid;
    v_evidence:=jsonb_build_object(
      'packet_id',v_packet_id,
      'target_node_id',v_target,
      'emission',v_packet,
      'campaign_key','ct.campaign.all-pentas-production-government.v1',
      'authority_created',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
    insert into integration_control.penta_production_mobilization_v1(
      handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,
      packet_id,state,evidence_sha256,evidence,updated_at
    ) values(
      h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,
      v_target,v_packet_id,'emitted',v_sha,v_evidence,now()
    )
    on conflict(handoff_key) do update set
      target_node_id=excluded.target_node_id,
      packet_id=excluded.packet_id,
      state='emitted',
      evidence_sha256=excluded.evidence_sha256,
      evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,
      updated_at=now();
    update integration_control.penta_census_handoffs_v1
    set state='acknowledged',
        payload=payload||jsonb_build_object(
          'production_mobilization_packet_id',v_packet_id,
          'target_node_id',v_target,
          'campaign_key','ct.campaign.all-pentas-production-government.v1',
          'acknowledged_at',clock_timestamp()
        ),
        updated_at=now()
    where handoff_key=h.handoff_key;
    v_emitted:=v_emitted+1;
  end loop;

  v_route:=pentas.route_tick_v2(greatest(100,v_limit*2));
  perform integration_control.penta_census_mobilization_reconcile_v1(greatest(250,v_limit*2));

  return jsonb_build_object(
    'state',case when v_failed>0 then 'DEGRADED' else 'COMPLETE' end,
    'emitted',v_emitted,
    'failed',v_failed,
    'route',v_route,
    'remaining_queued',(
      select count(*) from integration_control.penta_census_handoffs_v1
      where state='queued' and risk_class in ('D0','D1','D2')
    ),
    'D3_approval_required',(
      select count(*) from integration_control.penta_census_handoffs_v1
      where state='approval_required' and risk_class='D3'
    ),
    'authority_created',false,
    'observed_at',clock_timestamp()
  );
end
$function$;

comment on function integration_control.penta_census_mobilize_safe_handoffs_v1(integer) is
'PentaCensus D0-D2 mobilizer. v1 repair adds canonical penta.security -> ct.penta.security resolution without expanding authority.';

do $do$
begin
  if not exists (
    select 1 from pentas.nodes_v2
    where node_id='ct.penta.security'
      and lifecycle_state='active'
      and health_state in ('healthy','degraded')
      and authority_ceiling='D2'
      and endpoint_ref='penta_security.review_system_v1'
  ) then
    raise exception 'PENTASECURITY_NODE_REGISTRATION_READBACK_FAILED';
  end if;

  if position(
    $needle$when 'penta.security' then 'ct.penta.security'$needle$
    in pg_get_functiondef('integration_control.penta_census_mobilize_safe_handoffs_v1(integer)'::regprocedure)
  ) = 0 then
    raise exception 'PENTASECURITY_MOBILIZER_ROUTE_READBACK_FAILED';
  end if;
end
$do$;