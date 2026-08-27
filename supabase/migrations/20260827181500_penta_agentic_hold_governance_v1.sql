begin;

-- Additive successor to the archived A/B/C/D/S scheduler topology. Historical
-- ballots and quorum receipts remain evidence; they are not consulted here.
create table if not exists penta_runtime.penta_agentic_hold_policy_v1 (
  policy_id text primary key,
  required_layers text[] not null,
  minimum_distinct_agents integer not null check (minimum_distinct_agents >= 3),
  legacy_topology_status text not null default 'historical_superseded'
    check (legacy_topology_status = 'historical_superseded'),
  provider_effect boolean not null default false check (not provider_effect),
  paid_cost_minor bigint not null default 0 check (paid_cost_minor = 0),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_agentic_hold_cases_v1 (
  case_id uuid primary key default gen_random_uuid(),
  case_key text not null unique,
  campaign_id text not null references penta_runtime.d3_campaign_bindings_v1(campaign_id),
  hand_id uuid not null references penta_runtime.hold_hands_v1(hand_id),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  risk_class text not null check (risk_class in ('D1','D2','D3')),
  originator_agent_id text not null references penta_runtime.agent_registry_v1(agent_id),
  founder_authority_ref text,
  state text not null default 'raised'
    check (state in ('raised','remediating','agentic_resolution_ready','resolved','superseded')),
  layer_states jsonb not null default '{}'::jsonb,
  raised_at timestamptz not null default now(),
  evaluated_at timestamptz,
  resolved_at timestamptz,
  provider_effect boolean not null default false check (not provider_effect),
  paid_cost_minor bigint not null default 0 check (paid_cost_minor = 0),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists penta_runtime.penta_agentic_layer_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_key text not null unique,
  case_id uuid not null references penta_runtime.penta_agentic_hold_cases_v1(case_id),
  layer_key text not null check (layer_key in ('DISCOVER','GOVERN','EXECUTE','VERIFY','PRESERVE')),
  agent_id text not null references penta_runtime.agent_registry_v1(agent_id),
  disposition text not null check (disposition in ('PASS','HOLD','DENY','UNKNOWN')),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_ref text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  independent boolean not null default false,
  self_approval boolean not null default false check (not self_approval),
  observed_at timestamptz not null default now(),
  expires_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb,
  check (expires_at > observed_at)
);

create index if not exists penta_agentic_layer_receipts_lookup_v1
  on penta_runtime.penta_agentic_layer_receipts_v1(case_id,layer_key,observed_at desc);

create table if not exists penta_runtime.penta_agentic_supersessions_v1 (
  supersession_id uuid primary key default gen_random_uuid(),
  predecessor_contract text not null,
  successor_contract text not null,
  effective_scope text not null,
  historical_records_preserved boolean not null default true check (historical_records_preserved),
  created_at timestamptz not null default now(),
  unique(predecessor_contract,successor_contract,effective_scope)
);

alter table penta_runtime.penta_agentic_hold_policy_v1 enable row level security;
alter table penta_runtime.penta_agentic_hold_cases_v1 enable row level security;
alter table penta_runtime.penta_agentic_layer_receipts_v1 enable row level security;
alter table penta_runtime.penta_agentic_supersessions_v1 enable row level security;
alter table penta_runtime.penta_agentic_hold_policy_v1 force row level security;
alter table penta_runtime.penta_agentic_hold_cases_v1 force row level security;
alter table penta_runtime.penta_agentic_layer_receipts_v1 force row level security;
alter table penta_runtime.penta_agentic_supersessions_v1 force row level security;

revoke all on penta_runtime.penta_agentic_hold_policy_v1,
  penta_runtime.penta_agentic_hold_cases_v1,
  penta_runtime.penta_agentic_layer_receipts_v1,
  penta_runtime.penta_agentic_supersessions_v1 from public,anon,authenticated;
grant select,insert,update on penta_runtime.penta_agentic_hold_policy_v1,
  penta_runtime.penta_agentic_hold_cases_v1,
  penta_runtime.penta_agentic_layer_receipts_v1,
  penta_runtime.penta_agentic_supersessions_v1 to service_role;

insert into penta_runtime.penta_agentic_hold_policy_v1(
  policy_id,required_layers,minimum_distinct_agents,metadata
) values(
  'ct.penta.agentic.hold-governance.v1',
  array['DISCOVER','GOVERN','EXECUTE','VERIFY','PRESERVE'],3,
  jsonb_build_object(
    'approval_model','PENTA_LAYER_RECEIPTS',
    'originator_self_approval',false,
    'verify_must_be_independent',true,
    'govern_and_verify_must_be_distinct',true,
    'certification_effect',false,
    'runtime_activation_effect',false,
    'historical_quorum_records','preserved_read_only'
  )
) on conflict(policy_id) do update set
  required_layers=excluded.required_layers,
  minimum_distinct_agents=excluded.minimum_distinct_agents,
  metadata=excluded.metadata,
  active=true;

insert into penta_runtime.penta_agentic_supersessions_v1(
  predecessor_contract,successor_contract,effective_scope
) values(
  'ct.legacy.abcds.scheduler-governance',
  'ct.penta.agentic.hold-governance.v1',
  'prospective_hold_resolution_only'
) on conflict do nothing;

create or replace function penta_runtime.open_penta_agentic_hold_case_v1(
  p_campaign_id text,
  p_exact_head_sha text,
  p_content_sha256 text,
  p_risk_class text,
  p_originator_agent_id text,
  p_founder_authority_ref text default null
)
returns uuid
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  v_hand penta_runtime.hold_hands_v1%rowtype;
  v_agent penta_runtime.agent_registry_v1%rowtype;
  v_case_id uuid;
begin
  select * into strict v_hand from penta_runtime.hold_hands_v1
    where campaign_id=p_campaign_id and state<>'resolved';
  select * into strict v_agent from penta_runtime.agent_registry_v1
    where agent_id=p_originator_agent_id and status='active';
  if v_agent.self_approval or p_exact_head_sha<>v_hand.exact_head_sha then
    raise exception 'inactive/self-approving originator or stale exact head' using errcode='42501';
  end if;
  if p_risk_class='D3' and (p_founder_authority_ref is null or btrim(p_founder_authority_ref)='') then
    raise exception 'D3 case requires founder authority reference' using errcode='42501';
  end if;
  insert into penta_runtime.penta_agentic_hold_cases_v1(
    case_key,campaign_id,hand_id,exact_head_sha,content_sha256,risk_class,
    originator_agent_id,founder_authority_ref,metadata
  ) values(
    concat_ws(':',p_campaign_id,p_exact_head_sha,p_content_sha256),p_campaign_id,v_hand.hand_id,
    p_exact_head_sha,p_content_sha256,p_risk_class,p_originator_agent_id,p_founder_authority_ref,
    jsonb_build_object('hand_remains_raised',true,'historical_hold_preserved',true,
      'legacy_abcds_authority_used',false,'authority_manufactured',false)
  ) on conflict(case_key) do update set evaluated_at=now()
  returning case_id into v_case_id;
  return v_case_id;
end;
$function$;

create or replace function penta_runtime.record_penta_agentic_layer_receipt_v1(
  p_case_id uuid,
  p_layer_key text,
  p_agent_id text,
  p_disposition text,
  p_exact_head_sha text,
  p_content_sha256 text,
  p_evidence_ref text,
  p_evidence_sha256 text,
  p_independent boolean,
  p_expires_at timestamptz,
  p_metadata jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  v_case penta_runtime.penta_agentic_hold_cases_v1%rowtype;
  v_agent penta_runtime.agent_registry_v1%rowtype;
  v_receipt_id uuid;
  v_key text;
begin
  select * into strict v_case from penta_runtime.penta_agentic_hold_cases_v1
    where case_id=p_case_id and state not in ('resolved','superseded');
  select * into strict v_agent from penta_runtime.agent_registry_v1
    where agent_id=p_agent_id and status='active';
  if v_agent.self_approval or p_agent_id=v_case.originator_agent_id then
    raise exception 'originator self-approval is prohibited' using errcode='42501';
  end if;
  if p_exact_head_sha<>v_case.exact_head_sha or p_content_sha256<>v_case.content_sha256 then
    raise exception 'layer receipt is not bound to the exact case content' using errcode='22023';
  end if;
  if upper(p_layer_key)='VERIFY' and not p_independent then
    raise exception 'VERIFY layer must be independently produced' using errcode='42501';
  end if;
  if p_expires_at<=now() then
    raise exception 'layer receipt must be fresh' using errcode='22023';
  end if;
  v_key := concat_ws(':',p_case_id::text,upper(p_layer_key),p_agent_id,p_evidence_sha256);
  insert into penta_runtime.penta_agentic_layer_receipts_v1(
    receipt_key,case_id,layer_key,agent_id,disposition,exact_head_sha,content_sha256,
    evidence_ref,evidence_sha256,independent,expires_at,metadata
  ) values(
    v_key,p_case_id,upper(p_layer_key),p_agent_id,upper(p_disposition),p_exact_head_sha,
    p_content_sha256,p_evidence_ref,p_evidence_sha256,p_independent,p_expires_at,
    coalesce(p_metadata,'{}'::jsonb)
  ) on conflict(receipt_key) do nothing returning receipt_id into v_receipt_id;
  if v_receipt_id is null then
    select receipt_id into v_receipt_id
    from penta_runtime.penta_agentic_layer_receipts_v1 where receipt_key=v_key;
  end if;
  return v_receipt_id;
end;
$function$;

create or replace function penta_runtime.evaluate_penta_agentic_hold_case_v1(p_case_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  v_case penta_runtime.penta_agentic_hold_cases_v1%rowtype;
  v_binding penta_runtime.d3_campaign_bindings_v1%rowtype;
  v_hand penta_runtime.hold_hands_v1%rowtype;
  v_layers jsonb := '{}'::jsonb;
  v_layer text;
  v_receipt record;
  v_agents text[] := '{}'::text[];
  v_govern_agent text;
  v_verify_agent text;
  v_ready boolean := true;
  v_baseline boolean := false;
begin
  select * into strict v_case from penta_runtime.penta_agentic_hold_cases_v1
    where case_id=p_case_id for update;
  select * into strict v_binding from penta_runtime.d3_campaign_bindings_v1
    where campaign_id=v_case.campaign_id;
  select * into strict v_hand from penta_runtime.hold_hands_v1 where hand_id=v_case.hand_id;

  if now()<v_binding.starts_at or now()>=v_binding.expires_at
     or v_binding.directive_id is null or v_binding.founder_ref is null
     or v_case.exact_head_sha<>v_hand.exact_head_sha or v_hand.state<>'resolution_ready' then
    v_ready := false;
  end if;
  if v_case.risk_class='D3' and v_case.founder_authority_ref is distinct from v_binding.founder_ref then
    v_ready := false;
  end if;

  foreach v_layer in array array['DISCOVER','GOVERN','EXECUTE','VERIFY','PRESERVE'] loop
    select r.* into v_receipt
    from penta_runtime.penta_agentic_layer_receipts_v1 r
    join penta_runtime.agent_registry_v1 a on a.agent_id=r.agent_id
    where r.case_id=p_case_id and r.layer_key=v_layer and r.expires_at>now()
      and r.exact_head_sha=v_case.exact_head_sha and r.content_sha256=v_case.content_sha256
      and r.agent_id<>v_case.originator_agent_id and a.status='active' and not a.self_approval
      and (v_layer<>'VERIFY' or r.independent)
    order by r.observed_at desc limit 1;
    if not found or v_receipt.disposition<>'PASS' then
      v_layers := v_layers||jsonb_build_object(v_layer,coalesce(v_receipt.disposition,'UNKNOWN'));
      v_ready := false;
    else
      v_layers := v_layers||jsonb_build_object(v_layer,'PASS');
      if not v_receipt.agent_id=any(v_agents) then v_agents:=array_append(v_agents,v_receipt.agent_id); end if;
      if v_layer='GOVERN' then v_govern_agent:=v_receipt.agent_id; end if;
      if v_layer='VERIFY' then v_verify_agent:=v_receipt.agent_id; end if;
    end if;
  end loop;

  if cardinality(v_agents)<3 or v_govern_agent is not distinct from v_verify_agent then v_ready:=false; end if;
  select exists(
    select 1 from penta_runtime.runtime_release_baselines_v1 rb
    where rb.campaign_id=v_case.campaign_id and rb.exact_head_sha=v_case.exact_head_sha
      and rb.state='verified' and rb.rollback_ref<>''
      and rb.verified_by<>v_case.originator_agent_id
      and rb.independent_verifier_ref<>v_case.originator_agent_id
      and rb.verified_by is distinct from v_binding.founder_ref
      and rb.independent_verifier_ref is distinct from v_binding.founder_ref
  ) into v_baseline;
  if not v_baseline then v_ready:=false; end if;

  update penta_runtime.penta_agentic_hold_cases_v1 set
    layer_states=v_layers,
    state=case when v_ready then 'agentic_resolution_ready' else 'remediating' end,
    evaluated_at=now(),
    metadata=metadata||jsonb_build_object(
      'distinct_agents',cardinality(v_agents),'verified_baseline',v_baseline,
      'certification_effect',false,'runtime_activation_effect',false
    )
  where case_id=p_case_id;
  return jsonb_build_object(
    'case_id',p_case_id,'state',case when v_ready then 'AGENTIC_RESOLUTION_READY' else 'HAND_REMAINS_RAISED' end,
    'layers',v_layers,'distinct_agents',cardinality(v_agents),'verified_baseline',v_baseline,
    'additive_resolution_eligible',v_ready,'historical_hold_preserved',true,
    'certified',false,'runtime_activated',false,'provider_effect',false,'paid_cost_minor',0
  );
end;
$function$;

create or replace function penta_runtime.penta_agentic_hold_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  v_case record;
  v_layer text;
  v_count integer := 0;
begin
  perform penta_runtime.penta_hold_crawler_tick_v1();
  for v_case in
    select c.*,h.state as hand_state
    from penta_runtime.penta_agentic_hold_cases_v1 c
    join penta_runtime.hold_hands_v1 h on h.hand_id=c.hand_id
    where c.state not in ('resolved','superseded')
    for update of c skip locked
  loop
    perform penta_runtime.evaluate_penta_agentic_hold_case_v1(v_case.case_id);
    foreach v_layer in array array['DISCOVER','GOVERN','EXECUTE','VERIFY','PRESERVE'] loop
      if not exists(
        select 1 from penta_runtime.penta_agentic_layer_receipts_v1 r
        where r.case_id=v_case.case_id and r.layer_key=v_layer and r.disposition='PASS'
          and r.expires_at>now() and r.exact_head_sha=v_case.exact_head_sha
      ) then
        insert into penta_runtime.hold_remediation_tasks_v1(
          task_key,campaign_id,exact_head_sha,predicate_key,route_keys
        ) values(
          concat_ws(':',v_case.campaign_id,v_case.exact_head_sha,'penta-layer',lower(v_layer)),
          v_case.campaign_id,v_case.exact_head_sha,'penta_layer_'||lower(v_layer),
          case v_layer
            when 'DISCOVER' then array['penta.crawler','penta.vergence','penta.help']
            when 'GOVERN' then array['penta.bound','penta.secure','penta.help']
            when 'EXECUTE' then array['penta.orchestrator','penta.factory','penta.help']
            when 'VERIFY' then array['penta.test','penta.audit','penta.vergence','penta.help']
            else array['penta.vergence','penta.docs','penta.help'] end
        ) on conflict(task_key) do update set
          state=case when penta_runtime.hold_remediation_tasks_v1.state='completed' then 'completed' else 'queued' end,
          updated_at=now();
      end if;
    end loop;
    v_count:=v_count+1;
  end loop;
  return jsonb_build_object(
    'service','ct.penta.agentic.hold-tick.v1','cases_scanned',v_count,
    'hand_rule','raised_until_all_penta_layers_and_baseline_pass',
    'certification_effect',false,'runtime_activation_effect',false,
    'provider_effect',false,'paid_cost_minor',0,'at',now()
  );
end;
$function$;

revoke all on function penta_runtime.open_penta_agentic_hold_case_v1(text,text,text,text,text,text) from public,anon,authenticated;
revoke all on function penta_runtime.record_penta_agentic_layer_receipt_v1(uuid,text,text,text,text,text,text,text,boolean,timestamptz,jsonb) from public,anon,authenticated;
revoke all on function penta_runtime.evaluate_penta_agentic_hold_case_v1(uuid) from public,anon,authenticated;
revoke all on function penta_runtime.penta_agentic_hold_tick_v1() from public,anon,authenticated;
grant execute on function penta_runtime.open_penta_agentic_hold_case_v1(text,text,text,text,text,text),
  penta_runtime.record_penta_agentic_layer_receipt_v1(uuid,text,text,text,text,text,text,text,boolean,timestamptz,jsonb),
  penta_runtime.evaluate_penta_agentic_hold_case_v1(uuid),
  penta_runtime.penta_agentic_hold_tick_v1() to service_role;

do $block$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='penta-agentic-hold-governance-v1' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('penta-agentic-hold-governance-v1','*/5 * * * *',
      'select penta_runtime.penta_agentic_hold_tick_v1();');
  else
    perform cron.alter_job(v_jobid,schedule=>'*/5 * * * *',
      command=>'select penta_runtime.penta_agentic_hold_tick_v1();',active=>true);
  end if;
end
$block$;

commit;
