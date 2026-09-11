-- CHLOM C11 / DAIL cold checkpoint connector protocol v1
-- Source-only candidate. No provider write, credential mutation, money movement,
-- rights grant, D3 action, or production activation occurs merely by source presence.

create or replace function chlom_runtime.record_dail_cold_checkpoint_v2(
  p_idempotency_key text,
  p_source_event_count bigint,
  p_source_max_sequence_id bigint,
  p_source_head_event_hash text,
  p_snapshot_created_at timestamptz,
  p_snapshot_manifest_sha256 text,
  p_snapshot_package_sha256 text,
  p_snapshot_object_ref text,
  p_snapshot_bytes bigint,
  p_storage_provider text,
  p_encryption_state text,
  p_custody_verified boolean,
  p_readback_verified boolean,
  p_restore_path_verified boolean,
  p_recorded_by text,
  p_authority_basis text,
  p_receipt_dail_event_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path=''
set timezone='UTC'
as $function$
declare
  v_key text := pg_catalog.btrim(p_idempotency_key);
  v_source_head text := pg_catalog.lower(pg_catalog.btrim(p_source_head_event_hash));
  v_manifest_hash text := pg_catalog.lower(pg_catalog.btrim(p_snapshot_manifest_sha256));
  v_package_hash text := pg_catalog.lower(pg_catalog.btrim(p_snapshot_package_sha256));
  v_object_ref text := pg_catalog.btrim(p_snapshot_object_ref);
  v_recorded_by text := pg_catalog.btrim(p_recorded_by);
  v_authority_basis text := pg_catalog.btrim(p_authority_basis);
  v_verify jsonb;
  v_source_actual_count bigint;
  v_source_min bigint;
  v_source_created_at timestamptz;
  v_hot_count bigint;
  v_hot_max bigint;
  v_hot_head text;
  v_rpo bigint;
  v_checkpoint_id uuid := extensions.gen_random_uuid();
  v_inserted_id uuid;
  v_recorded_at timestamptz := pg_catalog.clock_timestamp();
  v_verify_sha text;
  v_previous_receipt_sha text;
  v_receipt_sha text;
  v_existing chlom_runtime.dail_cold_checkpoints_v1%rowtype;
begin
  if v_key is null or pg_catalog.length(v_key) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode='22023';
  end if;
  if p_source_event_count is null or p_source_event_count <= 0
     or p_source_max_sequence_id is null or p_source_max_sequence_id <= 0 then
    raise exception 'source event count and max sequence must be positive' using errcode='22023';
  end if;
  if v_source_head !~ '^[0-9a-f]{64}$'
     or v_manifest_hash !~ '^[0-9a-f]{64}$'
     or v_package_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'source, manifest, and package hashes must be lowercase SHA-256 values' using errcode='22023';
  end if;
  if p_snapshot_created_at is null
     or p_snapshot_created_at > pg_catalog.clock_timestamp() + interval '5 minutes' then
    raise exception 'snapshot creation time is invalid' using errcode='22023';
  end if;
  if p_snapshot_bytes is null or p_snapshot_bytes <= 0 then
    raise exception 'snapshot byte count must be positive' using errcode='22023';
  end if;
  if p_storage_provider not in ('google_drive','s3','gcs','azure_blob','other_provider_managed') then
    raise exception 'unsupported storage provider' using errcode='22023';
  end if;
  if p_encryption_state not in ('provider_managed_at_rest','client_managed','provider_and_client_managed') then
    raise exception 'unsupported encryption state' using errcode='22023';
  end if;
  if p_custody_verified is distinct from true
     or p_readback_verified is distinct from true
     or p_restore_path_verified is distinct from true then
    raise exception 'cold checkpoint requires custody, readback, and restore-path verification' using errcode='22023';
  end if;
  if v_object_ref is null or pg_catalog.length(v_object_ref) not between 1 and 1024
     or v_recorded_by is null or pg_catalog.length(v_recorded_by) not between 1 and 255
     or v_authority_basis is null or pg_catalog.length(v_authority_basis) not between 1 and 1024 then
    raise exception 'object reference, recorder, or authority basis is invalid' using errcode='22023';
  end if;

  -- Expensive verification occurs before the short cold-receipt critical section.
  -- This uses the checkpoint+tail verifier rather than the legacy exhaustive full-chain
  -- scan under the global DAIL append lock.
  v_verify := chlom_runtime.verify_dail_chain_checkpoint_v3();
  if coalesce((v_verify->>'ok')::boolean,false) is distinct from true
     or coalesce((v_verify->>'tail_failure_count')::integer,-1) <> 0 then
    raise exception 'bounded hot DAIL integrity verification did not pass' using errcode='55000';
  end if;

  select e.created_at
    into v_source_created_at
  from chlom_runtime.dail_events e
  where e.sequence_id=p_source_max_sequence_id and e.event_hash=v_source_head;
  if not found then
    raise exception 'snapshot source head is not present in immutable DAIL' using errcode='22023';
  end if;

  select pg_catalog.count(*), pg_catalog.min(e.sequence_id)
    into v_source_actual_count, v_source_min
  from chlom_runtime.dail_events e
  where e.sequence_id <= p_source_max_sequence_id;
  if v_source_actual_count <> p_source_event_count then
    raise exception 'snapshot event count does not match DAIL source prefix' using errcode='22023';
  end if;

  select pg_catalog.count(*), pg_catalog.max(e.sequence_id)
    into v_hot_count, v_hot_max
  from chlom_runtime.dail_events e;
  select e.event_hash into v_hot_head
  from chlom_runtime.dail_events e
  order by e.sequence_id desc limit 1;

  if coalesce((v_verify->>'current_max_sequence_id')::bigint,-1) > v_hot_max
     or coalesce(v_verify->>'current_head_hash','') = '' then
    raise exception 'bounded verifier readback is internally inconsistent' using errcode='55000';
  end if;
  if p_snapshot_created_at < v_source_created_at then
    raise exception 'snapshot predates declared source head' using errcode='22023';
  end if;

  v_rpo := pg_catalog.ceil(extract(epoch from p_snapshot_created_at-v_source_created_at))::bigint;
  v_verify_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_verify::text,'UTF8'),'sha256'),'hex'
  );

  -- Serialize only the cold checkpoint receipt chain; do not block DAIL appends.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtext('chlom_runtime.dail.cold-checkpoint.receipt.v2')
  );
  select c.checkpoint_receipt_sha256 into v_previous_receipt_sha
  from chlom_runtime.dail_cold_checkpoints_v1 c
  order by c.recorded_at desc,c.checkpoint_id desc limit 1;

  v_receipt_sha := pg_catalog.encode(
    extensions.digest(
      pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
          'contract','ct.chlom.dail-cold-checkpoint.v2',
          'previous_checkpoint_receipt_sha256',coalesce(v_previous_receipt_sha,'GENESIS'),
          'checkpoint_id',v_checkpoint_id,
          'idempotency_key',v_key,
          'source_event_count',p_source_event_count,
          'source_max_sequence_id',p_source_max_sequence_id,
          'source_head_event_hash',v_source_head,
          'snapshot_created_at',pg_catalog.to_char(p_snapshot_created_at at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
          'snapshot_manifest_sha256',v_manifest_hash,
          'snapshot_package_sha256',v_package_hash,
          'snapshot_object_ref',v_object_ref,
          'snapshot_bytes',p_snapshot_bytes,
          'storage_provider',p_storage_provider,
          'encryption_state',p_encryption_state,
          'verifier_output_sha256',v_verify_sha,
          'hot_head_event_hash_at_recording',v_hot_head,
          'recorded_by',v_recorded_by,
          'authority_basis',v_authority_basis,
          'recorded_at',pg_catalog.to_char(v_recorded_at at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        )::text,'UTF8'
      ),'sha256'
    ),'hex'
  );

  insert into chlom_runtime.dail_cold_checkpoints_v1(
    checkpoint_id,idempotency_key,source_event_count,source_min_sequence_id,
    source_max_sequence_id,source_head_event_hash,source_head_created_at,
    snapshot_created_at,snapshot_rpo_seconds,hot_event_count_at_recording,
    hot_max_sequence_id_at_recording,hot_head_event_hash_at_recording,
    hot_integrity_state,verification_checked_at,verification_failure_count,
    documented_correction_count,verifier_output,verifier_output_sha256,
    snapshot_manifest_sha256,snapshot_package_sha256,snapshot_object_ref,
    snapshot_bytes,storage_provider,encryption_state,custody_verified,
    readback_verified,restore_path_verified,receipt_dail_event_id,recorded_by,
    authority_basis,recorded_at,previous_checkpoint_receipt_sha256,
    checkpoint_receipt_sha256
  ) values (
    v_checkpoint_id,v_key,p_source_event_count,v_source_min,p_source_max_sequence_id,
    v_source_head,v_source_created_at,p_snapshot_created_at,v_rpo,v_hot_count,v_hot_max,
    v_hot_head,v_verify->>'integrity_state',coalesce((v_verify->>'checked_at')::timestamptz,clock_timestamp()),
    coalesce((v_verify->>'tail_failure_count')::integer,0),
    coalesce((v_verify->>'tail_corrected_event_count')::integer,0),
    v_verify,v_verify_sha,v_manifest_hash,v_package_hash,v_object_ref,p_snapshot_bytes,
    p_storage_provider,p_encryption_state,true,true,true,p_receipt_dail_event_id,
    v_recorded_by,v_authority_basis,v_recorded_at,v_previous_receipt_sha,v_receipt_sha
  )
  on conflict(idempotency_key) do nothing
  returning checkpoint_id into v_inserted_id;

  if v_inserted_id is null then
    select c.* into strict v_existing
    from chlom_runtime.dail_cold_checkpoints_v1 c where c.idempotency_key=v_key;
    if v_existing.source_event_count <> p_source_event_count
       or v_existing.source_max_sequence_id <> p_source_max_sequence_id
       or v_existing.source_head_event_hash <> v_source_head
       or v_existing.snapshot_manifest_sha256 <> v_manifest_hash
       or v_existing.snapshot_package_sha256 <> v_package_hash
       or v_existing.snapshot_object_ref <> v_object_ref
       or v_existing.snapshot_bytes <> p_snapshot_bytes
       or v_existing.storage_provider <> p_storage_provider
       or v_existing.encryption_state <> p_encryption_state
       or v_existing.recorded_by <> v_recorded_by
       or v_existing.authority_basis <> v_authority_basis then
      raise exception 'idempotency key collision for DAIL cold checkpoint' using errcode='23505';
    end if;
    v_checkpoint_id := v_existing.checkpoint_id;
    v_rpo := v_existing.snapshot_rpo_seconds;
    v_verify_sha := v_existing.verifier_output_sha256;
    v_receipt_sha := v_existing.checkpoint_receipt_sha256;
    v_previous_receipt_sha := v_existing.previous_checkpoint_receipt_sha256;
  end if;

  return pg_catalog.jsonb_build_object(
    'checkpoint_id',v_checkpoint_id,
    'contract','ct.chlom.dail-cold-checkpoint.v2',
    'route','cold_recovery',
    'state','CHECKPOINT_CUSTODY_VERIFIED',
    'source_event_count',p_source_event_count,
    'source_max_sequence_id',p_source_max_sequence_id,
    'source_head_event_hash',v_source_head,
    'hot_integrity_state',v_verify->>'integrity_state',
    'snapshot_rpo_seconds',v_rpo,
    'verifier_output_sha256',v_verify_sha,
    'previous_checkpoint_receipt_sha256',v_previous_receipt_sha,
    'checkpoint_receipt_sha256',v_receipt_sha,
    'global_dail_append_lock_held',false,
    'full_chain_scan_executed',false,
    'phase4_activation',false
  );
end
$function$;

create or replace function chlom_runtime.enqueue_dail_cold_checkpoint_v1(
  p_force boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path=''
set timezone='UTC'
as $function$
declare
  v_status jsonb;
  v_cold_state text;
  v_verify jsonb;
  v_source_count bigint;
  v_source_min bigint;
  v_source_max bigint;
  v_source_head text;
  v_source_head_created_at timestamptz;
  v_source_snapshot jsonb;
  v_source_sha text;
  v_occurrence_key text;
  v_job uuid;
  v_manifest uuid;
  v_existing uuid;
begin
  v_status := chlom_runtime.read_dail_phase4_assurance_status_v2(86400);
  v_cold_state := coalesce(v_status#>>'{cold_route,state}','UNKNOWN');
  if not p_force and v_cold_state='PASS' then
    return pg_catalog.jsonb_build_object('state','NOT_DUE','cold_state',v_cold_state,'observed_at',clock_timestamp());
  end if;

  select j.job_id into v_existing
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1'
    and j.job_state in ('queued','connector_in_progress','uploaded','hold')
  order by j.due_at desc limit 1;
  if found then
    return pg_catalog.jsonb_build_object('state','DEDUPED','job_id',v_existing,'cold_state',v_cold_state);
  end if;

  v_verify := chlom_runtime.verify_dail_chain_checkpoint_v3();
  if coalesce((v_verify->>'ok')::boolean,false) is distinct from true
     or coalesce((v_verify->>'tail_failure_count')::integer,-1) <> 0 then
    raise exception 'hot DAIL checkpoint+tail verification must pass before cold export queueing' using errcode='55000';
  end if;

  v_source_max := nullif(v_verify->>'current_max_sequence_id','')::bigint;
  v_source_head := pg_catalog.lower(coalesce(v_verify->>'current_head_hash',''));
  if v_source_max is null or v_source_max <= 0 or v_source_head !~ '^[0-9a-f]{64}$' then
    raise exception 'bounded verifier did not return a valid current DAIL head' using errcode='55000';
  end if;

  select pg_catalog.count(*),pg_catalog.min(e.sequence_id)
    into v_source_count,v_source_min
  from chlom_runtime.dail_events e where e.sequence_id <= v_source_max;
  select e.created_at into v_source_head_created_at
  from chlom_runtime.dail_events e
  where e.sequence_id=v_source_max and e.event_hash=v_source_head;
  if not found then
    raise exception 'verified current DAIL head is not readable' using errcode='55000';
  end if;

  v_occurrence_key := 'ct.backup.dail-cold.'||v_source_max::text||'.'||pg_catalog.substr(v_source_head,1,16);
  select j.job_id into v_existing
  from chlom_runtime.backup_continuity_jobs_v2 j where j.occurrence_key=v_occurrence_key;
  if found then
    return pg_catalog.jsonb_build_object('state','DEDUPED_SOURCE','job_id',v_existing,'occurrence_key',v_occurrence_key);
  end if;

  v_source_snapshot := pg_catalog.jsonb_build_object(
    'schema','ct.backup.dail-cold.connector-job.v1',
    'source_schema','chlom_runtime',
    'source_table','dail_events',
    'source_event_count',v_source_count,
    'source_min_sequence_id',v_source_min,
    'source_max_sequence_id',v_source_max,
    'source_head_event_hash',v_source_head,
    'source_head_created_at',v_source_head_created_at,
    'hot_verification',v_verify,
    'hot_verification_sha256',pg_catalog.encode(extensions.digest(pg_catalog.convert_to(v_verify::text,'UTF8'),'sha256'),'hex'),
    'connector_protocol','ct.backup.dail-cold.chunked-export.v1',
    'chunk_rpc','public.dail_cold_checkpoint_export_chunk_v1',
    'chunk_size',2000,
    'chunk_max',5000,
    'completion_rpc','chlom_runtime.complete_dail_cold_checkpoint_v1',
    'restore_scope','ledger_lineage',
    'restore_target_class','isolated_non_production',
    'requires_chunk_chain_verification',true,
    'requires_component_hash_verification',true,
    'requires_provider_readback',true,
    'requires_restore_drill',true,
    'contains_raw_credentials',false,
    'contains_private_keys',false,
    'provider_write_from_database',false,
    'external_connector_owner','ct.schedule.external-evidence-relay.hourly.v1',
    'drive_archive_root_id','1Xdgi5LMG17j_dOw0ESJw44Py9WXBYzTs',
    'drive_daily_snapshots_id','1WTvRuU2JBVn60AyJxxGgHegNZpS2U5Oy'
  );
  v_source_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_source_snapshot::text,'UTF8'),'sha256'),'hex'
  );

  insert into chlom_runtime.backup_manifests(
    backup_class,source_system,destination_system,destination_ref,encryption_profile,
    secret_reference,content_sha256,manifest_sha256,backup_state,contains_secrets,metadata
  ) values (
    'dail_cold_checkpoint_v1','chlom_runtime.dail_events','google_drive',
    'drive:folder:1Xdgi5LMG17j_dOw0ESJw44Py9WXBYzTs;daily:1WTvRuU2JBVn60AyJxxGgHegNZpS2U5Oy',
    'provider_managed_at_rest_no_plaintext_secrets',null,v_source_sha,v_source_sha,'planned',false,
    pg_catalog.jsonb_build_object(
      'schedule_id','ct.schedule.dail-cold-checkpoint.daily.v1',
      'occurrence_key',v_occurrence_key,
      'connector_required',true,
      'connector_protocol','ct.backup.dail-cold.chunked-export.v1',
      'source_snapshot_sha256',v_source_sha,
      'authority_effect','none',
      'phase4_activation',false
    )
  ) returning backup_id into v_manifest;

  insert into chlom_runtime.backup_continuity_jobs_v2(
    schedule_id,occurrence_key,local_backup_date,due_at,job_state,backup_manifest_id,
    drive_archive_root_id,drive_daily_snapshots_id,source_snapshot,evidence
  ) values (
    'ct.schedule.dail-cold-checkpoint.daily.v1',v_occurrence_key,
    (clock_timestamp() at time zone 'America/New_York')::date,clock_timestamp(),'queued',v_manifest,
    '1Xdgi5LMG17j_dOw0ESJw44Py9WXBYzTs','1WTvRuU2JBVn60AyJxxGgHegNZpS2U5Oy',
    v_source_snapshot,
    pg_catalog.jsonb_build_object(
      'source_snapshot_sha256',v_source_sha,
      'requested_by','chlom-c11-dail-cold-checkpoint-v1',
      'connector_failure_domain','google_drive',
      'no_duplicate_external_clock',true,
      'd3_human_reserved',true,
      'provider_write_from_database',false
    )
  ) returning job_id into v_job;

  perform chlom_runtime.append_dail_event(
    'backup.dail-cold.queued','backup_job',v_job::text,
    pg_catalog.jsonb_build_object(
      'schedule_id','ct.schedule.dail-cold-checkpoint.daily.v1',
      'occurrence_key',v_occurrence_key,
      'backup_manifest_id',v_manifest,
      'source_event_count',v_source_count,
      'source_max_sequence_id',v_source_max,
      'source_head_event_hash',v_source_head,
      'source_snapshot_sha256',v_source_sha,
      'connector_protocol','ct.backup.dail-cold.chunked-export.v1',
      'phase_transition',false,'provider_write',false,'money_movement',false
    ),
    'chlom-c11-due-generator',null,'ct.system.chlom.dail-cold-checkpoint','v1',
    v_occurrence_key,null,
    'CHLOM C11 bounded cold-recovery due generation; external connector remains separate',
    null,'restricted'
  );

  return pg_catalog.jsonb_build_object(
    'state','QUEUED','job_id',v_job,'backup_manifest_id',v_manifest,
    'occurrence_key',v_occurrence_key,'source_event_count',v_source_count,
    'source_max_sequence_id',v_source_max,'source_head_event_hash',v_source_head,
    'source_snapshot_sha256',v_source_sha,'cold_state_before_queue',v_cold_state,
    'provider_write',false,'phase4_activation',false
  );
end
$function$;

create or replace function public.dail_cold_checkpoint_export_chunk_v1(
  p_job_id uuid,
  p_after_sequence_id bigint default 0,
  p_limit integer default 2000
)
returns jsonb
language plpgsql
stable
security definer
set search_path=''
set timezone='UTC'
as $function$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_job chlom_runtime.backup_continuity_jobs_v2%rowtype;
  v_source_count bigint;
  v_source_min bigint;
  v_source_max bigint;
  v_source_head text;
  v_limit integer;
  v_events jsonb := '[]'::jsonb;
  v_count integer := 0;
  v_first bigint;
  v_last bigint;
  v_first_prev text;
  v_last_hash text;
  v_has_more boolean := false;
  v_chunk_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_job_id is null or coalesce(p_after_sequence_id,0) < 0 then
    raise exception 'valid job id and nonnegative cursor required' using errcode='22023';
  end if;
  if p_limit is null or p_limit < 1 or p_limit > 5000 then
    raise exception 'chunk limit must be between 1 and 5000' using errcode='22023';
  end if;
  v_limit := p_limit;

  select * into strict v_job
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.job_id=p_job_id
    and j.schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1'
    and j.job_state in ('queued','connector_in_progress','uploaded','hold');

  v_source_count := nullif(v_job.source_snapshot->>'source_event_count','')::bigint;
  v_source_min := nullif(v_job.source_snapshot->>'source_min_sequence_id','')::bigint;
  v_source_max := nullif(v_job.source_snapshot->>'source_max_sequence_id','')::bigint;
  v_source_head := pg_catalog.lower(coalesce(v_job.source_snapshot->>'source_head_event_hash',''));
  if v_source_count is null or v_source_min is null or v_source_max is null
     or v_source_head !~ '^[0-9a-f]{64}$' then
    raise exception 'job source snapshot is incomplete' using errcode='55000';
  end if;

  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object(
      'sequence_id',e.sequence_id,'event_id',e.event_id,'event_type',e.event_type,
      'schema_version',e.schema_version,'actor_ref',e.actor_ref,'actor_did',e.actor_did,
      'agent_id',e.agent_id,'source_system',e.source_system,'entity_type',e.entity_type,
      'entity_id',e.entity_id,'entity_version',e.entity_version,
      'correlation_id',e.correlation_id,'causation_id',e.causation_id,
      'authority_basis',e.authority_basis,'approval_id',e.approval_id,
      'visibility_class',e.visibility_class,'payload',e.payload,
      'payload_sha256',e.payload_sha256,'previous_event_hash',e.previous_event_hash,
      'event_hash',e.event_hash,'chain_anchor_state',e.chain_anchor_state,
      'signature_ref',e.signature_ref,'created_at',e.created_at
    ) order by e.sequence_id
  ),'[]'::jsonb),pg_catalog.count(*)::integer,pg_catalog.min(e.sequence_id),pg_catalog.max(e.sequence_id)
  into v_events,v_count,v_first,v_last
  from (
    select * from chlom_runtime.dail_events
    where sequence_id > coalesce(p_after_sequence_id,0)
      and sequence_id <= v_source_max
    order by sequence_id
    limit v_limit
  ) e;

  if v_count > 0 then
    select e.previous_event_hash into v_first_prev
    from chlom_runtime.dail_events e where e.sequence_id=v_first;
    select e.event_hash into v_last_hash
    from chlom_runtime.dail_events e where e.sequence_id=v_last;
    select exists(
      select 1 from chlom_runtime.dail_events e
      where e.sequence_id>v_last and e.sequence_id<=v_source_max
    ) into v_has_more;
  end if;

  v_chunk_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_events::text,'UTF8'),'sha256'),'hex'
  );

  return pg_catalog.jsonb_build_object(
    'contract','ct.backup.dail-cold.chunk.v1',
    'state',case when v_count=0 then 'EOF' else 'PASS_CHUNK' end,
    'job_id',p_job_id,
    'source_event_count',v_source_count,
    'source_min_sequence_id',v_source_min,
    'source_max_sequence_id',v_source_max,
    'source_head_event_hash',v_source_head,
    'requested_after_sequence_id',coalesce(p_after_sequence_id,0),
    'chunk_limit',v_limit,'chunk_event_count',v_count,
    'chunk_first_sequence_id',v_first,'chunk_last_sequence_id',v_last,
    'chunk_first_previous_event_hash',v_first_prev,
    'chunk_last_event_hash',v_last_hash,
    'chunk_sha256',v_chunk_sha,
    'has_more',v_has_more,
    'next_after_sequence_id',case when v_has_more then v_last else null end,
    'events',v_events,
    'provider_write',false,'authority_effect','none'
  );
end
$function$;

create or replace function chlom_runtime.complete_dail_cold_checkpoint_v1(
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
  v_package_hash text := pg_catalog.lower(pg_catalog.btrim(p_package_sha256));
  v_manifest_hash text := pg_catalog.lower(pg_catalog.btrim(p_manifest_sha256));
  v_checkpoint jsonb;
  v_checkpoint_id uuid;
  v_drill jsonb;
  v_drill_start timestamptz;
  v_drill_end timestamptz;
  v_object_ref text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if v_package_hash !~ '^[0-9a-f]{64}$' or v_manifest_hash !~ '^[0-9a-f]{64}$'
     or p_snapshot_bytes is null or p_snapshot_bytes<=0 or p_snapshot_created_at is null then
    raise exception 'valid package/manifest hashes, bytes, and snapshot time required' using errcode='22023';
  end if;
  if coalesce(pg_catalog.btrim(p_drive_target_folder_id),'')=''
     or coalesce(pg_catalog.btrim(p_drive_manifest_file_id),'')=''
     or coalesce(pg_catalog.btrim(p_drive_package_file_id),'')='' then
    raise exception 'exact Drive target, manifest, and package file IDs required' using errcode='22023';
  end if;

  select * into strict v_job
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.job_id=p_job_id and j.schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1'
  for update;
  if v_job.job_state='verified' then
    return pg_catalog.jsonb_build_object('state','DEDUPED_VERIFIED','job_id',p_job_id,'evidence',v_job.evidence);
  end if;
  if v_job.job_state not in ('queued','connector_in_progress','uploaded','hold') then
    raise exception 'DAIL cold checkpoint job is not completable from current state' using errcode='55000';
  end if;

  v_source_count := nullif(v_job.source_snapshot->>'source_event_count','')::bigint;
  v_source_max := nullif(v_job.source_snapshot->>'source_max_sequence_id','')::bigint;
  v_source_head := pg_catalog.lower(coalesce(v_job.source_snapshot->>'source_head_event_hash',''));
  if v_source_count is null or v_source_max is null or v_source_head !~ '^[0-9a-f]{64}$' then
    raise exception 'job source snapshot is invalid' using errcode='55000';
  end if;

  if coalesce((p_export_evidence->>'exported_event_count')::bigint,-1) <> v_source_count
     or coalesce((p_export_evidence->>'exported_max_sequence_id')::bigint,-1) <> v_source_max
     or pg_catalog.lower(coalesce(p_export_evidence->>'exported_head_event_hash','')) <> v_source_head
     or coalesce((p_export_evidence->>'chunk_chain_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'all_chunk_hashes_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'component_hashes_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'structured_data_parse_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'manifest_hash_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'package_hash_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'custody_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'drive_readback_verified')::boolean,false) is distinct from true
     or coalesce((p_export_evidence->>'restore_path_verified')::boolean,false) is distinct from true
     or coalesce(p_export_evidence->>'secret_scan','') <> 'PASS' then
    update chlom_runtime.backup_continuity_jobs_v2
      set job_state='hold',last_error='HOLD_DAIL_COLD_EXPORT_EVIDENCE_INCOMPLETE',
          evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object('export_evidence',coalesce(p_export_evidence,'{}'::jsonb)),
          updated_at=clock_timestamp()
    where job_id=p_job_id;
    return pg_catalog.jsonb_build_object('state','HOLD_DAIL_COLD_EXPORT_EVIDENCE_INCOMPLETE','job_id',p_job_id);
  end if;

  v_drill_start := nullif(p_recovery_evidence->>'drill_started_at','')::timestamptz;
  v_drill_end := nullif(p_recovery_evidence->>'drill_completed_at','')::timestamptz;
  if v_drill_start is null or v_drill_end is null
     or coalesce((p_recovery_evidence->>'restored_event_count')::bigint,-1) <> v_source_count
     or coalesce((p_recovery_evidence->>'restored_max_sequence_id')::bigint,-1) <> v_source_max
     or pg_catalog.lower(coalesce(p_recovery_evidence->>'restored_head_event_hash','')) <> v_source_head
     or coalesce((p_recovery_evidence->>'manifest_hash_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'package_hash_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'component_hashes_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'structured_data_parse_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'restore_path_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'cold_route_exercised')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'hot_route_unchanged')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'fault_injection_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'provider_exit_path_verified')::boolean,false) is distinct from true
     or coalesce((p_recovery_evidence->>'rollback_and_failback_verified')::boolean,false) is distinct from true
     or coalesce(p_recovery_evidence->>'restore_target_class','') <> 'isolated_non_production' then
    update chlom_runtime.backup_continuity_jobs_v2
      set job_state='hold',last_error='HOLD_DAIL_COLD_RECOVERY_DRILL_EVIDENCE_INCOMPLETE',
          evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object('export_evidence',p_export_evidence,'recovery_evidence',coalesce(p_recovery_evidence,'{}'::jsonb)),
          updated_at=clock_timestamp()
    where job_id=p_job_id;
    return pg_catalog.jsonb_build_object('state','HOLD_DAIL_COLD_RECOVERY_DRILL_EVIDENCE_INCOMPLETE','job_id',p_job_id);
  end if;

  v_object_ref := 'gdrive:folder:'||p_drive_target_folder_id||';manifest:'||p_drive_manifest_file_id||';package:'||p_drive_package_file_id||';scope:ledger_lineage';
  v_checkpoint := chlom_runtime.record_dail_cold_checkpoint_v2(
    'ct.dail.cold.'||v_source_max::text||'.'||pg_catalog.substr(v_source_head,1,16),
    v_source_count,v_source_max,v_source_head,p_snapshot_created_at,
    v_manifest_hash,v_package_hash,v_object_ref,p_snapshot_bytes,
    'google_drive','provider_managed_at_rest',true,true,true,
    'ct.chlom.agent.recovery','CHLOM C11 governed cold checkpoint connector completion',null
  );
  v_checkpoint_id := nullif(v_checkpoint->>'checkpoint_id','')::uuid;
  if v_checkpoint_id is null then
    raise exception 'cold checkpoint record did not return checkpoint id' using errcode='55000';
  end if;

  v_drill := chlom_runtime.record_dail_recovery_drill_v1(
    'ct.dail.cold.drill.'||v_checkpoint_id::text,
    v_checkpoint_id,'ledger_lineage','isolated_non_production',
    coalesce(p_recovery_evidence->>'restore_environment_ref','external-relay-isolated-restore'),
    v_drill_start,v_drill_end,v_source_count,v_source_max,v_source_head,
    true,true,true,true,true,true,true,true,true,true,
    'ct.chlom.agent.recovery','CHLOM C11 isolated cold-route recovery verification',null
  );
  if coalesce(v_drill->>'result','FAIL') <> 'PASS' then
    raise exception 'DAIL cold recovery drill did not pass' using errcode='55000';
  end if;

  update chlom_runtime.backup_continuity_jobs_v2
  set job_state='verified',drive_target_folder_id=p_drive_target_folder_id,
      drive_manifest_file_id=p_drive_manifest_file_id,drive_package_file_id=p_drive_package_file_id,
      package_sha256=v_package_hash,manifest_sha256=v_manifest_hash,
      readback_verified=true,restore_path_verified=true,last_error=null,
      evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
        'schema','ct.backup.dail-cold.connector-completion.v1',
        'checkpoint',v_checkpoint,'recovery_drill',v_drill,
        'export_evidence',p_export_evidence,'recovery_evidence',p_recovery_evidence,
        'provider_write_actor','external-evidence-relay','phase4_activation',false
      ),completed_at=clock_timestamp(),updated_at=clock_timestamp()
  where job_id=p_job_id;

  update chlom_runtime.backup_manifests
  set backup_state='verified',destination_ref='drive:folder:'||p_drive_target_folder_id||';manifest:'||p_drive_manifest_file_id||';package:'||p_drive_package_file_id,
      content_sha256=v_package_hash,manifest_sha256=v_manifest_hash,verified_at=clock_timestamp(),
      metadata=coalesce(metadata,'{}'::jsonb)||pg_catalog.jsonb_build_object(
        'drive_readback_verified',true,'restore_path_verified',true,
        'dail_checkpoint_id',v_checkpoint_id,'dail_recovery_drill_id',v_drill->>'drill_id',
        'connector_completion_state','verified'
      )
  where backup_id=v_job.backup_manifest_id;

  perform chlom_runtime.append_dail_event(
    'backup.dail-cold.verified','backup_job',p_job_id::text,
    pg_catalog.jsonb_build_object(
      'backup_manifest_id',v_job.backup_manifest_id,'checkpoint_id',v_checkpoint_id,
      'recovery_drill_id',v_drill->>'drill_id','source_event_count',v_source_count,
      'source_max_sequence_id',v_source_max,'source_head_event_hash',v_source_head,
      'package_sha256',v_package_hash,'manifest_sha256',v_manifest_hash,
      'readback_verified',true,'restore_path_verified',true,
      'phase_transition',false,'provider_write_actor','external-evidence-relay'
    ),
    'external-evidence-relay',null,'ct.system.chlom.dail-cold-checkpoint','v1',
    v_job.occurrence_key,null,
    'CHLOM C11 exact cold checkpoint/provider readback/recovery completion',null,'restricted'
  );

  return pg_catalog.jsonb_build_object(
    'state','VERIFIED','job_id',p_job_id,'checkpoint',v_checkpoint,'recovery_drill',v_drill,
    'readback_verified',true,'restore_path_verified',true,'phase4_activation',false
  );
end
$function$;

revoke all on function chlom_runtime.record_dail_cold_checkpoint_v2(text,bigint,bigint,text,timestamptz,text,text,text,bigint,text,text,boolean,boolean,boolean,text,text,uuid) from public,anon,authenticated;
revoke all on function chlom_runtime.enqueue_dail_cold_checkpoint_v1(boolean) from public,anon,authenticated;
revoke all on function public.dail_cold_checkpoint_export_chunk_v1(uuid,bigint,integer) from public,anon,authenticated;
revoke all on function chlom_runtime.complete_dail_cold_checkpoint_v1(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) from public,anon,authenticated;
grant execute on function chlom_runtime.record_dail_cold_checkpoint_v2(text,bigint,bigint,text,timestamptz,text,text,text,bigint,text,text,boolean,boolean,boolean,text,text,uuid) to service_role;
grant execute on function chlom_runtime.enqueue_dail_cold_checkpoint_v1(boolean) to service_role;
grant execute on function public.dail_cold_checkpoint_export_chunk_v1(uuid,bigint,integer) to service_role;
grant execute on function chlom_runtime.complete_dail_cold_checkpoint_v1(uuid,text,text,text,text,text,bigint,timestamptz,jsonb,jsonb) to service_role;

-- Internal due generation only. The existing canonical External Evidence Relay remains
-- the sole Google Drive connector failure domain; this cron never writes a provider.
do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule(
    'ct-dail-cold-checkpoint-due-v1',
    '17 * * * *',
    'select chlom_runtime.enqueue_dail_cold_checkpoint_v1(false);'
  );
end
$block$;
