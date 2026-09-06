begin;

-- CrownThrive Penta scoped memory + cursor fabric v1.
-- Additive only: reuses the existing Penta protocol cookie and PentaContext fabric.
-- No destructive authority, provider-write authority, merge authority, certification authority,
-- vote/quorum effect, credential authority, money movement, rights grant, or D3 is created.

create or replace function public.penta_scoped_memory_cursor_write_v1(
  p_system_key text,
  p_subject_ref text default null,
  p_subject_sha256 text default null,
  p_cursor_state text default 'idle',
  p_owner_system_key text default null,
  p_next_predicate text default null,
  p_memory_summary text default null,
  p_evidence_refs jsonb default '[]'::jsonb,
  p_actor_system_key text default 'penta.super'
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'extensions'
as $function$
declare
  v_system public.penta_system_registry%rowtype;
  v_scope text;
  v_state text:=lower(btrim(coalesce(p_cursor_state,'idle')));
  v_owner text;
  v_subject text;
  v_next text;
  v_memory text;
  v_cursor_id text;
  v_cursor jsonb;
  v_cookie jsonb;
  v_memory_receipt jsonb:=null;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select * into v_system from public.penta_system_registry where system_key=btrim(p_system_key);
  if not found then raise exception 'penta_system_not_registered'; end if;
  if v_state <> all(array['idle','active','waiting_dependency','hold','degraded','complete','superseded']::text[]) then
    raise exception 'invalid_cursor_state';
  end if;
  if p_subject_ref is not null and length(p_subject_ref)>512 then raise exception 'subject_ref_too_long'; end if;
  if p_subject_sha256 is not null and p_subject_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid_subject_sha256'; end if;
  if p_next_predicate is not null and length(p_next_predicate)>1024 then raise exception 'next_predicate_too_long'; end if;
  if p_memory_summary is not null and length(p_memory_summary)>4096 then raise exception 'memory_summary_too_long'; end if;
  if jsonb_typeof(coalesce(p_evidence_refs,'[]'::jsonb))<>'array' then raise exception 'evidence_refs_must_be_array'; end if;

  perform public.penta_cookie_install_v1(v_system.system_key,'penta.context');

  v_scope:=left('penta:'||lower(v_system.system_key),128);
  v_owner:=coalesce(nullif(btrim(p_owner_system_key),''),v_system.system_key);
  v_subject:=coalesce(nullif(btrim(p_subject_ref),''),'registry:'||v_system.system_key);
  v_next:=case when p_next_predicate is null then null else left(public.penta_context_redact_v1(p_next_predicate),1024) end;
  v_memory:=case when p_memory_summary is null then null else left(public.penta_context_redact_v1(p_memory_summary),2048) end;

  v_cursor_id:=public.penta_protocol_sha256_v1(jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'subject_ref',v_subject,
    'subject_sha256',p_subject_sha256,
    'state',v_state,
    'owner',v_owner,
    'next_predicate',v_next
  ));

  v_cursor:=jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'version','1.0.0',
    'cursor_id',v_cursor_id,
    'system_key',v_system.system_key,
    'subject_ref',v_subject,
    'subject_sha256',p_subject_sha256,
    'state',v_state,
    'owner_system_key',v_owner,
    'next_predicate',v_next,
    'memory_scope',v_scope,
    'memory_summary',case when v_memory is null then null else left(v_memory,512) end,
    'memory_summary_sha256',case when v_memory is null then null else encode(extensions.digest(convert_to(v_memory,'UTF8'),'sha256'),'hex') end,
    'deterministic',true,
    'append_supersede_only',true,
    'penta_chat_assist','context_only',
    'penta_brain_assist','planning_only',
    'destructive_authority',false,
    'authority_created',false,
    'updated_at',clock_timestamp()
  );

  v_cookie:=public.penta_cookie_observe_v1(
    v_system.system_key,
    jsonb_build_object(
      'scoped_cursor',v_cursor,
      'memory_scope',v_scope,
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
        'facts',jsonb_build_object(
          'cursor_id',v_cursor_id,
          'subject_ref',v_subject,
          'subject_sha256',p_subject_sha256,
          'cursor_state',v_state,
          'owner_system_key',v_owner,
          'next_predicate',v_next,
          'authority_created',false
        ),
        'trust_tier','authoritative'
      ),
      'internal',0.65,0.95,clock_timestamp(),null,
      coalesce(nullif(btrim(p_actor_system_key),''),v_system.system_key)
    );
  end if;

  return jsonb_build_object(
    'ok',true,
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'cursor_id',v_cursor_id,
    'memory_scope',v_scope,
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
set search_path to 'pg_catalog', 'public'
as $function$
declare
  v_system public.penta_system_registry%rowtype;
  v_cookie public.penta_protocol_cookies_v1%rowtype;
  v_scope text;
  v_memory jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select * into v_system from public.penta_system_registry where system_key=btrim(p_system_key);
  if not found then raise exception 'penta_system_not_registered'; end if;
  select * into v_cookie from public.penta_protocol_cookies_v1 where system_key=v_system.system_key;
  v_scope:=left('penta:'||lower(v_system.system_key),128);
  v_memory:=public.penta_context_query_v1(
    v_scope,coalesce(p_query,''),greatest(1,least(coalesce(p_limit,4),12)),4096,
    null,'internal','penta.context'
  );
  return jsonb_build_object(
    'ok',true,
    'contract','ct.penta.scoped-memory-cursor.v1',
    'system_key',v_system.system_key,
    'canonical_name',v_system.canonical_name,
    'version',v_system.version,
    'maturity',v_system.maturity,
    'authority_ceiling',v_system.risk_ceiling,
    'memory_scope',v_scope,
    'cursor',coalesce(v_cookie.observed_state->'scoped_cursor','{}'::jsonb),
    'assist_contract',coalesce(v_cookie.observed_state->'assist_contract','{}'::jsonb),
    'memory',v_memory,
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
set search_path to 'pg_catalog', 'public'
as $function$
declare
  r record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,1000),2000));
  v_considered integer:=0;
  v_initialized integer:=0;
  v_deferred integer:=0;
  v_result jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  for r in
    select s.system_key
    from public.penta_system_registry s
    left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
    where s.maturity<>'retired'
      and (
        c.cookie_id is null
        or coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'
      )
    order by s.system_key
    limit v_limit
  loop
    v_considered:=v_considered+1;
    begin
      v_result:=public.penta_scoped_memory_cursor_write_v1(
        r.system_key,'registry:'||r.system_key,null,'idle',r.system_key,null,null,
        jsonb_build_array('ct.penta.scoped-memory-cursor.v1:bootstrap'),
        'penta.context'
      );
      if coalesce(v_result->>'ok','false')='true' then v_initialized:=v_initialized+1;
      elsif v_result->'cookie'->>'state'='deferred_contention' then v_deferred:=v_deferred+1;
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
    'remaining',(
      select count(*)
      from public.penta_system_registry s
      left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
      where s.maturity<>'retired'
        and (c.cookie_id is null or coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1')
    ),
    'authority_created',false,
    'destructive_authority',false,
    'observed_at',clock_timestamp()
  );
end
$function$;

create or replace function public.penta_scoped_memory_cursor_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $function$
  select jsonb_build_object(
    'contract','ct.penta.scoped-memory-cursor.v1',
    'registered',count(*),
    'cookie_installed',count(*) filter (where c.cookie_id is not null),
    'scoped_cursor_ready',count(*) filter (where c.observed_state->'scoped_cursor'->>'contract'='ct.penta.scoped-memory-cursor.v1'),
    'missing_scoped_cursor',count(*) filter (where c.cookie_id is null or coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'),
    'penta_chat_assist','context_only',
    'penta_brain_assist','planning_only',
    'authority_created',false,
    'destructive_authority',false,
    'observed_at',clock_timestamp()
  )
  from public.penta_system_registry s
  left join public.penta_protocol_cookies_v1 c on c.system_key=s.system_key
  where s.maturity<>'retired';
$function$;

revoke all on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_reconcile_v1(integer) from public,anon,authenticated;
revoke all on function public.penta_scoped_memory_cursor_status_v1() from public,anon,authenticated;
grant execute on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text) to service_role;
grant execute on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) to service_role;
grant execute on function public.penta_scoped_memory_cursor_reconcile_v1(integer) to service_role;
grant execute on function public.penta_scoped_memory_cursor_status_v1() to service_role;

comment on function public.penta_scoped_memory_cursor_write_v1(text,text,text,text,text,text,text,jsonb,text) is
'Writes a minimal redacted per-system working cursor into the existing Penta protocol cookie and optionally appends a bounded PentaContext memory. PentaChat assistance is context-only; PentaBrain assistance is planning-only; no authority is created.';
comment on function public.penta_scoped_memory_cursor_read_v1(text,text,integer) is
'Reads one registered system scoped cursor plus bounded internal PentaContext recall. Service-role only; no secret or authority surface is created.';
comment on function public.penta_scoped_memory_cursor_reconcile_v1(integer) is
'Idempotently initializes the scoped-memory cursor contract for registered non-retired systems using existing cookies. Additive only; no deletion or scheduler creation.';
comment on function public.penta_scoped_memory_cursor_status_v1() is
'Aggregated coverage status for the scoped Penta memory/cursor compatibility fabric.';

commit;
