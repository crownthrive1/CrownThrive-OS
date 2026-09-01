-- PentaHelp independent-gate transport v1.
--
-- Root cause: penta_liaison_route_v1() durably records a routed liaison thread, but the
-- PentaLiaison edge surface only exposes status/route and does not deliver D0-D2 independent
-- gate work to a native Penta execution node. Exact-head requests could therefore remain
-- correctly fail-closed with attempt_count=0 forever even when the target native node exists.
--
-- This layer is transport only. It NEVER creates PASS, certification, rights, provider writes,
-- credentials, money, votes/quorum, D3, or authority. A target node keeps its own independent
-- decision/certification rules. Missing target nodes remain explicit HOLDs rather than being
-- silently treated as success.

create table if not exists penta_help.independent_gate_dispatches_v1 (
  dispatch_id uuid primary key default gen_random_uuid(),
  request_id uuid not null references penta_help.requests_v1(request_id) on delete restrict,
  destination_ref text not null,
  target_node_id text not null,
  exact_subject_ref text not null,
  exact_head_sha text,
  packet_id uuid,
  state text not null check (state in ('EMITTED','HOLD_TARGET_NODE_UNREGISTERED','HOLD_TARGET_NODE_UNHEALTHY')),
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid,
  dail_event_hash text,
  created_at timestamptz not null default now(),
  unique(request_id,destination_ref,exact_subject_ref)
);

alter table penta_help.independent_gate_dispatches_v1 enable row level security;
alter table penta_help.independent_gate_dispatches_v1 force row level security;
revoke all on penta_help.independent_gate_dispatches_v1 from public, anon, authenticated;
grant select on penta_help.independent_gate_dispatches_v1 to service_role;

create or replace function penta_help.reject_independent_gate_dispatch_mutation_v1()
returns trigger
language plpgsql
set search_path to 'pg_catalog','penta_help'
as $function$
begin
  raise exception 'PENTA_HELP_INDEPENDENT_GATE_DISPATCH_APPEND_ONLY';
end
$function$;

drop trigger if exists independent_gate_dispatch_append_only_v1 on penta_help.independent_gate_dispatches_v1;
create trigger independent_gate_dispatch_append_only_v1
before update or delete on penta_help.independent_gate_dispatches_v1
for each row execute function penta_help.reject_independent_gate_dispatch_mutation_v1();

create or replace function public.penta_help_dispatch_independent_gates_v1(p_limit integer default 16)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_help','pentas','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_limit integer:=greatest(1,least(coalesce(p_limit,16),64));
  r record;
  v_owner text;
  v_target text;
  v_state text;
  v_packet jsonb;
  v_packet_id uuid;
  v_payload jsonb;
  v_evidence jsonb;
  v_sha text;
  v_dispatch_id uuid;
  v_dail jsonb;
  v_event_id uuid;
  v_event_hash text;
  v_emitted integer:=0;
  v_holds integer:=0;
  v_existing integer:=0;
  v_route jsonb:='{}'::jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  for r in
    select q.*, l.destination_ref as liaison_destination_ref, l.thread_id
      from penta_help.requests_v1 q
      join lateral (
        select t.thread_id,t.destination_ref,t.state,t.updated_at
          from penta_help.liaison_threads_v1 t
         where t.request_id=q.request_id
           and t.state='routed'
         order by t.updated_at desc
         limit 1
      ) l on true
     where q.blocker_class='independent_gate'
       and q.risk_class in ('D0','D1','D2')
       and q.state not in ('resolved','retired','expired','waiting_human')
     order by q.created_at
     limit v_limit
  loop
    v_owner:=lower(coalesce(nullif(r.context->>'requested_owner',''),r.liaison_destination_ref,''));
    v_target:=case
      when v_owner in ('penta.certify','pentacertify','penta certifier','pentacertifier') then 'ct.penta.certify'
      when v_owner in ('penta.security','pentasecurity') then 'ct.penta.security'
      when v_owner in ('chlom','chlom_core','chlom core') then 'ct.chlom.authority'
      when v_owner in ('cie','ct.framework.cultural-imprint-engine','cultural imprint engine') then 'ct.cie.review'
      else 'unresolved://independent-gate-target'
    end;

    v_payload:=jsonb_build_object(
      'contract','ct.penta.help.independent-gate-transport.v1',
      'request_id',r.request_id,
      'blocker_code',r.blocker_code,
      'need',r.need,
      'source_kind',r.source_kind,
      'source_ref',r.source_ref,
      'source_state',r.source_state,
      'risk_class',r.risk_class,
      'authority_required',r.authority_required,
      'requested_owner',coalesce(r.context->>'requested_owner',r.liaison_destination_ref),
      'exact_head_sha',r.context->>'exact_head_sha',
      'repository',r.context->>'repository',
      'pr_number',r.context->'pr_number',
      'work_package',r.context->>'work_package',
      'prerequisites',r.context->>'prerequisites',
      'liaison_thread_id',r.thread_id,
      'originator_system_key',coalesce(r.context->>'originator_system_key',r.requester_system_key),
      'transport_only',true,
      'authority_created',false,
      'provider_write',false,
      'credential_change',false,
      'money_movement',false,
      'rights_grant',false,
      'vote_effect',false,
      'quorum_effect',false,
      'd3_execution',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

    select count(*) into v_existing
      from penta_help.independent_gate_dispatches_v1 d
     where d.request_id=r.request_id
       and d.destination_ref=coalesce(r.liaison_destination_ref,'')
       and d.exact_subject_ref=r.source_ref;
    if v_existing>0 then
      continue;
    end if;

    if not exists(
      select 1 from pentas.nodes_v2 n
       where n.node_id=v_target and n.lifecycle_state='active'
    ) then
      v_state:='HOLD_TARGET_NODE_UNREGISTERED';
      v_holds:=v_holds+1;
      v_packet_id:=null;
    elsif not exists(
      select 1 from pentas.nodes_v2 n
       where n.node_id=v_target and n.lifecycle_state='active' and n.health_state in ('healthy','degraded')
    ) then
      v_state:='HOLD_TARGET_NODE_UNHEALTHY';
      v_holds:=v_holds+1;
      v_packet_id:=null;
    else
      v_packet:=pentas.emit_v2(
        'institutional.independent-gate.review.request',
        'ct.penta.census',
        'direct',
        v_target,
        'independent-gate.review',
        'penta-help-independent-gate:'||r.request_id::text,
        v_payload,
        r.risk_class,
        r.risk_class,
        case r.risk_class when 'D0' then 10 when 'D1' then 20 else 30 end,
        greatest(3600,least(coalesce(r.ttl_seconds,21600),21600)),
        null,
        r.source_ref,
        jsonb_build_object(
          'source','PentaHelp/PentaLiaison',
          'request_id',r.request_id,
          'independent_gate',true,
          'transport_only',true,
          'authority_created',false)
      );
      v_packet_id:=nullif(v_packet->>'packet_id','')::uuid;
      if v_packet_id is null then
        raise exception 'PENTA_HELP_GATE_PACKET_EMIT_FAILED:%',r.request_id;
      end if;
      v_state:='EMITTED';
      v_emitted:=v_emitted+1;
    end if;

    v_evidence:=v_payload||jsonb_build_object(
      'target_node_id',v_target,
      'state',v_state,
      'packet_id',v_packet_id,
      'observed_at',clock_timestamp());
    v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

    v_dail:=public.chlom_append_dail_event(
      p_event_type=>'penta.help.independent-gate.transport.v1',
      p_entity_type=>'penta_help_request',
      p_entity_id=>r.request_id::text,
      p_payload=>v_evidence||jsonb_build_object('evidence_sha256',v_sha),
      p_actor_ref=>'PentaHelp/PentaLiaison/PentaCensus',
      p_actor_did=>null,
      p_agent_id=>'penta.liaison',
      p_entity_version=>'1.0.0',
      p_correlation_id=>'penta-help-independent-gate:'||r.request_id::text,
      p_causation_id=>null,
      p_authority_basis=>'D0-D2 transport only; destination retains independent authority and may PASS/HOLD/DENY under its own contract',
      p_approval_id=>null,
      p_visibility_class=>'internal');
    v_event_id:=nullif(v_dail->>'event_id','')::uuid;
    select event_hash into v_event_hash from chlom_runtime.dail_events where event_id=v_event_id;
    if v_event_hash is null then raise exception 'DAIL_GATE_TRANSPORT_READBACK_FAILED'; end if;

    insert into penta_help.independent_gate_dispatches_v1(
      request_id,destination_ref,target_node_id,exact_subject_ref,exact_head_sha,packet_id,state,
      evidence,evidence_sha256,dail_event_id,dail_event_hash)
    values(
      r.request_id,coalesce(r.liaison_destination_ref,''),v_target,r.source_ref,
      r.context->>'exact_head_sha',v_packet_id,v_state,v_evidence,v_sha,v_event_id,v_event_hash)
    returning dispatch_id into v_dispatch_id;
  end loop;

  if v_emitted>0 then
    v_route:=pentas.route_tick_v2(greatest(100,v_emitted*4));
  end if;

  return jsonb_build_object(
    'contract','ct.penta.help.independent-gate-transport.v1',
    'state',case when v_holds>0 then 'DEGRADED' else 'COMPLETE' end,
    'emitted',v_emitted,
    'holds',v_holds,
    'route',v_route,
    'unresolved_target_nodes',(
      select coalesce(jsonb_agg(jsonb_build_object(
        'request_id',d.request_id,'destination_ref',d.destination_ref,
        'target_node_id',d.target_node_id,'state',d.state,'exact_head_sha',d.exact_head_sha)
        order by d.created_at),'[]'::jsonb)
      from penta_help.independent_gate_dispatches_v1 d
      where d.state like 'HOLD_%'),
    'authority_created',false,
    'observed_at',clock_timestamp());
end
$function$;

revoke all on function public.penta_help_dispatch_independent_gates_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_help_dispatch_independent_gates_v1(integer) to service_role;

comment on table penta_help.independent_gate_dispatches_v1 is
'Append-only transport receipts for D0-D2 independent gate requests. EMITTED means delivery to a registered native Penta packet node only; it never means PASS or certification.';
comment on function public.penta_help_dispatch_independent_gates_v1(integer) is
'Delivers routed independent-gate requests to registered healthy native Penta nodes. Missing PentaSecurity/CHLOM/CIE exact-review nodes remain explicit HOLDs; no authority or disposition is manufactured.';
