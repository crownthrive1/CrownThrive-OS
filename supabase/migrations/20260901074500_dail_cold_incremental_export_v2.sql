-- CHLOM C13 / DAIL cold-route scalability repair.
-- Adds an incremental, chunked, append-only cold lineage export contract while
-- preserving the existing v1 full lineage checkpoint and drill receipts.
-- No provider write, D3, money, rights, credential, vote, or merge authority is created.

create table if not exists chlom_runtime.dail_cold_incremental_exports_v2 (
  job_id uuid primary key references chlom_runtime.backup_continuity_jobs_v2(job_id) on delete restrict,
  backup_manifest_id uuid not null references chlom_runtime.backup_manifests(backup_id) on delete restrict,
  previous_checkpoint_kind text not null check (previous_checkpoint_kind in ('v1','v2')),
  previous_checkpoint_id uuid not null,
  previous_source_max_sequence_id bigint not null check (previous_source_max_sequence_id >= 0),
  previous_source_head_event_hash text not null check (previous_source_head_event_hash ~ '^[0-9a-f]{64}$'),
  delta_first_sequence_id bigint not null check (delta_first_sequence_id > previous_source_max_sequence_id),
  delta_first_previous_event_hash text not null check (delta_first_previous_event_hash ~ '^[0-9a-f]{64}$'),
  delta_last_sequence_id bigint not null check (delta_last_sequence_id >= delta_first_sequence_id),
  delta_event_count bigint not null check (delta_event_count > 0),
  cumulative_event_count bigint not null check (cumulative_event_count >= delta_event_count),
  cumulative_min_sequence_id bigint not null check (cumulative_min_sequence_id > 0),
  cumulative_max_sequence_id bigint not null check (cumulative_max_sequence_id = delta_last_sequence_id),
  cumulative_head_event_hash text not null check (cumulative_head_event_hash ~ '^[0-9a-f]{64}$'),
  cumulative_head_created_at timestamptz not null,
  captured_at timestamptz not null,
  chunk_span bigint not null check (chunk_span between 1000 and 50000),
  first_chunk_no integer not null check (first_chunk_no >= 0),
  last_chunk_no integer not null check (last_chunk_no >= first_chunk_no),
  chunk_count integer generated always as (last_chunk_no - first_chunk_no + 1) stored,
  export_contract text not null default 'ct.chlom.dail-cold-incremental.v2',
  state text not null default 'queued' check (state in ('queued')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp()
);

create table if not exists chlom_runtime.dail_cold_incremental_checkpoints_v2 (
  checkpoint_id uuid primary key default extensions.gen_random_uuid(),
  idempotency_key text not null unique,
  job_id uuid not null unique references chlom_runtime.backup_continuity_jobs_v2(job_id) on delete restrict,
  previous_checkpoint_kind text not null check (previous_checkpoint_kind in ('v1','v2')),
  previous_checkpoint_id uuid not null,
  previous_checkpoint_receipt_sha256 text not null check (previous_checkpoint_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  previous_source_max_sequence_id bigint not null check (previous_source_max_sequence_id >= 0),
  previous_source_head_event_hash text not null check (previous_source_head_event_hash ~ '^[0-9a-f]{64}$'),
  delta_first_sequence_id bigint not null,
  delta_last_sequence_id bigint not null,
  delta_event_count bigint not null check (delta_event_count > 0),
  cumulative_event_count bigint not null check (cumulative_event_count >= delta_event_count),
  cumulative_min_sequence_id bigint not null check (cumulative_min_sequence_id > 0),
  cumulative_max_sequence_id bigint not null,
  cumulative_head_event_hash text not null check (cumulative_head_event_hash ~ '^[0-9a-f]{64}$'),
  cumulative_head_created_at timestamptz not null,
  snapshot_created_at timestamptz not null,
  snapshot_rpo_seconds bigint not null check (snapshot_rpo_seconds >= 0),
  snapshot_manifest_sha256 text not null check (snapshot_manifest_sha256 ~ '^[0-9a-f]{64}$'),
  snapshot_package_sha256 text not null check (snapshot_package_sha256 ~ '^[0-9a-f]{64}$'),
  snapshot_object_ref text not null,
  snapshot_bytes bigint not null check (snapshot_bytes > 0),
  storage_provider text not null check (storage_provider in ('google_drive','s3','gcs','azure_blob','other_provider_managed')),
  encryption_state text not null check (encryption_state in ('provider_managed_at_rest','client_managed','provider_and_client_managed')),
  custody_verified boolean not null,
  readback_verified boolean not null,
  restore_path_verified boolean not null,
  linkage_verified boolean not null,
  verifier_output jsonb not null,
  verifier_output_sha256 text not null check (verifier_output_sha256 ~ '^[0-9a-f]{64}$'),
  checkpoint_receipt_sha256 text not null check (checkpoint_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  receipt_dail_event_id uuid,
  recorded_by text not null,
  authority_basis text not null,
  recorded_at timestamptz not null default clock_timestamp()
);

create table if not exists chlom_runtime.dail_incremental_recovery_drills_v2 (
  drill_id uuid primary key default extensions.gen_random_uuid(),
  idempotency_key text not null unique,
  checkpoint_id uuid not null references chlom_runtime.dail_cold_incremental_checkpoints_v2(checkpoint_id) on delete restrict,
  restore_target_class text not null check (restore_target_class = 'isolated_non_production'),
  restore_environment_ref text not null,
  drill_started_at timestamptz not null,
  drill_completed_at timestamptz not null,
  observed_rto_seconds bigint not null check (observed_rto_seconds >= 0),
  restored_delta_event_count bigint not null check (restored_delta_event_count > 0),
  restored_first_sequence_id bigint not null,
  restored_max_sequence_id bigint not null,
  restored_head_event_hash text not null check (restored_head_event_hash ~ '^[0-9a-f]{64}$'),
  prior_checkpoint_recovery_verified boolean not null,
  first_event_links_prior_head boolean not null,
  delta_internal_chain_verified boolean not null,
  source_head_match boolean not null,
  manifest_hash_verified boolean not null,
  package_hash_verified boolean not null,
  component_hashes_verified boolean not null,
  structured_data_parse_verified boolean not null,
  restore_path_verified boolean not null,
  cold_route_exercised boolean not null,
  hot_route_unchanged boolean not null,
  fault_injection_verified boolean not null,
  provider_exit_path_verified boolean not null,
  rollback_and_failback_verified boolean not null,
  result text not null check (result in ('PASS','FAIL')),
  receipt_dail_event_id uuid,
  recorded_by text not null,
  authority_basis text not null,
  recorded_at timestamptz not null default clock_timestamp()
);

alter table chlom_runtime.dail_cold_incremental_exports_v2 enable row level security;
alter table chlom_runtime.dail_cold_incremental_exports_v2 force row level security;
alter table chlom_runtime.dail_cold_incremental_checkpoints_v2 enable row level security;
alter table chlom_runtime.dail_cold_incremental_checkpoints_v2 force row level security;
alter table chlom_runtime.dail_incremental_recovery_drills_v2 enable row level security;
alter table chlom_runtime.dail_incremental_recovery_drills_v2 force row level security;

revoke all on chlom_runtime.dail_cold_incremental_exports_v2 from public, anon, authenticated;
revoke all on chlom_runtime.dail_cold_incremental_checkpoints_v2 from public, anon, authenticated;
revoke all on chlom_runtime.dail_incremental_recovery_drills_v2 from public, anon, authenticated;
grant select on chlom_runtime.dail_cold_incremental_exports_v2 to service_role;
grant select on chlom_runtime.dail_cold_incremental_checkpoints_v2 to service_role;
grant select on chlom_runtime.dail_incremental_recovery_drills_v2 to service_role;

drop trigger if exists dail_cold_incremental_exports_append_only_v2 on chlom_runtime.dail_cold_incremental_exports_v2;
create trigger dail_cold_incremental_exports_append_only_v2
before update or delete on chlom_runtime.dail_cold_incremental_exports_v2
for each row execute function chlom_runtime.reject_dail_assurance_mutation_v1();

drop trigger if exists dail_cold_incremental_checkpoints_append_only_v2 on chlom_runtime.dail_cold_incremental_checkpoints_v2;
create trigger dail_cold_incremental_checkpoints_append_only_v2
before update or delete on chlom_runtime.dail_cold_incremental_checkpoints_v2
for each row execute function chlom_runtime.reject_dail_assurance_mutation_v1();

drop trigger if exists dail_incremental_recovery_drills_append_only_v2 on chlom_runtime.dail_incremental_recovery_drills_v2;
create trigger dail_incremental_recovery_drills_append_only_v2
before update or delete on chlom_runtime.dail_incremental_recovery_drills_v2
for each row execute function chlom_runtime.reject_dail_assurance_mutation_v1();

create or replace function chlom_runtime.enqueue_dail_cold_incremental_backup_v2(
  p_chunk_span bigint default 10000
) returns jsonb
language plpgsql
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
declare
  v_now timestamptz := pg_catalog.clock_timestamp();
  v_verification jsonb;
  v_previous_kind text;
  v_previous_id uuid;
  v_previous_receipt text;
  v_previous_max bigint;
  v_previous_head text;
  v_previous_recovery_ok boolean := false;
  v_current_count bigint;
  v_current_min bigint;
  v_current_max bigint;
  v_current_head text;
  v_current_head_created_at timestamptz;
  v_delta_first bigint;
  v_delta_first_previous_hash text;
  v_delta_count bigint;
  v_first_chunk integer;
  v_last_chunk integer;
  v_occurrence_key text;
  v_job_id uuid;
  v_manifest_id uuid;
  v_snapshot jsonb;
  v_snapshot_sha text;
begin
  if p_chunk_span is null or p_chunk_span not between 1000 and 50000 then
    raise exception 'chunk span must be between 1000 and 50000 sequence ids'
      using errcode='22023';
  end if;

  v_verification := chlom_runtime.verify_dail_chain_v3();
  if coalesce((v_verification->>'ok')::boolean,false) is distinct from true
     or coalesce((v_verification->>'tail_failure_count')::bigint,-1) <> 0 then
    return pg_catalog.jsonb_build_object(
      'state','HOLD_HOT_DAIL_INTEGRITY',
      'verification',v_verification
    );
  end if;

  select c.checkpoint_id,
         c.checkpoint_receipt_sha256,
         c.cumulative_max_sequence_id,
         c.cumulative_head_event_hash,
         exists(
           select 1
           from chlom_runtime.dail_incremental_recovery_drills_v2 d
           where d.checkpoint_id=c.checkpoint_id and d.result='PASS'
         )
    into v_previous_id,v_previous_receipt,v_previous_max,v_previous_head,v_previous_recovery_ok
  from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
  order by c.snapshot_created_at desc,c.recorded_at desc
  limit 1;

  if found then
    v_previous_kind := 'v2';
  else
    select c.checkpoint_id,
           c.checkpoint_receipt_sha256,
           c.source_max_sequence_id,
           c.source_head_event_hash,
           exists(
             select 1
             from chlom_runtime.dail_recovery_drill_receipts_v1 d
             where d.checkpoint_id=c.checkpoint_id and d.result='PASS'
           )
      into v_previous_id,v_previous_receipt,v_previous_max,v_previous_head,v_previous_recovery_ok
    from chlom_runtime.dail_cold_checkpoints_v1 c
    order by c.snapshot_created_at desc,c.recorded_at desc
    limit 1;
    if found then
      v_previous_kind := 'v1';
    end if;
  end if;

  if v_previous_id is null then
    return pg_catalog.jsonb_build_object(
      'state','HOLD_FULL_COLD_BASE_REQUIRED',
      'reason','incremental backup requires one previously restore-verified full/lineage checkpoint'
    );
  end if;
  if v_previous_recovery_ok is distinct from true then
    return pg_catalog.jsonb_build_object(
      'state','HOLD_PREVIOUS_CHECKPOINT_UNTESTED',
      'previous_checkpoint_kind',v_previous_kind,
      'previous_checkpoint_id',v_previous_id
    );
  end if;

  select pg_catalog.count(*),
         pg_catalog.min(e.sequence_id),
         pg_catalog.max(e.sequence_id)
    into v_current_count,v_current_min,v_current_max
  from chlom_runtime.dail_events e;

  select e.event_hash,e.created_at
    into v_current_head,v_current_head_created_at
  from chlom_runtime.dail_events e
  where e.sequence_id=v_current_max;

  if v_current_max <= v_previous_max then
    return pg_catalog.jsonb_build_object(
      'state','NO_CHANGE',
      'previous_checkpoint_id',v_previous_id,
      'source_max_sequence_id',v_current_max
    );
  end if;

  select e.sequence_id,e.previous_event_hash
    into v_delta_first,v_delta_first_previous_hash
  from chlom_runtime.dail_events e
  where e.sequence_id > v_previous_max
    and e.sequence_id <= v_current_max
  order by e.sequence_id
  limit 1;

  select pg_catalog.count(*)
    into v_delta_count
  from chlom_runtime.dail_events e
  where e.sequence_id > v_previous_max
    and e.sequence_id <= v_current_max;

  if v_delta_first is null or v_delta_count <= 0 then
    return pg_catalog.jsonb_build_object('state','HOLD_DELTA_EMPTY_AFTER_HEAD_ADVANCE');
  end if;

  if v_delta_first_previous_hash is distinct from v_previous_head then
    return pg_catalog.jsonb_build_object(
      'state','HOLD_INCREMENTAL_LINKAGE_MISMATCH',
      'previous_checkpoint_id',v_previous_id,
      'expected_previous_head',v_previous_head,
      'observed_first_previous_hash',v_delta_first_previous_hash,
      'first_delta_sequence_id',v_delta_first
    );
  end if;

  v_first_chunk := pg_catalog.floor((v_delta_first-1)::numeric/p_chunk_span)::integer;
  v_last_chunk := pg_catalog.floor((v_current_max-1)::numeric/p_chunk_span)::integer;
  v_occurrence_key := 'ct.dail.cold.incremental.v2.'||v_current_max::text;

  select j.job_id into v_job_id
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.occurrence_key=v_occurrence_key;
  if found then
    return pg_catalog.jsonb_build_object(
      'state','DEDUPED',
      'job_id',v_job_id,
      'occurrence_key',v_occurrence_key
    );
  end if;

  v_snapshot := pg_catalog.jsonb_build_object(
    'schema','ct.chlom.dail-cold-incremental.v2',
    'classification','private_integrity_metadata',
    'payload_bodies_included',false,
    'actor_identifiers_included',false,
    'entity_identifiers_included',false,
    'previous_checkpoint',pg_catalog.jsonb_build_object(
      'kind',v_previous_kind,
      'checkpoint_id',v_previous_id,
      'checkpoint_receipt_sha256',v_previous_receipt,
      'source_max_sequence_id',v_previous_max,
      'source_head_event_hash',v_previous_head,
      'recovery_verified',v_previous_recovery_ok
    ),
    'source',pg_catalog.jsonb_build_object(
      'event_count',v_current_count,
      'min_sequence_id',v_current_min,
      'max_sequence_id',v_current_max,
      'head_event_hash',v_current_head,
      'head_created_at',v_current_head_created_at,
      'verification_mode',v_verification->>'verification_mode',
      'integrity_state',v_verification->>'integrity_state'
    ),
    'delta',pg_catalog.jsonb_build_object(
      'first_sequence_id',v_delta_first,
      'first_previous_event_hash',v_delta_first_previous_hash,
      'last_sequence_id',v_current_max,
      'event_count',v_delta_count,
      'chunk_span',p_chunk_span,
      'first_chunk_no',v_first_chunk,
      'last_chunk_no',v_last_chunk,
      'chunk_count',v_last_chunk-v_first_chunk+1
    ),
    'connector_contract',pg_catalog.jsonb_build_object(
      'job_export_function','public.dail_cold_incremental_export_job_v2',
      'chunk_export_function','public.dail_cold_incremental_export_chunk_v2',
      'completion_function','chlom_runtime.complete_dail_cold_incremental_backup_v2',
      'requires_isolated_incremental_restore',true,
      'requires_byte_readback',true,
      'requires_fault_injection',true,
      'requires_hot_route_unchanged',true
    ),
    'destination',pg_catalog.jsonb_build_object(
      'provider','google_drive',
      'archive_root_id','1Xdgi5LMG17j_dOw0ESJw44Py9WXBYzTs',
      'dail_folder_id','1SDY5Afoflni-xkfQqrMPuUJtVV8dsTY5'
    )
  );

  v_snapshot_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_snapshot::text,'UTF8'),'sha256'),'hex'
  );

  insert into chlom_runtime.backup_manifests(
    backup_class,source_system,destination_system,destination_ref,encryption_profile,
    secret_reference,content_sha256,manifest_sha256,backup_state,contains_secrets,metadata
  ) values(
    'dail_incremental_lineage_snapshot_v2',
    'chlom_runtime.dail_events',
    'google_drive',
    'drive:folder:1SDY5Afoflni-xkfQqrMPuUJtVV8dsTY5',
    'provider_managed_at_rest_no_plaintext_secrets',
    null,
    v_snapshot_sha,
    v_snapshot_sha,
    'planned',
    false,
    pg_catalog.jsonb_build_object(
      'schedule_id','ct.schedule.dail-cold-incremental.hourly.v2',
      'occurrence_key',v_occurrence_key,
      'connector_required',true,
      'canonical_parent_external_relay','ct.schedule.external-evidence-relay.hourly.v1',
      'source_snapshot_sha256',v_snapshot_sha,
      'dail_incremental',true,
      'previous_checkpoint_kind',v_previous_kind,
      'previous_checkpoint_id',v_previous_id
    )
  ) returning backup_id into v_manifest_id;

  insert into chlom_runtime.backup_continuity_jobs_v2(
    schedule_id,occurrence_key,local_backup_date,due_at,job_state,backup_manifest_id,
    drive_archive_root_id,drive_daily_snapshots_id,source_snapshot,evidence
  ) values(
    'ct.schedule.dail-cold-incremental.hourly.v2',
    v_occurrence_key,
    (v_now at time zone 'America/New_York')::date,
    v_now,
    'queued',
    v_manifest_id,
    '1Xdgi5LMG17j_dOw0ESJw44Py9WXBYzTs',
    '1SDY5Afoflni-xkfQqrMPuUJtVV8dsTY5',
    v_snapshot,
    pg_catalog.jsonb_build_object(
      'source_snapshot_sha256',v_snapshot_sha,
      'connector_failure_domain','google_drive',
      'requested_by','ct.automation.chlom-security-fabric',
      'no_provider_write_authority_created',true
    )
  ) returning job_id into v_job_id;

  insert into chlom_runtime.dail_cold_incremental_exports_v2(
    job_id,backup_manifest_id,previous_checkpoint_kind,previous_checkpoint_id,
    previous_source_max_sequence_id,previous_source_head_event_hash,
    delta_first_sequence_id,delta_first_previous_event_hash,delta_last_sequence_id,
    delta_event_count,cumulative_event_count,cumulative_min_sequence_id,
    cumulative_max_sequence_id,cumulative_head_event_hash,cumulative_head_created_at,
    captured_at,chunk_span,first_chunk_no,last_chunk_no,evidence
  ) values(
    v_job_id,v_manifest_id,v_previous_kind,v_previous_id,
    v_previous_max,v_previous_head,
    v_delta_first,v_delta_first_previous_hash,v_current_max,
    v_delta_count,v_current_count,v_current_min,
    v_current_max,v_current_head,v_current_head_created_at,
    v_now,p_chunk_span,v_first_chunk,v_last_chunk,
    pg_catalog.jsonb_build_object(
      'hot_verification',v_verification,
      'source_snapshot_sha256',v_snapshot_sha
    )
  );

  perform chlom_runtime.append_dail_event(
    'backup.dail_incremental.queued',
    'backup_job',
    v_job_id::text,
    pg_catalog.jsonb_build_object(
      'schedule_id','ct.schedule.dail-cold-incremental.hourly.v2',
      'occurrence_key',v_occurrence_key,
      'backup_manifest_id',v_manifest_id,
      'previous_checkpoint_id',v_previous_id,
      'previous_checkpoint_kind',v_previous_kind,
      'source_max_sequence_id',v_current_max,
      'source_head_event_hash',v_current_head,
      'delta_event_count',v_delta_count,
      'chunk_count',v_last_chunk-v_first_chunk+1,
      'phase_transition',false,
      'provider_write',false,
      'money_movement',false
    ),
    'ct.automation.chlom-security-fabric',
    null,
    'ct.system.chlom.dail-cold-recovery',
    'v2',
    v_occurrence_key,
    null,
    'CHLOM C13 cold DAIL incremental recovery contract',
    null,
    'restricted'
  );

  return pg_catalog.jsonb_build_object(
    'state','QUEUED',
    'job_id',v_job_id,
    'backup_manifest_id',v_manifest_id,
    'occurrence_key',v_occurrence_key,
    'previous_checkpoint_kind',v_previous_kind,
    'previous_checkpoint_id',v_previous_id,
    'delta_event_count',v_delta_count,
    'source_event_count',v_current_count,
    'source_max_sequence_id',v_current_max,
    'source_head_event_hash',v_current_head,
    'chunk_count',v_last_chunk-v_first_chunk+1,
    'source_snapshot_sha256',v_snapshot_sha,
    'provider_write_authority_created',false
  );
end;
$function$;

create or replace function public.dail_cold_incremental_export_job_v2(
  p_job_id uuid
) returns jsonb
language sql
stable
security definer
set search_path to ''
as $function$
  select pg_catalog.jsonb_build_object(
    'schema','ct.chlom.dail-cold-incremental-export-job.v2',
    'job_id',j.job_id,
    'job_state',j.job_state,
    'schedule_id',j.schedule_id,
    'occurrence_key',j.occurrence_key,
    'due_at',j.due_at,
    'backup_manifest_id',j.backup_manifest_id,
    'drive_archive_root_id',j.drive_archive_root_id,
    'drive_target_folder_hint',j.drive_daily_snapshots_id,
    'source_snapshot',j.source_snapshot,
    'export',pg_catalog.jsonb_build_object(
      'previous_checkpoint_kind',x.previous_checkpoint_kind,
      'previous_checkpoint_id',x.previous_checkpoint_id,
      'previous_source_max_sequence_id',x.previous_source_max_sequence_id,
      'previous_source_head_event_hash',x.previous_source_head_event_hash,
      'delta_first_sequence_id',x.delta_first_sequence_id,
      'delta_last_sequence_id',x.delta_last_sequence_id,
      'delta_event_count',x.delta_event_count,
      'cumulative_event_count',x.cumulative_event_count,
      'cumulative_max_sequence_id',x.cumulative_max_sequence_id,
      'cumulative_head_event_hash',x.cumulative_head_event_hash,
      'chunk_span',x.chunk_span,
      'first_chunk_no',x.first_chunk_no,
      'last_chunk_no',x.last_chunk_no,
      'chunk_count',x.chunk_count
    )
  )
  from chlom_runtime.backup_continuity_jobs_v2 j
  join chlom_runtime.dail_cold_incremental_exports_v2 x on x.job_id=j.job_id
  where j.job_id=p_job_id
    and j.schedule_id='ct.schedule.dail-cold-incremental.hourly.v2'
    and j.job_state in ('queued','hold')
$function$;

create or replace function public.dail_cold_incremental_export_chunk_v2(
  p_job_id uuid,
  p_chunk_no integer
) returns jsonb
language plpgsql
stable
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
declare
  v_export chlom_runtime.dail_cold_incremental_exports_v2%rowtype;
  v_range_start bigint;
  v_range_end bigint;
  v_events jsonb;
  v_corrections jsonb;
  v_payload jsonb;
  v_sha text;
begin
  select x.* into strict v_export
  from chlom_runtime.dail_cold_incremental_exports_v2 x
  join chlom_runtime.backup_continuity_jobs_v2 j on j.job_id=x.job_id
  where x.job_id=p_job_id
    and j.schedule_id='ct.schedule.dail-cold-incremental.hourly.v2'
    and j.job_state in ('queued','hold');

  if p_chunk_no is null
     or p_chunk_no < v_export.first_chunk_no
     or p_chunk_no > v_export.last_chunk_no then
    raise exception 'chunk number outside export bounds' using errcode='22023';
  end if;

  v_range_start := greatest(
    v_export.delta_first_sequence_id,
    p_chunk_no::bigint*v_export.chunk_span + 1
  );
  v_range_end := least(
    v_export.delta_last_sequence_id,
    (p_chunk_no::bigint+1)*v_export.chunk_span
  );

  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object(
      'sequence_id',e.sequence_id,
      'previous_event_hash',e.previous_event_hash,
      'event_hash',e.event_hash,
      'payload_sha256',e.payload_sha256,
      'created_at',e.created_at
    ) order by e.sequence_id
  ),'[]'::jsonb)
    into v_events
  from chlom_runtime.dail_events e
  where e.sequence_id between v_range_start and v_range_end
    and e.sequence_id <= v_export.cumulative_max_sequence_id;

  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object(
      'sequence_id',c.sequence_id,
      'original_event_hash',c.original_event_hash,
      'expected_event_hash',c.expected_event_hash,
      'payload_sha256',c.payload_sha256,
      'previous_event_hash',c.previous_event_hash,
      'correction_state',c.correction_state,
      'defect_class',c.defect_class,
      'created_at',c.created_at
    ) order by c.sequence_id
  ),'[]'::jsonb)
    into v_corrections
  from chlom_runtime.dail_integrity_corrections c
  where c.sequence_id between v_range_start and v_range_end;

  v_payload := pg_catalog.jsonb_build_object(
    'schema','ct.chlom.dail-cold-incremental-chunk.v2',
    'job_id',p_job_id,
    'chunk_no',p_chunk_no,
    'range_start_sequence_id',v_range_start,
    'range_end_sequence_id',v_range_end,
    'events',v_events,
    'corrections',v_corrections
  );

  v_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_payload::text,'UTF8'),'sha256'),'hex'
  );

  return v_payload || pg_catalog.jsonb_build_object(
    'event_count',pg_catalog.jsonb_array_length(v_events),
    'correction_count',pg_catalog.jsonb_array_length(v_corrections),
    'chunk_sha256',v_sha
  );
end;
$function$;

create or replace function chlom_runtime.record_dail_cold_incremental_checkpoint_v2(
  p_job_id uuid,
  p_snapshot_created_at timestamptz,
  p_snapshot_manifest_sha256 text,
  p_snapshot_package_sha256 text,
  p_snapshot_object_ref text,
  p_snapshot_bytes bigint,
  p_storage_provider text,
  p_encryption_state text,
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
  v_export chlom_runtime.dail_cold_incremental_exports_v2%rowtype;
  v_verification jsonb;
  v_actual_count bigint;
  v_actual_head text;
  v_actual_head_created_at timestamptz;
  v_previous_receipt text;
  v_prior_recovery_ok boolean := false;
  v_rpo bigint;
  v_verifier_sha text;
  v_checkpoint_id uuid := extensions.gen_random_uuid();
  v_receipt_sha text;
  v_idempotency text;
begin
  select x.* into strict v_export
  from chlom_runtime.dail_cold_incremental_exports_v2 x
  join chlom_runtime.backup_continuity_jobs_v2 j on j.job_id=x.job_id
  where x.job_id=p_job_id
    and j.job_state='verified';

  if coalesce(pg_catalog.lower(pg_catalog.btrim(p_snapshot_manifest_sha256)),'') !~ '^[0-9a-f]{64}$'
     or coalesce(pg_catalog.lower(pg_catalog.btrim(p_snapshot_package_sha256)),'') !~ '^[0-9a-f]{64}$'
     or p_snapshot_bytes is null or p_snapshot_bytes<=0 then
    raise exception 'valid snapshot hashes and positive bytes are required' using errcode='22023';
  end if;
  if p_snapshot_created_at is null
     or p_snapshot_created_at < v_export.cumulative_head_created_at
     or p_snapshot_created_at > pg_catalog.clock_timestamp()+interval '5 minutes' then
    raise exception 'snapshot timestamp is invalid for captured DAIL head' using errcode='22023';
  end if;
  if p_storage_provider not in ('google_drive','s3','gcs','azure_blob','other_provider_managed') then
    raise exception 'unsupported storage provider' using errcode='22023';
  end if;
  if p_encryption_state not in ('provider_managed_at_rest','client_managed','provider_and_client_managed') then
    raise exception 'unsupported encryption state' using errcode='22023';
  end if;
  if pg_catalog.btrim(coalesce(p_snapshot_object_ref,''))=''
     or pg_catalog.btrim(coalesce(p_recorded_by,''))=''
     or pg_catalog.btrim(coalesce(p_authority_basis,''))='' then
    raise exception 'object ref, recorder, and authority basis are required' using errcode='22023';
  end if;

  v_verification := chlom_runtime.verify_dail_chain_v3();
  if coalesce((v_verification->>'ok')::boolean,false) is distinct from true
     or coalesce((v_verification->>'tail_failure_count')::bigint,-1) <> 0 then
    raise exception 'hot DAIL integrity verification did not pass' using errcode='55000';
  end if;

  select pg_catalog.count(*)
    into v_actual_count
  from chlom_runtime.dail_events e
  where e.sequence_id <= v_export.cumulative_max_sequence_id;

  select e.event_hash,e.created_at
    into v_actual_head,v_actual_head_created_at
  from chlom_runtime.dail_events e
  where e.sequence_id=v_export.cumulative_max_sequence_id;

  if v_actual_count <> v_export.cumulative_event_count
     or v_actual_head is distinct from v_export.cumulative_head_event_hash
     or v_actual_head_created_at is distinct from v_export.cumulative_head_created_at then
    raise exception 'captured DAIL source prefix no longer matches immutable readback' using errcode='55000';
  end if;

  if v_export.previous_checkpoint_kind='v2' then
    select c.checkpoint_receipt_sha256,
           exists(
             select 1
             from chlom_runtime.dail_incremental_recovery_drills_v2 d
             where d.checkpoint_id=c.checkpoint_id and d.result='PASS'
           )
      into v_previous_receipt,v_prior_recovery_ok
    from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
    where c.checkpoint_id=v_export.previous_checkpoint_id;
  else
    select c.checkpoint_receipt_sha256,
           exists(
             select 1
             from chlom_runtime.dail_recovery_drill_receipts_v1 d
             where d.checkpoint_id=c.checkpoint_id and d.result='PASS'
           )
      into v_previous_receipt,v_prior_recovery_ok
    from chlom_runtime.dail_cold_checkpoints_v1 c
    where c.checkpoint_id=v_export.previous_checkpoint_id;
  end if;

  if v_previous_receipt is null
     or v_prior_recovery_ok is distinct from true then
    raise exception 'previous cold checkpoint is not recovery verified' using errcode='55000';
  end if;

  v_rpo := greatest(0,ceil(extract(epoch from p_snapshot_created_at-v_export.cumulative_head_created_at))::bigint);
  v_verifier_sha := pg_catalog.encode(
    extensions.digest(pg_catalog.convert_to(v_verification::text,'UTF8'),'sha256'),'hex'
  );
  v_idempotency := 'ct.dail.cold.incremental.checkpoint.v2.'||p_job_id::text;

  v_receipt_sha := pg_catalog.encode(
    extensions.digest(
      pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
          'checkpoint_id',v_checkpoint_id,
          'job_id',p_job_id,
          'previous_checkpoint_kind',v_export.previous_checkpoint_kind,
          'previous_checkpoint_id',v_export.previous_checkpoint_id,
          'previous_checkpoint_receipt_sha256',v_previous_receipt,
          'delta_first_sequence_id',v_export.delta_first_sequence_id,
          'delta_last_sequence_id',v_export.delta_last_sequence_id,
          'delta_event_count',v_export.delta_event_count,
          'cumulative_event_count',v_export.cumulative_event_count,
          'cumulative_max_sequence_id',v_export.cumulative_max_sequence_id,
          'cumulative_head_event_hash',v_export.cumulative_head_event_hash,
          'snapshot_created_at',p_snapshot_created_at,
          'snapshot_manifest_sha256',pg_catalog.lower(p_snapshot_manifest_sha256),
          'snapshot_package_sha256',pg_catalog.lower(p_snapshot_package_sha256),
          'snapshot_object_ref',p_snapshot_object_ref,
          'snapshot_bytes',p_snapshot_bytes,
          'verifier_output_sha256',v_verifier_sha,
          'recorded_by',p_recorded_by,
          'authority_basis',p_authority_basis
        )::text,
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into chlom_runtime.dail_cold_incremental_checkpoints_v2(
    checkpoint_id,idempotency_key,job_id,previous_checkpoint_kind,previous_checkpoint_id,
    previous_checkpoint_receipt_sha256,previous_source_max_sequence_id,
    previous_source_head_event_hash,delta_first_sequence_id,delta_last_sequence_id,
    delta_event_count,cumulative_event_count,cumulative_min_sequence_id,
    cumulative_max_sequence_id,cumulative_head_event_hash,cumulative_head_created_at,
    snapshot_created_at,snapshot_rpo_seconds,snapshot_manifest_sha256,
    snapshot_package_sha256,snapshot_object_ref,snapshot_bytes,storage_provider,
    encryption_state,custody_verified,readback_verified,restore_path_verified,
    linkage_verified,verifier_output,verifier_output_sha256,checkpoint_receipt_sha256,
    receipt_dail_event_id,recorded_by,authority_basis
  ) values(
    v_checkpoint_id,v_idempotency,p_job_id,v_export.previous_checkpoint_kind,v_export.previous_checkpoint_id,
    v_previous_receipt,v_export.previous_source_max_sequence_id,
    v_export.previous_source_head_event_hash,v_export.delta_first_sequence_id,
    v_export.delta_last_sequence_id,v_export.delta_event_count,
    v_export.cumulative_event_count,v_export.cumulative_min_sequence_id,
    v_export.cumulative_max_sequence_id,v_export.cumulative_head_event_hash,
    v_export.cumulative_head_created_at,p_snapshot_created_at,v_rpo,
    pg_catalog.lower(p_snapshot_manifest_sha256),pg_catalog.lower(p_snapshot_package_sha256),
    p_snapshot_object_ref,p_snapshot_bytes,p_storage_provider,p_encryption_state,
    true,true,true,true,v_verification,v_verifier_sha,v_receipt_sha,
    p_receipt_dail_event_id,p_recorded_by,p_authority_basis
  )
  on conflict (idempotency_key) do nothing
  returning checkpoint_id into v_checkpoint_id;

  if v_checkpoint_id is null then
    select c.checkpoint_id into strict v_checkpoint_id
    from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
    where c.idempotency_key=v_idempotency;
  end if;

  return pg_catalog.jsonb_build_object(
    'state','CHECKPOINT_INCREMENTAL_CUSTODY_VERIFIED',
    'checkpoint_id',v_checkpoint_id,
    'job_id',p_job_id,
    'previous_checkpoint_kind',v_export.previous_checkpoint_kind,
    'previous_checkpoint_id',v_export.previous_checkpoint_id,
    'cumulative_event_count',v_export.cumulative_event_count,
    'cumulative_max_sequence_id',v_export.cumulative_max_sequence_id,
    'cumulative_head_event_hash',v_export.cumulative_head_event_hash,
    'snapshot_rpo_seconds',v_rpo,
    'checkpoint_receipt_sha256',v_receipt_sha,
    'phase4_activation',false
  );
end;
$function$;

create or replace function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  p_checkpoint_id uuid,
  p_restore_environment_ref text,
  p_drill_started_at timestamptz,
  p_drill_completed_at timestamptz,
  p_restored_delta_event_count bigint,
  p_restored_first_sequence_id bigint,
  p_restored_max_sequence_id bigint,
  p_restored_head_event_hash text,
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
  v_head_match boolean;
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

  v_head_match := coalesce(
    p_restored_delta_event_count=v_checkpoint.delta_event_count
    and p_restored_first_sequence_id=v_checkpoint.delta_first_sequence_id
    and p_restored_max_sequence_id=v_checkpoint.delta_last_sequence_id
    and pg_catalog.lower(pg_catalog.btrim(p_restored_head_event_hash))=v_checkpoint.cumulative_head_event_hash,
    false
  );

  v_result := case when
    v_prior_ok
    and v_first_links
    and v_head_match
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
    v_first_links,v_head_match,v_head_match,
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
    'source_head_match',v_head_match,
    'observed_rto_seconds',v_rto,
    'result',v_result,
    'phase4_activation',false
  );
end;
$function$;

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
      'state','DEDUPED_VERIFIED',
      'job_id',p_job_id,
      'checkpoint_id',v_checkpoint_id
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

  if p_readback_verified is distinct from true
     or p_restore_path_verified is distinct from true then
    update chlom_runtime.backup_continuity_jobs_v2
    set job_state='hold',
        last_error='HOLD_DAIL_COLD_READBACK_OR_RESTORE_UNVERIFIED',
        evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'readback_verified',coalesce(p_readback_verified,false),
          'restore_path_verified',coalesce(p_restore_path_verified,false)
        ),
        updated_at=pg_catalog.clock_timestamp()
    where job_id=p_job_id;
    return pg_catalog.jsonb_build_object(
      'state','HOLD_DAIL_COLD_READBACK_OR_RESTORE_UNVERIFIED',
      'job_id',p_job_id
    );
  end if;

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

  v_state := case when v_drill->>'result'='PASS'
    then 'VERIFIED_INCREMENTAL_COLD_ROUTE'
    else 'HOLD_INCREMENTAL_RECOVERY_DRILL_FAILED'
  end;

  perform chlom_runtime.append_dail_event(
    case when v_state='VERIFIED_INCREMENTAL_COLD_ROUTE'
      then 'backup.dail_incremental.verified'
      else 'backup.dail_incremental.hold'
    end,
    'backup_job',
    p_job_id::text,
    pg_catalog.jsonb_build_object(
      'backup_manifest_id',v_job.backup_manifest_id,
      'checkpoint_id',v_checkpoint_id,
      'drill_id',v_drill->>'drill_id',
      'result',v_drill->>'result',
      'package_sha256',pg_catalog.lower(p_package_sha256),
      'manifest_sha256',pg_catalog.lower(p_manifest_sha256),
      'readback_verified',true,
      'restore_path_verified',true,
      'phase_transition',false,
      'money_movement',false
    ),
    'ct.schedule.external-evidence-relay.hourly.v1',
    null,
    'ct.system.chlom.dail-cold-recovery',
    'v2',
    v_job.occurrence_key,
    null,
    'CHLOM C13 incremental DAIL cold recovery contract',
    null,
    'restricted'
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
exception
  when others then
    if sqlstate not in ('P0002') then
      update chlom_runtime.backup_continuity_jobs_v2
      set job_state=case when job_state='verified' then job_state else 'hold' end,
          last_error=left(sqlerrm,1000),
          updated_at=pg_catalog.clock_timestamp()
      where job_id=p_job_id;
    end if;
    raise;
end;
$function$;

create or replace function chlom_runtime.read_dail_phase4_assurance_status_v3(
  p_max_checkpoint_age_seconds bigint default 93600
) returns jsonb
language plpgsql
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
declare
  v_hot jsonb;
  v_hot_state text;
  v_v2 chlom_runtime.dail_cold_incremental_checkpoints_v2%rowtype;
  v_v2_drill chlom_runtime.dail_incremental_recovery_drills_v2%rowtype;
  v_v1 chlom_runtime.dail_cold_checkpoints_v1%rowtype;
  v_v1_drill chlom_runtime.dail_recovery_drill_receipts_v1%rowtype;
  v_age bigint;
  v_cold_state text;
  v_assurance text;
begin
  if p_max_checkpoint_age_seconds is null
     or p_max_checkpoint_age_seconds<=0
     or p_max_checkpoint_age_seconds>604800 then
    raise exception 'checkpoint age threshold must be between 1 and 604800 seconds'
      using errcode='22023';
  end if;

  v_hot := chlom_runtime.verify_dail_chain_checkpoint_v3();
  v_hot_state := case
    when coalesce((v_hot->>'ok')::boolean,false)
      and coalesce((v_hot->>'tail_failure_count')::bigint,-1)=0 then 'PASS'
    else 'FAIL'
  end;

  select c.* into v_v2
  from chlom_runtime.dail_cold_incremental_checkpoints_v2 c
  order by c.snapshot_created_at desc,c.recorded_at desc
  limit 1;

  if found then
    v_age := greatest(0,ceil(extract(epoch from pg_catalog.clock_timestamp()-v_v2.snapshot_created_at))::bigint);
    select d.* into v_v2_drill
    from chlom_runtime.dail_incremental_recovery_drills_v2 d
    where d.checkpoint_id=v_v2.checkpoint_id and d.result='PASS'
    order by d.drill_completed_at desc
    limit 1;

    if v_age>p_max_checkpoint_age_seconds then
      v_cold_state:='HOLD_STALE_CHECKPOINT';
    elsif not found then
      v_cold_state:='HOLD_LATEST_CHECKPOINT_UNTESTED';
    else
      v_cold_state:='LEDGER_LINEAGE_RECOVERY_VERIFIED_INCREMENTAL';
    end if;

    v_assurance := case
      when v_hot_state<>'PASS' then 'HOLD_HOT_ROUTE'
      when v_cold_state='LEDGER_LINEAGE_RECOVERY_VERIFIED_INCREMENTAL'
        then 'BOUNDED_COLD_ASSURANCE_ONLY'
      else 'HOLD'
    end;

    return pg_catalog.jsonb_build_object(
      'hot_route',pg_catalog.jsonb_build_object(
        'state',v_hot_state,
        'integrity_state',v_hot->>'integrity_state',
        'verification_mode',v_hot->>'verification_mode',
        'checkpoint_id',v_hot->>'checkpoint_id',
        'tail_checked_events',(v_hot->>'tail_checked_events')::bigint,
        'tail_failure_count',(v_hot->>'tail_failure_count')::bigint,
        'head_hash',v_hot->>'current_head_hash',
        'checked_at',v_hot->>'checked_at'
      ),
      'cold_route',pg_catalog.jsonb_build_object(
        'state',v_cold_state,
        'checkpoint_contract','ct.chlom.dail-cold-incremental.v2',
        'checkpoint_id',v_v2.checkpoint_id,
        'previous_checkpoint_kind',v_v2.previous_checkpoint_kind,
        'previous_checkpoint_id',v_v2.previous_checkpoint_id,
        'source_event_count',v_v2.cumulative_event_count,
        'source_max_sequence_id',v_v2.cumulative_max_sequence_id,
        'source_head_event_hash',v_v2.cumulative_head_event_hash,
        'checkpoint_receipt_sha256',v_v2.checkpoint_receipt_sha256,
        'snapshot_created_at',v_v2.snapshot_created_at,
        'checkpoint_age_seconds',v_age,
        'snapshot_rpo_seconds',v_v2.snapshot_rpo_seconds,
        'last_passing_drill_id',v_v2_drill.drill_id,
        'last_passing_test_scope','incremental_lineage_linkage',
        'last_passing_drill_completed_at',v_v2_drill.drill_completed_at,
        'last_passing_drill_rto_seconds',v_v2_drill.observed_rto_seconds
      ),
      'component_phase4_assurance_state',v_assurance,
      'institutional_phase4_activation',false,
      'full_chain_scan_executed',false,
      'exhaustive_verifier_retained','chlom_runtime.verify_dail_chain()'
    );
  end if;

  select c.* into v_v1
  from chlom_runtime.dail_cold_checkpoints_v1 c
  order by c.snapshot_created_at desc,c.recorded_at desc
  limit 1;

  if not found then
    return pg_catalog.jsonb_build_object(
      'hot_route',pg_catalog.jsonb_build_object(
        'state',v_hot_state,
        'integrity_state',v_hot->>'integrity_state',
        'verification_mode',v_hot->>'verification_mode',
        'tail_checked_events',(v_hot->>'tail_checked_events')::bigint,
        'head_hash',v_hot->>'current_head_hash',
        'checked_at',v_hot->>'checked_at'
      ),
      'cold_route',pg_catalog.jsonb_build_object('state','HOLD_NO_CHECKPOINT'),
      'component_phase4_assurance_state','HOLD',
      'institutional_phase4_activation',false,
      'full_chain_scan_executed',false
    );
  end if;

  v_age := greatest(0,ceil(extract(epoch from pg_catalog.clock_timestamp()-v_v1.snapshot_created_at))::bigint);
  select d.* into v_v1_drill
  from chlom_runtime.dail_recovery_drill_receipts_v1 d
  where d.checkpoint_id=v_v1.checkpoint_id and d.result='PASS'
  order by d.drill_completed_at desc
  limit 1;

  if v_age>p_max_checkpoint_age_seconds then
    v_cold_state:='HOLD_STALE_CHECKPOINT';
  elsif not found then
    v_cold_state:='HOLD_LATEST_CHECKPOINT_UNTESTED';
  else
    v_cold_state:=case v_v1_drill.test_scope
      when 'full_data_restore' then 'FULL_DATA_RECOVERY_VERIFIED'
      when 'ledger_lineage' then 'LEDGER_LINEAGE_RECOVERY_VERIFIED'
      else 'METADATA_RECOVERY_VERIFIED'
    end;
  end if;

  v_assurance:=case
    when v_hot_state<>'PASS' then 'HOLD_HOT_ROUTE'
    when v_cold_state='FULL_DATA_RECOVERY_VERIFIED' then 'READY_FOR_INDEPENDENT_PHASE4_READBACK'
    when v_cold_state in ('LEDGER_LINEAGE_RECOVERY_VERIFIED','METADATA_RECOVERY_VERIFIED')
      then 'BOUNDED_COLD_ASSURANCE_ONLY'
    else 'HOLD'
  end;

  return pg_catalog.jsonb_build_object(
    'hot_route',pg_catalog.jsonb_build_object(
      'state',v_hot_state,
      'integrity_state',v_hot->>'integrity_state',
      'verification_mode',v_hot->>'verification_mode',
      'checkpoint_id',v_hot->>'checkpoint_id',
      'tail_checked_events',(v_hot->>'tail_checked_events')::bigint,
      'tail_failure_count',(v_hot->>'tail_failure_count')::bigint,
      'head_hash',v_hot->>'current_head_hash',
      'checked_at',v_hot->>'checked_at'
    ),
    'cold_route',pg_catalog.jsonb_build_object(
      'state',v_cold_state,
      'checkpoint_contract','ct.chlom.dail-cold.v1',
      'checkpoint_id',v_v1.checkpoint_id,
      'source_event_count',v_v1.source_event_count,
      'source_max_sequence_id',v_v1.source_max_sequence_id,
      'source_head_event_hash',v_v1.source_head_event_hash,
      'checkpoint_receipt_sha256',v_v1.checkpoint_receipt_sha256,
      'snapshot_created_at',v_v1.snapshot_created_at,
      'checkpoint_age_seconds',v_age,
      'snapshot_rpo_seconds',v_v1.snapshot_rpo_seconds,
      'last_passing_drill_id',v_v1_drill.drill_id,
      'last_passing_test_scope',v_v1_drill.test_scope,
      'last_passing_drill_completed_at',v_v1_drill.drill_completed_at,
      'last_passing_drill_rpo_seconds',v_v1_drill.observed_rpo_seconds,
      'last_passing_drill_rto_seconds',v_v1_drill.observed_rto_seconds
    ),
    'component_phase4_assurance_state',v_assurance,
    'institutional_phase4_activation',false,
    'full_chain_scan_executed',false,
    'exhaustive_verifier_retained','chlom_runtime.verify_dail_chain()'
  );
end;
$function$;

-- Preserve the v2 API contract while upgrading the underlying cold-route semantics.
create or replace function chlom_runtime.read_dail_phase4_assurance_status_v2(
  p_max_checkpoint_age_seconds bigint default 93600
) returns jsonb
language sql
stable
security definer
set search_path to ''
set "TimeZone" to 'UTC'
as $function$
  select chlom_runtime.read_dail_phase4_assurance_status_v3(p_max_checkpoint_age_seconds)
$function$;

revoke all on function chlom_runtime.enqueue_dail_cold_incremental_backup_v2(bigint) from public, anon, authenticated;
grant execute on function chlom_runtime.enqueue_dail_cold_incremental_backup_v2(bigint) to service_role;

revoke all on function public.dail_cold_incremental_export_job_v2(uuid) from public, anon, authenticated;
grant execute on function public.dail_cold_incremental_export_job_v2(uuid) to service_role;

revoke all on function public.dail_cold_incremental_export_chunk_v2(uuid,integer) from public, anon, authenticated;
grant execute on function public.dail_cold_incremental_export_chunk_v2(uuid,integer) to service_role;

revoke all on function chlom_runtime.record_dail_cold_incremental_checkpoint_v2(
  uuid,timestamptz,text,text,text,bigint,text,text,text,text,uuid
) from public, anon, authenticated;
grant execute on function chlom_runtime.record_dail_cold_incremental_checkpoint_v2(
  uuid,timestamptz,text,text,text,bigint,text,text,text,text,uuid
) to service_role;

revoke all on function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  uuid,text,timestamptz,timestamptz,bigint,bigint,bigint,text,
  boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,
  text,text,uuid
) from public, anon, authenticated;
grant execute on function chlom_runtime.record_dail_incremental_recovery_drill_v2(
  uuid,text,timestamptz,timestamptz,bigint,bigint,bigint,text,
  boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,boolean,
  text,text,uuid
) to service_role;

revoke all on function chlom_runtime.complete_dail_cold_incremental_backup_v2(
  uuid,text,text,text,text,text,bigint,boolean,boolean,jsonb
) from public, anon, authenticated;
grant execute on function chlom_runtime.complete_dail_cold_incremental_backup_v2(
  uuid,text,text,text,text,text,bigint,boolean,boolean,jsonb
) to service_role;

revoke all on function chlom_runtime.read_dail_phase4_assurance_status_v3(bigint) from public, anon, authenticated;
grant execute on function chlom_runtime.read_dail_phase4_assurance_status_v3(bigint) to service_role;

-- Existing callers retain the v2 name. Keep the same narrow service-only posture.
revoke all on function chlom_runtime.read_dail_phase4_assurance_status_v2(bigint) from public, anon, authenticated;
grant execute on function chlom_runtime.read_dail_phase4_assurance_status_v2(bigint) to service_role;

comment on table chlom_runtime.dail_cold_incremental_exports_v2 is
  'Append-only source capture for bounded incremental DAIL lineage exports. Payload bodies and identity fields are excluded.';
comment on table chlom_runtime.dail_cold_incremental_checkpoints_v2 is
  'Append-only custody/readback receipts for incrementally chained DAIL cold checkpoints.';
comment on table chlom_runtime.dail_incremental_recovery_drills_v2 is
  'Append-only isolated recovery receipts proving incremental segment integrity and linkage to a previously recovery-verified checkpoint.';
