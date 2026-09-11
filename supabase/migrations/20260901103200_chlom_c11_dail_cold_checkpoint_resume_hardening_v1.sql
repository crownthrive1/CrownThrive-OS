-- CHLOM C11 DAIL cold checkpoint resume/privacy hardening v1.
-- Supersedes the initial chunk body with lineage-only export and durable CAS resume state.

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

  -- COLD ledger-lineage backup deliberately omits payload bodies. The immutable
  -- payload SHA-256 plus the event-chain fields are sufficient for lineage recovery
  -- while reducing provider exposure and package size.
  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object(
      'sequence_id',e.sequence_id,'event_id',e.event_id,'event_type',e.event_type,
      'schema_version',e.schema_version,'actor_ref',e.actor_ref,'actor_did',e.actor_did,
      'agent_id',e.agent_id,'source_system',e.source_system,'entity_type',e.entity_type,
      'entity_id',e.entity_id,'entity_version',e.entity_version,
      'correlation_id',e.correlation_id,'causation_id',e.causation_id,
      'authority_basis',e.authority_basis,'approval_id',e.approval_id,
      'visibility_class',e.visibility_class,'payload_sha256',e.payload_sha256,
      'previous_event_hash',e.previous_event_hash,'event_hash',e.event_hash,
      'chain_anchor_state',e.chain_anchor_state,'signature_ref',e.signature_ref,
      'created_at',e.created_at
    ) order by e.sequence_id
  ),'[]'::jsonb),pg_catalog.count(*)::integer,pg_catalog.min(e.sequence_id),pg_catalog.max(e.sequence_id)
  into v_events,v_count,v_first,v_last
  from (
    select sequence_id,event_id,event_type,schema_version,actor_ref,actor_did,agent_id,
           source_system,entity_type,entity_id,entity_version,correlation_id,causation_id,
           authority_basis,approval_id,visibility_class,payload_sha256,previous_event_hash,
           event_hash,chain_anchor_state,signature_ref,created_at
    from chlom_runtime.dail_events
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
    'job_id',p_job_id,'export_scope','ledger_lineage',
    'payload_body_included',false,
    'source_event_count',v_source_count,'source_min_sequence_id',v_source_min,
    'source_max_sequence_id',v_source_max,'source_head_event_hash',v_source_head,
    'requested_after_sequence_id',coalesce(p_after_sequence_id,0),
    'chunk_limit',v_limit,'chunk_event_count',v_count,
    'chunk_first_sequence_id',v_first,'chunk_last_sequence_id',v_last,
    'chunk_first_previous_event_hash',v_first_prev,'chunk_last_event_hash',v_last_hash,
    'chunk_sha256',v_chunk_sha,'has_more',v_has_more,
    'next_after_sequence_id',case when v_has_more then v_last else null end,
    'events',v_events,'provider_write',false,'authority_effect','none'
  );
end
$function$;

create or replace function chlom_runtime.record_dail_cold_export_progress_v1(
  p_job_id uuid,
  p_expected_after_sequence_id bigint,
  p_chunk_limit integer,
  p_chunk_sha256 text,
  p_chunk_last_sequence_id bigint,
  p_chunk_last_event_hash text
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
  v_chunk jsonb;
  v_expected_cursor bigint;
  v_current_count bigint;
  v_current_chunks integer;
  v_previous_chain text;
  v_new_chain text;
  v_chunk_count integer;
  v_last bigint;
  v_last_hash text;
  v_source_max bigint;
  v_export_complete boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_job_id is null or coalesce(p_expected_after_sequence_id,0)<0
     or p_chunk_limit is null or p_chunk_limit<1 or p_chunk_limit>5000
     or pg_catalog.lower(coalesce(p_chunk_sha256,'')) !~ '^[0-9a-f]{64}$'
     or pg_catalog.lower(coalesce(p_chunk_last_event_hash,'')) !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid DAIL cold export progress input' using errcode='22023';
  end if;

  select * into strict v_job
  from chlom_runtime.backup_continuity_jobs_v2 j
  where j.job_id=p_job_id
    and j.schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1'
    and j.job_state in ('queued','hold')
  for update;

  v_expected_cursor := coalesce(nullif(v_job.evidence->>'export_cursor_sequence_id','')::bigint,0);
  if v_expected_cursor <> coalesce(p_expected_after_sequence_id,0) then
    raise exception 'DAIL cold export cursor CAS conflict' using errcode='40001';
  end if;

  v_chunk := public.dail_cold_checkpoint_export_chunk_v1(
    p_job_id,v_expected_cursor,p_chunk_limit
  );
  v_chunk_count := coalesce((v_chunk->>'chunk_event_count')::integer,0);
  v_last := nullif(v_chunk->>'chunk_last_sequence_id','')::bigint;
  v_last_hash := pg_catalog.lower(coalesce(v_chunk->>'chunk_last_event_hash',''));
  v_source_max := nullif(v_chunk->>'source_max_sequence_id','')::bigint;

  if v_chunk_count <= 0 then
    if coalesce(v_chunk->>'state','')='EOF' and v_expected_cursor>=coalesce(v_source_max,0) then
      return pg_catalog.jsonb_build_object(
        'state','EOF','job_id',p_job_id,'export_cursor_sequence_id',v_expected_cursor,
        'export_complete',true,'provider_write',false
      );
    end if;
    raise exception 'nonterminal empty DAIL cold export chunk' using errcode='55000';
  end if;

  if pg_catalog.lower(v_chunk->>'chunk_sha256') <> pg_catalog.lower(p_chunk_sha256)
     or v_last is distinct from p_chunk_last_sequence_id
     or v_last_hash <> pg_catalog.lower(p_chunk_last_event_hash) then
    raise exception 'DAIL cold export progress does not match canonical chunk' using errcode='22023';
  end if;

  v_current_count := coalesce(nullif(v_job.evidence->>'exported_event_count','')::bigint,0);
  v_current_chunks := coalesce(nullif(v_job.evidence->>'export_chunk_count','')::integer,0);
  v_previous_chain := coalesce(nullif(v_job.evidence->>'export_chain_sha256',''),'GENESIS');
  v_new_chain := pg_catalog.encode(
    extensions.digest(
      pg_catalog.convert_to(
        v_previous_chain||':'||pg_catalog.lower(p_chunk_sha256)||':'||v_last::text||':'||v_chunk_count::text,
        'UTF8'
      ),'sha256'
    ),'hex'
  );
  v_export_complete := coalesce((v_chunk->>'has_more')::boolean,false) is distinct from true;

  update chlom_runtime.backup_continuity_jobs_v2
  set evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
        'export_cursor_sequence_id',v_last,
        'exported_event_count',v_current_count+v_chunk_count,
        'export_chunk_count',v_current_chunks+1,
        'export_last_event_hash',v_last_hash,
        'export_last_chunk_sha256',pg_catalog.lower(p_chunk_sha256),
        'export_chain_sha256',v_new_chain,
        'export_complete',v_export_complete,
        'export_progress_updated_at',clock_timestamp(),
        'export_payload_mode','lineage_metadata_no_payload_body'
      ),
      last_error=null,updated_at=clock_timestamp()
  where job_id=p_job_id;

  return pg_catalog.jsonb_build_object(
    'state',case when v_export_complete then 'EXPORT_COMPLETE' else 'PROGRESS_RECORDED' end,
    'job_id',p_job_id,'previous_cursor',v_expected_cursor,
    'export_cursor_sequence_id',v_last,
    'exported_event_count',v_current_count+v_chunk_count,
    'export_chunk_count',v_current_chunks+1,
    'export_chain_sha256',v_new_chain,
    'export_complete',v_export_complete,
    'provider_write',false,'authority_effect','none'
  );
end
$function$;

create or replace function chlom_runtime.enqueue_dail_cold_checkpoint_v2(
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
  v_result := chlom_runtime.enqueue_dail_cold_checkpoint_v1(p_force);
  v_job := nullif(v_result->>'job_id','')::uuid;
  if v_job is not null then
    update chlom_runtime.backup_continuity_jobs_v2
    set source_snapshot=coalesce(source_snapshot,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'progress_rpc','chlom_runtime.record_dail_cold_export_progress_v1',
          'resume_cursor_source','job.evidence.export_cursor_sequence_id',
          'export_payload_mode','lineage_metadata_no_payload_body',
          'export_progress_cas',true
        ),
        evidence=coalesce(evidence,'{}'::jsonb)||pg_catalog.jsonb_build_object(
          'export_cursor_sequence_id',coalesce(nullif(evidence->>'export_cursor_sequence_id','')::bigint,0),
          'exported_event_count',coalesce(nullif(evidence->>'exported_event_count','')::bigint,0),
          'export_chunk_count',coalesce(nullif(evidence->>'export_chunk_count','')::integer,0),
          'export_chain_sha256',coalesce(nullif(evidence->>'export_chain_sha256',''),'GENESIS'),
          'export_payload_mode','lineage_metadata_no_payload_body'
        ),
        updated_at=clock_timestamp()
    where job_id=v_job and schedule_id='ct.schedule.dail-cold-checkpoint.daily.v1';
  end if;
  return v_result||pg_catalog.jsonb_build_object(
    'protocol_revision','resume-hardening-v1',
    'progress_rpc','chlom_runtime.record_dail_cold_export_progress_v1',
    'export_payload_mode','lineage_metadata_no_payload_body'
  );
end
$function$;

revoke all on function public.dail_cold_checkpoint_export_chunk_v1(uuid,bigint,integer) from public,anon,authenticated;
revoke all on function chlom_runtime.record_dail_cold_export_progress_v1(uuid,bigint,integer,text,bigint,text) from public,anon,authenticated;
revoke all on function chlom_runtime.enqueue_dail_cold_checkpoint_v2(boolean) from public,anon,authenticated;
grant execute on function public.dail_cold_checkpoint_export_chunk_v1(uuid,bigint,integer) to service_role;
grant execute on function chlom_runtime.record_dail_cold_export_progress_v1(uuid,bigint,integer,text,bigint,text) to service_role;
grant execute on function chlom_runtime.enqueue_dail_cold_checkpoint_v2(boolean) to service_role;

do $block$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='ct-dail-cold-checkpoint-due-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule(
    'ct-dail-cold-checkpoint-due-v1',
    '17 * * * *',
    'select chlom_runtime.enqueue_dail_cold_checkpoint_v2(false);'
  );
end
$block$;
