-- QC hardening for CHLOM C13 incremental cold DAIL recovery v2.
-- This patch is intentionally in the same canonical branch as the originating build.
-- It tightens recovery evidence, fail-closed completion, and persistent HOLD behavior.

-- Replace the initial recovery function so the isolated restore must explicitly
-- prove the recovered delta's internal hash-chain, not merely count/head equality.
drop function if exists chlom_runtime.record_dail_incremental_recovery_drill_v2(
  uuid,text,timestamptz,timestamptz,bigint,bigint,bigint,text,
  boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,
  text,text,uuid
);

create or replace function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  p_checkpoint_id uuid,
  p_restore_environment_ref text,
  p_drill_started_at timestamptz,
  p_drill_completed_at timestamptz,
  p_restored_delta_event_count bigint,
  p_restored_first_sequence_id bigint,
  p_restored_max_sequence_id bigint,
  p_restored_head_event_hash text,
  p_delta_internal_chain_verified boolean,
  p_manifest_hash_verified boolean,
  p_package_hash_verified boolean,
  p_component_hashes_verified boolean,
  p_structured_data_parse_verified boolean,
  p_restore_path_verified boolean,
  p_cold_route_exercised boolean,
  p_hot_route_unchanged boolean,
  p_fault_injection_verified boolean,
  p_provider_exit_path_verified boolean,
  p_rollback_and_failback_verified boolean,
  p_recorded_by text,
  p_authority_basis text,
  p_receipt_dail_event_id uuid default null
) returns jsonb
language plpgsql
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
declare
  v_checkpoint chlom_runtime.dail_cold_incremental_checkpoints_v2%rowtype;
  v_prior_ok boolean := false;
  v_first_previous_hash text;
  v_first_links boolean;
  v_source_head_match boolean;
  v_result text;
  v_drill_id uuid;
  v_idempotency text;
  v_rto bigint;
begin
  select c.* into strict v_checkpoint
  from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
  where c.checkpoint_id=p_checkpoint_id;

  if p_drill_started_at is null or p_drill_completed_at is null
     or p_drill_completed_at<p_drill_started_at
     or p_drill_started_at<v_checkpoint.snapshot_created_at
     or p_drill_completed_at>pg_catalog.clock_timestamp()+interval '5 minutes' then
    raise exception 'invalid incremental recovery drill timestamps' using errcode='22023';
  end if;
  if pg_catalog.btrim(coalesce(p_restore_environment_ref,''))=''
     or pg_catalog.btrim(coalesce(p_recorded_by,''))=''
     or pg_catalog.btrim(coalesce(p_authority_basis,''))='' then
    raise exception 'restore ref, recorder, and authority basis are required' using errcode='22023';
  end if;
  if p_restored_delta_event_count is null or p_restored_delta_event_count<=0
     or p_restored_first_sequence_id is null or p_restored_first_sequence_id<=0
     or p_restored_max_sequence_id is null or p_restored_max_sequence_id<p_restored_first_sequence_id
     or coalesce(pg_catalog.lower(pg_catalog.btrim(p_restored_head_event_hash)),'') !~ '^[0-9a-f]{64}$' then
    raise exception 'restored incremental lineage counts/head are invalid' using errcode='22023';
  end if;

  if v_checkpoint.previous_checkpoint_kind='v2' then
    select exists(
      select 1
      from chlom_runtime.dail_incremental_recovery_drills_v2 d
      where d.checkpoint_id=v_checkpoint.previous_checkpoint_id and d.result='PASS'
    ) into v_prior_ok;
  else
    select exists(
      select 1
      from chlom_runtime.dail_recovery_drill_receipts_v1 d
      where d.checkpoint_id=v_checkpoint.previous_checkpoint_id and d.result='PASS'
    ) into v_prior_ok;
  end if;

  select e.previous_event_hash
    into v_first_previous_hash
  from chlom_runtime.dail_events e
  where e.sequence_id=v_checkpoint.delta_first_sequence_id;

  v_first_links := v_first_previous_hash is not distinct from v_checkpoint.previous_source_head_event_hash;
  v_source_head_match := coalesce(
    p_restored_delta_event_count=v_checkpoint.delta_event_count
    and p_restored_first_sequence_id=v_checkpoint.delta_first_sequence_id
    and p_restored_max_sequence_id=v_checkpoint.delta_last_sequence_id
    and pg_catalog.lower(pg_catalog.btrim(p_restored_head_event_hash))=v_checkpoint.cumulative_head_event_hash,
    false
  );

  v_result := case when
    v_prior_ok
    and v_first_links
    and v_source_head_match
    and p_delta_internal_chain_verified is true
    and p_manifest_hash_verified is true
    and p_package_hash_verified is true
    and p_component_hashes_verified is true
    and p_structured_data_parse_verified is true
    and p_restore_path_verified is true
    and p_cold_route_exercised is true
    and p_hot_route_unchanged is true
    and p_fault_injection_verified is true
    and p_provider_exit_path_verified is true
    and p_rollback_and_failback_verified is true
  then 'PASS' else 'FAIL' end;

  v_idempotency := 'ct.dail.cold.incremental.drill.v2.'||p_checkpoint_id::text;
  v_rto := greatest(0,ceil(extract(epoch from p_drill_completed_at-p_drill_started_at))::bigint);

  insert into chlom_runtime.dail_incremental_recovery_drills_v2(
    idempotency_key,checkpoint_id,restore_target_class,restore_environment_ref,
    drill_started_at,drill_completed_at,observed_rto_seconds,
    restored_delta_event_count,restored_first_sequence_id,restored_max_sequence_id,
    restored_head_event_hash,prior_checkpoint_recovery_verified,
    first_event_links_prior_head,delta_internal_chain_verified,source_head_match,
    manifest_hash_verified,package_hash_verified,component_hashes_verified,
    structured_data_parse_verified,restore_path_verified,cold_route_exercised,
    hot_route_unchanged,fault_injection_verified,provider_exit_path_verified,
    rollback_and_failback_verified,result,receipt_dail_event_id,recorded_by,authority_basis
  ) values(
    v_idempotency,p_checkpoint_id,'isolated_non_production',p_restore_environment_ref,
    p_drill_started_at,p_drill_completed_at,v_rto,
    p_restored_delta_event_count,p_restored_first_sequence_id,p_restored_max_sequence_id,
    pg_catalog.lower(pg_catalog.btrim(p_restored_head_event_hash)),v_prior_ok,
    v_first_links,coalesce(p_delta_internal_chain_verified,false),v_source_head_match,
    coalesce(p_manifest_hash_verified,false),coalesce(p_package_hash_verified,false),
    coalesce(p_component_hashes_verified,false),coalesce(p_structured_data_parse_verified,false),
    coalesce(p_restore_path_verified,false),coalesce(p_cold_route_exercised,false),
    coalesce(p_hot_route_unchanged,false),coalesce(p_fault_injection_verified,false),
    coalesce(p_provider_exit_path_verified,false),coalesce(p_rollback_and_failback_verified,false),
    v_result,p_receipt_dail_event_id,p_recorded_by,p_authority_basis
  )
  on conflict (idempotency_key) do nothing
  returning drill_id into v_drill_id;

  if v_drill_id is null then
    select d.drill_id into strict v_drill_id
    from chlom_runtime.dail_incremental_recovery_drills_v2 d
    where d.idempotency_key=v_idempotency;
  end if;

  return pg_catalog.jsonb_build_object(
    'state',case when v_result='PASS' then 'PASS_INCREMENTAL_RECOVERY' else 'FAIL_INCREMENTAL_RECOVERY' end,
    'drill_id',v_drill_id,
    'checkpoint_id',p_checkpoint_id,
    'prior_checkpoint_recovery_verified',v_prior_ok,
    'first_event_links_prior_head',v_first_links,
    'delta_internal_chain_verified',coalesce(p_delta_internal_chain_verified,false),
    'source_head_match',v_source_head_match,
    'observed_rto_seconds',v_rto,
    'result',v_result,
    'phase4_activation',false
  );
end;
$function$;

-- Replace completion so malformed/incomplete recovery evidence yields a durable
-- scoped HOLD rather than a nominally verified generic backup row.
create or replace function chlom_runtime.complete_dail_cold_incremental_backup_v2(
  p_job_id uuid,
  p_drive_target_folder_id text,
  p_drive_manifest_file_id text,
  p_drive_package_file_id text,
  p_package_sha256 text,
  p_manifest_sha256 text,
  p_package_bytes bigint,
  p_readback_verified boolean,
  p_restore_path_verified boolean,
  p_drill_evidence jsonb
) returns jsonb
language plpgsql
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
declare
  v_job chlom_runtime.backup_continuity_jobs_v2%rowtype;
  v_export chlom_runtime.dail_cold_incremental_exports_v2%rowtype;
  v_snapshot_created_at timestamptz;
  v_checkpoint jsonb;
  v_drill jsonb;
  v_checkpoint_id uuid;
  v_state text;
  v_object_ref text;
  v_error text;
  v_required_drill_evidence boolean;
begin
  select j.* into strict v_job
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.job_id=p_job_id for update;

  select x.* into strict v_export
  from chlom_runtime.dail_cold_incremental_exports_v2 x
  where x.job_id=p_job_id;

  if v_job.schedule_id<>'ct.schedule.dail-cold-incremental.hourly.v2' then
    raise exception 'job is not a DAIL incremental cold backup job' using errcode='22023';
  end if;
  if v_job.job_state='verified' then
    select c.checkpoint_id into v_checkpoint_id
    from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
    where c.job_id=p_job_id;
    return pg_catalog.jsonb_build_object(
      'state','DEDUPED_VERIFIED','job_id',p_job_id,'checkpoint_id',v_checkpoint_id
    );
  end if;
  if v_job.job_state not in ('queued','hold') then
    raise exception 'job is not completable from current state' using errcode='55000';
  end if;

  if coalesce(pg_catalog.lower(pg_catalog.btrim(p_package_sha256)),'') !~ '^[0-9a-f]{64}$'
     or coalesce(pg_catalog.lower(pg_catalog.btrim(p_manifest_sha256)),'') !~ '^[0-9a-f]{64}$'
     or p_package_bytes is null or p_package_bytes<=0
     or pg_catalog.btrim(coalesce(p_drive_target_folder_id,''))=''
     or pg_catalog.btrim(coalesce(p_drive_manifest_file_id,''))=''
     or pg_catalog.btrim(coalesce(p_drive_package_file_id,''))='' then
    raise exception 'valid provider object ids, hashes, and package bytes are required' using errcode='22023';
  end if;

  v_required_drill_evidence :=
    coalesce(pg_catalog.btrim(p_drill_evidence->>'restore_environment_ref'),'')<>''
    and coalesce(pg_catalog.btrim(p_drill_evidence->>'drill_started_at'),'')<>''
    and coalesce(pg_catalog.btrim(p_drill_evidence->>'drill_completed_at'),'')<>''
    and coalesce(pg_catalog.btrim(p_drill_evidence->>'restored_delta_event_count'),'')<>''
    and coalesce(pg_catalog.btrim(p_drill_evidence->>'restored_first_sequence_id'),'')<>''
    and coalesce(pg_catalog.btrim(p_drill_evidence->>'restored_max_sequence_id'),'')<>''
    and coalesce(pg_catalog.lower(pg_catalog.btrim(p_drill_evidence->>'restored_head_event_hash')),'') ~ '^[0-9a-f]{64}$'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'delta_internal_chain_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'manifest_hash_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'package_hash_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'component_hashes_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'structured_data_parse_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'cold_route_exercised'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'hot_route_unchanged'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'fault_injection_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'provider_exit_path_verified'),'false')='true'
    and coalesce(pg_catalog.lower(p_drill_evidence->>'rollback_and_failback_verified'),'false')='true';

  if p_readback_verified is distinct from true
     or p_restore_path_verified is distinct from true
     or v_required_drill_evidence is distinct from true then
    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='hold',
        last_error='HOLD_DAIL_COLD_READBACK_OR_RECOVERY_EVIDENCE_UNVERIFIED',
        evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'readback_verified',coalesce(p_readback_verified,false),
          'restore_path_verified',coalesce(p_restore_path_verified,false),
          'required_drill_evidence_verified',coalesce(v_required_drill_evidence,false)
        ),
        completed_at=null,
        updated_at=pg_catalog.clock_timestamp()
    where job_id=p_job_id;

    update chlom_runtime.backup_manifests
    set backup_state='created',
        verified_at=null,
        metadata=coalesce(metadata,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'connector_completion_state','hold',
          'hold_reason','HOLD_DAIL_COLD_READBACK_OR_RECOVERY_EVIDENCE_UNVERIFIED'
        )
    where backup_id=v_job.backup_manifest_id;

    return pg_catalog.jsonb_build_object(
      'state','HOLD_DAIL_COLD_READBACK_OR_RECOVERY_EVIDENCE_UNVERIFIED',
      'job_id',p_job_id
    );
  end if;

  begin
    v_snapshot_created_at := coalesce(
      nullif(p_drill_evidence->>'snapshot_created_at','')::timestamptz,
      pg_catalog.clock_timestamp()
    );
    v_object_ref := 'gdrive:file:'||p_drive_package_file_id||
                    ';manifest:'||p_drive_manifest_file_id||
                    ';scope:dail_incremental_lineage_v2';

    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='verified',
        drive_target_folder_id=p_drive_target_folder_id,
        drive_manifest_file_id=p_drive_manifest_file_id,
        drive_package_file_id=p_drive_package_file_id,
        package_sha256=pg_catalog.lower(p_package_sha256),
        manifest_sha256=pg_catalog.lower(p_manifest_sha256),
        readback_verified=true,
        restore_path_verified=true,
        evidence=coalesce(evidence,'{}'::jsonb)||coalesce(p_drill_evidence,'{}'::jsonb)||
          pg_catalog.jsonb_build_object(
            'completed_by','external-evidence-relay',
            'completed_at',pg_catalog.clock_timestamp(),
            'incremental_cold_contract','ct.chlom.dail-cold-incremental.v2'
          ),
        last_error=null,
        completed_at=pg_catalog.clock_timestamp(),
        updated_at=pg_catalog.clock_timestamp()
    where job_id=p_job_id;

    update chlom_runtime.backup_manifests
    set backup_state='verified',
        destination_ref='drive:folder:'||p_drive_target_folder_id||
          ';manifest:'||p_drive_manifest_file_id||
          ';package:'||p_drive_package_file_id,
        content_sha256=pg_catalog.lower(p_package_sha256),
        manifest_sha256=pg_catalog.lower(p_manifest_sha256),
        verified_at=pg_catalog.clock_timestamp(),
        metadata=coalesce(metadata,'{}'::jsonb)||coalesce(p_drill_evidence,'{}'::jsonb)||
          pg_catalog.jsonb_build_object(
            'drive_readback_verified',true,
            'restore_path_verified',true,
            'connector_completion_state','verified',
            'incremental_cold_contract','ct.chlom.dail-cold-incremental.v2'
          )
    where backup_id=v_job.backup_manifest_id;

    v_checkpoint := chlom_runtime.record_dail_cold_incremental_checkpoint_v2(
      p_job_id,
      v_snapshot_created_at,
      pg_catalog.lower(p_manifest_sha256),
      pg_catalog.lower(p_package_sha256),
      v_object_ref,
      p_package_bytes,
      'google_drive',
      'provider_managed_at_rest',
      'ct.schedule.external-evidence-relay.hourly.v1',
      'CHLOM C13 incremental DAIL cold recovery provider readback',
      null
    );

    v_checkpoint_id := (v_checkpoint->>'checkpoint_id')::uuid;

    v_drill := chlom_runtime.record_dail_incremental_recovery_drill_v2(
      v_checkpoint_id,
      p_drill_evidence->>'restore_environment_ref',
      (p_drill_evidence->>'drill_started_at')::timestamptz,
      (p_drill_evidence->>'drill_completed_at')::timestamptz,
      (p_drill_evidence->>'restored_delta_event_count')::bigint,
      (p_drill_evidence->>'restored_first_sequence_id')::bigint,
      (p_drill_evidence->>'restored_max_sequence_id')::bigint,
      p_drill_evidence->>'restored_head_event_hash',
      (p_drill_evidence->>'delta_internal_chain_verified')::boolean,
      (p_drill_evidence->>'manifest_hash_verified')::boolean,
      (p_drill_evidence->>'package_hash_verified')::boolean,
      (p_drill_evidence->>'component_hashes_verified')::boolean,
      (p_drill_evidence->>'structured_data_parse_verified')::boolean,
      true,
      (p_drill_evidence->>'cold_route_exercised')::boolean,
      (p_drill_evidence->>'hot_route_unchanged')::boolean,
      (p_drill_evidence->>'fault_injection_verified')::boolean,
      (p_drill_evidence->>'provider_exit_path_verified')::boolean,
      (p_drill_evidence->>'rollback_and_failback_verified')::boolean,
      'ct.schedule.external-evidence-relay.hourly.v1',
      'CHLOM C13 incremental DAIL isolated recovery drill',
      null
    );
  exception when others then
    v_error := left(sqlerrm,1000);
    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='hold',
        last_error='HOLD_DAIL_INCREMENTAL_COMPLETION_EXCEPTION: '||v_error,
        completed_at=null,
        updated_at=pg_catalog.clock_timestamp()
    where job_id=p_job_id;
    update chlom_runtime.backup_manifests
    set backup_state='created',
        verified_at=null,
        metadata=coalesce(metadata,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'connector_completion_state','hold',
          'hold_reason','HOLD_DAIL_INCREMENTAL_COMPLETION_EXCEPTION'
        )
    where backup_id=v_job.backup_manifest_id;
    return pg_catalog.jsonb_build_object(
      'state','HOLD_DAIL_INCREMENTAL_COMPLETION_EXCEPTION',
      'job_id',p_job_id,
      'error_class',sqlstate
    );
  end;

  if v_drill->>'result' <> 'PASS' then
    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='hold',
        last_error='HOLD_INCREMENTAL_RECOVERY_DRILL_FAILED',
        completed_at=null,
        updated_at=pg_catalog.clock_timestamp()
    where job_id=p_job_id;
    update chlom_runtime.backup_manifests
    set backup_state='created',
        verified_at=null,
        metadata=coalesce(metadata,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'connector_completion_state','hold',
          'hold_reason','HOLD_INCREMENTAL_RECOVERY_DRILL_FAILED'
        )
    where backup_id=v_job.backup_manifest_id;
    v_state := 'HOLD_INCREMENTAL_RECOVERY_DRILL_FAILED';
  else
    v_state := 'VERIFIED_INCREMENTAL_COLD_ROUTE';
  end if;

  perform chlom_runtime.append_dail_event(
    case when v_state='VERIFIED_INCREMENTAL_COLD_ROUTE'
      then 'backup.dail_incremental.verified'
      else 'backup.dail_incremental.hold'
    end,
    'backup_job',p_job_id::text,
    pg_catalog.jsonb_build_object(
      'backup_manifest_id',v_job.backup_manifest_id,
      'checkpoint_id',v_checkpoint_id,
      'drill_id',v_drill->>'drill_id',
      'result',v_drill->>'result',
      'package_sha256',pg_catalog.lower(p_package_sha256),
      'manifest_sha256',pg_catalog.lower(p_manifest_sha256),
      'readback_verified',true,
      'restore_path_verified',true,
      'delta_internal_chain_verified',v_drill->>'delta_internal_chain_verified',
      'phase_transition',false,
      'money_movement',false
    ),
    'ct.schedule.external-evidence-relay.hourly.v1',null,
    'ct.system.chlom.dail-cold-recovery','v2',v_job.occurrence_key,null,
    'CHLOM C13 incremental DAIL cold recovery contract',null,'restricted'
  );

  return pg_catalog.jsonb_build_object(
    'state',v_state,
    'job_id',p_job_id,
    'backup_manifest_id',v_job.backup_manifest_id,
    'checkpoint',v_checkpoint,
    'drill',v_drill,
    'provider_write_authority_created',false,
    'phase4_activation',false
  );
end;
$function$;

revoke all on function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  uuid,text,timestamptz,timestamptz,bigint,bigint,bigint,text,
  boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,
  text,text,uuid
) from public, anon, authenticated;
grant execute on function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  uuid,text,timestamptz,timestamptz,bigint,bigint,bigint,text,
  boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,
  text,text,uuid
) to service_role;

revoke all on function chlom_runtime.complete_dail_cold_incremental_backup_v2(
  uuid,text,text,text,text,text,bigint,boolean,boolean,jsonb
) from public, anon, authenticated;
grant execute on function chlom_runtime.complete_dail_cold_incremental_backup_v2(
  uuid,text,text,text,text,text,bigint,boolean,boolean,jsonb
) to service_role;
