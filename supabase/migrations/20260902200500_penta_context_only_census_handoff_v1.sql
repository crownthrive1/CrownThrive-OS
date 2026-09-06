-- CrownThrive PentaCensus -> PentaContext context-only handoff repair v1
--
-- Problem: penta_census_target_for_tag_v1 intentionally falls back to penta.context
-- for non-execution tags so PentaContext can retain the discovery. The production
-- mobilizer treated every target as an executable Pentas node, even though
-- PentaContext is a production context runtime with pm_execution_eligible=false
-- and no Pentas packet-execution node. That converted already-completed context
-- ingestion into target_node_unavailable failures.
--
-- Repair: when target_ref=penta.context, require the canonical idempotent
-- PentaContext ingest job to be COMPLETED with a context_id, then close the handoff
-- as context-only evidence. Never emit an execution packet and never create
-- execution/provider/certification/D3 authority.

create or replace function integration_control.penta_census_mobilize_safe_handoffs_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','pentas','extensions','chlom_runtime','public'
as $function$
declare
  h record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_target text;
  v_packet jsonb;
  v_packet_id uuid;
  v_emitted integer:=0;
  v_failed integer:=0;
  v_context_only integer:=0;
  v_route jsonb;
  v_sha text;
  v_evidence jsonb;
  v_context record;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:census-mobilization',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','emitted',0,'context_only_verified',0);
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
    -- PentaContext fallback is a context/evidence handoff, not an executable
    -- production packet route. Require its actual queue/readback before closing.
    if h.target_ref='penta.context' then
      select q.job_id,q.context_id,q.status,q.fingerprint_sha256,q.completed_at
      into v_context
      from public.penta_context_ingest_queue_v1 q
      where q.idempotency_key='penta-census-handoff:'||h.discovery_key||':'||h.tag
      order by q.updated_at desc
      limit 1;

      if v_context.job_id is null
         or v_context.status<>'completed'
         or v_context.context_id is null then
        v_failed:=v_failed+1;
        v_evidence:=jsonb_build_object(
          'reason','context_queue_not_completed',
          'target_ref',h.target_ref,
          'execution_effect',false,
          'packet_created',false,
          'authority_created',false
        );
        v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

        insert into integration_control.penta_production_mobilization_v1(
          handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,
          target_node_id,state,evidence_sha256,evidence,updated_at
        ) values (
          h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,
          'context://penta.context','failed',v_sha,v_evidence,now()
        )
        on conflict(handoff_key) do update set
          target_node_id=excluded.target_node_id,
          packet_id=null,
          state='failed',
          evidence_sha256=excluded.evidence_sha256,
          evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,
          updated_at=now();

        update integration_control.penta_census_handoffs_v1
        set state='failed',payload=payload||v_evidence,updated_at=now()
        where handoff_key=h.handoff_key;
        continue;
      end if;

      v_evidence:=jsonb_build_object(
        'state','CONTEXT_ONLY_VERIFIED',
        'target_ref',h.target_ref,
        'context_job_id',v_context.job_id,
        'context_id',v_context.context_id,
        'context_fingerprint_sha256',v_context.fingerprint_sha256,
        'context_completed_at',v_context.completed_at,
        'execution_effect',false,
        'packet_created',false,
        'authority_created',false
      );
      v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

      insert into integration_control.penta_production_mobilization_v1(
        handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,
        target_node_id,packet_id,state,evidence_sha256,evidence,completed_at,updated_at
      ) values (
        h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,
        'context://penta.context',null,'verified',v_sha,v_evidence,now(),now()
      )
      on conflict(handoff_key) do update set
        target_node_id=excluded.target_node_id,
        packet_id=null,
        state='verified',
        evidence_sha256=excluded.evidence_sha256,
        evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,
        completed_at=coalesce(integration_control.penta_production_mobilization_v1.completed_at,now()),
        updated_at=now();

      update integration_control.penta_census_handoffs_v1
      set state='completed',
          payload=payload||v_evidence,
          completed_at=coalesce(completed_at,now()),
          updated_at=now()
      where handoff_key=h.handoff_key;

      v_context_only:=v_context_only+1;
      continue;
    end if;

    v_target:=case h.target_ref
      when 'penta.build' then 'ct.penta.factory.software'
      when 'penta.certify' then 'ct.penta.certify'
      when 'ct.agent.penta-wire' then 'ct.penta.wire'
      when 'penta.release' then 'ct.penta.release'
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
        handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,
        target_node_id,state,evidence_sha256,evidence,updated_at
      ) values (
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
          select 1 from integration_control.penta_production_presence_v1 p
          where p.subject_key=h.entity_key
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
      handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,
      target_node_id,packet_id,state,evidence_sha256,evidence,updated_at
    ) values (
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
    'context_only_verified',v_context_only,
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
'PentaCensus bounded production mobilizer. penta.context is context-only: it requires completed PentaContext ingest readback, emits no Pentas execution packet, creates no authority, and records verified context custody. Other executable targets retain existing exact-node routing.';
