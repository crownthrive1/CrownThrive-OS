-- ct.thrivebase.sheets-mirror.progress-resume.v1
-- Root-cause repair discovered while validating PentaSELF finding
-- 449f9fb4-1300-478c-91dd-1dde6a9f318f.
--
-- The progress writer intentionally leaves an incomplete shard in WRITING
-- while clearing the queue lease and moving the queue to PARTIAL. The claim
-- contract previously excluded WRITING shards, so a successful first page
-- could never be reclaimed for page 2. Admit WRITING only through the existing
-- queue-state + expired/no-lease + SKIP LOCKED guards. No active lease is
-- weakened and no shard state needs destructive rewriting.

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
        'lease_expires_at',q.lease_expires_at
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
