-- CHLOM C11 DAIL cold checkpoint terminal-progress binding v1.
-- Makes the durable chunk-progress chain a mandatory predicate of provider completion.

create or replace function chlom_runtime.complete_dail_cold_checkpoint_v2(
  p_job_id uuid,
  p_drive_target_folder_id text,
  p_drive_manifest_file_id text,
  p_drive_package_file_id text,
  p_package_sha256 text,
  p_manifest_sha256 text,
  p_snapshot_bytes bigint,
  p_snapshot_created_at timestamptz,
  p_export_evidence jsonb,
  p_recovery_evidence jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=''
set timezone='UTC'
as $function$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_job chlom_runtime.backup_continuity_jobs_v2%rowtype;
  v_source_count bigint;
  v_source_max bigint;
  v_source_head text;
  v_progress_count bigint;
  v_progress_cursor bigint;
  v_progress_chunks integer;
  v_progress_last_hash text;
  v_progress_chain text;
  v_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into strict v_job
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.job_id=p_job_id
    and j.schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1';

  if v_job.job_state='verified' then
    return pg_catalog.jsonb_build_object('state','DEDUPED_VERIFIED','job_id',p_job_id,'evidence',v_job.evidence);
  end if;

  v_source_count := nullif(v_job.source_snapshot->>'source_event_count','')::bigint;
  v_source_max := nullif(v_job.source_snapshot->>'source_max_sequence_id','')::bigint;
  v_source_head := pg_catalog.lower(coalesce(v_job.source_snapshot->>'source_head_event_hash',''));
  v_progress_count := coalesce(nullif(v_job.evidence->>'exported_event_count','')::bigint,-1);
  v_progress_cursor := coalesce(nullif(v_job.evidence->>'export_cursor_sequence_id','')::bigint,-1);
  v_progress_chunks := coalesce(nullif(v_job.evidence->>'export_chunk_count','')::integer,-1);
  v_progress_last_hash := pg_catalog.lower(coalesce(v_job.evidence->>'export_last_event_hash',''));
  v_progress_chain := pg_catalog.lower(coalesce(v_job.evidence->>'export_chain_sha256',''));

  if coalesce((v_job.evidence->>'export_complete')::boolean,false) is distinct from true
     or v_source_count is null or v_source_max is null or v_source_head !~ '^[0-9a-f]{64}$'
     or v_progress_count <> v_source_count
     or v_progress_cursor <> v_source_max
     or v_progress_chunks <= 0
     or v_progress_last_hash <> v_source_head
     or v_progress_chain !~ '^[0-9a-f]{64}$'
     or pg_catalog.lower(coalesce(p_export_evidence->>'export_chain_sha256','')) <> v_progress_chain
     or coalesce((p_export_evidence->>'export_chunk_count')::integer,-1) <> v_progress_chunks
     or coalesce((p_export_evidence->>'exported_event_count')::bigint,-1) <> v_progress_count
     or coalesce((p_export_evidence->>'exported_max_sequence_id')::bigint,-1) <> v_progress_cursor
     or pg_catalog.lower(coalesce(p_export_evidence->>'exported_head_event_hash','')) <> v_progress_last_hash
     or coalesce(p_export_evidence->>'export_payload_mode','') <> 'lineage_metadata_no_payload_body'
     or coalesce((p_export_evidence->>'payload_body_included')::boolean,true) is distinct from false then
    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='hold',last_error='HOLD_DAIL_COLD_DURABLE_EXPORT_PROGRESS_MISMATCH',
        evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'terminal_progress_check_at',clock_timestamp(),
          'terminal_progress_mismatch',true
        ),updated_at=clock_timestamp()
    where job_id=p_job_id;
    return pg_catalog.jsonb_build_object(
      'state','HOLD_DAIL_COLD_DURABLE_EXPORT_PROGRESS_MISMATCH',
      'job_id',p_job_id,'provider_write',false,'phase4_activation',false
    );
  end if;

  v_result := chlom_runtime.complete_dail_cold_checkpoint_v1(
    p_job_id,p_drive_target_folder_id,p_drive_manifest_file_id,p_drive_package_file_id,
    p_package_sha256,p_manifest_sha256,p_snapshot_bytes,p_snapshot_created_at,
    p_export_evidence,p_recovery_evidence
  );

  return v_result||pg_catalog.jsonb_build_object(
    'terminal_progress_bound',true,
    'export_chain_sha256',v_progress_chain,
    'export_chunk_count',v_progress_chunks,
    'export_payload_mode','lineage_metadata_no_payload_body'
  );
end
$function$;

-- External callers must use v2 so terminal completion cannot bypass durable progress.
revoke all on function chlom_runtime.complete_dail_cold_checkpoint_v1(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) from public,anon,authenticated,service_role;
revoke all on function chlom_runtime.complete_dail_cold_checkpoint_v2(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) from public,anon,authenticated;
grant execute on function chlom_runtime.complete_dail_cold_checkpoint_v2(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) to service_role;

-- Ensure queued/resumed jobs advertise the mandatory terminal RPC.
update chlom_runtime.backup_continuity_jobs_v2
set source_snapshot=coalesce(source_snapshot,'{}'::jsonb)||pg_catalog.jsonb_build_object(
      'completion_rpc','chlom_runtime.complete_dail_cold_checkpoint_v2',
      'terminal_progress_binding_required',true
    ),updated_at=clock_timestamp()
where schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1'
  and job_state in ('queued','hold','connector_in_progress','uploaded');

create or replace function chlom_runtime.enqueue_dail_cold_checkpoint_v3(
  p_force boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path=''
set timezone='UTC'
as $function$
declare
  v_result jsonb;
  v_job uuid;
begin
  v_result := chlom_runtime.enqueue_dail_cold_checkpoint_v2(p_force);
  v_job := nullif(v_result->>'job_id','')::uuid;
  if v_job is not null then
    update chlom_runtime.backup_continuity_jobs_v2
    set source_snapshot=coalesce(source_snapshot,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'completion_rpc','chlom_runtime.complete_dail_cold_checkpoint_v2',
          'terminal_progress_binding_required',true
        ),updated_at=clock_timestamp()
    where job_id=v_job and schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1';
  end if;
  return v_result||pg_catalog.jsonb_build_object(
    'protocol_revision','terminal-progress-binding-v1',
    'completion_rpc','chlom_runtime.complete_dail_cold_checkpoint_v2',
    'terminal_progress_binding_required',true
  );
end
$function$;

revoke all on function chlom_runtime.enqueue_dail_cold_checkpoint_v3(boolean) from public,anon,authenticated;
grant execute on function chlom_runtime.enqueue_dail_cold_checkpoint_v3(boolean) to service_role;

do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule(
    'ct-dail-cold-checkpoint-due-v1',
    '17 * * * *',
    'select chlom_runtime.enqueue_dail_cold_checkpoint_v3(false);'
  );
end
$block$;
