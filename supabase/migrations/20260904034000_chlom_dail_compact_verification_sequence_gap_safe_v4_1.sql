-- CHLOM DAIL compact verifier v4.1
-- Repairs a false-positive integrity HOLD caused by treating PostgreSQL sequence
-- values as gapless. Sequences are not transactional; aborted inserts can leave
-- unused sequence IDs. Integrity is therefore enforced over the ordered set of
-- committed DAIL events using predecessor hashes, payload hashes, event hashes,
-- checkpoint boundary binding, and compact-segment Merkle roots.
--
-- This migration does not mutate immutable DAIL events and creates no authority.

create or replace function chlom_runtime.dail_verify_next_segment_v4(
  p_max_events integer default 5000
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'extensions', 'chlom_runtime', 'public'
set "TimeZone" to 'UTC'
as $function$
declare
  v_cursor chlom_runtime.dail_verification_cursors_v4%rowtype;
  v_head_sequence bigint;
  v_head_hash text;
  v_start bigint;
  v_end bigint;
  v_expected_count integer;
  v_count integer;
  v_min_sequence bigint;
  v_max_sequence bigint;
  v_hashes text[];
  v_first_hash text;
  v_last_hash text;
  v_first_prior_hash text;
  v_first_stored_previous_hash text;
  v_previous_root text;
  v_root text;
  v_payload_failures integer;
  v_link_failures integer;
  v_event_failures integer;
  v_corrections integer;
  v_first_failure bigint;
  v_contiguous boolean;
  v_boundary boolean;
  v_state text;
  v_segment_id uuid;
  v_segment_key text;
  v_canonical jsonb;
  v_payload_sha text;
  v_signature text;
  v_started_at timestamptz:=clock_timestamp();
  v_duration_ms numeric(18,3);
  v_sequence_gap_count bigint:=0;
  v_recovered_legacy_dense_gap_hold boolean:=false;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:dail:compact-verification:v4',0)) then
    return jsonb_build_object(
      'ok',true,
      'state','DEFERRED_CONCURRENT_RUN',
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  p_max_events:=greatest(100,least(coalesce(p_max_events,5000),10000));

  select * into v_cursor
  from chlom_runtime.dail_verification_cursors_v4
  where cursor_key='canonical'
  for update;

  if not found then
    return jsonb_build_object(
      'ok',false,
      'state','HOLD_NO_V4_CURSOR',
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  -- v4.0 could fail closed solely because sequence IDs were not dense even when
  -- every committed event hash/link check passed. Recover only that exact known
  -- false-positive shape; all other integrity/SUSPENDED states remain fail closed.
  if v_cursor.cursor_state='HOLD_INTEGRITY' then
    if coalesce((v_cursor.last_error->>'contiguous_sequence')::boolean,true)=false
       and coalesce((v_cursor.last_error->>'boundary_hash_match')::boolean,false)=true
       and coalesce((v_cursor.last_error->>'payload_hash_failures')::integer,0)=0
       and coalesce((v_cursor.last_error->>'predecessor_link_failures')::integer,0)=0
       and coalesce((v_cursor.last_error->>'event_hash_failures')::integer,0)=0
       and nullif(v_cursor.last_error->>'first_failure_sequence_id','') is null then
      v_recovered_legacy_dense_gap_hold:=true;
      update chlom_runtime.dail_verification_cursors_v4
      set cursor_state='ACTIVE',
          last_error=null,
          last_run_at=clock_timestamp(),
          updated_at=clock_timestamp()
      where cursor_key='canonical';
      v_cursor.cursor_state:='ACTIVE';
      v_cursor.last_error:=null;
    else
      return jsonb_build_object(
        'ok',false,
        'state','HOLD_INTEGRITY',
        'last_error',v_cursor.last_error,
        'authority_created',false,
        'observed_at',clock_timestamp()
      );
    end if;
  elsif v_cursor.cursor_state='SUSPENDED' then
    return jsonb_build_object(
      'ok',false,
      'state','SUSPENDED',
      'last_error',v_cursor.last_error,
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  select sequence_id,event_hash into v_head_sequence,v_head_hash
  from chlom_runtime.dail_events
  order by sequence_id desc
  limit 1;

  if v_head_sequence is null then
    return jsonb_build_object(
      'ok',true,
      'state','CAUGHT_UP_EMPTY',
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  if v_cursor.verified_through_sequence_id>=v_head_sequence then
    update chlom_runtime.dail_verification_cursors_v4
    set cursor_state='CAUGHT_UP',
        last_run_at=clock_timestamp(),
        updated_at=clock_timestamp(),
        last_error=null
    where cursor_key='canonical';

    return jsonb_build_object(
      'ok',true,
      'state','CAUGHT_UP',
      'verified_through_sequence_id',v_cursor.verified_through_sequence_id,
      'head_sequence_id',v_head_sequence,
      'sequence_span_lag',0,
      'dense_sequence_required',false,
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  -- Select the next N committed events, not the next N integer sequence values.
  -- PostgreSQL sequences can legally contain gaps after aborted/rolled-back work.
  with selected as (
    select e.*
    from chlom_runtime.dail_events e
    where e.sequence_id>v_cursor.verified_through_sequence_id
    order by e.sequence_id
    limit p_max_events
  ), source_rows as (
    select e.*,
           lag(e.event_hash,1,v_cursor.verified_through_event_hash)
             over(order by e.sequence_id) as prior_stored_hash
    from selected e
  ), payload_calc as (
    select s.*,
           encode(
             extensions.digest(
               convert_to(coalesce(s.payload,'{}'::jsonb)::text,'UTF8'),
               'sha256'
             ),
             'hex'
           ) as expected_payload_sha256
    from source_rows s
  ), event_calc as (
    select p.*,
           chlom_runtime.dail_expected_event_hash_v4(
             p.prior_stored_hash,
             p.event_id,
             p.schema_version,
             p.event_type,
             p.entity_type,
             p.entity_id,
             p.entity_version,
             p.actor_did,
             p.actor_ref,
             p.expected_payload_sha256,
             p.created_at
           ) as expected_event_hash
    from payload_calc p
  ), validated as (
    select e.*,
           exists(
             select 1
             from chlom_runtime.dail_integrity_corrections x
             where x.event_id=e.event_id
               and x.sequence_id=e.sequence_id
               and x.original_event_hash=e.event_hash
               and x.expected_event_hash=e.expected_event_hash
               and x.payload_sha256=e.expected_payload_sha256
               and x.previous_event_hash is not distinct from e.prior_stored_hash
               and x.correction_state='accepted'
           ) as documented_correction
    from event_calc e
  )
  select count(*)::integer,
         min(sequence_id),
         max(sequence_id),
         array_agg(event_hash order by sequence_id),
         (array_agg(event_hash order by sequence_id))[1],
         (array_agg(event_hash order by sequence_id desc))[1],
         (array_agg(prior_stored_hash order by sequence_id))[1],
         (array_agg(previous_event_hash order by sequence_id))[1],
         count(*) filter(where payload_sha256 is distinct from expected_payload_sha256)::integer,
         count(*) filter(where previous_event_hash is distinct from prior_stored_hash)::integer,
         count(*) filter(where event_hash is distinct from expected_event_hash and not documented_correction)::integer,
         count(*) filter(where documented_correction)::integer,
         min(sequence_id) filter(
           where payload_sha256 is distinct from expected_payload_sha256
              or previous_event_hash is distinct from prior_stored_hash
              or (event_hash is distinct from expected_event_hash and not documented_correction)
         )
  into v_count,
       v_min_sequence,
       v_max_sequence,
       v_hashes,
       v_first_hash,
       v_last_hash,
       v_first_prior_hash,
       v_first_stored_previous_hash,
       v_payload_failures,
       v_link_failures,
       v_event_failures,
       v_corrections,
       v_first_failure
  from validated;

  if coalesce(v_count,0)=0 then
    return jsonb_build_object(
      'ok',true,
      'state','DEFERRED_NO_VISIBLE_ROWS',
      'verified_through_sequence_id',v_cursor.verified_through_sequence_id,
      'head_sequence_id',v_head_sequence,
      'authority_created',false,
      'observed_at',clock_timestamp()
    );
  end if;

  v_start:=v_min_sequence;
  v_end:=v_max_sequence;
  v_expected_count:=v_count;

  -- "contiguous_sequence" is retained for schema compatibility, but v4.1
  -- defines it as contiguous committed-event selection. Dense integer sequence
  -- IDs are explicitly NOT an integrity requirement.
  v_contiguous:=v_count>0
                and v_min_sequence=v_start
                and v_max_sequence=v_end;
  v_boundary:=v_first_stored_previous_hash is not distinct from v_cursor.verified_through_event_hash;
  v_sequence_gap_count:=
      greatest(v_start-v_cursor.verified_through_sequence_id-1,0)
    + greatest((v_end-v_start+1)-v_count,0);

  v_state:=case
    when v_contiguous
     and v_boundary
     and v_payload_failures=0
     and v_link_failures=0
     and v_event_failures=0
    then 'PASS'
    else 'HOLD'
  end;

  if v_cursor.last_segment_id is null then
    v_previous_root:=v_cursor.base_merkle_root_sha256;
  else
    select merkle_root_sha256 into v_previous_root
    from chlom_runtime.dail_verification_segments_v4
    where segment_id=v_cursor.last_segment_id
      and verification_state='PASS';

    if v_previous_root is null then
      v_state:='HOLD';
      v_first_failure:=coalesce(v_first_failure,v_start);
      v_previous_root:=v_cursor.base_merkle_root_sha256;
    end if;
  end if;

  v_root:=chlom_runtime.dail_merkle_root_v2(v_hashes);
  v_segment_key:='dail-v4:'||lpad(v_start::text,18,'0')||'-'||lpad(v_end::text,18,'0');
  v_duration_ms:=round(extract(epoch from (clock_timestamp()-v_started_at))*1000,3);

  v_canonical:=jsonb_build_object(
    'contract','ct.dail.compact-verification-segment.v4.1',
    'segment_key',v_segment_key,
    'start_sequence_id',v_start,
    'end_sequence_id',v_end,
    'event_count',v_count,
    'expected_event_count',v_expected_count,
    'head_at_start_sequence_id',v_head_sequence,
    'head_at_start_event_hash',v_head_hash,
    'first_event_hash',v_first_hash,
    'last_event_hash',v_last_hash,
    'previous_segment_root_sha256',v_previous_root,
    'merkle_root_sha256',v_root,
    'contiguous_sequence',v_contiguous,
    'dense_sequence_required',false,
    'sequence_gap_count',v_sequence_gap_count,
    'sequence_gap_semantics','postgres_sequences_are_non_transactional; gaps_are_allowed; committed_event_hash_chain_is_authoritative',
    'boundary_hash_match',v_boundary,
    'payload_hash_failures',v_payload_failures,
    'predecessor_link_failures',v_link_failures,
    'event_hash_failures',v_event_failures,
    'documented_corrections',v_corrections,
    'recovered_legacy_dense_gap_hold',v_recovered_legacy_dense_gap_hold,
    'verification_state',v_state,
    'hash_algorithm','SHA-256',
    'verification_mode','bounded_committed_event_set_no_membership_rewrite'
  );

  v_payload_sha:=public.penta_protocol_sha256_v1(v_canonical);
  v_signature:=public.pentas_hmac_sha256_v2(v_canonical);

  insert into chlom_runtime.dail_verification_segments_v4(
    segment_key,
    start_sequence_id,
    end_sequence_id,
    event_count,
    head_at_start_sequence_id,
    head_at_start_event_hash,
    first_event_hash,
    last_event_hash,
    previous_segment_root_sha256,
    merkle_root_sha256,
    expected_event_count,
    contiguous_sequence,
    boundary_hash_match,
    payload_hash_failures,
    predecessor_link_failures,
    event_hash_failures,
    documented_corrections,
    first_failure_sequence_id,
    verification_state,
    canonical_payload_sha256,
    signature_ref,
    signature_state,
    verification_duration_ms,
    evidence
  ) values(
    v_segment_key,
    v_start,
    v_end,
    v_count,
    v_head_sequence,
    v_head_hash,
    v_first_hash,
    v_last_hash,
    v_previous_root,
    v_root,
    v_expected_count,
    v_contiguous,
    v_boundary,
    v_payload_failures,
    v_link_failures,
    v_event_failures,
    v_corrections,
    v_first_failure,
    v_state,
    v_payload_sha,
    'vault://ct_pentas_v2_hmac_primary#'||v_signature,
    'verified',
    v_duration_ms,
    jsonb_build_object(
      'canonical',v_canonical,
      'content_address','sha256:'||v_payload_sha,
      'mass_dail_event_update',false,
      'per_event_membership_write',false,
      'external_chain_transaction',false,
      'dense_sequence_required',false,
      'sequence_gap_count',v_sequence_gap_count
    )
  ) returning segment_id into v_segment_id;

  if v_state='PASS' then
    insert into chlom_runtime.dail_anchor_intents_v4(
      segment_id,
      checkpoint_root_sha256,
      anchor_policy,
      intent_state,
      authority_ref,
      evidence
    ) values(
      v_segment_id,
      v_root,
      'ct.policy.chlom.anchor.chain-portable.v1',
      'PRODUCTION_GATED',
      'CHLOM_D3_EXTERNAL_BROADCAST_SEPARATELY_CERTIFIED',
      jsonb_build_object(
        'segment_key',v_segment_key,
        'raw_private_evidence_included',false,
        'public_chain_broadcast',false,
        'provider_receipt_required',true,
        'dense_sequence_required',false
      )
    );

    update chlom_runtime.dail_verification_cursors_v4
    set verified_through_sequence_id=v_end,
        verified_through_event_hash=v_last_hash,
        last_segment_id=v_segment_id,
        cursor_state=case when v_end>=v_head_sequence then 'CAUGHT_UP' else 'ACTIVE' end,
        last_error=null,
        last_run_at=clock_timestamp(),
        updated_at=clock_timestamp()
    where cursor_key='canonical';
  else
    update chlom_runtime.dail_verification_cursors_v4
    set cursor_state='HOLD_INTEGRITY',
        last_error=jsonb_build_object(
          'segment_id',v_segment_id,
          'segment_key',v_segment_key,
          'first_failure_sequence_id',v_first_failure,
          'payload_hash_failures',v_payload_failures,
          'predecessor_link_failures',v_link_failures,
          'event_hash_failures',v_event_failures,
          'contiguous_sequence',v_contiguous,
          'dense_sequence_required',false,
          'sequence_gap_count',v_sequence_gap_count,
          'boundary_hash_match',v_boundary
        ),
        last_run_at=clock_timestamp(),
        updated_at=clock_timestamp()
    where cursor_key='canonical';
  end if;

  return jsonb_build_object(
    'ok',v_state='PASS',
    'state',case when v_state='PASS' then 'SEGMENT_ATTESTED' else 'HOLD_INTEGRITY' end,
    'segment_id',v_segment_id,
    'segment_key',v_segment_key,
    'start_sequence_id',v_start,
    'end_sequence_id',v_end,
    'event_count',v_count,
    'head_at_start_sequence_id',v_head_sequence,
    'sequence_span_lag',greatest(v_head_sequence-v_end,0),
    'sequence_gap_count',v_sequence_gap_count,
    'dense_sequence_required',false,
    'merkle_root_sha256',v_root,
    'canonical_payload_sha256',v_payload_sha,
    'signature_state','verified',
    'payload_hash_failures',v_payload_failures,
    'predecessor_link_failures',v_link_failures,
    'event_hash_failures',v_event_failures,
    'documented_corrections',v_corrections,
    'recovered_legacy_dense_gap_hold',v_recovered_legacy_dense_gap_hold,
    'verification_duration_ms',v_duration_ms,
    'mass_dail_event_update',false,
    'per_event_membership_write',false,
    'exact_antijoin_count',false,
    'authority_created',false,
    'observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function chlom_runtime.dail_verify_next_segment_v4(integer) from public, anon, authenticated;
grant execute on function chlom_runtime.dail_verify_next_segment_v4(integer) to service_role;
