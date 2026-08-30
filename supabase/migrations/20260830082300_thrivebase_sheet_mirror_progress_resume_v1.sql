-- ct.thrivebase.sheets-mirror.progress-resume.v1
-- Root-cause repair discovered while validating PentaSELF finding
-- 449f9fb4-1300-478c-91dd-1dde6a9f318f.
--
-- Incomplete pages clear their queue lease and move the queue to PARTIAL. The
-- shard must therefore also be PARTIAL; leaving it WRITING makes the next
-- claim impossible because thrivebase_sheet_mirror_claim_v1 only admits
-- PROVISIONED/PARTIAL/VERIFIED shards.

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
  select * into q
  from integration_control.thrivebase_sheet_mirror_queue_v1
  where queue_id=p_queue_id
  for update;

  if not found
     or q.lease_token is distinct from p_lease_token
     or q.lease_expires_at<now() then
    raise exception 'mirror_lease_invalid';
  end if;

  select * into r
  from integration_control.thrivebase_sheet_mirror_registry_v1
  where table_uuid=q.table_uuid;

  v_state:=case when p_complete then 'COMPLETE' else 'PARTIAL' end;

  update integration_control.thrivebase_sheet_mirror_queue_v1
  set state=v_state,
      next_offset=p_next_offset,
      shard_index=p_shard_index,
      lease_token=null,
      lease_expires_at=null,
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
    table_uuid,snapshot_generation,shard_index,row_offset_start,row_offset_end,
    spreadsheet_id,spreadsheet_url,spreadsheet_title,state,provider_revision_id,
    observed_grid_sha256,metadata
  ) values(
    q.table_uuid,q.snapshot_generation,p_shard_index,
    greatest(0,p_next_offset-p_rows_written),p_next_offset,
    p_spreadsheet_id,p_spreadsheet_url,
    r.schema_name||'.'||r.table_name||' — part '||lpad(p_shard_index::text,3,'0'),
    v_state,
    p_provider_revision_id,p_provider_readback_sha256,coalesce(p_evidence,'{}'::jsonb)
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

  v_evidence_sha:=encode(
    extensions.digest(
      r.table_did||'|'||q.snapshot_generation::text||'|'||p_shard_index::text||'|'||p_next_offset::text||'|'||coalesce(p_provider_readback_sha256,''),
      'sha256'
    ),
    'hex'
  );

  insert into integration_control.thrivebase_sheet_mirror_receipts_v1(
    table_uuid,snapshot_generation,shard_index,event_type,state,source_row_count,
    rows_written,source_schema_sha256,gm_fingerprint_sha256,provider_file_id,
    provider_revision_id,provider_readback_sha256,evidence_sha256,evidence
  ) values(
    q.table_uuid,q.snapshot_generation,p_shard_index,'SHEET_MIRROR_PROGRESS',v_state,
    r.estimated_rows,p_rows_written,r.source_schema_sha256,r.gm_fingerprint_sha256,
    p_spreadsheet_id,p_provider_revision_id,p_provider_readback_sha256,
    v_evidence_sha,coalesce(p_evidence,'{}'::jsonb)
  );

  return jsonb_build_object(
    'ok',true,
    'state',v_state,
    'table_did',r.table_did,
    'next_offset',p_next_offset,
    'evidence_sha256',v_evidence_sha
  );
end
$function$;

-- Repair only abandoned partial shards produced by the old contract. A live
-- lease is never touched.
update integration_control.thrivebase_sheet_mirror_shards_v1 s
set state='PARTIAL',
    updated_at=now(),
    metadata=coalesce(s.metadata,'{}'::jsonb)||jsonb_build_object(
      'repaired_by','ct.thrivebase.sheets-mirror.progress-resume.v1',
      'repaired_at',now(),
      'prior_state','WRITING',
      'authority_expansion',false
    )
from integration_control.thrivebase_sheet_mirror_queue_v1 q
where s.table_uuid=q.table_uuid
  and s.snapshot_generation=q.snapshot_generation
  and s.shard_index=q.shard_index
  and s.state='WRITING'
  and q.state='PARTIAL'
  and q.lease_token is null;
