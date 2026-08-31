-- CrownThrive production reconciliation — 2026-08-31
-- Captures already-observed production changes without introducing provider writes,
-- credential export, money movement, checkout activation, or D3 authority.

begin;

-- Gretna Junction commerce broker: public PentaWire projection is health/readiness only.
insert into integration_control.penta_wire_read_adapters_v1(
  service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,
  public_projection,provider_write,credential_forwarding,authority_effect,state,evidence,created_at,updated_at
) values(
  'gretna_junction_commerce','PUBLIC_HTTP','ct.gretna.commerce-control.v1',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/gretna-commerce-control-v1',
  jsonb_build_array('health.read'),true,false,false,'none','active',
  jsonb_build_object(
    'projection','unauthenticated GET health/readiness only',
    'edge_slug','gretna-commerce-control-v1',
    'edge_version',11,
    'edge_sha256','a16e172a056d3c5c500ed67e6aa1b372f7da3698abb55e4ff04d501d925a844c',
    'checkout_exposed',false,'credit_mutations_exposed',false,'stripe_write_exposed',false,
    'gateway_secret_sent',false,'authority_expansion',false
  ),now(),now()
) on conflict(service_id) do update set
  adapter_kind=excluded.adapter_kind,
  exact_contract=excluded.exact_contract,
  transport_ref=excluded.transport_ref,
  allowed_operations=excluded.allowed_operations,
  public_projection=excluded.public_projection,
  provider_write=false,
  credential_forwarding=false,
  authority_effect='none',
  state='active',
  evidence=excluded.evidence,
  updated_at=now();

update integration_control.services
set metadata=metadata||jsonb_build_object(
  'penta_wire_public_status_safe',true,
  'penta_wire_public_probe_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/gretna-commerce-control-v1',
  'write_methods_enabled',false,
  'delete_methods_enabled',false,
  'penta_wire_exact_contract','ct.gretna.commerce-control.v1',
  'penta_wire_public_projection','health_only'
),updated_at=now()
where service_id='gretna_junction_commerce';

-- Locticians/BD: preserve four live bounded reads and isolate only the degraded bulk list route.
update integration_control.locticians_endpoint_catalog_v2
set state='verified_read',internal_enabled=true,provider_http_status=200,
    verification_source='live_four_route_reverify_2026-08-31',last_verified_at=now(),updated_at=now()
where endpoint_id in (
  'locticians:user:fields','locticians:user:find','locticians:user:get_by_id','locticians:user:categories'
);

update integration_control.locticians_endpoint_catalog_v2
set state='provider_degraded',internal_enabled=false,mcp_enabled=false,provider_http_status=400,
    verification_source='live_bulk_get_degraded_2026-08-31',
    notes=case when notes like '%unfiltered/bulk list route returns HTTP 400 while four bounded user routes remain HTTP 200%'
      then notes else notes||' | 2026-08-31: unfiltered/bulk list route returns HTTP 400 while four bounded user routes remain HTTP 200; isolated from active read fabric.' end,
    last_verified_at=now(),updated_at=now()
where endpoint_id='locticians:user:get';

-- Remove a stale provider-record identity claim from the working legacy/master credential lane.
update integration_control.locticians_provider_key_lanes_v1
set metadata=(metadata - 'provider_key_id') || jsonb_build_object(
  'provider_key_mapping_state','legacy_master_unmapped_to_bd_api_keys_records_12_18',
  'provider_key_mapping_reconciled_at',now(),
  'provider_key_mapping_evidence','working primary differs from every provider token observed for bd_api_keys records 12-18; stale provider_key_id=15 removed',
  'secret_material_exposed',false
),updated_at=now()
where lane_id='ct.locticians.bd.hot.a.v3'
  and vault_alias='locticians_brilliant_directories_api_key';

-- Avoid repeatedly scanning all historical resolved PentaWire construction work.
create or replace function integration_control.penta_wire_close_resolved_gap_work_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime','public'
as $function$
declare
  b record;
  v_requests integer:=0;
  v_work integer:=0;
  v_units integer:=0;
  v_runs integer:=0;
  v_rc integer:=0;
  v_any boolean:=false;
begin
  with resolved as (
    select service_id from integration_control.penta_wire_service_bindings_v1 where gap_state='complete'
  )
  select exists(
      select 1 from chlom_runtime.construction_work_queue q join resolved r
      on q.work_id='ct.work.penta-wire.'||regexp_replace(lower(r.service_id),'[^a-z0-9]+','-','g')||'.v1'
      where q.state<>'done' limit 1
    ) or exists(
      select 1 from public.ct_factory_build_requests rq join resolved r
      on rq.request_key like 'penta-wire:'||r.service_id||':%'
      where rq.status<>'implemented' limit 1
    ) or exists(
      select 1 from public.ct_factory_build_runs br
      join public.ct_factory_build_requests rq on rq.id=br.build_request_id
      join resolved r on rq.request_key like 'penta-wire:'||r.service_id||':%'
      where br.status not in ('implemented','failed') limit 1
    ) or exists(
      select 1 from public.ct_factory_work_units wu
      join public.ct_factory_build_runs br on br.id=wu.build_run_id
      join public.ct_factory_build_requests rq on rq.id=br.build_request_id
      join resolved r on rq.request_key like 'penta-wire:'||r.service_id||':%'
      where wu.status in ('queued','ready') limit 1
    ) into v_any;

  if not v_any then
    return jsonb_build_object('contract','ct.penta.wire.resolved-gap-closeout.v1',
      'requests_closed',0,'construction_work_closed',0,'work_units_skipped',0,'build_runs_closed',0,
      'provider_write',false,'history_preserved',true,'authority_effect','none',
      'fast_path','no_open_resolved_gap_work','at',clock_timestamp());
  end if;

  for b in select service_id from integration_control.penta_wire_service_bindings_v1 where gap_state='complete'
  loop
    update chlom_runtime.construction_work_queue
    set state='done',blocker_reason=null,
        evidence=evidence||jsonb_build_object('resolved_by_penta_wire',true,'resolution_state','complete','resolved_at',clock_timestamp(),'authority_effect','none'),
        updated_at=now()
    where work_id='ct.work.penta-wire.'||regexp_replace(lower(b.service_id),'[^a-z0-9]+','-','g')||'.v1'
      and state<>'done';
    get diagnostics v_rc = row_count; v_work:=v_work+v_rc;

    update public.ct_factory_work_units wu
    set status='skipped',output=coalesce(output,'{}'::jsonb)||jsonb_build_object(
      'skipped_by','ct.agent.penta-wire','reason','gap_already_resolved_by_exact_runtime_adapter',
      'service_id',b.service_id,'authority_effect','none','provider_write',false,'resolved_at',clock_timestamp()),
      completed_at=coalesce(completed_at,clock_timestamp())
    where wu.status in ('queued','ready')
      and wu.build_run_id in (
        select br.id from public.ct_factory_build_runs br
        join public.ct_factory_build_requests rq on rq.id=br.build_request_id
        where rq.request_key like 'penta-wire:'||b.service_id||':%'
      );
    get diagnostics v_rc = row_count; v_units:=v_units+v_rc;

    update public.ct_factory_build_runs br
    set status='implemented',completed_at=coalesce(completed_at,clock_timestamp()),
        gate_summary=coalesce(gate_summary,'{}'::jsonb)||jsonb_build_object(
          'implemented_by_penta_wire',true,'service_id',b.service_id,
          'reason','exact adapter and MCP contract already live','provider_write',false,'authority_effect','none')
    where br.build_request_id in (
      select id from public.ct_factory_build_requests where request_key like 'penta-wire:'||b.service_id||':%'
    ) and br.status not in ('implemented','failed');
    get diagnostics v_rc = row_count; v_runs:=v_runs+v_rc;

    update public.ct_factory_build_requests
    set status='implemented',evidence=evidence||jsonb_build_object(
      'implemented_by_penta_wire',true,'service_id',b.service_id,'resolution_state','complete',
      'reason','exact adapter and closed-schema MCP contract are live and certified by PentaWire',
      'provider_write',false,'authority_effect','none','implemented_at',clock_timestamp()),updated_at=now()
    where request_key like 'penta-wire:'||b.service_id||':%'
      and status<>'implemented';
    get diagnostics v_rc = row_count; v_requests:=v_requests+v_rc;
  end loop;

  return jsonb_build_object('contract','ct.penta.wire.resolved-gap-closeout.v1',
    'requests_closed',v_requests,'construction_work_closed',v_work,'work_units_skipped',v_units,'build_runs_closed',v_runs,
    'provider_write',false,'history_preserved',true,'authority_effect','none','fast_path','work_present','at',clock_timestamp());
end
$function$;

-- Reconcile the 476-tool lifecycle by material change instead of rewriting every row on every cycle.
create or replace function integration_control.penta_wire_reconcile_tool_lifecycle_v2()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $function$
declare
  t integration_control.mcp_tools%rowtype;
  v_lifecycle text;
  v_execution text;
  v_schema text;
  v_authority text;
  v_basis text;
  v_reconcile boolean;
  v_human boolean;
  v_d3 boolean;
  v_evidence jsonb;
  v_sha text;
  v_active integer:=0;
  v_gated integer:=0;
  v_retired integer:=0;
  v_unresolved integer:=0;
  v_d3_count integer:=0;
  v_changed integer:=0;
  v_rc integer:=0;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;

  for t in select * from integration_control.mcp_tools order by service_id,tool_name
  loop
    v_execution:=case when t.enabled then 'enabled' else 'disabled' end;
    v_schema:=case
      when coalesce(t.input_schema->>'additionalProperties','')='false' then 'closed'
      when t.input_schema='{}'::jsonb and not t.enabled then 'not_applicable'
      else 'open_or_unspecified' end;
    v_d3:=t.risk_class='D3';

    if coalesce(t.notes,'') like '[SUPERSEDED]%'
       or lower(coalesce(t.notes,'')) ~ '(^|[ |;])superseded([ |;]|$)|(^|[ |;])retired([ |;]|$)' then
      v_lifecycle:='retired'; v_authority:='retired';
      v_basis:='explicit superseded/retired registry evidence'; v_reconcile:=false; v_human:=false;
    elsif t.enabled and v_schema='closed' then
      v_lifecycle:='active';
      v_authority:=case when v_d3 then 'd3_human_reserved' when t.requires_human_approval then 'human_gated' else 'autonomous_bounded' end;
      v_basis:='enabled tool with closed input contract'; v_reconcile:=false; v_human:=v_d3 or t.requires_human_approval;
    elsif t.enabled then
      v_lifecycle:='unresolved'; v_authority:=case when v_d3 then 'd3_human_reserved' else 'unresolved' end;
      v_basis:='enabled tool does not have a closed input schema'; v_reconcile:=true; v_human:=v_d3;
    elsif v_d3 or lower(coalesce(t.notes,'')) ~ '(disabled|fail-closed|containment|pending|candidate|no invocation authority|intentional gate|intentionally gated|gated until|intentionally remains off|remains off|not exposed|not executable|not configured|credential .* not configured|central dispatch not yet enabled|closed despite|requires .* approval|human-reserved|human reserved)' then
      v_lifecycle:='intentionally_gated'; v_authority:=case when v_d3 then 'd3_human_reserved' else 'human_gated' end;
      v_basis:=case when v_d3 then 'disabled D3 tool is intentionally human-reserved' else 'disabled tool has explicit registry gating/containment rationale' end;
      v_reconcile:=false; v_human:=v_d3 or t.requires_human_approval;
    else
      v_lifecycle:='unresolved'; v_authority:='unresolved';
      v_basis:='disabled tool has no explicit retirement or intentional-gate rationale'; v_reconcile:=true; v_human:=false;
    end if;

    v_evidence:=jsonb_build_object(
      'contract','ct.penta.wire.tool-lifecycle.v2','classifier_version','2.1.1',
      'tool_name',t.tool_name,'service_id',t.service_id,'operation_key',t.operation_key,
      'risk_class',t.risk_class,'enabled',t.enabled,'requires_human_approval',t.requires_human_approval,
      'input_additional_properties',t.input_schema->'additionalProperties',
      'lifecycle_state',v_lifecycle,'execution_state',v_execution,'schema_state',v_schema,
      'authority_state',v_authority,'classification_basis',v_basis,
      'requires_reconciliation',v_reconcile,'human_help_required',v_human,'d3_human_reserved',v_d3,
      'notes_sha256',encode(extensions.digest(convert_to(coalesce(t.notes,''),'UTF8'),'sha256'),'hex')
    );
    v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

    insert into integration_control.penta_wire_tool_contract_states_v2(
      tool_name,service_id,lifecycle_state,execution_state,schema_state,authority_state,
      classification_basis,requires_reconciliation,human_help_required,d3_human_reserved,
      evidence,evidence_sha256,classified_at,updated_at
    ) values(
      t.tool_name,t.service_id,v_lifecycle,v_execution,v_schema,v_authority,
      v_basis,v_reconcile,v_human,v_d3,v_evidence||jsonb_build_object('classified_at',clock_timestamp()),v_sha,clock_timestamp(),clock_timestamp()
    ) on conflict(tool_name) do update set
      service_id=excluded.service_id,lifecycle_state=excluded.lifecycle_state,
      execution_state=excluded.execution_state,schema_state=excluded.schema_state,
      authority_state=excluded.authority_state,classification_basis=excluded.classification_basis,
      requires_reconciliation=excluded.requires_reconciliation,human_help_required=excluded.human_help_required,
      d3_human_reserved=excluded.d3_human_reserved,evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,
      classified_at=excluded.classified_at,updated_at=clock_timestamp()
    where (integration_control.penta_wire_tool_contract_states_v2.service_id,
           integration_control.penta_wire_tool_contract_states_v2.lifecycle_state,
           integration_control.penta_wire_tool_contract_states_v2.execution_state,
           integration_control.penta_wire_tool_contract_states_v2.schema_state,
           integration_control.penta_wire_tool_contract_states_v2.authority_state,
           integration_control.penta_wire_tool_contract_states_v2.classification_basis,
           integration_control.penta_wire_tool_contract_states_v2.requires_reconciliation,
           integration_control.penta_wire_tool_contract_states_v2.human_help_required,
           integration_control.penta_wire_tool_contract_states_v2.d3_human_reserved)
          is distinct from
          (excluded.service_id,excluded.lifecycle_state,excluded.execution_state,excluded.schema_state,
           excluded.authority_state,excluded.classification_basis,excluded.requires_reconciliation,
           excluded.human_help_required,excluded.d3_human_reserved)
       or (integration_control.penta_wire_tool_contract_states_v2.evidence - 'classified_at' - 'classifier_version')
          is distinct from (excluded.evidence - 'classified_at' - 'classifier_version');
    get diagnostics v_rc = row_count; v_changed:=v_changed+v_rc;

    case v_lifecycle when 'active' then v_active:=v_active+1;
      when 'intentionally_gated' then v_gated:=v_gated+1;
      when 'retired' then v_retired:=v_retired+1;
      else v_unresolved:=v_unresolved+1; end case;
    if v_d3 then v_d3_count:=v_d3_count+1; end if;
  end loop;

  return jsonb_build_object('contract','ct.penta.wire.tool-lifecycle-reconciliation.v2','classifier_version','2.1.1',
    'registered_tools',(select count(*) from integration_control.mcp_tools),'active_tools',v_active,
    'intentionally_gated_tools',v_gated,'retired_tools',v_retired,'unresolved_tools',v_unresolved,'d3_tools',v_d3_count,
    'rows_changed',v_changed,
    'accounting_identity_pass',((select count(*) from integration_control.mcp_tools)=v_active+v_gated+v_retired+v_unresolved),
    'authority_expansion',false,'observed_at',clock_timestamp());
end
$function$;

commit;
