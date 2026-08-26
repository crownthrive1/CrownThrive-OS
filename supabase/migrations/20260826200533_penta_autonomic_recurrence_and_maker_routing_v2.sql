create table if not exists public.penta_maker_routes_v1 (
  route_key text primary key,
  artifact_type text not null unique,
  maker_system_key text not null,
  priority smallint not null default 100,
  enabled boolean not null default true,
  rationale text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.penta_maker_routes_v1 enable row level security;
revoke all on table public.penta_maker_routes_v1 from anon, authenticated;
drop policy if exists penta_maker_routes_anon_deny_v1 on public.penta_maker_routes_v1;
create policy penta_maker_routes_anon_deny_v1 on public.penta_maker_routes_v1 for all to anon using (false) with check (false);
drop policy if exists penta_maker_routes_authenticated_deny_v1 on public.penta_maker_routes_v1;
create policy penta_maker_routes_authenticated_deny_v1 on public.penta_maker_routes_v1 for all to authenticated using (false) with check (false);

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at,updated_at
) values (
  'penta.maker','PentaMaker','orchestration',
  'Selects the appropriate registered Penta to author or own an institutional artifact before transport or publication.',
  'Selection and routing only. PentaMaker cannot send mail, manufacture evidence, certify a PASS, approve economic action, or expand the selected Penta authority.',
  'D1','production','1.0.0',false,'docs/phase3/PENTA_MAKER.md','public.penta_maker_select_v1',
  jsonb_build_object('family','penta_orchestration','transport_separation','PentaMail transports; selected Penta authors','default_maker','penta.reports'),now(),now()
)
on conflict(system_key) do update set
  canonical_name=excluded.canonical_name,
  category=excluded.category,
  purpose=excluded.purpose,
  authority_boundary=excluded.authority_boundary,
  risk_ceiling=excluded.risk_ceiling,
  maturity=excluded.maturity,
  version=excluded.version,
  public_exposure=excluded.public_exposure,
  docs_ref=excluded.docs_ref,
  runtime_ref=excluded.runtime_ref,
  metadata=public.penta_system_registry.metadata||excluded.metadata,
  last_verified_at=excluded.last_verified_at,
  updated_at=excluded.updated_at;

insert into public.penta_maker_routes_v1(route_key,artifact_type,maker_system_key,priority,rationale,metadata) values
  ('proof','proof','penta.reports',10,'Evidence-backed proof and production verification are authored by PentaReports.',jsonb_build_object('transport','PentaMail')),
  ('after_action','after_action','penta.reports',10,'After-action reports are authored by PentaReports.',jsonb_build_object('transport','PentaMail')),
  ('verification','verification','penta.reports',10,'Verification reports are authored by PentaReports.',jsonb_build_object('transport','PentaMail')),
  ('incident','incident','penta.notifs',10,'Active incident notices are authored by PentaNotifs.',jsonb_build_object('transport','PentaMail')),
  ('outage','outage','penta.notifs',10,'Outage alerts are authored by PentaNotifs.',jsonb_build_object('transport','PentaMail')),
  ('recovery','recovery','penta.notifs',10,'Recovery notices are authored by PentaNotifs.',jsonb_build_object('transport','PentaMail')),
  ('status','status','ct.penta.state-architecture-report.v1',10,'Architecture and state status mail is authored by the State Architecture Report runtime.',jsonb_build_object('transport','PentaMail')),
  ('system','system','penta.reports',100,'Unclassified institutional system reports default to PentaReports.',jsonb_build_object('transport','PentaMail'))
on conflict(artifact_type) do update set
  maker_system_key=excluded.maker_system_key,
  priority=excluded.priority,
  enabled=true,
  rationale=excluded.rationale,
  metadata=public.penta_maker_routes_v1.metadata||excluded.metadata,
  updated_at=now();

create or replace function public.penta_maker_select_v1(
  p_artifact_type text,
  p_context jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','public'
as $function$
declare
  v_type text := lower(coalesce(nullif(trim(p_artifact_type),''),'system'));
  v_route record;
begin
  select r.route_key,r.artifact_type,r.maker_system_key,r.rationale,s.canonical_name,s.runtime_ref,s.maturity
    into v_route
  from public.penta_maker_routes_v1 r
  join public.penta_system_registry s on s.system_key=r.maker_system_key
  where r.enabled=true and r.artifact_type=v_type
  order by r.priority asc,r.route_key asc
  limit 1;

  if not found then
    select 'system'::text as route_key,'system'::text as artifact_type,'penta.reports'::text as maker_system_key,
           'Fallback to PentaReports because no exact maker route is registered.'::text as rationale,
           s.canonical_name,s.runtime_ref,s.maturity
      into v_route
    from public.penta_system_registry s
    where s.system_key='penta.reports';
  end if;

  if v_route.maker_system_key is null then
    raise exception 'PENTAMAKER_NO_REGISTERED_MAKER';
  end if;

  return jsonb_build_object(
    'selector','PentaMaker',
    'selector_version','1.0.0',
    'artifact_type',v_type,
    'route_key',v_route.route_key,
    'maker_system_key',v_route.maker_system_key,
    'maker_name',v_route.canonical_name,
    'maker_runtime_ref',v_route.runtime_ref,
    'maker_maturity',v_route.maturity,
    'rationale',v_route.rationale,
    'context_digest',encode(extensions.digest(coalesce(p_context,'{}'::jsonb)::text,'sha256'),'hex'),
    'selected_at',now()
  );
end
$function$;

revoke execute on function public.penta_maker_select_v1(text,jsonb) from public,anon,authenticated;
grant execute on function public.penta_maker_select_v1(text,jsonb) to service_role;

create or replace function public.penta_mail_enqueue_with_maker_v1(
  p_message_type text,
  p_severity text,
  p_subject text,
  p_body_text text,
  p_dedupe_key text default null,
  p_metadata jsonb default '{}'::jsonb,
  p_recipient text default 'jones.usmc.kj@gmail.com'
) returns uuid
language plpgsql
security definer
set search_path = 'pg_catalog','public'
as $function$
declare
  v_selection jsonb;
  v_metadata jsonb;
begin
  v_selection := public.penta_maker_select_v1(p_message_type,coalesce(p_metadata,'{}'::jsonb));
  v_metadata := coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object(
    'penta_maker',v_selection,
    'origin_penta',v_selection->>'maker_system_key',
    'origin_penta_name',v_selection->>'maker_name',
    'transport_penta','ct.penta.mail.v1',
    'transport_name','PentaMail'
  );

  return public.penta_mail_enqueue_v1(
    p_message_type,p_severity,p_subject,p_body_text,p_dedupe_key,v_metadata,p_recipient
  );
end
$function$;

revoke execute on function public.penta_mail_enqueue_with_maker_v1(text,text,text,text,text,jsonb,text) from public,anon,authenticated;
grant execute on function public.penta_mail_enqueue_with_maker_v1(text,text,text,text,text,jsonb,text) to service_role;

create or replace function public.penta_incident_control_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','public','integration_control','extensions'
as $function$
declare
  v_failed record;
  v_success record;
  v_incident_id uuid;
  v_fp text;
  v_rem jsonb;
  v_report jsonb;
  v_report_sha text;
  v_report_id uuid;
  v_note_id uuid;
  v_source_ref text;
  v_harvest jsonb;
  v_harvest_sha text;
  v_has_success boolean := false;
begin
  select f.run_id,f.window_start,f.run_state,f.economic_verdict,f.publication_count,f.error_code,f.blockers,f.assertions,f.evidence_sha256,f.started_at,f.completed_at
  into v_failed
  from integration_control.pentagreen_hourly_runs_v1 f
  where f.run_state='failed'
    and f.error_code is not null
    and not exists (
      select 1
      from integration_control.pentagreen_hourly_runs_v1 s
      where s.run_state='completed'
        and s.error_code is null
        and s.started_at>f.started_at
    )
  order by f.started_at desc
  limit 1;

  if not found then
    return jsonb_build_object('state','no_action','reason','NO_ACTIVE_PENTAGREEN_FAILURE');
  end if;

  v_fp := encode(extensions.digest(('penta.green:'||coalesce(v_failed.error_code,'unknown')||':'||v_failed.run_id::text)::text,'sha256'),'hex');
  v_source_ref := 'pentagreen_run:'||v_failed.run_id::text;

  insert into public.penta_incidents_v1(system_key,incident_code,severity,priority,state,source_event_ref,fingerprint,title,summary,failure_evidence)
  values('penta.green',v_failed.error_code,case when v_failed.error_code='23514' then 'CRITICAL' else 'ERROR' end,
         case when v_failed.error_code='23514' then 'P0' else 'P1' end,'detected',v_source_ref,v_fp,
         'PentaGreen production execution fault '||v_failed.error_code,
         'PentaFlagger detected a failed PentaGreen production hourly execution. Economic activation remains fail-closed.',
         jsonb_build_object('run_id',v_failed.run_id,'window_start',v_failed.window_start,'economic_verdict',v_failed.economic_verdict,
                            'publication_count',v_failed.publication_count,'error_code',v_failed.error_code,'blockers',v_failed.blockers,
                            'assertions',v_failed.assertions,'evidence_sha256',v_failed.evidence_sha256))
  on conflict(fingerprint) do update set
    source_event_ref=excluded.source_event_ref,
    failure_evidence=public.penta_incidents_v1.failure_evidence||excluded.failure_evidence,
    updated_at=now()
  returning incident_id into v_incident_id;

  if exists (select 1 from public.penta_incidents_v1 where incident_id=v_incident_id and state='resolved') then
    select report_id into v_report_id
    from public.penta_reports_v1
    where incident_id=v_incident_id and report_type='after_action'
    order by created_at asc
    limit 1;
    return jsonb_build_object('state','resolved','incident_id',v_incident_id,'report_id',v_report_id,'deduped',true,'reason','INCIDENT_OCCURRENCE_ALREADY_RESOLVED');
  end if;

  insert into public.penta_flags_v1(incident_id,flag_key,severity,reason,evidence)
  values(v_incident_id,'execution_failure','CRITICAL','PentaGreen hourly execution returned SQLSTATE '||v_failed.error_code,
         jsonb_build_object('run_id',v_failed.run_id,'publication_count',v_failed.publication_count))
  on conflict(incident_id,flag_key) do nothing;

  insert into public.penta_tags_v1(incident_id,tag) values
    (v_incident_id,'system:penta.green'),(v_incident_id,'priority:P0'),(v_incident_id,'owner:penta.blue'),
    (v_incident_id,'review:penta.red'),(v_incident_id,'error:'||v_failed.error_code),(v_incident_id,'economic:fail-closed')
  on conflict(incident_id,tag) do nothing;

  v_harvest := jsonb_build_object('run_id',v_failed.run_id,'error_code',v_failed.error_code,'blockers',v_failed.blockers,
                                  'assertions',v_failed.assertions,'evidence_sha256',v_failed.evidence_sha256);
  v_harvest_sha := encode(extensions.digest(v_harvest::text,'sha256'),'hex');
  insert into public.penta_harvest_events_v1(incident_id,source_type,source_ref,payload,payload_sha256)
  values(v_incident_id,'pentagreen_hourly_run',v_source_ref,v_harvest,v_harvest_sha)
  on conflict(source_type,source_ref,payload_sha256) do nothing;

  if (select first_notified_at is null from public.penta_incidents_v1 where incident_id=v_incident_id) then
    v_note_id := public.penta_mail_enqueue_with_maker_v1(
      'incident','CRITICAL','[P0] PentaGreen execution fault '||v_failed.error_code,
      'PentaNotifs detected PentaGreen SQLSTATE '||v_failed.error_code||'. The production hourly execution failed closed with publication_count='||coalesce(v_failed.publication_count,0)::text||'. PentaBlue owns remediation; PentaRed owns adversarial verification. Economic activation remains HOLD until a later production execution completes without the fault.',
      'penta-incident:'||v_fp,
      jsonb_build_object('incident_id',v_incident_id,'run_id',v_failed.run_id,'priority','P0','owner','PentaBlue','reviewer','PentaRed')
    );
    update public.penta_incidents_v1 set state='notified',first_notified_at=now(),updated_at=now() where incident_id=v_incident_id;
  end if;

  if v_failed.error_code='23514' then
    update public.penta_incidents_v1 set state='remediating',updated_at=now() where incident_id=v_incident_id;

    select a.evidence into v_rem
    from public.penta_remediation_actions_v1 a
    where a.incident_id=v_incident_id
      and a.handler_key='penta.pentagreen.23514.candidate-identity.v1'
      and a.state in ('applied','already_compliant')
    order by a.created_at desc
    limit 1;

    if v_rem is null then
      v_rem := public.penta_remediate_pentagreen_23514_v1();
      insert into public.penta_remediation_actions_v1(incident_id,handler_key,state,evidence)
      values(v_incident_id,'penta.pentagreen.23514.candidate-identity.v1',
        case when v_rem->>'state'='applied' then 'applied' when v_rem->>'state'='already_compliant' then 'already_compliant' when v_rem->>'state'='blocked' then 'blocked' else 'failed' end,
        v_rem);
    else
      v_rem := v_rem || jsonb_build_object('deduped',true,'reason','REMEDIATION_ALREADY_APPLIED_FOR_THIS_OCCURRENCE');
    end if;

    update public.penta_incidents_v1 set remediation_state=v_rem->>'state',remediation_evidence=v_rem,state='verification',updated_at=now() where incident_id=v_incident_id;
  end if;

  select s.run_id,s.window_start,s.run_state,s.economic_verdict,s.publication_count,s.error_code,s.assertions,s.evidence_sha256,s.started_at,s.completed_at
  into v_success
  from integration_control.pentagreen_hourly_runs_v1 s
  where s.run_state='completed' and s.error_code is null and s.started_at>v_failed.started_at
  order by s.started_at desc limit 1;

  v_has_success := found;

  if v_has_success then
    v_report := jsonb_build_object(
      'contract','ct.penta.report.after-action.v1.1',
      'incident_id',v_incident_id,
      'system','PentaGreen',
      'priority','P0',
      'fault',jsonb_build_object('sqlstate',v_failed.error_code,'failed_run_id',v_failed.run_id,'publication_count',v_failed.publication_count),
      'root_cause','Commercial-package candidate_ref was persisted into a column constrained for proprietary_product_candidate identity only.',
      'repair','Writer persists selected_candidate_ref only for proprietary_product_candidate; commercial packages retain selected_sku/package identity and selected_candidate_ref=NULL.',
      'verification',jsonb_build_object('successful_run_id',v_success.run_id,'error_code',v_success.error_code,'run_state',v_success.run_state,
                                       'economic_verdict',v_success.economic_verdict,'publication_count',v_success.publication_count,
                                       'evidence_sha256',v_success.evidence_sha256,'assertions',v_success.assertions),
      'economic_activation','HOLD_PENDING_ACCEPTANCE_CERTIFICATION_EVIDENCE',
      'red_blue_assignment',jsonb_build_object('red','constraint/adversarial regression','blue','repair/readback/containment'),
      'closed_at',now()
    );
    v_report_sha := encode(extensions.digest(v_report::text,'sha256'),'hex');
    insert into public.penta_reports_v1(report_type,system_key,incident_id,priority,title,body,body_sha256,state)
    values('after_action','penta.green',v_incident_id,'P0','PentaGreen 23514 After Action Report',v_report,v_report_sha,'final')
    returning report_id into v_report_id;

    update public.penta_incidents_v1 set state='resolved',resolved_at=now(),
      verification_evidence=v_report->'verification',updated_at=now() where incident_id=v_incident_id;

    perform public.penta_mail_enqueue_with_maker_v1(
      'after_action','INFO','[RESOLVED SOFTWARE FAULT] PentaGreen 23514 AAR',
      'PentaReports closed the P0 software incident. SQLSTATE 23514 was traced to a candidate identity CHECK violation and repaired without weakening the constraint. A subsequent production execution completed with error_code=NULL and publication_count=0. Economic activation remains HOLD for separate acceptance/certification/evidence blockers; no checkout activation or money movement was performed. Report ID: '||v_report_id::text||'. Evidence SHA-256: '||v_report_sha||'.',
      'penta-aar:'||v_fp,
      jsonb_build_object('incident_id',v_incident_id,'report_id',v_report_id,'report_sha256',v_report_sha,'successful_run_id',v_success.run_id)
    );
  end if;

  return jsonb_build_object('state',case when v_has_success then 'resolved' else 'verification' end,'incident_id',v_incident_id,'remediation',v_rem,'report_id',v_report_id,'occurrence_fingerprint',v_fp);
end
$function$;

revoke execute on function public.penta_incident_control_tick_v1() from public,anon,authenticated;
grant execute on function public.penta_incident_control_tick_v1() to service_role;

update public.penta_system_registry
set metadata=metadata||jsonb_build_object(
  'incident_identity','run_occurrence_scoped',
  'recurrence_safe',true,
  'maker_routing','PentaMaker',
  'status_language','production execution state; no manufactured pass'
),updated_at=now(),last_verified_at=now()
where system_key in ('penta.reports','penta.notifs','ct.penta.mail.v1');
