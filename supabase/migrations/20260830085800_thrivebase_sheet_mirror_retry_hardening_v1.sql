-- ThriveBase Sheets Mirror retry/pagination hardening v1
-- Finding: 449f9fb4-1300-478c-91dd-1dde6a9f318f
-- Authority: D2 bounded remediation. No D3/provider/credential authority is created.

alter table integration_control.thrivebase_sheet_mirror_queue_v1
  add column if not exists next_attempt_at timestamptz,
  add column if not exists transient_failure_count integer not null default 0;

create index if not exists idx_thrivebase_sheet_mirror_queue_retry_v1
  on integration_control.thrivebase_sheet_mirror_queue_v1(state,next_attempt_at,priority,enqueued_at)
  where state in ('QUEUED','PARTIAL');

create or replace function public.thrivebase_sheet_mirror_claim_v1(
  p_limit integer default 4,
  p_lease_seconds integer default 900
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public'
as $function$
declare
  v_token uuid:=gen_random_uuid();
  v_ids uuid[];
begin
  select array_agg(queue_id) into v_ids
  from (
    select q.queue_id
    from integration_control.thrivebase_sheet_mirror_queue_v1 q
    join integration_control.thrivebase_sheet_mirror_registry_v1 r
      on r.table_uuid=q.table_uuid and r.current
    join integration_control.thrivebase_sheet_mirror_shards_v1 s
      on s.table_uuid=q.table_uuid
     and s.snapshot_generation=q.snapshot_generation
     and s.shard_index=q.shard_index
    where q.state in ('QUEUED','PARTIAL')
      and (q.lease_expires_at is null or q.lease_expires_at<now())
      and (q.next_attempt_at is null or q.next_attempt_at<=now())
      and q.attempt_count<q.max_attempts
      and nullif(s.spreadsheet_id,'') is not null
      and s.state in ('PROVISIONED','PARTIAL','VERIFIED','WRITING')
    order by q.priority,q.enqueued_at
    for update of q skip locked
    limit greatest(1,least(coalesce(p_limit,4),12))
  ) s;

  if v_ids is null then
    return jsonb_build_object('lease_token',v_token,'tasks','[]'::jsonb);
  end if;

  update integration_control.thrivebase_sheet_mirror_queue_v1
  set state='CLAIMED',
      lease_token=v_token,
      lease_expires_at=now()+make_interval(secs=>greatest(120,least(coalesce(p_lease_seconds,900),3600))),
      attempt_count=attempt_count+1,
      updated_at=now()
  where queue_id=any(v_ids);

  return jsonb_build_object(
    'lease_token',v_token,
    'tasks',(
      select coalesce(jsonb_agg(jsonb_build_object(
        'queue_id',q.queue_id,
        'table_uuid',r.table_uuid,
        'table_did',r.table_did,
        'schema_name',r.schema_name,
        'table_name',r.table_name,
        'source_schema_sha256',r.source_schema_sha256,
        'gm_fingerprint_sha256',r.gm_fingerprint_sha256,
        'penta_code',r.penta_code,
        'penta_envelope',r.penta_envelope,
        'mirror_mode',r.mirror_mode,
        'capacity_mode',r.capacity_mode,
        'sensitivity_class',r.sensitivity_class,
        'estimated_rows',r.estimated_rows,
        'estimated_bytes',r.estimated_bytes,
        'column_count',r.column_count,
        'estimated_cells',r.estimated_cells,
        'primary_key_columns',r.primary_key_columns,
        'source_column_contract',r.source_column_contract,
        'drive_schema_folder_id',r.drive_schema_folder_id,
        'primary_spreadsheet_id',s.spreadsheet_id,
        'primary_spreadsheet_url',s.spreadsheet_url,
        'snapshot_generation',q.snapshot_generation,
        'next_offset',q.next_offset,
        'page_size',q.page_size,
        'shard_index',q.shard_index,
        'lease_token',q.lease_token,
        'lease_expires_at',q.lease_expires_at,
        'next_attempt_at',q.next_attempt_at,
        'transient_failure_count',q.transient_failure_count
      ) order by q.priority,q.enqueued_at),'[]'::jsonb)
      from integration_control.thrivebase_sheet_mirror_queue_v1 q
      join integration_control.thrivebase_sheet_mirror_registry_v1 r
        on r.table_uuid=q.table_uuid
      join integration_control.thrivebase_sheet_mirror_shards_v1 s
        on s.table_uuid=q.table_uuid
       and s.snapshot_generation=q.snapshot_generation
       and s.shard_index=q.shard_index
      where q.queue_id=any(v_ids)
    )
  );
end
$function$;

create or replace function public.thrivebase_sheet_mirror_record_progress_v1(
  p_queue_id uuid,
  p_lease_token uuid,
  p_spreadsheet_id text,
  p_spreadsheet_url text,
  p_shard_index integer,
  p_rows_written integer,
  p_next_offset bigint,
  p_complete boolean,
  p_provider_revision_id text,
  p_provider_readback_sha256 text,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions'
as $function$
declare
  q integration_control.thrivebase_sheet_mirror_queue_v1%rowtype;
  r integration_control.thrivebase_sheet_mirror_registry_v1%rowtype;
  v_state text;
  v_evidence_sha text;
begin
  select * into q from integration_control.thrivebase_sheet_mirror_queue_v1 where queue_id=p_queue_id for update;
  if not found or q.lease_token is distinct from p_lease_token or q.lease_expires_at<now() then raise exception 'mirror_lease_invalid'; end if;
  select * into r from integration_control.thrivebase_sheet_mirror_registry_v1 where table_uuid=q.table_uuid;
  v_state:=case when p_complete then 'COMPLETE' else 'PARTIAL' end;

  update integration_control.thrivebase_sheet_mirror_queue_v1
  set state=v_state,
      next_offset=p_next_offset,
      shard_index=p_shard_index,
      lease_token=null,
      lease_expires_at=null,
      next_attempt_at=null,
      transient_failure_count=0,
      attempt_count=0,
      updated_at=now()
  where queue_id=p_queue_id;

  update integration_control.thrivebase_sheet_mirror_registry_v1
  set sync_state=case when p_complete then 'SYNCED' else 'PARTIAL' end,
      primary_spreadsheet_id=coalesce(primary_spreadsheet_id,p_spreadsheet_id),
      primary_spreadsheet_url=coalesce(primary_spreadsheet_url,p_spreadsheet_url),
      last_snapshot_generation=q.snapshot_generation,
      last_snapshot_started_at=coalesce(last_snapshot_started_at,now()),
      last_snapshot_completed_at=case when p_complete then now() else last_snapshot_completed_at end,
      last_row_count=case when p_complete then p_next_offset else last_row_count end,
      last_source_digest=p_provider_readback_sha256,
      last_error_class=null,
      penta_code='PENTA:TBL/1|did='||r.table_did||'|uuid='||r.table_uuid::text||'|src='||r.schema_name||'.'||r.table_name||'|fp='||r.gm_fingerprint_sha256||'|mode='||r.mirror_mode||'|state='||case when p_complete then 'SYNCED' else 'PARTIAL' end,
      updated_at=now()
  where table_uuid=q.table_uuid;

  insert into integration_control.thrivebase_sheet_mirror_shards_v1(
    table_uuid,snapshot_generation,shard_index,row_offset_start,row_offset_end,spreadsheet_id,spreadsheet_url,spreadsheet_title,state,provider_revision_id,observed_grid_sha256,metadata
  ) values(
    q.table_uuid,q.snapshot_generation,p_shard_index,greatest(0,p_next_offset-p_rows_written),p_next_offset,p_spreadsheet_id,p_spreadsheet_url,
    r.schema_name||'.'||r.table_name||' — part '||lpad(p_shard_index::text,3,'0'),
    case when p_complete then 'COMPLETE' else 'WRITING' end,p_provider_revision_id,p_provider_readback_sha256,coalesce(p_evidence,'{}'::jsonb)
  )
  on conflict(table_uuid,snapshot_generation,shard_index) do update
    set row_offset_end=excluded.row_offset_end,
        spreadsheet_id=excluded.spreadsheet_id,
        spreadsheet_url=excluded.spreadsheet_url,
        state=excluded.state,
        provider_revision_id=excluded.provider_revision_id,
        observed_grid_sha256=excluded.observed_grid_sha256,
        metadata=integration_control.thrivebase_sheet_mirror_shards_v1.metadata||excluded.metadata,
        updated_at=now();

  v_evidence_sha:=encode(extensions.digest(r.table_did||'|'||q.snapshot_generation::text||'|'||p_shard_index::text||'|'||p_next_offset::text||'|'||coalesce(p_provider_readback_sha256,''),'sha256'),'hex');
  insert into integration_control.thrivebase_sheet_mirror_receipts_v1(
    table_uuid,snapshot_generation,shard_index,event_type,state,source_row_count,rows_written,source_schema_sha256,gm_fingerprint_sha256,provider_file_id,provider_revision_id,provider_readback_sha256,evidence_sha256,evidence
  ) values(
    q.table_uuid,q.snapshot_generation,p_shard_index,'SHEET_MIRROR_PROGRESS',v_state,r.estimated_rows,p_rows_written,r.source_schema_sha256,r.gm_fingerprint_sha256,p_spreadsheet_id,p_provider_revision_id,p_provider_readback_sha256,v_evidence_sha,coalesce(p_evidence,'{}'::jsonb)
  );
  return jsonb_build_object('ok',true,'state',v_state,'table_did',r.table_did,'next_offset',p_next_offset,'evidence_sha256',v_evidence_sha);
end
$function$;

create or replace function public.thrivebase_sheet_mirror_record_failure_v1(
  p_queue_id uuid,
  p_lease_token uuid,
  p_error_class text,
  p_error_sha256 text,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions'
as $function$
declare
  q integration_control.thrivebase_sheet_mirror_queue_v1%rowtype;
  r integration_control.thrivebase_sheet_mirror_registry_v1%rowtype;
  v_retryable boolean:=lower(coalesce(p_evidence->>'retryable','false'))='true';
  v_retry_after_ms integer;
  v_transient_count integer;
  v_backoff_seconds integer;
  v_state text;
begin
  select * into q from integration_control.thrivebase_sheet_mirror_queue_v1 where queue_id=p_queue_id for update;
  if not found or q.lease_token is distinct from p_lease_token then raise exception 'mirror_lease_invalid'; end if;
  select * into r from integration_control.thrivebase_sheet_mirror_registry_v1 where table_uuid=q.table_uuid;

  if coalesce(p_evidence->>'retry_after_ms','') ~ '^[0-9]+$' then
    v_retry_after_ms:=least(900000,greatest(0,(p_evidence->>'retry_after_ms')::integer));
  end if;

  if v_retryable then
    v_transient_count:=coalesce(q.transient_failure_count,0)+1;
    v_backoff_seconds:=greatest(5,least(900,coalesce(ceil(v_retry_after_ms/1000.0)::integer,(5*power(2,least(v_transient_count-1,6)))::integer)));
    v_state:='PARTIAL';
    update integration_control.thrivebase_sheet_mirror_queue_v1
      set state='PARTIAL',
          attempt_count=greatest(attempt_count-1,0),
          transient_failure_count=v_transient_count,
          next_attempt_at=now()+make_interval(secs=>v_backoff_seconds),
          lease_token=null,
          lease_expires_at=null,
          updated_at=now()
      where queue_id=p_queue_id;
  else
    v_state:=case when q.attempt_count>=q.max_attempts then 'ERROR' else 'PARTIAL' end;
    update integration_control.thrivebase_sheet_mirror_queue_v1
      set state=v_state,
          next_attempt_at=null,
          lease_token=null,
          lease_expires_at=null,
          updated_at=now()
      where queue_id=p_queue_id;
  end if;

  update integration_control.thrivebase_sheet_mirror_registry_v1
    set sync_state=case when v_retryable then 'PARTIAL' else 'ERROR' end,
        last_error_class=p_error_class,
        updated_at=now()
    where table_uuid=q.table_uuid;

  insert into integration_control.thrivebase_sheet_mirror_receipts_v1(
    table_uuid,snapshot_generation,shard_index,event_type,state,source_schema_sha256,gm_fingerprint_sha256,evidence_sha256,evidence
  ) values(
    q.table_uuid,q.snapshot_generation,q.shard_index,'SHEET_MIRROR_FAILURE',v_state,r.source_schema_sha256,r.gm_fingerprint_sha256,p_error_sha256,
    coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object('retry_state',v_state,'transient_failure_count',case when v_retryable then v_transient_count else q.transient_failure_count end,'next_attempt_at',case when v_retryable then now()+make_interval(secs=>v_backoff_seconds) else null end)
  );
  return jsonb_build_object('ok',false,'state',v_state,'retryable',v_retryable,'backoff_seconds',case when v_retryable then v_backoff_seconds else null end,'error_sha256',p_error_sha256);
end
$function$;

create or replace function public.thrivebase_sheet_mirror_resume_error_v1(
  p_queue_id uuid,
  p_expected_error_sha256 text,
  p_reason text
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions'
as $function$
declare
  q integration_control.thrivebase_sheet_mirror_queue_v1%rowtype;
  r integration_control.thrivebase_sheet_mirror_registry_v1%rowtype;
  v_last_error_sha text;
  v_evidence_sha text;
begin
  if nullif(trim(coalesce(p_reason,'')),'') is null then raise exception 'mirror_resume_reason_required'; end if;
  if coalesce(p_expected_error_sha256,'') !~ '^[0-9a-f]{64}$' then raise exception 'mirror_resume_error_hash_required'; end if;

  select * into q from integration_control.thrivebase_sheet_mirror_queue_v1 where queue_id=p_queue_id for update;
  if not found then raise exception 'mirror_queue_not_found'; end if;
  if q.state<>'ERROR' or q.lease_token is not null or (q.lease_expires_at is not null and q.lease_expires_at>=now()) then raise exception 'mirror_queue_not_resumable'; end if;
  select * into r from integration_control.thrivebase_sheet_mirror_registry_v1 where table_uuid=q.table_uuid;
  select evidence_sha256 into v_last_error_sha
    from integration_control.thrivebase_sheet_mirror_receipts_v1
    where table_uuid=q.table_uuid and snapshot_generation=q.snapshot_generation and event_type='SHEET_MIRROR_FAILURE'
    order by created_at desc limit 1;
  if v_last_error_sha is distinct from p_expected_error_sha256 then raise exception 'mirror_resume_error_hash_mismatch'; end if;

  update integration_control.thrivebase_sheet_mirror_queue_v1
    set state='PARTIAL',attempt_count=0,transient_failure_count=0,next_attempt_at=now(),lease_token=null,lease_expires_at=null,updated_at=now()
    where queue_id=p_queue_id;
  update integration_control.thrivebase_sheet_mirror_registry_v1
    set sync_state='PARTIAL',last_error_class=null,updated_at=now()
    where table_uuid=q.table_uuid;

  v_evidence_sha:=encode(extensions.digest(q.queue_id::text||'|'||p_expected_error_sha256||'|'||trim(p_reason)||'|'||clock_timestamp()::text,'sha256'),'hex');
  insert into integration_control.thrivebase_sheet_mirror_receipts_v1(
    table_uuid,snapshot_generation,shard_index,event_type,state,source_schema_sha256,gm_fingerprint_sha256,evidence_sha256,evidence
  ) values(
    q.table_uuid,q.snapshot_generation,q.shard_index,'SHEET_MIRROR_RESUME','PARTIAL',r.source_schema_sha256,r.gm_fingerprint_sha256,v_evidence_sha,
    jsonb_build_object('prior_error_sha256',p_expected_error_sha256,'reason',trim(p_reason),'next_offset',q.next_offset,'authority','D2 bounded exact-error resume; no provider/credential authority')
  );
  return jsonb_build_object('ok',true,'state','PARTIAL','queue_id',q.queue_id,'next_offset',q.next_offset,'evidence_sha256',v_evidence_sha);
end
$function$;

revoke all on function public.thrivebase_sheet_mirror_resume_error_v1(uuid,text,text) from public,anon,authenticated;
grant execute on function public.thrivebase_sheet_mirror_resume_error_v1(uuid,text,text) to service_role;
grant execute on function public.thrivebase_sheet_mirror_resume_error_v1(uuid,text,text) to postgres;

comment on function public.thrivebase_sheet_mirror_resume_error_v1(uuid,text,text) is
'Governed bounded resume of an exhausted mirror task. Requires exact latest failure SHA and no active lease; retained receipts provide immutable history.';
