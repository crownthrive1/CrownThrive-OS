begin;

-- CrownThrive Penta scoped memory + cursor fabric v1.
-- Current-main successor of PR3797. Compatibility layer only: reuse the existing
-- scoped_memory_v1 pointer and PentaContext; do not create a second memory store,
-- scheduler, identity, authority surface, provider write, certification, vote/quorum,
-- credential, money, rights or D3 path.

create or replace function public.penta_scoped_memory_require_caller_v1(
  p_system_key text
)
returns text
language plpgsql
stable
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  v_claims jsonb:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
  v_role text:=coalesce(v_claims->>'role','');
  v_claim_system text:=coalesce(nullif(btrim(v_claims->>'penta_system_key'),''),nullif(btrim(v_claims->>'system_key'),''));
  v_system_key text:=btrim(coalesce(p_system_key,''));
begin
  if v_system_key='' then raise exception 'invalid_system_key'; end if;

  -- Direct governed database execution is distinguishable from API service-role execution.
  if session_user in ('postgres','supabase_admin') then
    return 'db-admin';
  end if;

  if v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if v_claim_system is null then raise exception 'penta_system_claim_required'; end if;
  if v_claim_system not in (v_system_key,'penta.context','penta.super') then
    raise exception 'cross_penta_caller_denied';
  end if;
  return v_claim_system;
end
$function$;

create or replace function public.penta_scoped_memory_cursor_write_v1(
  p_system_key text,
  p_subject_ref text default null,
  p_subject_sha256 text default null,
  p_cursor_state text default 'idle',
  p_owner_system_key text default null,
  p_next_predicate text default null,
  p_memory_summary text default null,
  p_evidence_refs jsonb default '[]'::jsonb,
  p_actor_system_key text default 'penta.context',
  p_expected_cookie_revision text default null,
  p_lease_id uuid default null,
  p_lease_expires_at timestamptz default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','extensions'
as $function$
declare
  v_system public.penta_system_registry%rowtype;
  v_existing_cookie public.penta_protocol_cookies_v1%rowtype;
  v_pointer jsonb;
  v_scope text;
  v_continuity_cursor text;
  v_continuity_contract text;
  v_state text:=lower(btrim(coalesce(p_cursor_state,'idle')));
  v_owner text;
  v_subject text;
  v_next text;
  v_memory text;
  v_actor text:=coalesce(nullif(btrim(p_actor_system_key),''),'penta.context');
  v_caller text;
  v_cursor_id text;
  v_cursor jsonb;
  v_cookie jsonb;
  v_memory_receipt jsonb:=null;
  v_existing_cursor_id text;
begin
  v_caller:=public.penta_scoped_memory_require_caller_v1(p_system_key);

  select * into v_system
  from public.penta_system_registry
  where system_key=btrim(p_system_key) and maturity<>'retired';
  if not found then raise exception 'penta_system_not_registered'; end if;

  if v_state <> all(array['idle','active','waiting_dependency','hold','degraded','complete','superseded']::text[]) then
    raise exception 'invalid_cursor_state';
  end if;
  if p_subject_ref is not null and length(p_subject_ref)>512 then raise exception 'subject_ref_too_long'; end if;
  if p_subject_sha256 is not null and p_subject_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_subject_sha256'; end if;
  if p_next_predicate is not null and length(p_next_predicate)>1024 then raise exception 'next_predicate_too_long'; end if;
  if p_memory_summary is not null and length(p_memory_summary)>4096 then raise exception 'memory_summary_too_long'; end if;
  if jsonb_typeof(coalesce(p_evidence_refs,'[]'::jsonb))<>'array' then raise exception 'evidence_refs_must_be_array'; end if;
  if p_expected_cookie_revision is null or p_expected_cookie_revision !~ '^[0-9a-f]{64}$' then
    raise exception 'expected_cookie_revision_required';
  end if;

  v_owner:=coalesce(nullif(btrim(p_owner_system_key),''),v_system.system_key);
  if v_owner<>v_system.system_key then raise exception 'owner_override_not_authorized'; end if;
  if v_actor<>'penta.context' then raise exception 'actor_override_not_authorized'; end if;

  if v_state='active' then
    if p_lease_id is null or p_lease_expires_at is null then raise exception 'active_cursor_lease_required'; end if;
    if p_lease_expires_at<=clock_timestamp() then raise exception 'cursor_lease_expired'; end if;
    if p_lease_expires_at>clock_timestamp()+interval '24 hours' then raise exception 'cursor_lease_too_long'; end if;
  elsif (p_lease_id is null)<>(p_lease_expires_at is null) then
    raise exception 'incomplete_cursor_lease';
  end if;

  perform public.penta_cookie_install_v1(v_system.system_key,'penta.context');
  begin
    select * into v_existing_cookie
    from public.penta_protocol_cookies_v1
    where system_key=v_system.system_key
    for update nowait;
  exception when lock_not_available then
    return jsonb_build_object(
      'ok',false,'state','deferred_contention','retryable',true,
      'system_key',v_system.system_key,'authority_created',false
    );
  end;

  if not found then raise exception 'penta_cookie_missing_after_install'; end if;
  if v_existing_cookie.cookie_state<>'active' then raise exception 'cookie_not_active'; end if;
  if v_existing_cookie.current_revision<>p_expected_cookie_revision then raise exception 'stale_cookie_revision'; end if;

  v_pointer:=coalesce(v_existing_cookie.observed_state->'scoped_memory_v1','{}'::jsonb);
  v_scope:=nullif(btrim(v_pointer->>'scope'),'');
  v_continuity_cursor:=nullif(btrim(v_pointer->>'cursor'),'');
  v_continuity_contract:=nullif(btrim(v_pointer->>'contract'),'');
  if v_scope is null or v_continuity_cursor is null or v_continuity_contract is null then
    raise exception 'scoped_memory_pointer_required';
  end if;
  if not exists(
    select 1 from public.penta_context_records_v1 r
    where r.context_id::text=v_continuity_cursor
      and r.scope_key=v_scope
      and r.system_ref=v_system.system_key
      and r.tenant_ref='crownthrive'
  ) then
    raise exception 'scoped_memory_pointer_identity_mismatch';
  end if;

  v_subject:=coalesce(nullif(btrim(p_subject_ref),''),'registry:'||v_system.system_key);
  v_next:=case when p_next_predicate is null then null else left(public.penta_context_redact_v1(p_next_predicate),1024) end;
  v_memory:=case when p_memory_summary is null then null else left(public.penta_context_redact_v1(p_memory_summary),2048) end;

  v_cursor_id:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'continuity_cursor_ref',v_continuity_cursor,
    'subject_ref',v_subject,
    'subject_sha256',p_subject_sha256,
    'state',v_state,
    'owner',v_owner,
    'next_predicate',v_next,
    'lease_id',p_lease_id,
    'lease_expires_at',p_lease_expires_at
  ));

  v_existing_cursor_id:=nullif(v_existing_cookie.observed_state->'scoped_cursor'->>'cursor_id','');
  if v_existing_cursor_id=v_cursor_id then
    return jsonb_build_object(
      'ok',true,'state','no_change','contract','ct.penta.scoped-memory-cursor.v1',
      'system_key',v_system.system_key,'cursor_id',v_cursor_id,
      'cookie_revision',v_existing_cookie.current_revision,'authority_created',false
    );
  end if;

  v_cursor:=jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'version','1.1.0',
    'cursor_id',v_cursor_id,
    'system_key',v_system.system_key,
    'subject_ref',v_subject,
    'subject_sha256',p_subject_sha256,
    'state',v_state,
    'owner_system_key',v_owner,
    'next_predicate',v_next,
    'memory_scope',v_scope,
    'continuity_cursor_ref',v_continuity_cursor,
    'continuity_contract_ref',v_continuity_contract,
    'memory_pointer_source','scoped_memory_v1',
    'prior_cookie_revision',v_existing_cookie.current_revision,
    'lease_id',p_lease_id,
    'lease_expires_at',p_lease_expires_at,
    'memory_summary',case when v_memory is null then null else left(v_memory,512) end,
    'memory_summary_sha256',case when v_memory is null then null else encode(extensions.digest(convert_to(v_memory,'UTF8'),'sha256'),'hex') end,
    'deterministic',true,
    'cas_required',true,
    'append_supersede_only',true,
    'penta_chat_assist','context_only',
    'penta_brain_assist','planning_only',
    'caller_ref',v_caller,
    'destructive_authority',false,
    'authority_created',false,
    'updated_at',clock_timestamp()
  );

  v_cookie:=public.penta_cookie_observe_v1(
    v_system.system_key,
    jsonb_build_object(
      'scoped_cursor',v_cursor,
      'memory_scope',v_scope,
      'memory_policy',jsonb_build_object(
        'mode','minimal',
        'durable_store','PentaContext',
        'pointer_source','scoped_memory_v1',
        'inline_summary_max_chars',512,
        'append_supersede_only',true,
        'cas_required',true,
        'lease_required_for_active',true
      ),
      'assist_contract',jsonb_build_object(
        'penta_chat','context_only',
        'penta_brain','planning_only',
        'authority_created',false,
        'd3_human_reserved',true
      )
    ),
    'penta.context',
    coalesce(p_evidence_refs,'[]'::jsonb)
  );

  if v_cookie->>'state'='deferred_contention' then
    return jsonb_build_object(
      'ok',false,'state','deferred_contention','retryable',true,
      'system_key',v_system.system_key,'authority_created',false
    );
  end if;

  if v_memory is not null and btrim(v_memory)<>'' then
    v_memory_receipt:=public.penta_context_ingest_v1(
      v_scope,
      'system',
      'penta-scoped-cursor:'||v_cursor_id,
      v_memory,
      'Scoped memory — '||v_system.canonical_name,
      left(v_memory,512),
      array['penta_scoped_memory','penta_cursor',lower(v_system.category)],
      jsonb_build_object(
        'system_ref',v_system.system_key,
        'tenant_ref','crownthrive',
        'facts',jsonb_build_object(
          'cursor_id',v_cursor_id,
          'continuity_cursor_ref',v_continuity_cursor,
          'continuity_contract_ref',v_continuity_contract,
          'subject_ref',v_subject,
          'subject_sha256',p_subject_sha256,
          'cursor_state',v_state,
          'owner_system_key',v_owner,
          'next_predicate',v_next,
          'lease_id',p_lease_id,
          'lease_expires_at',p_lease_expires_at,
          'authority_created',false
        ),
        'trust_tier','authoritative'
      ),
      'internal',0.65,0.95,clock_timestamp(),p_lease_expires_at,
      'penta.context'
    );
  end if;

  return jsonb_build_object(
    'ok',true,
    'state','observed',
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'cursor_id',v_cursor_id,
    'memory_scope',v_scope,
    'continuity_cursor_ref',v_continuity_cursor,
    'cursor',v_cursor,
    'cookie',v_cookie,
    'memory_receipt',v_memory_receipt,
    'authority_created',false,
    'destructive_authority',false
  );
end
$function$;

create or replace function public.penta_scoped_memory_cursor_read_v1(
  p_system_key text,
  p_query text default '',
  p_limit integer default 4
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  v_system public.penta_system_registry%rowtype;
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_pointer jsonb;
  v_scope text;
  v_memory jsonb;
  v_cursor jsonb;
  v_runtime_state text;
  v_caller text;
begin
  v_caller:=public.penta_scoped_memory_require_caller_v1(p_system_key);
  select * into v_system
  from public.penta_system_registry
  where system_key=btrim(p_system_key) and maturity<>'retired';
  if not found then raise exception 'penta_system_not_registered'; end if;

  select * into v_cookie
  from public.penta_protocol_cookies_v1
  where system_key=v_system.system_key;
  if not found then raise exception 'penta_cookie_missing'; end if;

  v_pointer:=coalesce(v_cookie.observed_state->'scoped_memory_v1','{}'::jsonb);
  v_scope:=nullif(btrim(v_pointer->>'scope'),'');
  if v_scope is null or nullif(btrim(v_pointer->>'cursor'),'') is null then raise exception 'scoped_memory_pointer_required'; end if;
  if not exists(
    select 1 from public.penta_context_records_v1 r
    where r.context_id::text=v_pointer->>'cursor'
      and r.scope_key=v_scope
      and r.system_ref=v_system.system_key
      and r.tenant_ref='crownthrive'
  ) then raise exception 'scoped_memory_pointer_identity_mismatch'; end if;

  v_memory:=public.penta_context_query_v1(
    v_scope,coalesce(p_query,''),greatest(1,least(coalesce(p_limit,4),8)),4096,
    null,'internal','penta.context'
  );
  v_cursor:=coalesce(v_cookie.observed_state->'scoped_cursor','{}'::jsonb);
  v_runtime_state:=coalesce(v_cursor->>'state','uninitialized');
  if v_runtime_state='active'
     and nullif(v_cursor->>'lease_expires_at','') is not null
     and (v_cursor->>'lease_expires_at')::timestamptz<=clock_timestamp()
  then v_runtime_state:='expired'; end if;

  return jsonb_build_object(
    'ok',true,
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'canonical_name',v_system.canonical_name,
    'version',v_system.version,
    'maturity',v_system.maturity,
    'authority_ceiling',v_system.risk_ceiling,
    'memory_scope',v_scope,
    'continuity_pointer',v_pointer,
    'cursor',v_cursor,
    'cursor_runtime_state',v_runtime_state,
    'assist_contract',coalesce(v_cookie.observed_state->'assist_contract','{}'::jsonb),
    'memory',v_memory,
    'caller_ref',v_caller,
    'authority_created',false
  );
end
$function$;

create or replace function public.penta_scoped_memory_cursor_reconcile_v1(
  p_limit integer default 1000
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  r record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,1000),2000));
  v_considered integer:=0;
  v_initialized integer:=0;
  v_deferred integer:=0;
  v_pointer_missing integer:=0;
  v_result jsonb;
begin
  perform public.penta_scoped_memory_require_caller_v1('penta.context');
  for r in
    select s.system_key,c.current_revision,c.observed_state->'scoped_memory_v1' as pointer
    from public.penta_system_registry s
    left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
    where s.maturity<>'retired'
      and coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'
    order by s.system_key
    limit v_limit
  loop
    v_considered:=v_considered+1;
    if nullif(btrim(r.pointer->>'scope'),'') is null or nullif(btrim(r.pointer->>'cursor'),'') is null then
      v_pointer_missing:=v_pointer_missing+1;
      continue;
    end if;
    if r.current_revision is null then
      v_pointer_missing:=v_pointer_missing+1;
      continue;
    end if;
    begin
      v_result:=public.penta_scoped_memory_cursor_write_v1(
        r.system_key,'registry:'||r.system_key,null,'idle',r.system_key,null,null,
        jsonb_build_array('ct.penta.scoped-memory-cursor.v1:bootstrap'),
        'penta.context',r.current_revision,null,null
      );
      if coalesce(v_result->>'ok','false')='true' then v_initialized:=v_initialized+1;
      elsif v_result->>'state'='deferred_contention' then v_deferred:=v_deferred+1;
      end if;
    exception when lock_not_available or serialization_failure or deadlock_detected then
      v_deferred:=v_deferred+1;
    end;
  end loop;

  return jsonb_build_object(
    'ok',true,
    'contract','ct.penta.scoped-memory-cursor.v1',
    'considered',v_considered,
    'initialized',v_initialized,
    'deferred',v_deferred,
    'pointer_missing',v_pointer_missing,
    'remaining',(
      select count(*)
      from public.penta_system_registry s
      left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
      where s.maturity<>'retired'
        and coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'
    ),
    'authority_created',false,
    'destructive_authority',false,
    'observed_at',clock_timestamp()
  );
end
$function$;

create or replace function public.penta_scoped_memory_cursor_status_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  v_result jsonb;
begin
  perform public.penta_scoped_memory_require_caller_v1('penta.context');
  select jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'registered',count(*),
    'cookie_installed',count(*) filter (where c.cookie_id is not null),
    'continuity_pointer_ready',count(*) filter (where nullif(btrim(c.observed_state->'scoped_memory_v1'->>'scope'),'') is not null and nullif(btrim(c.observed_state->'scoped_memory_v1'->>'cursor'),'') is not null),
    'working_cursor_ready',count(*) filter (where c.observed_state->'scoped_cursor'->>'contract'='ct.penta.scoped-memory-cursor.v1'),
    'pointer_cursor_aligned',count(*) filter (where c.observed_state->'scoped_cursor'->>'memory_scope'=c.observed_state->'scoped_memory_v1'->>'scope' and c.observed_state->'scoped_cursor'->>'continuity_cursor_ref'=c.observed_state->'scoped_memory_v1'->>'cursor'),
    'expired_active_cursor',count(*) filter (where c.observed_state->'scoped_cursor'->>'state'='active' and nullif(c.observed_state->'scoped_cursor'->>'lease_expires_at','') is not null and (c.observed_state->'scoped_cursor'->>'lease_expires_at')::timestamptz<=clock_timestamp()),
    'missing_scoped_cursor',count(*) filter (where coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'),
    'penta_chat_assist','context_only',
    'penta_brain_assist','planning_only',
    'authority_created',false,
    'destructive_authority',false,
    'observed_at',clock_timestamp()
  ) into v_result
  from public.penta_system_registry s
  left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
  where s.maturity<>'retired';
  return v_result;
end
$function$;

revoke all on function public.penta_scoped_memory_require_caller_v1(text) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text,text,uuid,timestamptz) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_reconcile_v1(integer) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_status_v1() from public,anon,authenticated;

grant execute on function public.penta_scoped_memory_require_caller_v1(text) to service_role;
grant execute on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text,text,uuid,timestamptz) to service_role;
grant execute on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) to service_role;
grant execute on function public.penta_scoped_memory_cursor_reconcile_v1(integer) to service_role;
grant execute on function public.penta_scoped_memory_cursor_status_v1() to service_role;

comment on function public.penta_scoped_memory_require_caller_v1(text) is
'Fails closed for API callers unless service_role carries an exact Penta system claim matching the target or the bounded PentaContext/PentaSuper coordinator. Direct governed database admin sessions are distinguished by session_user.';
comment on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text,text,uuid,timestamptz) is
'CAS- and lease-aware minimal working cursor writer over the existing scoped_memory_v1 pointer. Owner/actor overrides are prohibited and pointer provenance is validated before mutation.';
comment on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) is
'Bounded scoped recall plus cursor read with caller and pointer-provenance checks. Expired active leases are surfaced as expired; read does not mutate state.';
comment on function public.penta_scoped_memory_cursor_reconcile_v1(integer) is
'Idempotent bootstrap of only missing working cursors using each exact current cookie revision. It never resets an existing cursor or creates a memory silo.';
comment on function public.penta_scoped_memory_cursor_status_v1() is
'Aggregated alignment and expired-lease status for canonical continuity pointers and deterministic working cursors.';

commit;
