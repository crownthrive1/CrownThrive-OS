-- CrownThrive CHLOM Security Fabric
-- Bounded PR restack execution adapter for ct.penta.pr-terminalization-policy.v2.
-- This migration creates no merge/close/certification/D3 authority. It only prepares
-- a collision-safe draft successor through the existing PentaPM GitHub provider.

create or replace function penta_pm.assignment_restack_prepare_v1(p_assignment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_pm, integration_control, extensions
as $function$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_expected_main_sha text;
  v_branch text;
  v_payload jsonb;
  v_outbox penta_pm.provider_outbox%rowtype;
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
begin
  if session_user not in ('postgres','supabase_admin') and current_user not in ('postgres','service_role') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:pm:assignment-restack:'||p_assignment_id::text,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id
  for update;

  if not found then
    return jsonb_build_object('state','HOLD','reason','assignment_not_found','assignment_id',p_assignment_id,'authority_created',false);
  end if;
  if a.state in ('COMPLETED','SUPERSEDED','RETIRED') then
    return jsonb_build_object('state','NOOP_TERMINAL_ASSIGNMENT','assignment_id',a.assignment_id,'assignment_state',a.state,'authority_created',false);
  end if;
  if a.task_kind <> 'PR_RESTACK_CURRENT_MAIN' then
    return jsonb_build_object('state','HOLD','reason','task_kind_not_restack','task_kind',a.task_kind,'authority_created',false);
  end if;
  if a.authority_ceiling not in ('D0','D1','D2') or a.risk_class not in ('D0','D1','D2') then
    return jsonb_build_object('state','HOLD','reason','authority_or_risk_out_of_bounds','authority_ceiling',a.authority_ceiling,'risk_class',a.risk_class,'authority_created',false);
  end if;
  if a.source_repo is distinct from 'crownthrive1/CrownThrive-OS' or a.source_pr_number is null or a.exact_head_sha !~ '^[0-9a-f]{40}$' then
    return jsonb_build_object('state','HOLD','reason','exact_predecessor_identity_invalid','source_repo',a.source_repo,'source_pr_number',a.source_pr_number,'authority_created',false);
  end if;
  if not (a.owner_pentas @> '["PentaMerge","PentaPR","PentaPM"]'::jsonb) then
    return jsonb_build_object('state','HOLD','reason','required_native_owners_missing','owner_pentas',a.owner_pentas,'authority_created',false);
  end if;

  v_expected_main_sha := substring(coalesce(a.exact_artifact_ref,'') from 'main@([0-9a-f]{40})');
  if v_expected_main_sha is null then
    return jsonb_build_object('state','HOLD','reason','expected_main_sha_missing','exact_artifact_ref',a.exact_artifact_ref,'authority_created',false);
  end if;

  v_branch := format('penta/restack-pr%s-%s-v1',a.source_pr_number,left(v_expected_main_sha,8));
  v_payload := jsonb_build_object(
    'contract','ct.penta.pr-terminalization-policy.v2',
    'assignment_contract','ct.penta.assignment-fulfillment.v1',
    'assignment_id',a.assignment_id,
    'assignment_key',a.assignment_key,
    'task_kind',a.task_kind,
    'repository',a.source_repo,
    'predecessor_pr',a.source_pr_number,
    'expected_predecessor_head_sha',a.exact_head_sha,
    'expected_main_sha',v_expected_main_sha,
    'successor_branch',v_branch,
    'successor_title',format('chore(cos): restack PR #%s on current main',a.source_pr_number),
    'successor_body',format('Canonical current-main successor for predecessor #%s.\n\nPredecessor head: `%s`\nExpected protected main: `%s`\nAssignment: `%s`\n\nThis draft preserves predecessor history and inherits no review, provider PASS, certification, release authority, or merge authority. It remains fail-closed until the current exact head passes the applicable PentaSecurity -> CHLOM -> CIE (where applicable) -> independent PentaCertifier chain and provider gates. Predecessor closure is separate and forbidden until successor/provider readback is durably recorded.',a.source_pr_number,a.exact_head_sha,v_expected_main_sha,a.assignment_id),
    'acceptance_criteria',a.acceptance_criteria,
    'required_projections',to_jsonb(a.required_projections),
    'draft',true,
    'expected_head_cas',true,
    'collision_policy','FAIL_CLOSED_ON_PATH_DRIFT',
    'exactly_one_successor',true,
    'preserve_predecessor_branch',true,
    'close_predecessor',false,
    'merge_successor',false,
    'inherit_reviews',false,
    'inherit_certificates',false,
    'credential_change',false,
    'money_movement',false,
    'authority_created',false
  );

  v_outbox := penta_pm.queue_provider_write_v1(
    'pr_restack_prepare',
    v_payload,
    null,
    'assignment-restack:'||a.assignment_id::text
  );

  update integration_control.penta_assignment_contracts_v1
  set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'restack_provider_operation','pr_restack_prepare',
        'restack_provider_outbox_id',v_outbox.id,
        'restack_expected_main_sha',v_expected_main_sha,
        'restack_successor_branch',v_branch,
        'restack_queued_at',clock_timestamp(),
        'authority_created',false
      ),
      updated_at=clock_timestamp()
  where assignment_id=a.assignment_id;

  return jsonb_build_object(
    'state',case when v_outbox.status='succeeded' then 'PROVIDER_ALREADY_SUCCEEDED' else 'QUEUED_PROVIDER_RESTACK' end,
    'assignment_id',a.assignment_id,
    'outbox_id',v_outbox.id,
    'outbox_status',v_outbox.status,
    'expected_main_sha',v_expected_main_sha,
    'successor_branch',v_branch,
    'authority_created',false
  );
end
$function$;

revoke all on function penta_pm.assignment_restack_prepare_v1(uuid) from public;
grant execute on function penta_pm.assignment_restack_prepare_v1(uuid) to service_role;

create or replace function penta_pm.assignment_restack_readback_v1(p_assignment_id uuid, p_apply boolean default true)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_pm, penta_runtime, integration_control, chlom_runtime, extensions
as $function$
declare
  a integration_control.penta_assignment_contracts_v1%rowtype;
  q penta_pm.provider_outbox%rowtype;
  r penta_runtime.penta_pm_github_provider_receipts%rowtype;
  v_result jsonb;
  v_pr integer;
  v_head text;
  v_base text;
  v_event jsonb;
  v_already_applied boolean:=false;
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
begin
  if session_user not in ('postgres','supabase_admin') and current_user not in ('postgres','service_role') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then return jsonb_build_object('state','HOLD','reason','assignment_not_found','assignment_id',p_assignment_id); end if;

  select * into q
  from penta_pm.provider_outbox
  where dedupe_key='assignment-restack:'||p_assignment_id::text
  order by created_at desc
  limit 1;
  if not found then return jsonb_build_object('state','HOLD','reason','provider_outbox_missing','assignment_id',p_assignment_id); end if;

  select * into r
  from penta_runtime.penta_pm_github_provider_receipts
  where run_id=q.id and operation='pr_restack_prepare'
  order by created_at desc
  limit 1;

  if not found then
    return jsonb_build_object('state','AWAITING_PROVIDER_RECEIPT','assignment_id',a.assignment_id,'outbox_id',q.id,'outbox_status',q.status,'attempts',q.attempts,'authority_created',false);
  end if;
  if r.status <> 'PASS' then
    return jsonb_build_object('state',case when r.status='DEFERRED' then 'AWAITING_PROVIDER_RETRY' else 'HOLD_PROVIDER_RESTACK_FAILED' end,'assignment_id',a.assignment_id,'outbox_id',q.id,'provider_receipt_id',r.id,'provider_status',r.provider_status,'evidence',r.evidence,'authority_created',false);
  end if;

  v_result:=coalesce(r.evidence->'result','{}'::jsonb);
  v_pr:=nullif(v_result->>'successor_pr','')::integer;
  v_head:=nullif(v_result->>'successor_head_sha','');
  v_base:=nullif(v_result->>'base_sha','');
  if v_pr is null or v_head !~ '^[0-9a-f]{40}$' or v_base !~ '^[0-9a-f]{40}$' then
    return jsonb_build_object('state','HOLD_PROVIDER_RECEIPT_INCOMPLETE','assignment_id',a.assignment_id,'provider_receipt_id',r.id,'evidence',r.evidence,'authority_created',false);
  end if;

  v_already_applied:=coalesce(a.metadata->>'restack_provider_receipt_id','')=r.id::text;
  if p_apply and not v_already_applied then
    update integration_control.penta_assignment_contracts_v1
    set state='AWAITING_PROJECTION',
        metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
          'restack_provider_receipt_id',r.id,
          'restack_successor_pr',v_pr,
          'restack_successor_head_sha',v_head,
          'restack_successor_base_sha',v_base,
          'restack_provider_readback_at',clock_timestamp(),
          'predecessor_close_forbidden_until_projection_readback',true,
          'authority_created',false
        ),
        updated_at=clock_timestamp()
    where assignment_id=a.assignment_id;

    update integration_control.penta_production_mobilization_v1
    set state='verified',
        evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object('provider_receipt_id',r.id,'successor_pr',v_pr,'successor_head_sha',v_head,'base_sha',v_base,'coordination_only',target_ref in ('penta.merge','penta.pr'),'authority_created',false),
        evidence_sha256=encode(extensions.digest(convert_to((coalesce(evidence,'{}'::jsonb)||jsonb_build_object('provider_receipt_id',r.id,'successor_pr',v_pr,'successor_head_sha',v_head,'base_sha',v_base,'authority_created',false))::text,'UTF8'),'sha256'),'hex'),
        completed_at=clock_timestamp(),updated_at=clock_timestamp()
    where handoff_key like 'assignment:'||a.assignment_id::text||':%'
      and state in ('queued','held','emitted','routed','in_progress');

    update integration_control.penta_census_handoffs_v1
    set state='in_progress',
        payload=coalesce(payload,'{}'::jsonb)||jsonb_build_object('provider_receipt_id',r.id,'successor_pr',v_pr,'successor_head_sha',v_head,'base_sha',v_base,'predecessor_close_forbidden',true,'authority_created',false),
        updated_at=clock_timestamp()
    where handoff_key like 'assignment:'||a.assignment_id::text||':%'
      and state in ('queued','acknowledged','failed','in_progress');

    v_event:=chlom_runtime.append_dail_event(
      'penta.assignment.pr_restack.provider_readback',
      'penta_assignment',a.assignment_id::text,
      jsonb_build_object('assignment_key',a.assignment_key,'predecessor_pr',a.source_pr_number,'predecessor_head_sha',a.exact_head_sha,'successor_pr',v_pr,'successor_head_sha',v_head,'base_sha',v_base,'provider_receipt_id',r.id,'predecessor_close_forbidden',true,'merge_authority_created',false,'certification_created',false,'authority_created',false,'observed_at',clock_timestamp()),
      'PentaPM/PentaPR/PentaMerge',null,'PentaPM','1.0.0','ctcorr:penta-assignment-restack:'||a.assignment_id::text,null,'ct.penta.pr-terminalization-policy.v2',null,'internal'
    );
  end if;

  return jsonb_build_object('state','SUCCESSOR_PROVIDER_READBACK','assignment_id',a.assignment_id,'successor_pr',v_pr,'successor_head_sha',v_head,'base_sha',v_base,'provider_receipt_id',r.id,'applied',p_apply and not v_already_applied,'event',v_event,'predecessor_close_forbidden',true,'authority_created',false);
end
$function$;

revoke all on function penta_pm.assignment_restack_readback_v1(uuid,boolean) from public;
grant execute on function penta_pm.assignment_restack_readback_v1(uuid,boolean) to service_role;

create or replace function integration_control.penta_census_mobilize_safe_handoffs_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, pentas, penta_pm, extensions, chlom_runtime
as $function$
declare
  h record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,100),500));
  v_target text;
  v_packet jsonb;
  v_packet_id uuid;
  v_emitted integer:=0;
  v_failed integer:=0;
  v_restack_queued integer:=0;
  v_restack_coordination_held integer:=0;
  v_route jsonb;
  v_sha text;
  v_evidence jsonb;
  v_assignment_id uuid;
  v_adapter jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:census-mobilization',0)) then return jsonb_build_object('state','DEFERRED_CONTENTION','emitted',0); end if;

  for h in
    select x.*,d.entity_kind,d.entity_key,d.canonical_name,d.rationale
    from integration_control.penta_census_handoffs_v1 x
    join integration_control.penta_census_discoveries_v1 d on d.discovery_key=x.discovery_key
    where x.state='queued' and x.risk_class in ('D0','D1','D2')
      and not exists(select 1 from integration_control.penta_production_mobilization_v1 m where m.handoff_key=x.handoff_key and m.state not in ('failed','superseded'))
    order by case x.risk_class when 'D0' then 0 when 'D1' then 1 else 2 end,x.created_at
    limit v_limit
    for update of x skip locked
  loop
    -- Exact compatibility bridge for governed current-main PR restacks only.
    if h.tag='assignment:PR_RESTACK_CURRENT_MAIN' and h.target_ref in ('penta.merge','penta.pr','ct.penta.pm.v1') then
      begin
        v_assignment_id:=nullif(h.payload->>'assignment_id','')::uuid;
      exception when others then
        v_assignment_id:=null;
      end;

      if v_assignment_id is null then
        v_evidence:=jsonb_build_object('reason','restack_assignment_id_missing','target_ref',h.target_ref,'authority_created',false);
        v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
        insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,state,evidence_sha256,evidence,updated_at)
        values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,h.target_ref,'failed',v_sha,v_evidence,now())
        on conflict(handoff_key) do update set state='failed',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
        update integration_control.penta_census_handoffs_v1 set state='failed',payload=payload||v_evidence,updated_at=now() where handoff_key=h.handoff_key;
        v_failed:=v_failed+1;
        continue;
      end if;

      if h.target_ref='ct.penta.pm.v1' then
        v_adapter:=penta_pm.assignment_restack_prepare_v1(v_assignment_id);
        if coalesce(v_adapter->>'state','') in ('QUEUED_PROVIDER_RESTACK','PROVIDER_ALREADY_SUCCEEDED') then
          v_evidence:=jsonb_build_object('adapter','penta_pm.assignment_restack_prepare_v1','result',v_adapter,'execution_owner','PentaPM','coordination_owners',jsonb_build_array('PentaMerge','PentaPR'),'provider_write_scope','draft_successor_prepare_only','authority_created',false);
          v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
          insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,state,evidence_sha256,evidence,updated_at)
          values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,'ct.penta.pm.v1','queued',v_sha,v_evidence,now())
          on conflict(handoff_key) do update set target_node_id=excluded.target_node_id,state='queued',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
          update integration_control.penta_census_handoffs_v1 set state='acknowledged',payload=payload||jsonb_build_object('restack_adapter_result',v_adapter,'execution_owner','PentaPM','authority_created',false),updated_at=now() where handoff_key=h.handoff_key;
          v_restack_queued:=v_restack_queued+1;
        else
          v_evidence:=jsonb_build_object('reason','restack_adapter_hold','result',v_adapter,'authority_created',false);
          v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
          insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,state,evidence_sha256,evidence,updated_at)
          values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,'ct.penta.pm.v1','held',v_sha,v_evidence,now())
          on conflict(handoff_key) do update set state='held',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
          update integration_control.penta_census_handoffs_v1 set state='acknowledged',payload=payload||v_evidence,updated_at=now() where handoff_key=h.handoff_key;
          v_restack_coordination_held:=v_restack_coordination_held+1;
        end if;
      else
        v_evidence:=jsonb_build_object('reason','coordination_owner_waiting_on_pentapm_provider_restack','execution_owner','PentaPM','coordination_owner',case h.target_ref when 'penta.merge' then 'PentaMerge' else 'PentaPR' end,'assignment_id',v_assignment_id,'merge_or_close_authority_created',false,'authority_created',false);
        v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
        insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,state,evidence_sha256,evidence,updated_at)
        values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,h.target_ref,'held',v_sha,v_evidence,now())
        on conflict(handoff_key) do update set state='held',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
        update integration_control.penta_census_handoffs_v1 set state='acknowledged',payload=payload||v_evidence,updated_at=now() where handoff_key=h.handoff_key;
        v_restack_coordination_held:=v_restack_coordination_held+1;
      end if;
      continue;
    end if;

    v_target:=case h.target_ref
      when 'penta.build' then 'ct.penta.factory.software'
      when 'penta.certify' then 'ct.penta.certify'
      when 'ct.agent.penta-wire' then 'ct.penta.wire'
      when 'penta.release' then 'ct.penta.release'
      else null end;

    if v_target is null or not exists(select 1 from pentas.nodes_v2 n where n.node_id=v_target and n.lifecycle_state='active' and n.health_state in ('healthy','degraded')) then
      v_failed:=v_failed+1;
      v_evidence:=jsonb_build_object('reason','target_node_unavailable','target_ref',h.target_ref,'mapped_target_node_id',v_target,'authority_created',false);
      v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
      insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,state,evidence_sha256,evidence,updated_at)
      values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,coalesce(v_target,'unresolved://target'),'failed',v_sha,v_evidence,now())
      on conflict(handoff_key) do update set state='failed',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
      update integration_control.penta_census_handoffs_v1 set state='failed',payload=payload||v_evidence,updated_at=now() where handoff_key=h.handoff_key;
      continue;
    end if;

    v_packet:=pentas.emit_v2(
      'institutional.production-reconciliation.request','ct.penta.census','direct',v_target,'penta.production.reconciliation','penta-census-handoff:'||h.handoff_key,
      jsonb_build_object('handoff_key',h.handoff_key,'discovery_key',h.discovery_key,'entity_kind',h.entity_kind,'entity_key',h.entity_key,'canonical_name',h.canonical_name,'tag',h.tag,'risk_class',h.risk_class,'target_ref',h.target_ref,'production_presence',exists(select 1 from integration_control.penta_production_presence_v1 p where p.subject_key=h.entity_key),'government_assignment',exists(select 1 from integration_control.penta_government_assignments_v1 g where g.entity_kind=h.entity_kind and g.entity_key=h.entity_key and g.state='active'),'requested_outcome',case h.tag when 'needs-build' then 'exact_build_candidate_and_tests' when 'needs-contract' then 'complete_contract_and_assurance' when 'needs-production' then 'exact_release_and_provider_readback' when 'needs-registration' then 'canonical_registry_binding' when 'needs-upgrade' then 'newer_generation_candidate' when 'needs-wiring' then 'exact_adapter_and_route_binding' else 'reconciliation' end,'guardrails',jsonb_build_object('source_maturity_preserved',true,'D3_human_reserved',true,'money_movement',false,'authority_manufacture',false,'provider_write_requires_exact_existing_authority',true)),
      h.risk_class,h.risk_class,case h.risk_class when 'D0' then 10 when 'D1' then 20 else 30 end,86400,null,'penta-census-handoff:'||h.handoff_key,
      jsonb_build_object('campaign_key','ct.campaign.all-pentas-production-government.v1','source','PentaCensus','classification_only',false,'authority_created',false)
    );
    v_packet_id:=nullif(v_packet->>'packet_id','')::uuid;
    v_evidence:=jsonb_build_object('packet_id',v_packet_id,'target_node_id',v_target,'emission',v_packet,'campaign_key','ct.campaign.all-pentas-production-government.v1','authority_created',false);
    v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
    insert into integration_control.penta_production_mobilization_v1(handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,packet_id,state,evidence_sha256,evidence,updated_at)
    values(h.handoff_key,h.discovery_key,h.entity_kind,h.entity_key,h.tag,h.risk_class,h.target_ref,v_target,v_packet_id,'emitted',v_sha,v_evidence,now())
    on conflict(handoff_key) do update set target_node_id=excluded.target_node_id,packet_id=excluded.packet_id,state='emitted',evidence_sha256=excluded.evidence_sha256,evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,updated_at=now();
    update integration_control.penta_census_handoffs_v1 set state='acknowledged',payload=payload||jsonb_build_object('production_mobilization_packet_id',v_packet_id,'target_node_id',v_target,'campaign_key','ct.campaign.all-pentas-production-government.v1','acknowledged_at',clock_timestamp()),updated_at=now() where handoff_key=h.handoff_key;
    v_emitted:=v_emitted+1;
  end loop;

  v_route:=pentas.route_tick_v2(greatest(100,v_limit*2));
  perform integration_control.penta_census_mobilization_reconcile_v1(greatest(250,v_limit*2));
  return jsonb_build_object('state',case when v_failed>0 then 'DEGRADED' else 'COMPLETE' end,'emitted',v_emitted,'failed',v_failed,'restack_provider_queued',v_restack_queued,'restack_coordination_held',v_restack_coordination_held,'route',v_route,'remaining_queued',(select count(*) from integration_control.penta_census_handoffs_v1 where state='queued' and risk_class in ('D0','D1','D2')),'D3_approval_required',(select count(*) from integration_control.penta_census_handoffs_v1 where state='approval_required' and risk_class='D3'),'authority_created',false,'observed_at',clock_timestamp());
end
$function$;

comment on function penta_pm.assignment_restack_prepare_v1(uuid) is 'Queues exactly one collision-safe current-main draft successor preparation for an existing D0-D2 PR restack assignment. No merge/close/certification authority.';
comment on function penta_pm.assignment_restack_readback_v1(uuid,boolean) is 'Consumes exact PentaPM provider receipt for a restack successor and advances only to AWAITING_PROJECTION. Never closes predecessor or manufactures certification.';
