begin;

create table if not exists penta_runtime.hold_hands_v1 (
  hand_id uuid primary key default gen_random_uuid(),
  campaign_id text not null unique references penta_runtime.d3_campaign_bindings_v1(campaign_id),
  hold_evidence_sha256 text not null check (hold_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  producer_ids text[] not null default '{}'::text[],
  state text not null default 'raised' check (state in ('raised','resolution_ready','resolved')),
  current_predicates jsonb not null default '{}'::jsonb,
  raised_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  resolved_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists penta_runtime.hold_crawler_observations_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  observation_key text not null unique,
  campaign_id text not null references penta_runtime.d3_campaign_bindings_v1(campaign_id),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  predicate_key text not null check (predicate_key in (
    'exact_head_ci','security_gate','independent_verifier','rollback_readback',
    'zero_cost_budget','provider_containment'
  )),
  status text not null check (status in ('PASS','HOLD','FAIL','UNKNOWN')),
  source_type text not null check (source_type in (
    'github_exact_head','security_gate','independent_verifier','rollback_readback',
    'budget_readback','provider_readback','component_readback'
  )),
  source_ref text not null,
  observer_id text not null,
  independent boolean not null default false,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now(),
  expires_at timestamptz not null,
  check (expires_at > observed_at)
);

create index if not exists hold_crawler_observations_lookup_v1
  on penta_runtime.hold_crawler_observations_v1(campaign_id,exact_head_sha,predicate_key,observed_at desc);

create table if not exists penta_runtime.hold_remediation_tasks_v1 (
  remediation_id uuid primary key default gen_random_uuid(),
  task_key text not null unique,
  campaign_id text not null references penta_runtime.d3_campaign_bindings_v1(campaign_id),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  predicate_key text not null,
  route_keys text[] not null,
  state text not null default 'queued' check (state in ('queued','claimed','completed','blocked','superseded')),
  action_class text not null default 'internal_reversible',
  provider_effect boolean not null default false check (not provider_effect),
  paid_cost_minor bigint not null default 0 check (paid_cost_minor = 0),
  certification_effect boolean not null default false check (not certification_effect),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_runtime.hold_resolutions_v1 (
  resolution_id uuid primary key default gen_random_uuid(),
  campaign_id text not null unique references penta_runtime.d3_campaign_bindings_v1(campaign_id),
  hand_id uuid not null references penta_runtime.hold_hands_v1(hand_id),
  baseline_id uuid not null references penta_runtime.runtime_release_baselines_v1(baseline_id),
  exact_head_sha text not null check (exact_head_sha ~ '^[0-9a-f]{40}$'),
  independent_verifier_ref text not null,
  resolution_evidence_sha256 text not null check (resolution_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  resolver_id text not null,
  self_certification boolean not null default false check (not self_certification),
  provider_effect boolean not null default false check (not provider_effect),
  resolved_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

alter table penta_runtime.hold_hands_v1 enable row level security;
alter table penta_runtime.hold_crawler_observations_v1 enable row level security;
alter table penta_runtime.hold_remediation_tasks_v1 enable row level security;
alter table penta_runtime.hold_resolutions_v1 enable row level security;

revoke all on penta_runtime.hold_hands_v1,
  penta_runtime.hold_crawler_observations_v1,
  penta_runtime.hold_remediation_tasks_v1,
  penta_runtime.hold_resolutions_v1 from public,anon,authenticated;
grant select,insert,update on penta_runtime.hold_hands_v1,
  penta_runtime.hold_crawler_observations_v1,
  penta_runtime.hold_remediation_tasks_v1,
  penta_runtime.hold_resolutions_v1 to service_role;

create or replace function penta_runtime.raise_hold_hand_v1(
  p_campaign_id text,
  p_exact_head_sha text,
  p_producer_ids text[] default '{}'::text[]
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  h penta_runtime.d3_campaign_holds_v1%rowtype;
  v_hand_id uuid;
begin
  if p_exact_head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'exact head must be lowercase Git SHA-1' using errcode='22023';
  end if;
  select * into h from penta_runtime.d3_campaign_holds_v1 where campaign_id=p_campaign_id;
  if not found then
    return jsonb_build_object('campaign_id',p_campaign_id,'state','NOT_REQUIRED','hand_raised',false);
  end if;

  insert into penta_runtime.hold_hands_v1(
    campaign_id,hold_evidence_sha256,exact_head_sha,producer_ids,state,metadata
  ) values(
    p_campaign_id,h.evidence_sha256,p_exact_head_sha,coalesce(p_producer_ids,'{}'::text[]),'raised',
    jsonb_build_object(
      'hold_reason',h.hold_reason,
      'held_by',h.held_by,
      'held_at',h.held_at,
      'hand_rule','remain_raised_until_independent_resolution_receipt',
      'authority_manufactured',false
    )
  ) on conflict(campaign_id) do update set
    exact_head_sha=excluded.exact_head_sha,
    producer_ids=excluded.producer_ids,
    last_seen_at=now(),
    state=case when penta_runtime.hold_hands_v1.state='resolved' then 'resolved' else 'raised' end,
    metadata=penta_runtime.hold_hands_v1.metadata||excluded.metadata
  returning hand_id into v_hand_id;

  return jsonb_build_object(
    'campaign_id',p_campaign_id,'hand_id',v_hand_id,'state','RAISED',
    'exact_head_sha',p_exact_head_sha,'provider_effect',false,'paid_cost_minor',0,
    'certification_effect',false
  );
end;
$function$;

create or replace function penta_runtime.record_hold_crawler_observation_v1(
  p_campaign_id text,
  p_exact_head_sha text,
  p_predicate_key text,
  p_status text,
  p_source_type text,
  p_source_ref text,
  p_observer_id text,
  p_independent boolean,
  p_evidence_sha256 text,
  p_expires_at timestamptz,
  p_payload jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  v_id uuid;
  v_key text;
begin
  if p_source_ref is null or btrim(p_source_ref)='' or p_observer_id is null or btrim(p_observer_id)='' then
    raise exception 'source_ref and observer_id are required' using errcode='22023';
  end if;
  v_key := p_campaign_id||':'||p_exact_head_sha||':'||p_predicate_key||':'||p_evidence_sha256;
  insert into penta_runtime.hold_crawler_observations_v1(
    observation_key,campaign_id,exact_head_sha,predicate_key,status,source_type,source_ref,
    observer_id,independent,evidence_sha256,payload,expires_at
  ) values(
    v_key,p_campaign_id,p_exact_head_sha,p_predicate_key,p_status,p_source_type,p_source_ref,
    p_observer_id,p_independent,p_evidence_sha256,coalesce(p_payload,'{}'::jsonb),p_expires_at
  ) on conflict(observation_key) do nothing
  returning observation_id into v_id;
  if v_id is null then
    select observation_id into v_id
    from penta_runtime.hold_crawler_observations_v1 where observation_key=v_key;
  end if;
  return v_id;
end;
$function$;

create or replace function penta_runtime.penta_hold_crawler_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  hand record;
  predicate text;
  routes text[];
  v_status text;
  v_predicates jsonb;
  v_all_pass boolean;
  v_hands integer := 0;
  v_tasks integer := 0;
begin
  for hand in
    select * from penta_runtime.hold_hands_v1 where state<>'resolved' for update skip locked
  loop
    v_hands := v_hands+1;
    v_predicates := '{}'::jsonb;
    v_all_pass := true;
    foreach predicate in array array[
      'exact_head_ci','security_gate','independent_verifier','rollback_readback',
      'zero_cost_budget','provider_containment'
    ] loop
      select case
        when o.status='PASS' and o.independent and not (o.observer_id=any(hand.producer_ids)) then 'PASS'
        when o.status is null then 'UNKNOWN'
        else o.status
      end into v_status
      from (select 1) seed
      left join lateral (
        select * from penta_runtime.hold_crawler_observations_v1 x
        where x.campaign_id=hand.campaign_id and x.exact_head_sha=hand.exact_head_sha
          and x.predicate_key=predicate and x.expires_at>now()
        order by x.observed_at desc limit 1
      ) o on true;
      v_status := coalesce(v_status,'UNKNOWN');
      v_predicates := v_predicates||jsonb_build_object(predicate,v_status);
      if v_status<>'PASS' then
        v_all_pass := false;
        routes := case predicate
          when 'exact_head_ci' then array['penta.crawler','penta.test','penta.help']
          when 'security_gate' then array['penta.crawler','penta.audit','penta.help']
          when 'independent_verifier' then array['penta.certify','penta.vergence','penta.help']
          when 'rollback_readback' then array['penta.test','penta.audit','penta.help']
          when 'zero_cost_budget' then array['penta.costs','smart.treasury','penta.help']
          else array['penta.crawler','penta.route','penta.help']
        end;
        insert into penta_runtime.hold_remediation_tasks_v1(
          task_key,campaign_id,exact_head_sha,predicate_key,route_keys
        ) values(
          hand.campaign_id||':'||hand.exact_head_sha||':'||predicate,
          hand.campaign_id,hand.exact_head_sha,predicate,routes
        ) on conflict(task_key) do update set
          state=case when penta_runtime.hold_remediation_tasks_v1.state='completed' then 'completed' else 'queued' end,
          route_keys=excluded.route_keys,updated_at=now();
        v_tasks := v_tasks+1;
      end if;
    end loop;
    update penta_runtime.hold_hands_v1 set
      current_predicates=v_predicates,
      state=case when v_all_pass then 'resolution_ready' else 'raised' end,
      last_seen_at=now()
    where hand_id=hand.hand_id;
  end loop;
  return jsonb_build_object(
    'service','ct.penta.hold-crawler.v1','hands_scanned',v_hands,
    'remediation_routes_observed',v_tasks,'provider_effect',false,
    'paid_cost_minor',0,'certification_effect',false,'at',now()
  );
end;
$function$;

create or replace function penta_runtime.resolve_hold_if_ready_v1(
  p_campaign_id text,
  p_resolver_id text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog'
as $function$
declare
  b penta_runtime.d3_campaign_bindings_v1%rowtype;
  hand penta_runtime.hold_hands_v1%rowtype;
  baseline penta_runtime.runtime_release_baselines_v1%rowtype;
  v_resolution_id uuid;
  v_digest text;
begin
  select * into strict b from penta_runtime.d3_campaign_bindings_v1 where campaign_id=p_campaign_id;
  select * into strict hand from penta_runtime.hold_hands_v1 where campaign_id=p_campaign_id for update;
  if hand.state<>'resolution_ready' then
    return jsonb_build_object('campaign_id',p_campaign_id,'state','HAND_REMAINS_RAISED','resolved',false);
  end if;
  select * into baseline
  from penta_runtime.runtime_release_baselines_v1 rb
  where rb.campaign_id=p_campaign_id and rb.exact_head_sha=hand.exact_head_sha
    and rb.state='verified' and rb.independent_verifier_ref is distinct from b.founder_ref
    and rb.verified_by is distinct from b.founder_ref and rb.rollback_ref<>''
  order by rb.verified_at desc limit 1;
  if not found or baseline.verified_by=any(hand.producer_ids)
    or baseline.independent_verifier_ref=any(hand.producer_ids) then
    return jsonb_build_object('campaign_id',p_campaign_id,'state','HAND_REMAINS_RAISED','resolved',false,
      'reason','independent exact-head verified baseline is absent');
  end if;
  if p_resolver_id is null or btrim(p_resolver_id)='' or p_resolver_id=any(hand.producer_ids) then
    raise exception 'resolver must be a distinct non-producing identity' using errcode='42501';
  end if;
  v_digest := encode(extensions.digest(
    concat_ws(':',p_campaign_id,hand.exact_head_sha,baseline.baseline_id::text,
      baseline.independent_verification_sha256,baseline.rollback_ref,p_resolver_id),
    'sha256'
  ),'hex');
  insert into penta_runtime.hold_resolutions_v1(
    campaign_id,hand_id,baseline_id,exact_head_sha,independent_verifier_ref,
    resolution_evidence_sha256,resolver_id,metadata
  ) values(
    p_campaign_id,hand.hand_id,baseline.baseline_id,hand.exact_head_sha,
    baseline.independent_verifier_ref,v_digest,p_resolver_id,
    jsonb_build_object('historical_hold_preserved',true,'runtime_activated',false,
      'provider_effect',false,'authority_manufactured',false)
  ) on conflict(campaign_id) do nothing
  returning resolution_id into v_resolution_id;
  update penta_runtime.hold_hands_v1 set state='resolved',resolved_at=now(),last_seen_at=now()
  where hand_id=hand.hand_id and exists(
    select 1 from penta_runtime.hold_resolutions_v1 r where r.campaign_id=p_campaign_id
  );
  return jsonb_build_object(
    'campaign_id',p_campaign_id,'resolution_id',v_resolution_id,'state','RESOLVED',
    'historical_hold_preserved',true,'runtime_activated',false,
    'provider_effect',false,'certification_effect',false
  );
end;
$function$;

create or replace function penta_runtime.campaign_hold_hand_status_v1(p_campaign_id text)
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog'
as $function$
  select coalesce((
    select jsonb_build_object(
      'campaign_id',h.campaign_id,'hand_id',h.hand_id,'hand_state',upper(h.state),
      'hand_raised',h.state<>'resolved','exact_head_sha',h.exact_head_sha,
      'predicates',h.current_predicates,'raised_at',h.raised_at,
      'last_seen_at',h.last_seen_at,'resolved_at',h.resolved_at,
      'historical_hold_preserved',true,
      'pending_remediations',(select count(*) from penta_runtime.hold_remediation_tasks_v1 t
        where t.campaign_id=h.campaign_id and t.state in ('queued','claimed','blocked'))
    ) from penta_runtime.hold_hands_v1 h where h.campaign_id=p_campaign_id
  ),jsonb_build_object('campaign_id',p_campaign_id,'hand_state','NOT_RAISED','hand_raised',false));
$function$;

revoke all on function penta_runtime.raise_hold_hand_v1(text,text,text[]) from public,anon,authenticated;
revoke all on function penta_runtime.record_hold_crawler_observation_v1(text,text,text,text,text,text,text,boolean,text,timestamptz,jsonb) from public,anon,authenticated;
revoke all on function penta_runtime.penta_hold_crawler_tick_v1() from public,anon,authenticated;
revoke all on function penta_runtime.resolve_hold_if_ready_v1(text,text) from public,anon,authenticated;
revoke all on function penta_runtime.campaign_hold_hand_status_v1(text) from public,anon,authenticated;
grant execute on function penta_runtime.raise_hold_hand_v1(text,text,text[]),
  penta_runtime.record_hold_crawler_observation_v1(text,text,text,text,text,text,text,boolean,text,timestamptz,jsonb),
  penta_runtime.penta_hold_crawler_tick_v1(),
  penta_runtime.resolve_hold_if_ready_v1(text,text),
  penta_runtime.campaign_hold_hand_status_v1(text) to service_role;

do $block$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='penta-hold-hand-crawler-v1' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('penta-hold-hand-crawler-v1','*/5 * * * *',
      'select penta_runtime.penta_hold_crawler_tick_v1();');
  else
    perform cron.alter_job(v_jobid,schedule=>'*/5 * * * *',
      command=>'select penta_runtime.penta_hold_crawler_tick_v1();',active=>true);
  end if;
end
$block$;

commit;
