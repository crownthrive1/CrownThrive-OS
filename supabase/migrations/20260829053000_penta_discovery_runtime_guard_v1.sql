-- PentaDiscovery runtime parity guard, autonomous watchdog, and certification interlock.
-- Stable contract remains 1.0.0; this is an additive operational hardening layer.

create table if not exists penta_runtime.penta_discovery_runtime_guard_state_v1 (
  runtime_component text primary key,
  expected_edge_slug text not null,
  expected_runtime_release text not null,
  expected_name text not null,
  expected_service text not null,
  expected_contract_version text not null,
  expected_stable_contract_version text not null,
  expected_economic_version text not null,
  expected_packet_protocol_version text not null,
  expected_verify_jwt boolean not null default true,
  expected_source_control_ref text not null,
  fail_closed boolean not null default true,
  active boolean not null default true,
  state text not null default 'HOLD'
    check (state in ('UNKNOWN','HOLD','WARMING','READY','DRIFT')),
  consecutive_passes integer not null default 0 check (consecutive_passes >= 0),
  consecutive_failures integer not null default 0 check (consecutive_failures >= 0),
  last_probe_key text,
  last_enqueued_at timestamptz,
  last_claimed_at timestamptz,
  last_probe_at timestamptz,
  last_pass_at timestamptz,
  last_failure_at timestamptz,
  last_http_status integer,
  last_response_sha256 text,
  last_observed jsonb not null default '{}'::jsonb,
  last_dispatch_request_id bigint,
  incident_id uuid references public.penta_incidents_v1(incident_id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_runtime.penta_discovery_runtime_probe_receipts_v1 (
  probe_id uuid primary key default gen_random_uuid(),
  probe_key text not null unique,
  runtime_component text not null references penta_runtime.penta_discovery_runtime_guard_state_v1(runtime_component),
  provider_status integer not null,
  passed boolean not null,
  failure_code text,
  expected jsonb not null,
  observed jsonb not null,
  response_sha256 text not null,
  target_request_id text,
  dail_receipt jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null unique,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  created_at timestamptz not null default clock_timestamp(),
  check (completed_at >= started_at),
  check (response_sha256 ~ '^[0-9a-f]{64}$'),
  check (evidence_sha256 ~ '^[0-9a-f]{64}$')
);

alter table penta_runtime.penta_discovery_runtime_guard_state_v1 enable row level security;
alter table penta_runtime.penta_discovery_runtime_probe_receipts_v1 enable row level security;

revoke all on penta_runtime.penta_discovery_runtime_guard_state_v1 from public, anon, authenticated;
revoke all on penta_runtime.penta_discovery_runtime_probe_receipts_v1 from public, anon, authenticated;
grant select,insert,update on penta_runtime.penta_discovery_runtime_guard_state_v1 to service_role;
grant select,insert on penta_runtime.penta_discovery_runtime_probe_receipts_v1 to service_role;

create or replace function penta_runtime.reject_penta_discovery_probe_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $$
begin
  raise exception 'PENTA_DISCOVERY_RUNTIME_PROBE_RECEIPTS_APPEND_ONLY';
end
$$;

revoke all on function penta_runtime.reject_penta_discovery_probe_receipt_mutation_v1() from public, anon, authenticated;

DROP TRIGGER IF EXISTS penta_discovery_probe_receipts_append_only_v1
  ON penta_runtime.penta_discovery_runtime_probe_receipts_v1;
create trigger penta_discovery_probe_receipts_append_only_v1
before update or delete on penta_runtime.penta_discovery_runtime_probe_receipts_v1
for each row execute function penta_runtime.reject_penta_discovery_probe_receipt_mutation_v1();

insert into penta_runtime.penta_discovery_runtime_guard_state_v1(
  runtime_component,
  expected_edge_slug,
  expected_runtime_release,
  expected_name,
  expected_service,
  expected_contract_version,
  expected_stable_contract_version,
  expected_economic_version,
  expected_packet_protocol_version,
  expected_verify_jwt,
  expected_source_control_ref,
  fail_closed,
  active,
  state,
  incident_id,
  metadata
)
values (
  'penta-discovery-edge',
  'penta-discovery',
  'ct.penta.discovery.runtime.2.0.0',
  'PentaDiscovery',
  'ct.penta.discovery.family.v2',
  '2.0.0',
  '1.0.0',
  '2.0.0',
  '3.0.0',
  true,
  'github:crownthrive1/CrownThrive-OS:main:supabase/functions/penta-discovery/index.ts',
  true,
  true,
  'HOLD',
  (
    select incident_id
    from public.penta_incidents_v1
    where system_key='penta.discovery'
      and incident_code='PENTA_DISCOVERY_RUNTIME_DRIFT'
      and state<>'resolved'
    order by opened_at desc
    limit 1
  ),
  jsonb_build_object(
    'watchdog_edge_slug','penta-discovery-runtime-watchdog',
    'watchdog_contract','ct.penta.discovery.runtime-watchdog.v1',
    'required_consecutive_passes',2,
    'incident_resolution_passes',3,
    'freshness_seconds',180,
    'authority_manufacture',false,
    'provider_money_movement',false
  )
)
on conflict (runtime_component) do update
set expected_edge_slug=excluded.expected_edge_slug,
    expected_runtime_release=excluded.expected_runtime_release,
    expected_name=excluded.expected_name,
    expected_service=excluded.expected_service,
    expected_contract_version=excluded.expected_contract_version,
    expected_stable_contract_version=excluded.expected_stable_contract_version,
    expected_economic_version=excluded.expected_economic_version,
    expected_packet_protocol_version=excluded.expected_packet_protocol_version,
    expected_verify_jwt=excluded.expected_verify_jwt,
    expected_source_control_ref=excluded.expected_source_control_ref,
    fail_closed=true,
    active=true,
    state=case
      when penta_discovery_runtime_guard_state_v1.state='READY' then 'HOLD'
      else penta_discovery_runtime_guard_state_v1.state
    end,
    consecutive_passes=0,
    incident_id=coalesce(penta_discovery_runtime_guard_state_v1.incident_id,excluded.incident_id),
    metadata=penta_discovery_runtime_guard_state_v1.metadata||excluded.metadata,
    updated_at=clock_timestamp();

create or replace function penta_runtime.penta_discovery_watchdog_claim_probe_v1(
  p_probe_key text,
  p_min_interval_seconds integer default 20
)
returns jsonb
language plpgsql
set search_path to 'pg_catalog','penta_runtime'
as $$
declare
  s penta_runtime.penta_discovery_runtime_guard_state_v1%rowtype;
  v_min integer := greatest(10,least(coalesce(p_min_interval_seconds,20),300));
begin
  if p_probe_key is null or length(p_probe_key)<16 or length(p_probe_key)>300 then
    raise exception 'PENTA_DISCOVERY_WATCHDOG_PROBE_KEY_INVALID';
  end if;

  select * into s
  from penta_runtime.penta_discovery_runtime_guard_state_v1
  where runtime_component='penta-discovery-edge'
  for update;

  if not found then
    raise exception 'PENTA_DISCOVERY_RUNTIME_GUARD_NOT_CONFIGURED';
  end if;
  if not s.active then
    return jsonb_build_object('claimed',false,'reason','WATCHDOG_DISABLED');
  end if;
  if s.last_claimed_at is not null
     and s.last_claimed_at > clock_timestamp()-make_interval(secs=>v_min) then
    return jsonb_build_object(
      'claimed',false,
      'reason','PROBE_RATE_LIMITED',
      'last_claimed_at',s.last_claimed_at,
      'minimum_interval_seconds',v_min
    );
  end if;

  update penta_runtime.penta_discovery_runtime_guard_state_v1
  set last_probe_key=p_probe_key,
      last_claimed_at=clock_timestamp(),
      updated_at=clock_timestamp()
  where runtime_component=s.runtime_component;

  return jsonb_build_object(
    'claimed',true,
    'runtime_component',s.runtime_component,
    'expected',jsonb_build_object(
      'edge_slug',s.expected_edge_slug,
      'runtime_release',s.expected_runtime_release,
      'name',s.expected_name,
      'service',s.expected_service,
      'contract_version',s.expected_contract_version,
      'stable_contract_version',s.expected_stable_contract_version,
      'economic_version',s.expected_economic_version,
      'packet_protocol_version',s.expected_packet_protocol_version,
      'verify_jwt',s.expected_verify_jwt
    ),
    'fail_closed',s.fail_closed
  );
end
$$;

revoke all on function penta_runtime.penta_discovery_watchdog_claim_probe_v1(text,integer) from public, anon, authenticated;
grant execute on function penta_runtime.penta_discovery_watchdog_claim_probe_v1(text,integer) to service_role;

create or replace function penta_runtime.penta_discovery_watchdog_record_probe_v1(
  p_probe_key text,
  p_provider_status integer,
  p_passed boolean,
  p_failure_code text,
  p_observed jsonb,
  p_response_sha256 text,
  p_target_request_id text,
  p_started_at timestamptz,
  p_completed_at timestamptz
)
returns jsonb
language plpgsql
set search_path to 'pg_catalog','penta_runtime','public','extensions'
as $$
declare
  s penta_runtime.penta_discovery_runtime_guard_state_v1%rowtype;
  v_expected jsonb;
  v_observed jsonb := coalesce(p_observed,'{}'::jsonb);
  v_payload jsonb;
  v_evidence_sha text;
  v_dail jsonb := '{}'::jsonb;
  v_passes integer;
  v_failures integer;
  v_state text;
  v_incident uuid;
  v_fingerprint text;
begin
  if p_probe_key is null or length(p_probe_key)<16 or length(p_probe_key)>300 then
    raise exception 'PENTA_DISCOVERY_WATCHDOG_PROBE_KEY_INVALID';
  end if;
  if p_response_sha256 is null or p_response_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'PENTA_DISCOVERY_WATCHDOG_RESPONSE_DIGEST_INVALID';
  end if;
  if p_started_at is null or p_completed_at is null or p_completed_at<p_started_at then
    raise exception 'PENTA_DISCOVERY_WATCHDOG_TIME_INVALID';
  end if;

  select * into s
  from penta_runtime.penta_discovery_runtime_guard_state_v1
  where runtime_component='penta-discovery-edge'
  for update;

  if not found then
    raise exception 'PENTA_DISCOVERY_RUNTIME_GUARD_NOT_CONFIGURED';
  end if;
  if s.last_probe_key is distinct from p_probe_key then
    raise exception 'PENTA_DISCOVERY_WATCHDOG_PROBE_NOT_CLAIMED';
  end if;

  v_expected:=jsonb_build_object(
    'edge_slug',s.expected_edge_slug,
    'runtime_release',s.expected_runtime_release,
    'name',s.expected_name,
    'service',s.expected_service,
    'contract_version',s.expected_contract_version,
    'stable_contract_version',s.expected_stable_contract_version,
    'economic_version',s.expected_economic_version,
    'packet_protocol_version',s.expected_packet_protocol_version,
    'verify_jwt',s.expected_verify_jwt,
    'source_control_ref',s.expected_source_control_ref
  );
  v_payload:=jsonb_build_object(
    'probe_key',p_probe_key,
    'runtime_component',s.runtime_component,
    'provider_status',coalesce(p_provider_status,0),
    'passed',coalesce(p_passed,false),
    'failure_code',nullif(left(coalesce(p_failure_code,''),500),''),
    'expected',v_expected,
    'observed',v_observed,
    'response_sha256',p_response_sha256,
    'target_request_id',nullif(left(coalesce(p_target_request_id,''),300),''),
    'started_at',p_started_at,
    'completed_at',p_completed_at,
    'authority_created',false,
    'provider_write_performed',false,
    'provider_money_movement',false
  );
  v_evidence_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

  begin
    v_dail:=public.chlom_append_dail_event(
      p_event_type=>case when coalesce(p_passed,false)
        then 'penta.discovery.runtime.guard.pass'
        else 'penta.discovery.runtime.guard.drift' end,
      p_entity_type=>'penta_runtime_guard',
      p_entity_id=>p_probe_key,
      p_payload=>v_payload,
      p_actor_ref=>'PentaDiscoveryRuntimeWatchdog',
      p_actor_did=>null,
      p_agent_id=>'ct.agent.penta-discovery-runtime-watchdog',
      p_entity_version=>'1.0.0',
      p_correlation_id=>p_probe_key,
      p_causation_id=>null,
      p_authority_basis=>'ct.penta.discovery.runtime-guard.v1',
      p_approval_id=>null,
      p_visibility_class=>'internal'
    );
  exception when others then
    v_dail:=jsonb_build_object('recorded',false,'reason','DAIL_APPEND_FAILED','error',left(sqlerrm,300));
  end;

  insert into penta_runtime.penta_discovery_runtime_probe_receipts_v1(
    probe_key,runtime_component,provider_status,passed,failure_code,
    expected,observed,response_sha256,target_request_id,dail_receipt,
    evidence_sha256,started_at,completed_at
  ) values (
    p_probe_key,s.runtime_component,coalesce(p_provider_status,0),coalesce(p_passed,false),
    nullif(left(coalesce(p_failure_code,''),500),''),v_expected,v_observed,p_response_sha256,
    nullif(left(coalesce(p_target_request_id,''),300),''),v_dail,v_evidence_sha,p_started_at,p_completed_at
  ) on conflict (probe_key) do nothing;

  if coalesce(p_passed,false) then
    v_passes:=s.consecutive_passes+1;
    v_failures:=0;
    v_state:=case when v_passes>=2 then 'READY' else 'WARMING' end;
  else
    v_passes:=0;
    v_failures:=s.consecutive_failures+1;
    v_state:='DRIFT';
  end if;

  v_incident:=s.incident_id;
  if not coalesce(p_passed,false) then
    if v_incident is null or not exists(
      select 1 from public.penta_incidents_v1 i
      where i.incident_id=v_incident and i.state<>'resolved'
    ) then
      v_fingerprint:=encode(extensions.digest(convert_to(
        'penta-discovery-runtime-drift:'||s.expected_runtime_release,'UTF8'
      ),'sha256'),'hex');
      select i.incident_id into v_incident
      from public.penta_incidents_v1 i
      where i.system_key='penta.discovery'
        and i.incident_code='PENTA_DISCOVERY_RUNTIME_DRIFT'
        and i.state<>'resolved'
      order by i.opened_at desc limit 1;
      if v_incident is null then
        insert into public.penta_incidents_v1(
          system_key,incident_code,severity,priority,state,source_event_ref,
          fingerprint,title,summary,failure_evidence,remediation_state
        ) values (
          'penta.discovery','PENTA_DISCOVERY_RUNTIME_DRIFT','CRITICAL','P0','remediating',
          'penta-runtime-watchdog:'||p_probe_key,v_fingerprint,
          'PentaDiscovery runtime parity failed',
          'The autonomous runtime watchdog could not verify the canonical PentaDiscovery contract; certification and governed dispatch are fail-closed.',
          v_payload,'watchdog_detected'
        ) returning incident_id into v_incident;
      else
        update public.penta_incidents_v1
        set state='remediating',severity='CRITICAL',priority='P0',
            failure_evidence=coalesce(failure_evidence,'{}'::jsonb)||v_payload,
            remediation_state='watchdog_detected',updated_at=clock_timestamp()
        where incident_id=v_incident;
      end if;
    end if;

    insert into public.penta_flags_v1(incident_id,flag_key,severity,reason,evidence)
    values (
      v_incident,'penta.discovery.runtime.fail_closed','CRITICAL',
      'Canonical PentaDiscovery runtime attestation failed; certification and dispatch must remain held.',
      v_payload
    ) on conflict (incident_id,flag_key) do nothing;

    insert into public.penta_remediation_actions_v1(incident_id,handler_key,state,evidence)
    select v_incident,'PentaSELF→PentaFactory→PentaCertify','planned',jsonb_build_object(
      'required_actions',jsonb_build_array(
        'restore_canonical_edge_bundle','read_after_write','two_consecutive_watchdog_passes','full_chain_recertification'
      ),
      'authority_expansion',false,
      'provider_money_movement',false,
      'source_probe_key',p_probe_key
    )
    where not exists(
      select 1 from public.penta_remediation_actions_v1 r
      where r.incident_id=v_incident
        and r.handler_key='PentaSELF→PentaFactory→PentaCertify'
        and r.state in ('planned','applied')
    );
  elsif v_incident is not null and v_passes>=2 then
    update public.penta_incidents_v1
    set state=case when v_passes>=3 then 'resolved' else 'verification' end,
        remediation_state=case when v_passes>=3 then 'verified_and_resolved' else 'canonical_runtime_restored' end,
        remediation_evidence=coalesce(remediation_evidence,'{}'::jsonb)||jsonb_build_object(
          'latest_probe_key',p_probe_key,'consecutive_passes',v_passes,'response_sha256',p_response_sha256
        ),
        verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||v_payload,
        resolved_at=case when v_passes>=3 then clock_timestamp() else resolved_at end,
        updated_at=clock_timestamp()
    where incident_id=v_incident;

    update public.penta_remediation_actions_v1
    set state=case when v_passes>=3 then 'applied' else state end,
        evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object(
          'latest_probe_key',p_probe_key,'consecutive_passes',v_passes,'runtime_state',v_state
        )
    where incident_id=v_incident
      and handler_key='PentaSELF→PentaFactory→PentaCertify'
      and state in ('planned','applied');
  end if;

  update penta_runtime.penta_discovery_runtime_guard_state_v1
  set state=v_state,
      consecutive_passes=v_passes,
      consecutive_failures=v_failures,
      last_probe_at=p_completed_at,
      last_pass_at=case when coalesce(p_passed,false) then p_completed_at else last_pass_at end,
      last_failure_at=case when coalesce(p_passed,false) then last_failure_at else p_completed_at end,
      last_http_status=coalesce(p_provider_status,0),
      last_response_sha256=p_response_sha256,
      last_observed=v_observed,
      incident_id=v_incident,
      updated_at=clock_timestamp()
  where runtime_component=s.runtime_component;

  update public.penta_system_registry
  set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'runtime_guard','ct.penta.discovery.runtime-guard.v1',
        'runtime_guard_state',v_state,
        'runtime_guard_probe_key',p_probe_key,
        'runtime_guard_last_probe_at',p_completed_at,
        'runtime_guard_consecutive_passes',v_passes,
        'runtime_guard_consecutive_failures',v_failures,
        'runtime_guard_fail_closed',true
      ),
      last_verified_at=case when v_state='READY' then p_completed_at else last_verified_at end,
      updated_at=clock_timestamp()
  where system_key='penta.discovery';

  return jsonb_build_object(
    'runtime_component',s.runtime_component,
    'state',v_state,
    'ready',v_state='READY',
    'consecutive_passes',v_passes,
    'consecutive_failures',v_failures,
    'probe_key',p_probe_key,
    'probe_evidence_sha256',v_evidence_sha,
    'dail_receipt',v_dail,
    'incident_id',v_incident,
    'authority_created',false,
    'provider_money_movement',false
  );
end
$$;

revoke all on function penta_runtime.penta_discovery_watchdog_record_probe_v1(text,integer,boolean,text,jsonb,text,text,timestamptz,timestamptz) from public, anon, authenticated;
grant execute on function penta_runtime.penta_discovery_watchdog_record_probe_v1(text,integer,boolean,text,jsonb,text,text,timestamptz,timestamptz) to service_role;

create or replace function penta_runtime.penta_discovery_runtime_guard_status_v1()
returns jsonb
language sql
stable
set search_path to 'pg_catalog','penta_runtime'
as $$
  select jsonb_build_object(
    'runtime_component',s.runtime_component,
    'state',s.state,
    'ready',(
      s.active
      and s.state='READY'
      and s.consecutive_passes>=2
      and s.last_pass_at is not null
      and s.last_pass_at>=clock_timestamp()-interval '3 minutes'
    ),
    'active',s.active,
    'fail_closed',s.fail_closed,
    'expected_edge_slug',s.expected_edge_slug,
    'expected_runtime_release',s.expected_runtime_release,
    'expected_source_control_ref',s.expected_source_control_ref,
    'consecutive_passes',s.consecutive_passes,
    'consecutive_failures',s.consecutive_failures,
    'last_probe_at',s.last_probe_at,
    'last_pass_at',s.last_pass_at,
    'last_failure_at',s.last_failure_at,
    'last_http_status',s.last_http_status,
    'last_response_sha256',s.last_response_sha256,
    'last_observed',s.last_observed,
    'incident_id',s.incident_id,
    'watchdog_schedule','* * * * *',
    'freshness_seconds',180,
    'authority_created',false,
    'provider_money_movement',false
  )
  from penta_runtime.penta_discovery_runtime_guard_state_v1 s
  where s.runtime_component='penta-discovery-edge'
$$;

revoke all on function penta_runtime.penta_discovery_runtime_guard_status_v1() from public, anon, authenticated;
grant execute on function penta_runtime.penta_discovery_runtime_guard_status_v1() to service_role;

create or replace function penta_runtime.assert_penta_discovery_runtime_ready_v1()
returns void
language plpgsql
set search_path to 'pg_catalog','penta_runtime'
as $$
declare v_status jsonb;
begin
  v_status:=penta_runtime.penta_discovery_runtime_guard_status_v1();
  if coalesce((v_status->>'ready')::boolean,false) is not true then
    raise exception 'PENTA_DISCOVERY_RUNTIME_NOT_CERTIFIED %',v_status;
  end if;
end
$$;

revoke all on function penta_runtime.assert_penta_discovery_runtime_ready_v1() from public, anon, authenticated;
grant execute on function penta_runtime.assert_penta_discovery_runtime_ready_v1() to service_role;

create or replace function penta_runtime.enforce_penta_discovery_runtime_guard_on_cert_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','penta_runtime'
as $$
begin
  if upper(coalesce(new.verdict,''))='PASS' then
    perform penta_runtime.assert_penta_discovery_runtime_ready_v1();
  end if;
  return new;
end
$$;

revoke all on function penta_runtime.enforce_penta_discovery_runtime_guard_on_cert_v1() from public, anon, authenticated;

DROP TRIGGER IF EXISTS penta_discovery_cert_v2_runtime_guard_v1
  ON penta_runtime.penta_discovery_certifications_v2;
create trigger penta_discovery_cert_v2_runtime_guard_v1
before insert on penta_runtime.penta_discovery_certifications_v2
for each row execute function penta_runtime.enforce_penta_discovery_runtime_guard_on_cert_v1();

create or replace function penta_runtime.penta_discovery_watchdog_dispatch_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_runtime','net'
as $$
declare
  v_request_id bigint;
begin
  select net.http_post(
    url:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-discovery-runtime-watchdog',
    headers:=jsonb_build_object(
      'content-type','application/json',
      'x-crownthrive-source','PentaTime:ct-penta-discovery-runtime-watchdog-v1'
    ),
    body:=jsonb_build_object(
      'action','probe',
      'requested_at',clock_timestamp(),
      'authority_created',false,
      'provider_money_movement',false
    ),
    timeout_milliseconds:=30000
  ) into v_request_id;

  update penta_runtime.penta_discovery_runtime_guard_state_v1
  set last_enqueued_at=clock_timestamp(),
      last_dispatch_request_id=v_request_id,
      updated_at=clock_timestamp()
  where runtime_component='penta-discovery-edge';

  return jsonb_build_object(
    'state','REQUESTED',
    'request_id',v_request_id,
    'watchdog_edge_slug','penta-discovery-runtime-watchdog',
    'authority_created',false,
    'provider_money_movement',false,
    'requested_at',clock_timestamp()
  );
end
$$;

revoke all on function penta_runtime.penta_discovery_watchdog_dispatch_v1() from public, anon, authenticated;
grant execute on function penta_runtime.penta_discovery_watchdog_dispatch_v1() to service_role;

DO $schedule$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-penta-discovery-runtime-watchdog-v1';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'ct-penta-discovery-runtime-watchdog-v1',
    '* * * * *',
    'select penta_runtime.penta_discovery_watchdog_dispatch_v1();'
  );
end
$schedule$;

update public.penta_system_registry
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'runtime_guard','ct.penta.discovery.runtime-guard.v1',
      'runtime_watchdog_edge','penta-discovery-runtime-watchdog',
      'runtime_watchdog_schedule','* * * * *',
      'runtime_guard_fail_closed',true,
      'runtime_guard_required_for_certification',true,
      'runtime_guard_required_consecutive_passes',2,
      'runtime_guard_freshness_seconds',180,
      'runtime_drift_incident_id','451152e0-f253-4665-8b1c-7ac80e3c2b6c'
    ),
    updated_at=clock_timestamp()
where system_key='penta.discovery';

select penta_runtime.penta_discovery_runtime_guard_status_v1();
