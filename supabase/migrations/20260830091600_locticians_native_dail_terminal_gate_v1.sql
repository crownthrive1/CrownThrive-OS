-- Locticians native action DAIL terminal gate v1.
-- Closes the gap where crm.locticians_native_action_cycle_v1 could persist
-- state='complete' without canonical CHLOM DAIL evidence/readback.
-- Public-safe: DAIL payloads contain only IDs/hashes/minimal operational metadata.

alter table crm.locticians_native_action_queue_v1
  add column if not exists dail_event_id uuid,
  add column if not exists dail_event_hash text,
  add column if not exists dail_bound_at timestamptz,
  add column if not exists dail_evidence_state text not null default 'unbound';

alter table crm.locticians_native_action_queue_v1
  drop constraint if exists locticians_native_action_queue_v1_dail_evidence_state_check;
alter table crm.locticians_native_action_queue_v1
  add constraint locticians_native_action_queue_v1_dail_evidence_state_check
  check (dail_evidence_state in ('unbound','bound','hold'));

create unique index if not exists locticians_native_action_queue_v1_dail_event_uidx
  on crm.locticians_native_action_queue_v1(dail_event_id)
  where dail_event_id is not null;

create or replace function crm.locticians_native_bind_dail_action_v1(
  p_action_id uuid,
  p_reason text default 'terminal_complete'
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','crm','chlom_runtime','extensions'
as $$
declare
  a crm.locticians_native_action_queue_v1%rowtype;
  d jsonb;
  v_event_id uuid;
  v_event_hash text;
  v_event_key_sha text;
  v_receipt_sha text;
  v_readback boolean:=false;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;

  select * into a
  from crm.locticians_native_action_queue_v1
  where action_id=p_action_id
  for update;
  if not found then raise exception 'LOCTICIANS_ACTION_NOT_FOUND'; end if;

  if a.state<>'complete' then
    return jsonb_build_object('state','hold','reason','ACTION_NOT_COMPLETE','action_id',a.action_id);
  end if;

  if a.dail_event_id is not null then
    select exists(
      select 1 from chlom_runtime.dail_events e
      where e.event_id=a.dail_event_id
        and e.event_hash=a.dail_event_hash
        and e.entity_type='locticians_native_action'
        and e.entity_id=a.action_id::text
    ) into v_readback;
    if not v_readback then raise exception 'DAIL_READBACK_MISSING_FOR_BOUND_ACTION'; end if;
    return jsonb_build_object(
      'state','bound','action_id',a.action_id,'dail_event_id',a.dail_event_id,
      'dail_event_hash',a.dail_event_hash,'idempotent_replay',true
    );
  end if;

  v_event_key_sha:=encode(extensions.digest(convert_to(a.event_key,'UTF8'),'sha256'),'hex');
  v_receipt_sha:=encode(extensions.digest(convert_to(coalesce(a.provider_receipt,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');

  d:=chlom_runtime.append_dail_event(
    'locticians.native.action.completed',
    'locticians_native_action',
    a.action_id::text,
    jsonb_build_object(
      'directive','ct.directive.dail.mandatory-evidence-spine.v1',
      'action_type',a.action_type,
      'provider_model',a.provider_model,
      'provider_operation',a.provider_operation,
      'risk_class',a.risk_class,
      'terminal_state','complete',
      'event_key_sha256',v_event_key_sha,
      'provider_receipt_sha256',v_receipt_sha,
      'action_created_at',a.created_at,
      'action_updated_at',a.updated_at,
      'binding_reason',coalesce(nullif(p_reason,''),'terminal_complete'),
      'full_payload_in_dail',false,
      'provider_write_implied',false
    ),
    'crm.locticians_native_action_queue_v1',
    null,
    a.agent_id,
    '1.0.0',
    'locticians-native-action:'||a.action_id::text,
    null,
    'ct.directive.dail.mandatory-evidence-spine.v1',
    null,
    'internal'
  );
  v_event_id:=(d->>'event_id')::uuid;
  v_event_hash:=d->>'event_hash';

  update crm.locticians_native_action_queue_v1
     set dail_event_id=v_event_id,
         dail_event_hash=v_event_hash,
         dail_bound_at=now(),
         dail_evidence_state='bound',
         updated_at=updated_at
   where action_id=a.action_id;

  select exists(
    select 1 from chlom_runtime.dail_events e
    where e.event_id=v_event_id
      and e.event_hash=v_event_hash
      and e.entity_type='locticians_native_action'
      and e.entity_id=a.action_id::text
  ) into v_readback;
  if not v_readback then raise exception 'DAIL_APPEND_READBACK_FAILED'; end if;

  return jsonb_build_object(
    'state','bound','action_id',a.action_id,'dail_event_id',v_event_id,
    'dail_event_hash',v_event_hash,'idempotent_replay',false,'readback',true
  );
end $$;

create or replace function crm.locticians_native_complete_dail_trigger_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','crm'
as $$
begin
  if new.state='complete' and new.dail_event_id is null then
    perform crm.locticians_native_bind_dail_action_v1(
      new.action_id,
      case when tg_op='INSERT' then 'complete_insert' else 'complete_transition' end
    );
  end if;
  return new;
end $$;

drop trigger if exists locticians_native_complete_dail_bind_v1 on crm.locticians_native_action_queue_v1;
create trigger locticians_native_complete_dail_bind_v1
after insert or update of state on crm.locticians_native_action_queue_v1
for each row
when (new.state='complete' and new.dail_event_id is null)
execute function crm.locticians_native_complete_dail_trigger_v1();

create or replace function crm.locticians_native_dail_terminal_assert_v1()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','crm','chlom_runtime'
as $$
declare
  v_state text;
  v_event_id uuid;
  v_event_hash text;
  v_ok boolean:=false;
begin
  select state,dail_event_id,dail_event_hash
    into v_state,v_event_id,v_event_hash
  from crm.locticians_native_action_queue_v1
  where action_id=new.action_id;

  if v_state='complete' then
    if v_event_id is null or coalesce(v_event_hash,'')='' then
      raise exception 'DAIL_TERMINAL_BINDING_REQUIRED:%',new.action_id;
    end if;
    select exists(
      select 1 from chlom_runtime.dail_events e
      where e.event_id=v_event_id
        and e.event_hash=v_event_hash
        and e.entity_type='locticians_native_action'
        and e.entity_id=new.action_id::text
    ) into v_ok;
    if not v_ok then raise exception 'DAIL_TERMINAL_READBACK_REQUIRED:%',new.action_id; end if;
  end if;
  return new;
end $$;

drop trigger if exists locticians_native_dail_terminal_assert_v1 on crm.locticians_native_action_queue_v1;
create constraint trigger locticians_native_dail_terminal_assert_v1
after insert or update on crm.locticians_native_action_queue_v1
deferrable initially deferred
for each row
execute function crm.locticians_native_dail_terminal_assert_v1();

create or replace function crm.locticians_native_dail_backfill_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','crm'
as $$
declare
  r record;
  v_result jsonb;
  v_bound integer:=0;
  v_failed integer:=0;
  v_results jsonb:='[]'::jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  for r in
    select action_id
    from crm.locticians_native_action_queue_v1
    where state='complete' and dail_event_id is null
    order by created_at,action_id
    limit greatest(1,least(coalesce(p_limit,100),500))
    for update skip locked
  loop
    begin
      v_result:=crm.locticians_native_bind_dail_action_v1(r.action_id,'retroactive_terminal_backfill');
      v_bound:=v_bound+1;
      v_results:=v_results||jsonb_build_array(v_result);
    exception when others then
      v_failed:=v_failed+1;
      update crm.locticians_native_action_queue_v1
         set dail_evidence_state='hold',
             hold_reason=coalesce(hold_reason,'')||case when coalesce(hold_reason,'')='' then '' else ' | ' end||'DAIL_BIND_FAILED:'||left(sqlerrm,200)
       where action_id=r.action_id;
      v_results:=v_results||jsonb_build_array(jsonb_build_object('action_id',r.action_id,'state','hold','error',left(sqlerrm,200)));
    end;
  end loop;
  return jsonb_build_object(
    'state',case when v_failed=0 then 'pass' else 'hold' end,
    'bound',v_bound,'failed',v_failed,
    'remaining_unbound_complete',(select count(*) from crm.locticians_native_action_queue_v1 where state='complete' and dail_event_id is null),
    'results',v_results,'at',now()
  );
end $$;

create or replace function crm.locticians_native_dail_status_v1()
returns jsonb
language sql
security definer
set search_path='pg_catalog','crm','chlom_runtime'
as $$
select jsonb_build_object(
  'complete_total',(select count(*) from crm.locticians_native_action_queue_v1 where state='complete'),
  'complete_bound',(select count(*) from crm.locticians_native_action_queue_v1 where state='complete' and dail_evidence_state='bound' and dail_event_id is not null),
  'complete_unbound',(select count(*) from crm.locticians_native_action_queue_v1 where state='complete' and dail_event_id is null),
  'ready_total',(select count(*) from crm.locticians_native_action_queue_v1 where state='ready'),
  'readback_mismatch',(select count(*) from crm.locticians_native_action_queue_v1 q where q.state='complete' and q.dail_event_id is not null and not exists(select 1 from chlom_runtime.dail_events e where e.event_id=q.dail_event_id and e.event_hash=q.dail_event_hash and e.entity_type='locticians_native_action' and e.entity_id=q.action_id::text)),
  'directive','ct.directive.dail.mandatory-evidence-spine.v1',
  'at',now()
)
$$;

revoke execute on function crm.locticians_native_bind_dail_action_v1(uuid,text) from public,anon,authenticated;
revoke execute on function crm.locticians_native_complete_dail_trigger_v1() from public,anon,authenticated;
revoke execute on function crm.locticians_native_dail_terminal_assert_v1() from public,anon,authenticated;
revoke execute on function crm.locticians_native_dail_backfill_v1(integer) from public,anon,authenticated;
revoke execute on function crm.locticians_native_dail_status_v1() from public,anon,authenticated;
grant execute on function crm.locticians_native_bind_dail_action_v1(uuid,text) to service_role;
grant execute on function crm.locticians_native_dail_backfill_v1(integer) to service_role;
grant execute on function crm.locticians_native_dail_status_v1() to service_role;
