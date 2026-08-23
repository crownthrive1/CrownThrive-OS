-- CrownThrive Agent A Emergency Execution Bridge v2
-- Public-safe source migration. Protected algorithm bodies/weights are not present.
-- Authority boundary: D0-D2 controlled-test only. No provider write, money movement,
-- rights grant, D3, sovereign vote, direct-main merge, or silent delete.

begin;

create table if not exists chlom_runtime.gen7_stale_packet_actions(
  action_id uuid primary key default gen_random_uuid(),
  action_key text not null unique,
  cycle_id text not null,
  packet_id text not null,
  lifecycle_state text not null,
  actor_agent_id text not null,
  target_agent_id text,
  verifier_agent_id text,
  action_type text not null check(action_type in ('rebind_current_executor','verifier_rearm','replan_escalation','no_action')),
  stale_seconds integer not null,
  retry_count_before integer not null,
  retry_count_after integer not null,
  action_state text not null check(action_state in ('done','hold','error','noop')),
  result jsonb not null default '{}'::jsonb,
  evidence_refs text[] not null default '{}',
  action_sha256 text not null check(action_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);
alter table chlom_runtime.gen7_stale_packet_actions enable row level security;
alter table chlom_runtime.gen7_stale_packet_actions force row level security;
revoke all on chlom_runtime.gen7_stale_packet_actions from public,anon,authenticated;
grant select,insert on chlom_runtime.gen7_stale_packet_actions to service_role;

create or replace function chlom_runtime.reject_gen7_stale_action_delete()
returns trigger language plpgsql as $$ begin raise exception 'gen7_stale_packet_actions_append_only'; end $$;
drop trigger if exists trg_reject_gen7_stale_packet_actions_delete on chlom_runtime.gen7_stale_packet_actions;
create trigger trg_reject_gen7_stale_packet_actions_delete
before delete on chlom_runtime.gen7_stale_packet_actions
for each row execute function chlom_runtime.reject_gen7_stale_action_delete();

create or replace function chlom_runtime.gen7_actuate_stale_portfolio_v2(
  p_cycle_id text,
  p_stale_seconds integer default 1800
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime','extensions'
as $$
declare
  r chlom_runtime.gen6_dispatch_decisions%rowtype;
  v_now timestamptz:=clock_timestamp();
  v_stale integer;
  v_action text;
  v_key text;
  v_hash text;
  v_result jsonb;
  v_actions jsonb:='[]'::jsonb;
  v_done integer:=0;
  v_hold integer:=0;
  v_error integer:=0;
  v_run_id text;
  v_retry_after integer;
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if coalesce(trim(p_cycle_id),'')='' then raise exception 'cycle_id_required'; end if;
  perform pg_advisory_xact_lock(hashtext('chlom_runtime.gen7.stale.actuator.v2'));

  perform chlom_runtime.gen7_observe_stale_running_packets(p_stale_seconds);

  for r in
    select * from chlom_runtime.gen6_dispatch_decisions
    where lifecycle_state in ('running','verifying')
    order by priority_score desc,created_at asc
  loop
    v_stale:=greatest(0,extract(epoch from(v_now-coalesce(r.last_progress_at,r.started_at,r.verifying_at,r.updated_at)))::integer);
    if v_stale < greatest(300,p_stale_seconds) then continue; end if;

    if r.lifecycle_state='running' and r.retry_count<2 then
      v_action:='rebind_current_executor';
    elsif r.lifecycle_state='verifying' then
      v_action:='verifier_rearm';
    else
      v_action:='replan_escalation';
    end if;

    v_key:=encode(extensions.digest(convert_to(r.packet_id||'|'||v_action||'|'||date_trunc('hour',v_now)::text,'UTF8'),'sha256'),'hex');
    if exists(select 1 from chlom_runtime.gen7_stale_packet_actions where action_key=v_key) then continue; end if;

    begin
      if v_action='rebind_current_executor' then
        v_result:=chlom_runtime.gen6_rebind_running_packet(
          r.packet_id,'ct.relay.agent-a',r.owner_agent_id,r.verifier_agent_id,
          p_cycle_id||':rebind:'||replace(r.packet_id,'ct.packet.gen6.',''),
          'Gen-7 stale actuator v2: re-arm the already-governed scheduled owner/verifier without changing packet progress or blockers.',
          'ct.gen7.stale-actuator.v2',p_stale_seconds
        );
        select retry_count into v_retry_after from chlom_runtime.gen6_dispatch_decisions where packet_id=r.packet_id;
        v_done:=v_done+1;
      elsif v_action='verifier_rearm' then
        v_run_id:=p_cycle_id||':verifier-rearm:'||replace(r.packet_id,'ct.packet.gen6.','');
        v_result:=chlom_runtime.gen6_record_agent_heartbeat(
          v_run_id,p_cycle_id,r.verifier_agent_id,r.packet_id,'verifier','verifying',r.progress_percent,0,
          array['ct.gen7.stale-actuator.v2','packet:'||r.packet_id],
          jsonb_build_object('stale_seconds',v_stale,'review_rearmed',true,'progress_preserved',r.progress_percent,'blockers_preserved',r.current_blocker_count),
          'Gen-7 stale actuator v2 re-armed the independent verifier; review evidence is required before any transition.',null,'live'
        );
        update chlom_runtime.gen6_dispatch_decisions
           set last_transition_reason='stale_verifier_rearmed_v2: independent review still required',updated_at=v_now
         where packet_id=r.packet_id;
        v_retry_after:=r.retry_count;
        v_done:=v_done+1;
      else
        v_run_id:=p_cycle_id||':replan:'||replace(r.packet_id,'ct.packet.gen6.','');
        v_result:=chlom_runtime.gen6_record_agent_heartbeat(
          v_run_id,p_cycle_id,'ct.relay.agent-a',r.packet_id,'orchestrator','running',r.progress_percent,0,
          array['ct.gen7.stale-actuator.v2','packet:'||r.packet_id],
          jsonb_build_object('stale_seconds',v_stale,'retry_count',r.retry_count,'replan_required',true,'progress_preserved',r.progress_percent,'blockers_preserved',r.current_blocker_count),
          'Gen-7 stale actuator v2 escalated packet for bounded replan because scheduled continuation attempts did not produce material progress.',null,'live'
        );
        update chlom_runtime.gen6_dispatch_decisions
           set last_transition_reason='replan_required_v2: stale after governed continuation attempts',updated_at=v_now
         where packet_id=r.packet_id;
        v_retry_after:=r.retry_count;
        v_hold:=v_hold+1;
      end if;

      v_hash:=encode(extensions.digest(convert_to(v_key||'|'||coalesce(v_result,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
      insert into chlom_runtime.gen7_stale_packet_actions(
        action_key,cycle_id,packet_id,lifecycle_state,actor_agent_id,target_agent_id,verifier_agent_id,
        action_type,stale_seconds,retry_count_before,retry_count_after,action_state,result,evidence_refs,action_sha256
      ) values(
        v_key,p_cycle_id,r.packet_id,r.lifecycle_state,'ct.relay.agent-a',r.owner_agent_id,r.verifier_agent_id,
        v_action,v_stale,r.retry_count,coalesce(v_retry_after,r.retry_count),case when v_action='replan_escalation' then 'hold' else 'done' end,
        coalesce(v_result,'{}'::jsonb),array['ct.gen7.stale-actuator.v2','packet:'||r.packet_id],v_hash
      );
      v_actions:=v_actions||jsonb_build_array(jsonb_build_object('packet_id',r.packet_id,'action',v_action,'stale_seconds',v_stale,'retry_before',r.retry_count,'retry_after',coalesce(v_retry_after,r.retry_count),'result',v_result));
    exception when others then
      v_error:=v_error+1;
      v_hash:=encode(extensions.digest(convert_to(v_key||'|ERROR|'||sqlerrm,'UTF8'),'sha256'),'hex');
      insert into chlom_runtime.gen7_stale_packet_actions(
        action_key,cycle_id,packet_id,lifecycle_state,actor_agent_id,target_agent_id,verifier_agent_id,
        action_type,stale_seconds,retry_count_before,retry_count_after,action_state,result,evidence_refs,action_sha256
      ) values(
        v_key,p_cycle_id,r.packet_id,r.lifecycle_state,'ct.relay.agent-a',r.owner_agent_id,r.verifier_agent_id,
        v_action,v_stale,r.retry_count,r.retry_count,'error',jsonb_build_object('error',sqlerrm),array['ct.gen7.stale-actuator.v2','packet:'||r.packet_id],v_hash
      ) on conflict(action_key) do nothing;
      v_actions:=v_actions||jsonb_build_array(jsonb_build_object('packet_id',r.packet_id,'action',v_action,'error',sqlerrm));
    end;
  end loop;

  perform chlom_runtime.append_dail_event(
    'gen7.stale_portfolio.actuated','agent_portfolio',p_cycle_id,
    jsonb_build_object('cycle_id',p_cycle_id,'threshold_seconds',p_stale_seconds,'actions',v_actions,'done_actions',v_done,'hold_actions',v_hold,'errors',v_error,'progress_fabricated',false,'provider_write_performed',false,'D3_auto',false,'sovereign_vote_effect',false),
    'ct.relay.agent-a',null,'ct.relay.agent-a','2.0.0',p_cycle_id,null,
    'Gen-7 stale portfolio actuator v2. Rebind/rearm/escalation only; progress and blocker reductions require new evidence.',null,'restricted'
  );

  return jsonb_build_object('cycle_id',p_cycle_id,'threshold_seconds',p_stale_seconds,'actions',v_actions,'done_actions',v_done,'hold_actions',v_hold,'errors',v_error,'progress_fabricated',false);
end $$;

create or replace function chlom_runtime.gen6_record_agent_heartbeat(
  p_run_id text,p_cycle_id text,p_agent_id text,p_packet_id text,p_role_type text,p_run_state text,
  p_progress numeric default 0,p_work_units integer default 0,p_evidence_refs text[] default '{}'::text[],
  p_metrics jsonb default '{}'::jsonb,p_reason text default null,p_error_code text default null,p_run_kind text default 'live'
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime'
as $$
declare
  v_now timestamptz:=clock_timestamp();
  v_exists boolean;
  v_health text;
  v_ttl integer:=3600;
begin
  select exists(select 1 from chlom_runtime.agent_templates where agent_id=p_agent_id),
         coalesce((select heartbeat_ttl_seconds from chlom_runtime.agent_templates where agent_id=p_agent_id),3600)
    into v_exists,v_ttl;
  if not v_exists then raise exception 'unknown_agent_identity'; end if;
  if p_run_state not in ('planned','running','verifying','done','blocked','error','noop','cancelled') then raise exception 'invalid_run_state'; end if;
  if p_progress<0 or p_progress>100 then raise exception 'invalid_progress'; end if;

  insert into chlom_runtime.gen6_agent_runs(
    run_id,cycle_id,agent_id,packet_id,role_type,run_kind,run_state,started_at,last_heartbeat_at,completed_at,
    progress_percent,work_units_completed,evidence_refs,transition_reason,error_code,metrics,created_at,updated_at
  ) values(
    p_run_id,p_cycle_id,p_agent_id,p_packet_id,p_role_type,p_run_kind,p_run_state,
    case when p_run_state in ('running','verifying','done','blocked','error','noop') then v_now else null end,
    v_now,case when p_run_state in ('done','blocked','error','noop','cancelled') then v_now else null end,
    p_progress,p_work_units,coalesce(p_evidence_refs,'{}'::text[]),p_reason,p_error_code,
    coalesce(p_metrics,'{}'::jsonb)||jsonb_build_object('heartbeat_ttl_seconds',v_ttl,'heartbeat_fresh_until',v_now+make_interval(secs=>v_ttl)),v_now,v_now
  ) on conflict(run_id) do update set
    run_state=excluded.run_state,last_heartbeat_at=v_now,
    completed_at=case when excluded.run_state in ('done','blocked','error','noop','cancelled') then v_now else chlom_runtime.gen6_agent_runs.completed_at end,
    progress_percent=excluded.progress_percent,
    work_units_completed=greatest(chlom_runtime.gen6_agent_runs.work_units_completed,excluded.work_units_completed),
    evidence_refs=case when cardinality(excluded.evidence_refs)>0 then excluded.evidence_refs else chlom_runtime.gen6_agent_runs.evidence_refs end,
    transition_reason=excluded.transition_reason,error_code=excluded.error_code,
    metrics=chlom_runtime.gen6_agent_runs.metrics||excluded.metrics,updated_at=v_now;

  if p_run_kind<>'canary' then
    v_health:=case when p_run_state='error' then 'failed' when p_run_state='blocked' then 'degraded' else 'healthy' end;
    insert into chlom_runtime.agent_health(agent_id,run_id,health_state,current_task,last_heartbeat_at,last_success_at,last_error_code,resource_state,updated_at)
    values(
      p_agent_id,p_run_id,v_health,p_packet_id,v_now,case when p_run_state in ('done','noop') then v_now else null end,p_error_code,
      jsonb_build_object('gen6_cycle_id',p_cycle_id,'run_state',p_run_state,'progress_percent',p_progress,'work_units',p_work_units,'telemetry_source','gen6_first_class','live_heartbeat_observed',true,'heartbeat_fresh',true,'heartbeat_ttl_seconds',v_ttl,'heartbeat_fresh_until',v_now+make_interval(secs=>v_ttl)),v_now
    ) on conflict(agent_id) do update set
      run_id=excluded.run_id,health_state=excluded.health_state,current_task=excluded.current_task,last_heartbeat_at=v_now,
      last_success_at=coalesce(excluded.last_success_at,chlom_runtime.agent_health.last_success_at),last_error_code=excluded.last_error_code,
      resource_state=chlom_runtime.agent_health.resource_state||excluded.resource_state,updated_at=v_now;

    update chlom_runtime.gen6_dispatch_decisions
       set last_heartbeat_at=v_now,
           last_progress_at=case when p_progress>progress_percent then v_now else last_progress_at end,
           progress_percent=greatest(progress_percent,p_progress),updated_at=v_now
     where packet_id=p_packet_id;
  end if;

  return jsonb_build_object('run_id',p_run_id,'agent_id',p_agent_id,'packet_id',p_packet_id,'run_state',p_run_state,'heartbeat_at',v_now,'heartbeat_ttl_seconds',v_ttl,'heartbeat_fresh_until',v_now+make_interval(secs=>v_ttl),'run_kind',p_run_kind);
end $$;

create or replace function chlom_runtime.reconcile_gen6_agent_health_freshness()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime'
as $$
declare
  v_now timestamptz:=clock_timestamp();
  v_stale integer:=0;
  v_fresh integer:=0;
  r record;
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then raise exception 'service_role_required'; end if;
  for r in
    select h.agent_id,h.last_heartbeat_at,coalesce(t.heartbeat_ttl_seconds,3600) ttl,h.health_state
    from chlom_runtime.agent_health h
    join chlom_runtime.agent_templates t on t.agent_id=h.agent_id
    where h.agent_id='ct.relay.agent-a' or h.agent_id like 'ct.gen6.agent-%'
  loop
    if r.last_heartbeat_at is null or r.last_heartbeat_at < v_now-make_interval(secs=>r.ttl) then
      update chlom_runtime.agent_health
         set health_state=case when health_state='failed' then 'failed' else 'degraded' end,
             last_error_code=case when health_state='failed' then last_error_code else 'HEARTBEAT_STALE' end,
             resource_state=resource_state||jsonb_build_object('heartbeat_fresh',false,'heartbeat_stale_at',v_now,'heartbeat_ttl_seconds',r.ttl),updated_at=v_now
       where agent_id=r.agent_id;
      v_stale:=v_stale+1;
    else
      update chlom_runtime.agent_health
         set resource_state=resource_state||jsonb_build_object('live_heartbeat_observed',true,'heartbeat_fresh',true,'heartbeat_ttl_seconds',r.ttl,'heartbeat_fresh_until',r.last_heartbeat_at+make_interval(secs=>r.ttl)),
             last_error_code=case when last_error_code='HEARTBEAT_STALE' then null else last_error_code end,updated_at=v_now
       where agent_id=r.agent_id;
      v_fresh:=v_fresh+1;
    end if;
  end loop;
  return jsonb_build_object('fresh',v_fresh,'stale',v_stale,'evaluated_at',v_now);
end $$;

create or replace function chlom_runtime.gen7_stale_portfolio_maintenance_v2(p_cycle_id text,p_stale_seconds integer default 1800)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime'
as $$
declare v_act jsonb; v_health jsonb;
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then raise exception 'service_role_required'; end if;
  v_act:=chlom_runtime.gen7_actuate_stale_portfolio_v2(p_cycle_id,p_stale_seconds);
  v_health:=chlom_runtime.reconcile_gen6_agent_health_freshness();
  return jsonb_build_object('actuation',v_act,'health_freshness',v_health);
end $$;

create or replace function chlom_runtime.gen6_finalize_cycle(p_cycle_id text,p_started_at timestamptz,p_source_ref text default null,p_cycle_kind text default 'live')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime'
as $$
declare
 v_now timestamptz:=clock_timestamp();
 v_seconds numeric;
 v_started integer:=0; v_verifying integer:=0; v_done integer:=0; v_blocked integer:=0;
 v_before integer:=0; v_after integer:=0; v_active integer:=0;
 v_review numeric; v_verify numeric; v_cycle numeric;
 v_agents jsonb; v_original jsonb;
 v_control_runs integer:=0; v_control_work integer:=0;
 v_touched text[]:='{}'::text[]; v_prev_after integer;
begin
 if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then raise exception 'service_role_required'; end if;
 if p_cycle_kind not in ('live','bootstrap','canary','replay') then raise exception 'invalid_cycle_kind'; end if;
 v_seconds:=greatest(1,extract(epoch from (v_now-p_started_at)));

 select coalesce(array_agg(distinct packet_id) filter(where packet_id is not null),'{}'::text[]),
        count(*) filter(where packet_id is null),coalesce(sum(work_units_completed) filter(where packet_id is null),0)
   into v_touched,v_control_runs,v_control_work
 from chlom_runtime.gen6_agent_runs where cycle_id=p_cycle_id and run_kind='live';

 select count(*) into v_active from chlom_runtime.gen6_dispatch_decisions
 where lifecycle_state in ('running','verifying') and packet_id<>'ct.packet.gen6.telemetry-canary';

 select count(distinct packet_id) into v_started from chlom_runtime.gen6_agent_runs
 where cycle_id=p_cycle_id and run_kind='live' and packet_id is not null and role_type='owner' and started_at is not null;

 if cardinality(v_touched)>0 then
   select count(*) filter(where lifecycle_state='verifying'),count(*) filter(where lifecycle_state='done'),count(*) filter(where lifecycle_state='blocked')
     into v_verifying,v_done,v_blocked
   from chlom_runtime.gen6_dispatch_decisions where packet_id=any(v_touched);
 end if;

 select blocker_count_after into v_prev_after from chlom_runtime.gen6_cycle_metrics
 where cycle_id<>p_cycle_id and self_assessment->>'metric_scope'='packet_only_for_throughput'
 order by created_at desc limit 1;

 select coalesce(sum(current_blocker_count),0),avg(review_wait_seconds),avg(verification_seconds),avg(cycle_time_seconds)
   into v_after,v_review,v_verify,v_cycle
 from chlom_runtime.gen6_dispatch_decisions
 where packet_id=any(array['ct.packet.gen6.pr209-commercial-sites-close','ct.packet.gen6.pr220-public-projection-containment','ct.packet.gen6.pr169-cie-linkage-current-head','ct.packet.gen6.pr204-homepage-reconciliation','ct.packet.gen6.pr216-virality-canon']::text[]);
 v_before:=coalesce(v_prev_after,(select coalesce(sum(baseline_blocker_count),0) from chlom_runtime.gen6_dispatch_decisions where packet_id=any(array['ct.packet.gen6.pr209-commercial-sites-close','ct.packet.gen6.pr220-public-projection-containment','ct.packet.gen6.pr169-cie-linkage-current-head','ct.packet.gen6.pr204-homepage-reconciliation','ct.packet.gen6.pr216-virality-canon']::text[])));

 select coalesce(jsonb_object_agg(agent_id,jsonb_build_object('packet_runs',runs,'done_runs',done,'blocked_runs',blocked,'work_units',work_units)),'{}'::jsonb)
   into v_agents
 from (select agent_id,count(*) runs,count(*) filter(where run_state='done') done,count(*) filter(where run_state='blocked') blocked,coalesce(sum(work_units_completed),0) work_units from chlom_runtime.gen6_agent_runs where cycle_id=p_cycle_id and run_kind='live' and packet_id is not null group by agent_id) s;

 select coalesce(jsonb_object_agg(packet_id,jsonb_build_object('state',lifecycle_state,'progress',progress_percent,'baseline_blockers',baseline_blocker_count,'current_blockers',current_blocker_count,'head',current_head_sha,'last_progress_at',last_progress_at,'last_heartbeat_at',last_heartbeat_at,'retry_count',retry_count)),'{}'::jsonb)
   into v_original
 from chlom_runtime.gen6_dispatch_decisions
 where packet_id=any(array['ct.packet.gen6.pr209-commercial-sites-close','ct.packet.gen6.pr220-public-projection-containment','ct.packet.gen6.pr169-cie-linkage-current-head','ct.packet.gen6.pr204-homepage-reconciliation','ct.packet.gen6.pr216-virality-canon']::text[]);

 insert into chlom_runtime.gen6_cycle_metrics(
   cycle_id,cycle_kind,started_at,completed_at,target_wip,active_wip,packets_started,packets_verifying,packets_done,packets_blocked,
   packets_closed_per_hour,blocker_count_before,blocker_count_after,blocker_burndown,avg_review_wait_seconds,avg_verification_seconds,avg_cycle_time_seconds,
   throughput_by_agent,original_five_progress,self_assessment,source_ref,updated_at
 ) values(
   p_cycle_id,p_cycle_kind,p_started_at,v_now,4,least(6,v_active),v_started,v_verifying,v_done,v_blocked,
   round((v_done*3600.0/v_seconds)::numeric,4),v_before,v_after,v_before-v_after,v_review,v_verify,v_cycle,
   v_agents,v_original,jsonb_build_object('metric_scope','packet_only_for_throughput','control_plane_runs_excluded',v_control_runs,'control_plane_work_units_excluded',v_control_work,'touched_packets',v_touched,'active_wip_source','dispatch_decisions_running_or_verifying','cycle_force_test',coalesce(p_source_ref,'') ilike '%force test%'),p_source_ref,v_now
 ) on conflict(cycle_id) do update set
   completed_at=v_now,active_wip=excluded.active_wip,packets_started=excluded.packets_started,packets_verifying=excluded.packets_verifying,
   packets_done=excluded.packets_done,packets_blocked=excluded.packets_blocked,packets_closed_per_hour=excluded.packets_closed_per_hour,
   blocker_count_before=excluded.blocker_count_before,blocker_count_after=excluded.blocker_count_after,blocker_burndown=excluded.blocker_burndown,
   avg_review_wait_seconds=excluded.avg_review_wait_seconds,avg_verification_seconds=excluded.avg_verification_seconds,avg_cycle_time_seconds=excluded.avg_cycle_time_seconds,
   throughput_by_agent=excluded.throughput_by_agent,original_five_progress=excluded.original_five_progress,self_assessment=excluded.self_assessment,
   source_ref=excluded.source_ref,updated_at=v_now;

 return jsonb_build_object('cycle_id',p_cycle_id,'packet_metric_scope',true,'control_plane_runs_excluded',v_control_runs,'active_wip',v_active,'packets_started',v_started,'packets_verifying',v_verifying,'packets_done',v_done,'packets_blocked',v_blocked,'packets_closed_per_hour',round((v_done*3600.0/v_seconds)::numeric,4),'blocker_count_before',v_before,'blocker_count_after',v_after,'blocker_burndown',v_before-v_after,'completed_at',v_now);
end $$;

create or replace function chlom_runtime.agent_a_emergency_portfolio_cycle_v2(
  p_cycle_id text,p_source_ref text default 'founder-directed emergency execution bridge v2',p_execute boolean default true
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','chlom_runtime','extensions'
as $$
declare
  v_started timestamptz:=clock_timestamp();
  v_act jsonb; v_pf jsonb; v_dispatch jsonb; v_metrics jsonb;
  v_total_blockers integer; v_owner_verifier_conflicts integer; v_state_counts jsonb; v_204 jsonb;
  v_agent text; v_role text; v_task text; v_work integer; v_agent_metrics jsonb; v_run_id text; v_evidence text[];
begin
  if current_user not in ('postgres','service_role') and coalesce(current_setting('request.jwt.claim.role',true),'')<>'service_role' then raise exception 'service_role_required'; end if;
  if coalesce(trim(p_cycle_id),'')='' then raise exception 'cycle_id_required'; end if;
  perform pg_advisory_xact_lock(hashtext('chlom_runtime.agent-a.emergency-cycle.v2'));

  perform chlom_runtime.gen6_record_agent_heartbeat(
    p_cycle_id||':agent-a:start',p_cycle_id,'ct.relay.agent-a',null,'orchestrator','running',0,0,
    array[p_source_ref,'ct.agent-a.execution-bridge.v2'],jsonb_build_object('target_wip',4,'hard_max_wip',6,'continuation_before_dispatch',true,'stale_actuator','v2','force_test',coalesce(p_source_ref,'') ilike '%force test%'),
    'Agent A emergency portfolio cycle v2 started.',null,'live');

  v_act:=chlom_runtime.gen7_actuate_stale_portfolio_v2(p_cycle_id||':stale',1800);
  v_pf:=chlom_runtime.agent_a_portfolio_preflight(p_cycle_id,4,6,true,p_source_ref||' | post-stale-actuation');
  if p_execute then v_dispatch:=chlom_runtime.agent_a_start_portfolio_cycle(p_cycle_id,p_source_ref||' | WIP4 execution',true);
  else v_dispatch:=chlom_runtime.agent_a_start_portfolio_cycle(p_cycle_id,p_source_ref||' | dry run',false); end if;

  select coalesce(sum(current_blocker_count),0),count(*) filter(where owner_agent_id=verifier_agent_id)
    into v_total_blockers,v_owner_verifier_conflicts from chlom_runtime.gen6_dispatch_decisions;
  select coalesce(jsonb_object_agg(lifecycle_state,n),'{}'::jsonb) into v_state_counts
    from (select lifecycle_state,count(*) n from chlom_runtime.gen6_dispatch_decisions group by lifecycle_state) q;
  select jsonb_build_object('packet_id',packet_id,'state',lifecycle_state,'progress',progress_percent,'blockers',current_blocker_count,'head',current_head_sha,'owner',owner_agent_id,'verifier',verifier_agent_id)
    into v_204 from chlom_runtime.gen6_dispatch_decisions where packet_id='ct.packet.gen6.pr204-homepage-reconciliation';

  foreach v_agent in array array['ct.gen6.agent-l','ct.gen6.agent-m','ct.gen6.agent-n','ct.gen6.agent-o','ct.gen6.agent-p']::text[] loop
    v_role:=case v_agent when 'ct.gen6.agent-l' then 'router' when 'ct.gen6.agent-m' then 'reconciler' when 'ct.gen6.agent-n' then 'verifier' when 'ct.gen6.agent-o' then 'documentation' else 'sre' end;
    v_task:=case v_agent when 'ct.gen6.agent-l' then 'portfolio-intake-tags-dependencies-and-wip-routing' when 'ct.gen6.agent-m' then 'portfolio-source-state-and-blocker-reconciliation' when 'ct.gen6.agent-n' then 'portfolio-proof-drift-and-separation-verification' when 'ct.gen6.agent-o' then 'current-main-docs-homepage-and-planned-packet-reconciliation' else 'wip-throughput-backpressure-and-staleness-assessment' end;
    v_work:=1;
    v_agent_metrics:=case v_agent
      when 'ct.gen6.agent-l' then jsonb_build_object('preflight_snapshot',v_pf->>'snapshot_sha256','target_wip',v_pf->'target_wip','active_wip',v_pf->'active_wip','available_slots',v_pf->'available_slots','selected',v_pf->'selected_packet_ids','deferred',v_pf->'deferred_packet_ids')
      when 'ct.gen6.agent-m' then jsonb_build_object('total_current_blockers',v_total_blockers,'packet_states',v_state_counts,'stale_actions',v_act->'actions')
      when 'ct.gen6.agent-n' then jsonb_build_object('owner_verifier_conflicts',v_owner_verifier_conflicts,'invariant_state',v_pf->>'invariant_state','stale_actuator_errors',v_act->'errors')
      when 'ct.gen6.agent-o' then jsonb_build_object('homepage_packet',coalesce(v_204,'{}'::jsonb),'no_public_change_inferred',true)
      else jsonb_build_object('target_wip',4,'hard_max_wip',6,'active_wip',v_pf->'active_wip','available_slots',v_pf->'available_slots','stale_done_actions',v_act->'done_actions','stale_hold_actions',v_act->'hold_actions') end;
    v_run_id:=p_cycle_id||':subroute:'||right(v_agent,1);
    v_evidence:=array[p_source_ref,'preflight:'||coalesce(v_pf->>'snapshot_sha256','unknown'),'stale-actuator:v2'];
    perform chlom_runtime.gen6_record_agent_heartbeat(v_run_id,p_cycle_id,v_agent,null,v_role,'done',100,v_work,v_evidence,
      v_agent_metrics||jsonb_build_object('internal_subroute',true,'packet_progress_effect',false,'provider_write_performed',false,'D3_auto',false),
      v_task||' completed as an internal control-plane subroute; no packet progress was fabricated.',null,'live');
  end loop;

  perform chlom_runtime.gen6_record_agent_heartbeat(
    p_cycle_id||':agent-a:done',p_cycle_id,'ct.relay.agent-a',null,'orchestrator','done',100,1,
    array[p_source_ref,'preflight:'||coalesce(v_pf->>'snapshot_sha256','unknown'),'stale-actuator:v2'],
    jsonb_build_object('target_wip',4,'hard_max_wip',6,'preflight',v_pf,'actuation',v_act,'dispatch',v_dispatch,'L_P_telemetry_live',true,'progress_fabricated',false),
    'Agent A emergency portfolio cycle v2 completed control-plane actuation and L-P telemetry.',null,'live');

  v_metrics:=chlom_runtime.gen6_finalize_cycle(p_cycle_id,v_started,p_source_ref,'live');
  perform chlom_runtime.append_dail_event(
    'agent_a.emergency_portfolio_cycle_v2.completed','agent_portfolio',p_cycle_id,
    jsonb_build_object('cycle_id',p_cycle_id,'preflight',v_pf,'stale_actuation',v_act,'dispatch',v_dispatch,'cycle_metrics',v_metrics,'L_P_telemetry_live',true,'target_wip',4,'hard_max_wip',6,'provider_write_performed',false,'progress_fabricated',false,'D3_auto',false,'sovereign_vote_effect',false),
    'ct.relay.agent-a',null,'ct.relay.agent-a','2.0.2',p_cycle_id,null,
    'Agent A execution bridge v2 cycle.',null,'restricted');
  return jsonb_build_object('cycle_id',p_cycle_id,'preflight',v_pf,'stale_actuation',v_act,'dispatch',v_dispatch,'cycle_metrics',v_metrics,'L_P_telemetry_live',true,'progress_fabricated',false,'completed_at',clock_timestamp());
end $$;

revoke all on function chlom_runtime.gen7_actuate_stale_portfolio_v2(text,integer) from public,anon,authenticated;
revoke all on function chlom_runtime.gen6_record_agent_heartbeat(text,text,text,text,text,text,numeric,integer,text[],jsonb,text,text,text) from public,anon,authenticated;
revoke all on function chlom_runtime.reconcile_gen6_agent_health_freshness() from public,anon,authenticated;
revoke all on function chlom_runtime.gen7_stale_portfolio_maintenance_v2(text,integer) from public,anon,authenticated;
revoke all on function chlom_runtime.agent_a_emergency_portfolio_cycle_v2(text,text,boolean) from public,anon,authenticated;
grant execute on function chlom_runtime.gen7_actuate_stale_portfolio_v2(text,integer) to service_role;
grant execute on function chlom_runtime.gen6_record_agent_heartbeat(text,text,text,text,text,text,numeric,integer,text[],jsonb,text,text,text) to service_role;
grant execute on function chlom_runtime.reconcile_gen6_agent_health_freshness() to service_role;
grant execute on function chlom_runtime.gen7_stale_portfolio_maintenance_v2(text,integer) to service_role;
grant execute on function chlom_runtime.agent_a_emergency_portfolio_cycle_v2(text,text,boolean) to service_role;

do $$ declare j record; begin
  for j in select jobid from cron.job where jobname in ('gen7-stale-portfolio-watch-10m','gen7-stale-portfolio-actuator-10m') loop perform cron.unschedule(j.jobid); end loop;
  perform cron.schedule('gen7-stale-portfolio-actuator-10m','*/10 * * * *',$cron$select chlom_runtime.gen7_stale_portfolio_maintenance_v2('ct.gen7.maintenance.'||to_char(clock_timestamp() at time zone 'UTC','YYYYMMDDHH24MI'),1800);$cron$);
end $$;

update chlom_runtime.agent_templates
set metadata=metadata||jsonb_build_object('execution_bridge_version','2.0.2','live_internal_subroute_telemetry',true,'stale_actuator','gen7_actuate_stale_portfolio_v2','heartbeat_freshness','reconcile_gen6_agent_health_freshness','updated_at',now()),updated_at=now()
where agent_id in ('ct.relay.agent-a','ct.gen6.agent-l','ct.gen6.agent-m','ct.gen6.agent-n','ct.gen6.agent-o','ct.gen6.agent-p');

select chlom_runtime.append_dail_event(
  'agent_a.execution_bridge_v2.source_migration','control_patch','ct.relay.agent-a',
  jsonb_build_object('version','2.0.2','target_wip',4,'hard_max_wip',6,'continuation_before_dispatch',true,'stale_actuator','gen7_actuate_stale_portfolio_v2','heartbeat_freshness','reconcile_gen6_agent_health_freshness','packet_only_metrics',true,'provider_write_performed',false,'progress_fabricated',false,'D3_auto',false,'sovereign_vote_effect',false,'silent_delete',false),
  'ct.relay.agent-a',null,'ct.relay.agent-a','2.0.2','ct.agent-a.execution-bridge-v2-source',null,
  'Source-controlled migration for the emergency execution bridge v2.',null,'restricted'
);

commit;
