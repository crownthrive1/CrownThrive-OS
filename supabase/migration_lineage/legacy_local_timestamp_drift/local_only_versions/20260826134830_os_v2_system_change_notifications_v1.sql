-- CrownThrive OS V2 material system-change notification rail
-- Phase 3 production. Records meaningful control-plane changes and queues immediate
-- founder system messages through the existing CrownThrive Mailgun relay.

create table if not exists os_v2.system_notification_preferences (
  preference_key text primary key,
  recipient text not null,
  enabled boolean not null default true,
  immediate_material_changes boolean not null default true,
  daily_brief boolean not null default true,
  weekly_brief boolean not null default true,
  minimum_severity text not null default 'info' check(minimum_severity in ('info','warning','critical')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into os_v2.system_notification_preferences(preference_key,recipient,enabled,immediate_material_changes,daily_brief,weekly_brief,minimum_severity,metadata)
values('founder_primary','jones.usmc.kj@gmail.com',true,true,true,true,'info',jsonb_build_object('phase',3,'system_messages',true,'source','founder_directive_2026_08_26'))
on conflict(preference_key) do update set recipient=excluded.recipient,enabled=true,immediate_material_changes=true,daily_brief=true,weekly_brief=true,minimum_severity='info',metadata=os_v2.system_notification_preferences.metadata||excluded.metadata,updated_at=now();

create table if not exists os_v2.system_change_events (
  event_id uuid primary key default gen_random_uuid(),
  source_system text not null,
  event_type text not null,
  entity_ref text,
  severity text not null default 'info' check(severity in ('info','warning','critical')),
  title text not null,
  summary text not null,
  details jsonb not null default '{}'::jsonb,
  dedupe_key text not null unique,
  occurred_at timestamptz not null default now(),
  notification_id uuid references os_v2.notifications(notification_id) on delete set null,
  notified_at timestamptz
);
create index if not exists system_change_events_occurred_idx on os_v2.system_change_events(occurred_at desc);
create index if not exists system_change_events_source_idx on os_v2.system_change_events(source_system,event_type,occurred_at desc);

alter table os_v2.system_notification_preferences enable row level security;
alter table os_v2.system_change_events enable row level security;
revoke all on os_v2.system_notification_preferences from anon,authenticated;
revoke all on os_v2.system_change_events from anon,authenticated;

create or replace function os_v2.severity_rank(p_severity text) returns integer
language sql immutable set search_path='pg_catalog' as $$
select case p_severity when 'critical' then 3 when 'warning' then 2 else 1 end;
$$;

create or replace function os_v2.request_notification_flush_v1()
returns jsonb
language plpgsql security definer
set search_path='os_v2','vault','net','pg_catalog'
as $$
declare v_token text; v_request_id bigint;
begin
  select decrypted_secret into v_token from vault.decrypted_secrets where name='ct_os_v2_runtime_token' order by created_at desc limit 1;
  if v_token is null then return jsonb_build_object('state','hold','reason','OS_V2_RUNTIME_TOKEN_UNAVAILABLE'); end if;
  v_request_id:=net.http_post(
    url:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/crownthrive-os-v2-runtime',
    body:=jsonb_build_object('action','flush_notifications'),
    headers:=jsonb_build_object('content-type','application/json','x-ct-os-token',v_token),
    timeout_milliseconds:=120000
  );
  return jsonb_build_object('state','requested','request_id',v_request_id);
end $$;
revoke all on function os_v2.request_notification_flush_v1() from public,anon,authenticated;
grant execute on function os_v2.request_notification_flush_v1() to service_role;

create or replace function os_v2.record_system_change(
  p_source_system text,
  p_event_type text,
  p_entity_ref text,
  p_severity text,
  p_title text,
  p_summary text,
  p_details jsonb,
  p_dedupe_key text
) returns jsonb
language plpgsql security definer
set search_path='pg_catalog','os_v2'
as $$
declare
  v_event_id uuid;
  v_notification_id uuid;
  v_pref os_v2.system_notification_preferences%rowtype;
  v_subject text;
  v_body text;
  v_flush jsonb;
begin
  if p_severity not in ('info','warning','critical') then raise exception 'unsupported_severity'; end if;
  insert into os_v2.system_change_events(source_system,event_type,entity_ref,severity,title,summary,details,dedupe_key)
  values(left(p_source_system,120),left(p_event_type,160),left(p_entity_ref,240),p_severity,left(p_title,240),left(p_summary,4000),coalesce(p_details,'{}'::jsonb),left(p_dedupe_key,500))
  on conflict(dedupe_key) do nothing returning event_id into v_event_id;
  if v_event_id is null then return jsonb_build_object('state','duplicate_suppressed','dedupe_key',p_dedupe_key); end if;

  select * into v_pref from os_v2.system_notification_preferences where preference_key='founder_primary';
  if not found or not v_pref.enabled or not v_pref.immediate_material_changes or os_v2.severity_rank(p_severity)<os_v2.severity_rank(v_pref.minimum_severity) then
    return jsonb_build_object('state','recorded_not_notified','event_id',v_event_id);
  end if;

  v_subject := '[CrownThrive System] ' || p_title;
  v_body := format('CrownThrive Phase 3 System Message\n\nSeverity: %s\nSource: %s\nEvent: %s\nEntity: %s\nTime: %s\n\n%s\n\nProduction policy\n• Phase 3 is production.\n• PentaSELF may heal only within bounded authority.\n• D3 remains human-reserved.\n• No raw credentials or secrets are included in this message.\n\nThis message was generated because a material system change or update occurred.',upper(p_severity),p_source_system,p_event_type,coalesce(p_entity_ref,'n/a'),now() at time zone 'America/New_York',p_summary);

  insert into os_v2.notifications(channel,recipient,subject,body,severity,state,available_at)
  values('email',v_pref.recipient,v_subject,v_body,p_severity,'queued',now())
  returning notification_id into v_notification_id;

  update os_v2.system_change_events set notification_id=v_notification_id,notified_at=now() where event_id=v_event_id;
  v_flush:=os_v2.request_notification_flush_v1();
  return jsonb_build_object('state','queued','event_id',v_event_id,'notification_id',v_notification_id,'recipient',v_pref.recipient,'subject',v_subject,'flush',v_flush);
end $$;
revoke all on function os_v2.record_system_change(text,text,text,text,text,text,jsonb,text) from public,anon,authenticated;
grant execute on function os_v2.record_system_change(text,text,text,text,text,text,jsonb,text) to service_role;

create or replace function os_v2.notify_penta_self_action_v1() returns trigger
language plpgsql security definer set search_path='pg_catalog','os_v2' as $$
declare v_title text; v_sev text; v_summary text;
begin
  if new.result_state='failed' then v_sev:='critical'; v_title:='PentaSELF action failed';
  elsif new.action_key='recover_failed_required_job' and new.result_state='applied' then v_sev:='warning'; v_title:='PentaSELF recovered a required production job';
  elsif new.action_key='schedule_missing_job' and new.result_state='applied' then v_sev:='warning'; v_title:='PentaSELF repaired a missing production schedule';
  else return new; end if;
  v_summary:=format('PentaSELF action %s on %s finished with state %s. Capability: %s. Authority class: %s. Reversible: %s.',new.action_key,coalesce(new.target_ref,'n/a'),new.result_state,coalesce(new.capability_key,'n/a'),coalesce(new.authority_class,'n/a'),coalesce(new.reversible,false));
  perform os_v2.record_system_change('PentaSELF',new.action_key,new.target_ref,v_sev,v_title,v_summary,jsonb_build_object('receipt_id',new.receipt_id,'cycle_id',new.cycle_id,'result_state',new.result_state,'authority_class',new.authority_class,'reversible',new.reversible),'penta_self_action:'||new.receipt_id::text);
  return new;
end $$;
drop trigger if exists trg_os_v2_notify_penta_self_action_v1 on penta_self.action_receipts_v1;
create trigger trg_os_v2_notify_penta_self_action_v1 after insert on penta_self.action_receipts_v1 for each row execute function os_v2.notify_penta_self_action_v1();

create or replace function os_v2.notify_penta_system_registry_v1() returns trigger
language plpgsql security definer set search_path='pg_catalog','os_v2' as $$
declare v_title text; v_summary text; v_kind text;
begin
  if tg_op='INSERT' then
    v_kind:='system_institutionalized'; v_title:=new.canonical_name||' institutionalized';
    v_summary:=format('%s entered the Penta system registry at maturity %s, version %s, risk ceiling %s.',new.canonical_name,new.maturity,new.version,new.risk_ceiling);
  elsif old.maturity is distinct from new.maturity or old.version is distinct from new.version or old.runtime_ref is distinct from new.runtime_ref or old.authority_boundary is distinct from new.authority_boundary or old.risk_ceiling is distinct from new.risk_ceiling then
    v_kind:='system_registry_changed'; v_title:=new.canonical_name||' system definition changed';
    v_summary:=format('%s changed: maturity %s→%s; version %s→%s; risk %s→%s; authority %s→%s.',new.canonical_name,old.maturity,new.maturity,old.version,new.version,old.risk_ceiling,new.risk_ceiling,old.authority_boundary,new.authority_boundary);
  else return new; end if;
  perform os_v2.record_system_change('PentaRegistry',v_kind,new.system_key,'info',v_title,v_summary,jsonb_build_object('system_key',new.system_key,'maturity',new.maturity,'version',new.version,'runtime_ref',new.runtime_ref,'authority_boundary',new.authority_boundary,'risk_ceiling',new.risk_ceiling),v_kind||':'||new.system_key||':'||coalesce(new.version,'')||':'||coalesce(new.maturity,'')||':'||extract(epoch from new.updated_at)::bigint::text);
  return new;
end $$;
drop trigger if exists trg_os_v2_notify_penta_system_registry_v1 on public.penta_system_registry;
create trigger trg_os_v2_notify_penta_system_registry_v1 after insert or update on public.penta_system_registry for each row execute function os_v2.notify_penta_system_registry_v1();

create or replace function os_v2.notify_provider_cert_state_v1() returns trigger
language plpgsql security definer set search_path='pg_catalog','os_v2' as $$
declare v_sev text; v_title text; v_summary text;
begin
  if old.certification_state is not distinct from new.certification_state then return new; end if;
  v_sev:=case when new.certification_state='certified' then 'info' when new.certification_state ilike '%blocked%' or new.certification_state ilike '%failed%' then 'critical' else 'info' end;
  v_title:=case when new.certification_state='certified' then new.provider_system||' provider capability certified' else new.provider_system||' certification advanced to '||new.certification_state end;
  v_summary:=format('Provider %s / surface %s moved from %s to %s. Remaining requirements: %s.',new.provider_system,new.surface_id,coalesce(old.certification_state,'none'),new.certification_state,coalesce(new.missing_requirements::text,'[]'));
  perform os_v2.record_system_change('PentaCertify','provider_certification_state_changed',new.surface_id,v_sev,v_title,v_summary,jsonb_build_object('provider_system',new.provider_system,'surface_id',new.surface_id,'from',old.certification_state,'to',new.certification_state,'missing_requirements',new.missing_requirements),'provider_cert:'||new.surface_id||':'||new.certification_state||':'||extract(epoch from new.updated_at)::bigint::text);
  return new;
end $$;
drop trigger if exists trg_os_v2_notify_provider_cert_state_v1 on public.ct_factory_adapter_certification_queue;
create trigger trg_os_v2_notify_provider_cert_state_v1 after update of certification_state on public.ct_factory_adapter_certification_queue for each row execute function os_v2.notify_provider_cert_state_v1();

create or replace function os_v2.notify_runtime_state_v1() returns trigger
language plpgsql security definer set search_path='pg_catalog','os_v2' as $$
declare v_title text; v_summary text; v_sev text:='info';
begin
  if old.version is not distinct from new.version and old.state is not distinct from new.state and old.release_state is not distinct from new.release_state then return new; end if;
  if new.state ilike '%fail%' or new.release_state ilike '%fail%' then v_sev:='critical'; end if;
  v_title:='CrownThrive OS runtime/release state changed';
  v_summary:=format('OS V2 changed: version %s→%s; runtime %s→%s; release %s→%s.',old.version,new.version,old.state,new.state,old.release_state,new.release_state);
  perform os_v2.record_system_change('CrownThrive OS V2','runtime_state_changed','os_v2.runtime_state',v_sev,v_title,v_summary,jsonb_build_object('old_version',old.version,'new_version',new.version,'old_state',old.state,'new_state',new.state,'old_release_state',old.release_state,'new_release_state',new.release_state),'os_runtime:'||coalesce(new.version,'')||':'||coalesce(new.state,'')||':'||coalesce(new.release_state,'')||':'||extract(epoch from new.updated_at)::bigint::text);
  return new;
end $$;
drop trigger if exists trg_os_v2_notify_runtime_state_v1 on os_v2.runtime_state;
create trigger trg_os_v2_notify_runtime_state_v1 after update on os_v2.runtime_state for each row execute function os_v2.notify_runtime_state_v1();

create or replace function os_v2.record_external_system_change_v1(p_event_type text,p_entity_ref text,p_severity text,p_title text,p_summary text,p_details jsonb default '{}'::jsonb,p_dedupe_key text default null) returns jsonb
language plpgsql security definer set search_path='pg_catalog','os_v2' as $$
begin
  return os_v2.record_system_change('ExternalProduction',p_event_type,p_entity_ref,p_severity,p_title,p_summary,coalesce(p_details,'{}'::jsonb),coalesce(p_dedupe_key,p_event_type||':'||coalesce(p_entity_ref,'')||':'||extract(epoch from now())::bigint::text));
end $$;
revoke all on function os_v2.record_external_system_change_v1(text,text,text,text,text,jsonb,text) from public,anon,authenticated;
grant execute on function os_v2.record_external_system_change_v1(text,text,text,text,text,jsonb,text) to service_role;
